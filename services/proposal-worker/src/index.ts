/**
 * Cytellect proposal service (Cloudflare Workers + D1).
 *
 * Holds the operator's OpenAI key as a secret, authenticates installations by
 * invitation-issued device tokens, reserves budget before every model call and
 * returns an unvalidated draft that the local API validates. Request bodies,
 * goals and images are never logged or stored.
 */
import { draftProposal, inputTokenCeiling, MODEL, ModelError, PROMPT_VERSION, observedCost, type Preview, type ReasoningEffort } from "./openai";
import { D1Store, type D1Database, type Store } from "./store";
import contract from "./contract.json";
import { boundedJson, matchesSchema } from "./schema";

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
  REASONING_EFFORT?: string;
  LOW_EFFORT_EVALUATED?: string;
  PRICE_CACHED_INPUT_USD_PER_MTOK?: string;
  PRICE_CACHE_WRITE_USD_PER_MTOK?: string;
}

export const LIMITS = {
  bodyBytes: 6 * 1024 * 1024,
  goalChars: 2000,
  channels: 6,
  previews: 6,
  previewBase64Chars: 700_000,
};

interface Config {
  apiKey: string;
  model: string;
  budget: number;
  deviceRequests: number;
  priceIn: number;
  priceOut: number;
  maxOutputTokens: number;
  reasoningEffort: ReasoningEffort;
  priceCachedIn: number;
  priceCacheWrite: number;
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
  const priceCachedIn = positive(env.PRICE_CACHED_INPUT_USD_PER_MTOK);
  const priceCacheWrite = positive(env.PRICE_CACHE_WRITE_USD_PER_MTOK);
  const reasoningEffort = env.REASONING_EFFORT ?? "medium";
  const maxOutputTokens = env.MAX_OUTPUT_TOKENS === undefined || env.MAX_OUTPUT_TOKENS === "" ? 8000 : Number(env.MAX_OUTPUT_TOKENS);
  // Pricing floors match this exact model/standard tier; changing provider or tier
  // requires a separate reviewed adapter, not just an arbitrary model environment value.
  if (!env.OPENAI_API_KEY || env.OPENAI_MODEL !== MODEL || !budget || !deviceRequests || !Number.isInteger(deviceRequests)
    || !priceIn || priceIn < 2 || !priceOut || priceOut < 10 || !priceCachedIn || priceCachedIn < 0.1
    || !priceCacheWrite || priceCacheWrite < 2.5 || priceCacheWrite < priceIn
    || !Number.isInteger(maxOutputTokens) || maxOutputTokens < 1024 || maxOutputTokens > 16000
    || !["low", "medium"].includes(reasoningEffort)
    || (reasoningEffort === "low" && env.LOW_EFFORT_EVALUATED !== "true")) return null;
  return {
    apiKey: env.OPENAI_API_KEY, model: env.OPENAI_MODEL, budget, deviceRequests: Math.floor(deviceRequests),
    priceIn, priceOut, priceCachedIn, priceCacheWrite, maxOutputTokens, reasoningEffort: reasoningEffort as ReasoningEffort,
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
  try {
    const value = await boundedJson(request.body, LIMITS.bodyBytes);
    return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : null;
  } catch {
    return null;
  }
}

/** Shape limits before any billable call; semantic validation stays in the local API. */
export function checkRequest(body: Record<string, unknown>): { context: Record<string, unknown>; previews: Preview[] } | null {
  const context = body.context as Record<string, unknown> | undefined;
  if (!matchesSchema(context, contract.context_schema)) return null;
  const channels = (context!.channels as { token: string }[]).map((channel) => channel.token);
  if (new Set(channels).size !== channels.length) return null;
  const previews = body.previews ?? [];
  if (!Array.isArray(previews) || previews.length > LIMITS.previews) return null;
  for (const preview of previews) {
    if (!preview || typeof preview !== "object" || Array.isArray(preview)
      || Object.keys(preview).some((key) => !["channel", "png_base64"].includes(key))
      || !channels.includes(preview.channel)) return null;
    if (typeof preview.png_base64 !== "string" || preview.png_base64.length > LIMITS.previewBase64Chars
      || !/^[A-Za-z0-9+/]+={0,2}$/.test(preview.png_base64) || !preview.png_base64.startsWith("iVBORw0KGgo")) return null;
    // Validate PNG header dimensions without decoding researcher pixels in the relay.
    try {
      const bytes = Uint8Array.from(atob(preview.png_base64), (c) => c.charCodeAt(0));
      const view = new DataView(bytes.buffer);
      if (bytes.length < 33 || view.getUint32(8) !== 13 || view.getUint32(12) !== 0x49484452) return null;
      const width = view.getUint32(16), height = view.getUint32(20);
      if (width < 1 || height < 1 || width > 512 || height > 512) return null;
    } catch { return null; }
  }
  const extra = Object.keys(body).filter((key) => key !== "context" && key !== "previews");
  return extra.length ? null : { context: context!, previews: previews as Preview[] };
}

export function worstCaseUsd(config: Config, context: unknown, previews: Preview[]): number {
  const input = inputTokenCeiling(config, context, previews);
  const perCall = (input * Math.max(config.priceCacheWrite, config.priceCachedIn) + config.maxOutputTokens * config.priceOut) / 1_000_000;
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
    const requestId = request.headers.get("idempotency-key");
    if (!requestId || !/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(requestId)) return failure(400, "request_id_required");
    if (!(await store.claimRequest(deviceHash, requestId.toLowerCase(), now))) return failure(409, "duplicate_request");
    const period = month(now);
    if (!(await store.countDeviceRequest(deviceHash, period, config.deviceRequests))) return failure(429, "device_quota_exhausted");
    const reservation = crypto.randomUUID();
    const amount = worstCaseUsd(config, checked.context, checked.previews);
    if (!(await store.reserve(reservation, period, amount, config.budget, now))) return failure(429, "monthly_budget_exhausted");
    try {
      const result = await draftProposal({ ...config, fetcher: options.fetcher },
        checked.context, checked.previews);
      // Non-cached input may include cache writes. Until the API's write breakdown is
      // confirmed, retain its higher tariff; this is a conservative ledger, not an invoice.
      const spent = result.usageComplete ? ((result.inputTokens - result.cachedInputTokens) * config.priceCacheWrite
        + result.cachedInputTokens * config.priceCachedIn + result.outputTokens * config.priceOut) / 1_000_000 : amount;
      await store.settle(reservation, period, spent, result.usageComplete ? {
        model: config.model, promptVersion: PROMPT_VERSION, inputTokens: result.inputTokens,
        cachedInputTokens: result.cachedInputTokens, outputTokens: result.outputTokens, calls: result.calls,
      } : undefined);
      return json(200, { draft: result.draft, model: config.model, prompt_version: PROMPT_VERSION });
    } catch (error) {
      // Usage of a failed call is unknown here: settle conservatively at the reserved amount.
      const usage = error instanceof ModelError ? error.observedUsage : undefined;
      await store.settle(reservation, period, usage
        ? Math.max(amount, observedCost(usage, config.priceCacheWrite, config.priceCachedIn, config.priceOut)) : amount,
      usage ? { ...usage, model: config.model, promptVersion: PROMPT_VERSION } : undefined);
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
