/**
 * Cytellect proposal service (Cloudflare Workers + D1).
 *
 * Holds the operator's OpenAI key as a secret, authenticates installations by
 * invitation-issued device tokens, reserves budget before every model call and
 * returns an unvalidated draft that the local API validates. Request bodies,
 * goals and images are never logged or stored.
 */
import { draftProposal, ModelError, PROMPT_VERSION, type Preview } from "./openai";
import { D1Store, type D1Database, type Store } from "./store";

export interface Env {
  DB: D1Database;
  OPENAI_API_KEY?: string;
  OPENAI_MODEL?: string;
  ADMIN_TOKEN?: string;
  MONTHLY_BUDGET_USD?: string;
  DEVICE_MONTHLY_REQUESTS?: string;
  PRICE_INPUT_USD_PER_MTOK?: string;
  PRICE_OUTPUT_USD_PER_MTOK?: string;
  MAX_OUTPUT_TOKENS?: string;
}

export const LIMITS = {
  bodyBytes: 6 * 1024 * 1024,
  goalChars: 2000,
  channels: 6,
  previews: 6,
  previewBase64Chars: 700_000,
  /** Conservative token allowance per preview image at low detail. */
  previewTokens: 1_000,
};

interface Config {
  apiKey: string;
  model: string;
  budget: number;
  deviceRequests: number;
  priceIn: number;
  priceOut: number;
  maxOutputTokens: number;
}

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status, headers: { "content-type": "application/json", "cache-control": "no-store" },
  });
}

const failure = (status: number, code: string) => json(status, { code });

function positive(value: string | undefined): number | null {
  const number = Number(value);
  return value && Number.isFinite(number) && number > 0 ? number : null;
}

/** Billable calls are disabled unless every limit is configured (requirement L05). */
export function readConfig(env: Env): Config | null {
  const budget = positive(env.MONTHLY_BUDGET_USD);
  const deviceRequests = positive(env.DEVICE_MONTHLY_REQUESTS);
  const priceIn = positive(env.PRICE_INPUT_USD_PER_MTOK);
  const priceOut = positive(env.PRICE_OUTPUT_USD_PER_MTOK);
  if (!env.OPENAI_API_KEY || !env.OPENAI_MODEL || !budget || !deviceRequests || !priceIn || !priceOut) return null;
  return {
    apiKey: env.OPENAI_API_KEY, model: env.OPENAI_MODEL, budget, deviceRequests: Math.floor(deviceRequests),
    priceIn, priceOut, maxOutputTokens: Math.min(4000, Math.floor(positive(env.MAX_OUTPUT_TOKENS) ?? 1500)),
  };
}

async function sha256(text: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

function token(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(32));
  return btoa(String.fromCharCode(...bytes)).replaceAll("+", "-").replaceAll("/", "_").replace(/=+$/, "");
}

function bearer(request: Request): string | null {
  const match = /^Bearer ([A-Za-z0-9_-]{20,200})$/.exec(request.headers.get("authorization") ?? "");
  return match ? match[1] : null;
}

function equal(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let difference = 0;
  for (let index = 0; index < a.length; index += 1) difference |= a.charCodeAt(index) ^ b.charCodeAt(index);
  return difference === 0;
}

async function readJson(request: Request): Promise<Record<string, unknown> | null> {
  const length = Number(request.headers.get("content-length") ?? "0");
  if (length > LIMITS.bodyBytes) return null;
  const text = await request.text();
  if (text.length > LIMITS.bodyBytes) return null;
  try {
    const value = JSON.parse(text);
    return value && typeof value === "object" && !Array.isArray(value) ? value : null;
  } catch {
    return null;
  }
}

/** Shape limits before any billable call; semantic validation stays in the local API. */
export function checkRequest(body: Record<string, unknown>): { context: Record<string, unknown>; previews: Preview[] } | null {
  const context = body.context as Record<string, unknown> | undefined;
  if (!context || typeof context !== "object" || Array.isArray(context)) return null;
  if (typeof context.goal === "string" && context.goal.length > LIMITS.goalChars) return null;
  if (!Array.isArray(context.channels) || context.channels.length < 1 || context.channels.length > LIMITS.channels) return null;
  const previews = body.previews ?? [];
  if (!Array.isArray(previews) || previews.length > LIMITS.previews) return null;
  for (const preview of previews) {
    if (!preview || typeof preview.channel !== "string" || !/^[a-z0-9][a-z0-9_.-]{0,31}$/.test(preview.channel)) return null;
    if (typeof preview.png_base64 !== "string" || preview.png_base64.length > LIMITS.previewBase64Chars
      || !/^[A-Za-z0-9+/]+={0,2}$/.test(preview.png_base64) || !preview.png_base64.startsWith("iVBORw0KGgo")) return null;
  }
  const extra = Object.keys(body).filter((key) => key !== "context" && key !== "previews");
  return extra.length ? null : { context, previews: previews as Preview[] };
}

export function worstCaseUsd(config: Config, context: unknown, previews: Preview[], promptChars: number): number {
  // Counting each character as a token over-estimates input; two calls cover one repair.
  const input = promptChars + JSON.stringify(context).length + previews.length * LIMITS.previewTokens;
  const perCall = (input * config.priceIn + config.maxOutputTokens * config.priceOut) / 1_000_000;
  return perCall * 2;
}

const month = (now: number) => new Date(now).toISOString().slice(0, 7);

export async function handle(request: Request, env: Env, store: Store, options: { fetcher?: typeof fetch; now?: () => number } = {}): Promise<Response> {
  const now = options.now?.() ?? Date.now();
  const url = new URL(request.url);
  if (request.method !== "POST") return failure(405, "method_not_allowed");

  if (url.pathname === "/v1/admin/invitations") {
    const presented = bearer(request);
    if (!env.ADMIN_TOKEN || !presented || !equal(presented, env.ADMIN_TOKEN)) return failure(401, "unauthorized");
    const invitation = token();
    const hours = Math.min(168, Math.max(1, Number(url.searchParams.get("hours") ?? "24") || 24));
    await store.createInvitation(await sha256(invitation), now + hours * 3_600_000);
    return json(201, { invitation, expires_in_hours: hours });
  }

  if (url.pathname === "/v1/devices") {
    const body = await readJson(request);
    const invitation = typeof body?.invitation === "string" ? body.invitation : "";
    if (!/^[A-Za-z0-9_-]{20,200}$/.test(invitation)) return failure(400, "invitation_invalid");
    const device = token();
    if (!(await store.redeemInvitation(await sha256(invitation), await sha256(device), now))) return failure(403, "invitation_invalid");
    return json(201, { device_token: device });
  }

  if (url.pathname === "/v1/proposals") {
    const presented = bearer(request);
    const deviceHash = presented ? await sha256(presented) : null;
    if (!deviceHash || !(await store.deviceActive(deviceHash))) return failure(401, "unauthorized");
    const config = readConfig(env);
    if (!config) return failure(503, "proposal_service_disabled");
    const body = await readJson(request);
    const checked = body && checkRequest(body);
    if (!checked) return failure(400, "request_invalid");
    const period = month(now);
    if (!(await store.countDeviceRequest(deviceHash, period, config.deviceRequests))) return failure(429, "device_quota_exhausted");
    const reservation = crypto.randomUUID();
    const amount = worstCaseUsd(config, checked.context, checked.previews, 4000);
    if (!(await store.reserve(reservation, period, amount, config.budget, now))) return failure(429, "monthly_budget_exhausted");
    try {
      const result = await draftProposal({ apiKey: config.apiKey, model: config.model, maxOutputTokens: config.maxOutputTokens, fetcher: options.fetcher },
        checked.context, checked.previews);
      const spent = (result.inputTokens * config.priceIn + result.outputTokens * config.priceOut) / 1_000_000;
      await store.settle(reservation, period, spent);
      return json(200, { draft: result.draft, model: config.model, prompt_version: PROMPT_VERSION });
    } catch (error) {
      // Usage of a failed call is unknown here: settle conservatively at the reserved amount.
      await store.settle(reservation, period, amount);
      const code = error instanceof ModelError ? error.code : "model_unavailable";
      return failure(code === "model_unavailable" ? 503 : 502, code);
    }
  }
  return failure(404, "not_found");
}

export default {
  fetch(request: Request, env: Env): Promise<Response> {
    return handle(request, env, new D1Store(env.DB));
  },
};
