/**
 * Cytellect proposal service and cloud gateway (Cloudflare Workers + D1).
 *
 * Holds the operator's OpenAI and Modal keys as secrets, authenticates
 * installations by user-bound device tokens from the e-mail login (or, during
 * migration, invitation-issued tokens), reserves budget before every model call
 * and returns an unvalidated draft that the local API validates. Request bodies,
 * goals and images are never logged or stored.
 */
import { draftProposal, inputTokenCeiling, MODEL, ModelError, PROMPT_VERSION, NUCLEAR_FILTER_PREVIOUS_PROMPT_VERSION, PARENT_PREVIOUS_PROMPT_VERSION, CELLPOSE_PREVIOUS_PROMPT_VERSION, OBJECT_PREVIOUS_PROMPT_VERSION, NCL_PREVIOUS_PROMPT_VERSION, PREVIOUS_PROMPT_VERSION, PROCESSING_PROMPT_VERSION, LEGACY_PROMPT_VERSION, PREIMPORT_PROMPT_VERSION, observedCost, type Preview, type ReasoningEffort } from "./openai";
import { D1Store, type D1Database, type Store } from "./store";
import contract from "./contract.json";
import { matchesSchema } from "./schema";
import { D1AuthStore } from "./auth-store";
import { handleCloud, isCloudPath, lookupDevice, type CloudEnv } from "./cloud";
import { bearer, equal, json, month, nextMonth, readObject, sha256, token } from "./http";
import { configuredMailer, type Mailer } from "./mail";

export interface Env extends CloudEnv {
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
  /** "false" closes the invitation flow and its device tokens after migration. */
  LEGACY_INVITATIONS?: string;
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

const readJson = (request: Request) => readObject(request, LIMITS.bodyBytes);

/** Shape limits before any billable call; semantic validation stays in the local API. */
export function checkRequest(body: Record<string, unknown>): { context: Record<string, unknown>; previews: Preview[] } | null {
  const context = body.context as Record<string, unknown> | undefined;
  if (!matchesSchema(context, contract.context_schema)) return null;
  const channels = (context!.channels as { token: string }[]).map((channel) => channel.token);
  if (new Set(channels).size !== channels.length) return null;
  if (context!.field_count === 0) {
    if (channels.length || !String(context!.goal ?? "").trim() || context!.condition_count
      || context!.units_known || context!.pairing_known || context!.complete_pair_count
      || context!.supplied_regions || context!.measured_table || context!.background_available
      || (context!.units_per_condition as unknown[] | undefined)?.length) return null;
  } else if (!channels.length) return null;
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
  const extra = Object.keys(body).filter((key) => key !== "context" && key !== "previews" && key !== "prompt_version");
  return extra.length ? null : { context: context!, previews: previews as Preview[] };
}

export function worstCaseUsd(config: Config, context: unknown, previews: Preview[]): number {
  const input = inputTokenCeiling(config, context, previews);
  const perCall = (input * Math.max(config.priceCacheWrite, config.priceCachedIn) + config.maxOutputTokens * config.priceOut) / 1_000_000;
  return perCall * 2;
}

export interface HandleOptions {
  fetcher?: typeof fetch;
  now?: () => number;
  /** Account store; defaults to D1 when the binding is present. */
  auth?: D1AuthStore;
  /** Mail sender; defaults to Resend when configured. null forces "not configured". */
  mailer?: Mailer | null;
  /** Upstream for the GPU gateway (tests substitute a fake Modal server). */
  gpuFetcher?: typeof fetch;
  /** Wall clock for GPU elapsed time. */
  clock?: () => number;
}

const legacyInvitations = (env: Env) => env.LEGACY_INVITATIONS !== "false";

export async function handle(request: Request, env: Env, store: Store, options: HandleOptions = {}): Promise<Response> {
  const now = options.now?.() ?? Date.now();
  const url = new URL(request.url);
  const auth = options.auth ?? (env.DB ? new D1AuthStore(env.DB) : undefined);
  if (isCloudPath(url.pathname)) {
    if (!auth) return json(503, { error: "auth_unavailable" });
    return handleCloud(request, {
      env, auth, now, clock: options.clock ?? Date.now, gpuFetcher: options.gpuFetcher ?? ((input, init) => fetch(input, init)),
      mailer: "mailer" in options ? options.mailer ?? null : configuredMailer(env),
    });
  }
  if (request.method !== "POST") return failure(405, "method_not_allowed");

  if ((url.pathname === "/v1/admin/invitations" || url.pathname === "/v1/devices") && !legacyInvitations(env)) {
    return failure(404, "not_found");
  }

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
    if (!deviceHash) return failure(401, "unauthorized");
    // User-bound tokens from the e-mail login first; invitation tokens only during migration.
    const user = auth ? await lookupDevice(auth, env, deviceHash, now) : { kind: "none" as const };
    if (user.kind === "revoked") return failure(403, "revoked");
    if (user.kind === "expired" || (user.kind === "none" && !(legacyInvitations(env) && await store.deviceActive(deviceHash)))) {
      return failure(401, "unauthorized");
    }
    const config = readConfig(env);
    if (!config) return failure(503, "proposal_service_disabled");
    if (await store.budgetBlocked()) return failure(503, "budget_reconciliation_required");
    const body = await readJson(request);
    const checked = body && checkRequest(body);
    if (!checked) return failure(400, "request_invalid");
    const promptVersion = body!.prompt_version ?? LEGACY_PROMPT_VERSION;
    if (typeof promptVersion !== "string" || ![PROMPT_VERSION, NUCLEAR_FILTER_PREVIOUS_PROMPT_VERSION, PARENT_PREVIOUS_PROMPT_VERSION, CELLPOSE_PREVIOUS_PROMPT_VERSION, OBJECT_PREVIOUS_PROMPT_VERSION, NCL_PREVIOUS_PROMPT_VERSION, PREVIOUS_PROMPT_VERSION, PROCESSING_PROMPT_VERSION, PREIMPORT_PROMPT_VERSION, LEGACY_PROMPT_VERSION].includes(promptVersion)) return failure(400, "prompt_version_unsupported");
    if (checked.context.field_count === 0 && promptVersion === LEGACY_PROMPT_VERSION) return failure(400, "prompt_version_unsupported");
    const modelConfig = {...config, promptVersion};
    const requestId = request.headers.get("idempotency-key");
    if (!requestId || !/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(requestId)) return failure(400, "request_id_required");
    if (!(await store.claimRequest(deviceHash, requestId.toLowerCase(), now))) return failure(409, "duplicate_request");
    const period = month(now);
    if (!(await store.countDeviceRequest(deviceHash, period, config.deviceRequests))) return failure(429, "device_quota_exhausted");
    const reservation = crypto.randomUUID();
    const amount = worstCaseUsd(modelConfig, checked.context, checked.previews);
    if (user.kind === "ok") {
      const admitted = await store.reserveForUser(reservation, period, amount, config.budget, now, user.email, user.limits.proposal_usd_month);
      if (admitted === "user") return json(429, { code: "quota_exceeded", resets_at: nextMonth(now) });
      if (admitted === "budget") return failure(429, "monthly_budget_exhausted");
    } else if (!(await store.reserve(reservation, period, amount, config.budget, now))) return failure(429, "monthly_budget_exhausted");
    try {
      const result = await draftProposal({ ...modelConfig, fetcher: options.fetcher, beforeCall: async () => {
        if (await store.budgetBlocked()) throw new ModelError("budget_reconciliation_required");
      } },
        checked.context, checked.previews);
      // Non-cached input may include cache writes. Until the API's write breakdown is
      // confirmed, retain its higher tariff; this is a conservative ledger, not an invoice.
      const spent = result.usageComplete ? ((result.inputTokens - result.cachedInputTokens) * config.priceCacheWrite
        + result.cachedInputTokens * config.priceCachedIn + result.outputTokens * config.priceOut) / 1_000_000 : amount;
      await store.settle(reservation, period, spent, result.usageComplete ? {
        model: config.model, promptVersion, inputTokens: result.inputTokens,
        cachedInputTokens: result.cachedInputTokens, outputTokens: result.outputTokens, calls: result.calls,
      } : undefined);
      return json(200, { draft: result.draft, model: config.model, prompt_version: promptVersion });
    } catch (error) {
      // Usage of a failed call is unknown here: settle conservatively at the reserved amount.
      const usage = error instanceof ModelError ? error.observedUsage : undefined;
      await store.settle(reservation, period, usage
        ? Math.max(amount, observedCost(usage, config.priceCacheWrite, config.priceCachedIn, config.priceOut)) : amount,
      usage ? { ...usage, model: config.model, promptVersion } : undefined,
      error instanceof ModelError && error.code === "model_usage_exceeded");
      if (error instanceof ModelError && error.validatedDraft !== undefined) {
        return json(200, { draft: error.validatedDraft, model: config.model, prompt_version: promptVersion });
      }
      const code = error instanceof ModelError ? error.code : "model_unavailable";
      if (error instanceof ModelError && code === "model_unavailable") {
        // Only ModelError's allowlisted diagnostics; never provider messages or headers.
        return json(503, { code,
          ...(error.providerHttpStatus === undefined ? {} : { provider_http_status: error.providerHttpStatus }),
          ...(error.providerErrorCode === undefined ? {} : { provider_error_code: error.providerErrorCode }),
        });
      }
      return failure(code === "model_unavailable" || code === "budget_reconciliation_required" ? 503 : 502, code);
    }
  }
  return failure(404, "not_found");
}

export default {
  fetch(request: Request, env: Env): Promise<Response> {
    return handle(request, env, new D1Store(env.DB));
  },
};
