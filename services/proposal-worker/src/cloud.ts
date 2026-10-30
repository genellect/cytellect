/**
 * Cloud access for installations: e-mail login codes, owner approval, user-bound
 * device tokens, the owner's admin page and the GPU (Cellpose on Modal) gateway.
 *
 * Nothing but e-mail addresses, hashes of codes and tokens, request/approval
 * timestamps and usage counters is stored. Request and response bodies of the
 * GPU gateway are streamed through unchanged and never read, stored or logged.
 * Login codes are never logged.
 */
import { adminPage, messagePage } from "./admin-page";
import { D1AuthStore, type CodePurpose, type UserRecord, type UserState } from "./auth-store";
import { base64url, bearer, boundedText, equal, fromBase64url, hmac, json, month, nextMonth, readObject, sha256, token } from "./http";
import type { Mailer } from "./mail";

export interface CloudEnv {
  OWNER_EMAIL?: string;
  /** When set (e.g. "https://api.example.org"), the admin page and its APIs answer only on
   * this origin, so one access policy in front of it covers every way in, and approval
   * links point to it. Other origins (such as workers.dev) get 404 for those paths. */
  ADMIN_ORIGIN?: string;
  ADMIN_SIGNING_KEY?: string;
  RESEND_API_KEY?: string;
  MAIL_FROM?: string;
  MODAL_URL?: string;
  MODAL_PROXY_TOKEN?: string;
  /** Global monthly GPU wall-clock seconds; the gateway is disabled unless positive. */
  GPU_MONTHLY_SECONDS?: string;
  USER_GPU_SECONDS_MONTH?: string;
  USER_PROPOSAL_USD_MONTH?: string;
}

export interface CloudContext {
  env: CloudEnv;
  auth: D1AuthStore;
  mailer: Mailer | null;
  now: number;
  /** Wall clock for GPU elapsed time (tests substitute a fake). */
  clock: () => number;
  gpuFetcher: typeof fetch;
  /** ExecutionContext.waitUntil when running in Workers. */
  waitUntil?: (promise: Promise<unknown>) => void;
  /** Health-check deadline; tests shorten it. */
  healthTimeoutMs?: number;
}

const SECOND = 1000, MINUTE = 60 * SECOND, HOUR = 60 * MINUTE, DAY = 24 * HOUR;
export const AUTH = {
  codeTtl: 10 * MINUTE,
  codeResend: 60 * SECOND,
  maxAttempts: 5,
  deviceTtl: 90 * DAY,
  deviceTouch: HOUR,
  adminSessionTtl: 12 * HOUR,
  approvalTtl: 7 * DAY,
  requestTokenTtl: 14 * DAY,
  bodyBytes: 4096,
  /** Wrong codes per address and purpose within a day before the address is locked. */
  maxFailures: 20,
  lockDuration: DAY,
} as const;
/**
 * Limits per keyed hash of the IP (IPv6 by /64) or e-mail address: [kind, max, window].
 * A window starts at its first hit. Code sends are also limited per recipient, so
 * rotating IP addresses does not add codes or guesses for one address.
 */
export const RATE = {
  codeIp: ["code-ip", 20, HOUR],
  codeEmail: ["code-email", 6, HOUR],
  codeSendDay: ["code-send-day", 10, DAY],
  verifyIp: ["verify-ip", 30, HOUR],
  requestIp: ["request-ip", 240, HOUR],
  adminIp: ["admin-ip", 10, HOUR],
  adminVerifyIp: ["admin-verify-ip", 20, HOUR],
  adminSendHour: ["admin-send-hour", 5, HOUR],
  adminSendDay: ["admin-send-day", 10, DAY],
  ownerNotices: ["owner-notice", 20, DAY],
} as const satisfies Record<string, readonly [string, number, number]>;
/** GPU admission: one request in flight per user; a slot older than this is stale. */
export const GPU_SLOT_STALE_MS = 35 * MINUTE;
/** Seconds held against the global cap for every inference request in flight. */
export const GPU_GLOBAL_HOLD_SECONDS = 300;
/** A health check waits at most this long (a cold start then answers 503 gpu_starting). */
export const GPU_HEALTH_TIMEOUT_MS = 25_000;
/** Held against the global cap by a health check in flight: its deadline plus rounding. */
export const GPU_HEALTH_HOLD_SECONDS = 30;
/** A health check's slot expires soon after its deadline, even if never released. */
export const GPU_HEALTH_SLOT_MS = 60_000;
export const DEFAULT_LIMITS = { gpuSeconds: 3600, proposalUsd: 5 };
export const GPU_PREFIX = "/v1/cellpose";
/** Modal server routes (engines/cellpose/server.py), mirrored under GPU_PREFIX. */
const GPU_ROUTES = { GET: ["/health"], POST: ["/", "/v1/cellpose"] } as const;
const GPU_MAX_BODY_BYTES = 256 * 1024 * 1024;
const ADMIN_COOKIE = "__Host-cytellect_admin";

const fail = (status: number, error: string, extra: Record<string, unknown> = {}, headers: Record<string, string> = {}) =>
  json(status, { error, ...extra }, headers);

export function normalizeEmail(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const email = value.trim().toLowerCase();
  return email.length <= 254 && /^[a-z0-9._%+-]{1,64}@[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$/.test(email)
    ? email : null;
}

interface AuthConfig { owner: string; key: string }

/** Login, approval and the admin page are closed unless the owner and signing key are set. */
function authConfig(env: CloudEnv): AuthConfig | null {
  const owner = normalizeEmail(env.OWNER_EMAIL);
  const key = env.ADMIN_SIGNING_KEY ?? "";
  return owner && key.length >= 32 ? { owner, key } : null;
}

function nonNegative(value: string | undefined, fallback: number): number {
  if (value === undefined || value.trim() === "") return fallback;
  const number = Number(value);
  // A malformed operator value closes the feature rather than granting a default.
  return Number.isFinite(number) && number >= 0 ? number : 0;
}

export function userLimits(env: CloudEnv, user: { gpu_seconds_month: number | null; proposal_usd_month: number | null }) {
  return {
    gpu_seconds_month: user.gpu_seconds_month ?? Math.floor(nonNegative(env.USER_GPU_SECONDS_MONTH, DEFAULT_LIMITS.gpuSeconds)),
    proposal_usd_month: user.proposal_usd_month ?? nonNegative(env.USER_PROPOSAL_USD_MONTH, DEFAULT_LIMITS.proposalUsd),
  };
}

/** IPv4 address, or the /64 prefix of an IPv6 address (one subscriber's usual allocation). */
export function ipBucket(ip: string): string {
  if (!ip.includes(":")) return ip;
  const [head, tail, extra] = ip.toLowerCase().split("::");
  if (extra !== undefined) return ip;
  const left = head ? head.split(":") : [];
  const right = tail ? tail.split(":") : [];
  const width = (groups: string[]) => groups.reduce((sum, group) => sum + (group.includes(".") ? 2 : 1), 0);
  const groups = tail === undefined ? left : [...left, ...Array(Math.max(0, 8 - width(left) - width(right))).fill("0"), ...right];
  const prefix = groups.slice(0, 4);
  if (prefix.length < 4 || prefix.some((group) => !/^[0-9a-f]{1,4}$/.test(group))) return ip;
  return `${prefix.map((group) => parseInt(group, 16).toString(16)).join(":")}::/64`;
}

const clientIp = (request: Request) => ipBucket(request.headers.get("cf-connecting-ip") ?? "unknown");

const rateKey = (cfg: AuthConfig, kind: string, value: string) =>
  hmac(cfg.key, "rate-limit", `${kind}\u0000${value}`).then((hash) => `${kind}:${hash}`);

const retryAfter = (until: number, now: number) => Math.max(1, Math.ceil((until - now) / SECOND));

async function limited(ctx: CloudContext, cfg: AuthConfig, [kind, max, window]: readonly [string, number, number], value: string) {
  const { count, window_start } = await ctx.auth.hit(await rateKey(cfg, kind, value), ctx.now, window);
  if (count <= max) return null;
  return fail(429, "rate_limited", { retry_after_seconds: retryAfter(window_start + window, ctx.now) });
}

/** 429 while the address is locked after too many wrong codes for this purpose. */
async function lockedOut(ctx: CloudContext, cfg: AuthConfig, email: string, purpose: CodePurpose) {
  const since = await ctx.auth.lockedSince(await rateKey(cfg, `lock-${purpose}`, email), ctx.now, AUTH.lockDuration);
  return since === null ? null : fail(429, "rate_limited", { retry_after_seconds: retryAfter(since + AUTH.lockDuration, ctx.now) });
}

/** Counts a wrong code; at the daily maximum the code is voided and the address locked. */
async function recordFailure(ctx: CloudContext, cfg: AuthConfig, email: string, purpose: CodePurpose) {
  const { count } = await ctx.auth.hit(await rateKey(cfg, `fail-${purpose}`, email), ctx.now, DAY);
  if (count < AUTH.maxFailures) return null;
  await ctx.auth.lock(await rateKey(cfg, `lock-${purpose}`, email), ctx.now);
  await ctx.auth.deleteCode(email, purpose);
  return fail(429, "rate_limited", { retry_after_seconds: AUTH.lockDuration / SECOND });
}

function sixDigits(): string {
  // Rejection sampling keeps every code equally likely.
  for (;;) {
    const [value] = crypto.getRandomValues(new Uint32Array(1));
    if (value < 4_294_000_000) return String(value % 1_000_000).padStart(6, "0");
  }
}

const codeHash = (cfg: AuthConfig, email: string, purpose: CodePurpose, code: string) =>
  hmac(cfg.key, "login-code", `${purpose}\u0000${email}\u0000${code}`);

/** The owner is always allowed; the row exists so devices can reference it. */
async function currentUser(ctx: CloudContext, cfg: AuthConfig, email: string): Promise<UserRecord | null> {
  const user = await ctx.auth.user(email);
  if (email !== cfg.owner || user?.state === "allowed") return user;
  await ctx.auth.allow(email, ctx.now);
  return ctx.auth.user(email);
}

/** 429 during the 60-second resend interval, checked before any counter is consumed. */
async function resendWait(ctx: CloudContext, email: string, purpose: CodePurpose) {
  const existing = await ctx.auth.code(email, purpose);
  if (!existing || ctx.now - existing.sent_at >= AUTH.codeResend) return null;
  return fail(429, "rate_limited", { retry_after_seconds: Math.ceil((existing.sent_at + AUTH.codeResend - ctx.now) / SECOND) });
}

async function sendCode(ctx: CloudContext, cfg: AuthConfig, email: string, purpose: CodePurpose): Promise<Response | null> {
  const locked = await lockedOut(ctx, cfg, email, purpose);
  if (locked) return locked;
  const waiting = await resendWait(ctx, email, purpose);
  if (waiting) return waiting;
  if (!ctx.mailer) return fail(503, "mail_unavailable");
  // Per recipient, whatever the requesting IP: bounds codes, guesses and mail volume.
  const capped = purpose === "admin"
    ? await limited(ctx, cfg, RATE.adminSendHour, email) ?? await limited(ctx, cfg, RATE.adminSendDay, email)
    : await limited(ctx, cfg, RATE.codeSendDay, email);
  if (capped) return capped;
  const code = sixDigits();
  await ctx.auth.putCode(email, purpose, await codeHash(cfg, email, purpose, code), ctx.now, ctx.now + AUTH.codeTtl);
  try {
    await ctx.mailer.send({
      to: email,
      subject: purpose === "admin" ? "Cytellect 管理ページのログインコード" : "Cytellect のログインコード",
      text: `ログインコード: ${code}\n\nこのコードは 10 分間有効です。心当たりがない場合は、このメールを無視してください。\n`,
    });
  } catch {
    // An undelivered code must not block a retry by the cooldown.
    await ctx.auth.deleteCode(email, purpose);
    return fail(502, "mail_failed");
  }
  return null;
}

async function verifyCode(ctx: CloudContext, cfg: AuthConfig, email: string, code: unknown, purpose: CodePurpose): Promise<Response | null> {
  const locked = await lockedOut(ctx, cfg, email, purpose);
  if (locked) return locked;
  const row = await ctx.auth.code(email, purpose);
  if (!row) return fail(400, "code_expired");
  if (row.expires_at <= ctx.now) {
    await ctx.auth.deleteCode(email, purpose);
    return fail(400, "code_expired");
  }
  if (row.attempts >= AUTH.maxAttempts) return fail(400, "too_many_attempts");
  const candidate = typeof code === "string" ? code.replace(/\s/g, "") : "";
  const hash = /^\d{6}$/.test(candidate) ? await codeHash(cfg, email, purpose, candidate) : "";
  if (hash && equal(hash, row.code_hash)) {
    return await ctx.auth.consumeCode(email, purpose, hash, ctx.now, AUTH.maxAttempts) ? null : fail(400, "code_expired");
  }
  const attempts = await ctx.auth.failAttempt(email, purpose, AUTH.maxAttempts);
  const lockedNow = attempts === null ? null : await recordFailure(ctx, cfg, email, purpose);
  if (lockedNow) return lockedNow;
  if (attempts === null || attempts >= AUTH.maxAttempts) return fail(400, "too_many_attempts");
  return fail(400, "code_invalid", { attempts_left: AUTH.maxAttempts - attempts });
}

/** Signed, single-use approval link token: payload.signature. */
async function approvalToken(ctx: CloudContext, cfg: AuthConfig, email: string) {
  const expires = ctx.now + AUTH.approvalTtl;
  const payload = base64url(new TextEncoder().encode(`${email}\n${expires}\n${token()}`));
  const signed = `${payload}.${await hmac(cfg.key, "approval-link", payload)}`;
  await ctx.auth.addApprovalLink(await sha256(signed), email, expires);
  return signed;
}

async function readApprovalToken(cfg: AuthConfig, value: unknown, now: number) {
  if (typeof value !== "string" || value.length > 1200) return null;
  const [payload, signature, extra] = value.split(".");
  if (!payload || !signature || extra !== undefined || !equal(signature, await hmac(cfg.key, "approval-link", payload))) return null;
  const bytes = fromBase64url(payload);
  if (!bytes) return null;
  const [email, expires] = new TextDecoder().decode(bytes).split("\n");
  if (normalizeEmail(email) !== email || !(Number(expires) > now)) return null;
  return { email, hash: await sha256(value) };
}

/** The configured admin origin; undefined when unset, null when set but malformed. */
function adminOrigin(env: CloudEnv): string | null | undefined {
  const value = env.ADMIN_ORIGIN?.trim();
  if (!value) return undefined;
  try {
    const url = new URL(value);
    return url.protocol === "https:" && url.origin === value.replace(/\/$/, "") ? url.origin : null;
  } catch {
    return null;
  }
}

async function notifyOwner(ctx: CloudContext, cfg: AuthConfig, user: UserRecord, requestOrigin: string) {
  const configured = adminOrigin(ctx.env);
  const origin = configured ?? requestOrigin;
  if (!ctx.mailer || (user.notified_at !== null && ctx.now - user.notified_at < AUTH.approvalTtl)) return;
  // A global daily cap keeps a flood of distinct addresses from flooding the owner;
  // requests are still recorded and listed on the admin page.
  if (await limited(ctx, cfg, RATE.ownerNotices, "all")) return;
  try {
    const link = `${origin}/v1/admin/approve?t=${encodeURIComponent(await approvalToken(ctx, cfg, user.email))}`;
    await ctx.mailer.send({
      to: cfg.owner,
      subject: "Cytellect の利用申請",
      text: `${user.email} から、Cytellect のクラウド機能（GPU 推論と解析提案）の利用申請がありました。\n\n`
        + `承認する場合は、次のリンクを開いて「承認する」を押してください（7 日間、1 回だけ有効）。\n${link}\n\n`
        + `管理ページ: ${origin}/admin\n`,
    });
    await ctx.auth.markNotified(user.email, ctx.now);
  } catch {
    // Left unnotified: the next request retries, and the admin page lists it.
  }
}

async function notifyAllowed(ctx: CloudContext, email: string) {
  if (!ctx.mailer) return false;
  try {
    await ctx.mailer.send({
      to: email,
      subject: "Cytellect のクラウド機能が利用できるようになりました",
      text: "Cytellect のクラウド機能（GPU 推論と解析提案）が利用できるようになりました。\n\n"
        + "作業画面の「クラウド機能を有効にする」から、このメールアドレスでログインしてください。\n",
    });
    return true;
  } catch { return false; }
}

export type DeviceLookup =
  | { kind: "none" | "expired" | "revoked" }
  | { kind: "ok"; email: string; limits: ReturnType<typeof userLimits> };

/** Resolves a user-bound device token; also extends its 90-day idle expiry. */
export async function lookupDevice(auth: D1AuthStore, env: CloudEnv, hash: string, now: number): Promise<DeviceLookup> {
  const device = await auth.device(hash);
  if (!device) return { kind: "none" };
  if (device.expires_at <= now) return { kind: "expired" };
  const owner = device.email === normalizeEmail(env.OWNER_EMAIL);
  if (!owner && device.state === "revoked") return { kind: "revoked" };
  if (device.revoked_at !== null || (!owner && device.state !== "allowed")) return { kind: "expired" };
  if (now - device.last_used_at >= AUTH.deviceTouch) await auth.touchDevice(hash, now, now + AUTH.deviceTtl);
  return { kind: "ok", email: device.email, limits: userLimits(env, device) };
}

async function authenticate(request: Request, ctx: CloudContext) {
  const presented = bearer(request);
  if (!presented) return fail(401, "auth_required");
  const result = await lookupDevice(ctx.auth, ctx.env, await sha256(presented), ctx.now);
  if (result.kind === "revoked") return fail(403, "revoked");
  if (result.kind !== "ok") return fail(401, "auth_required");
  return result;
}

const stateName = (state: UserState | undefined) =>
  state === "pending" ? "pending_approval" : state ?? "none";

// ---------------------------------------------------------------------------
// Installation routes

async function authCode(request: Request, ctx: CloudContext, cfg: AuthConfig, origin: string) {
  const email = normalizeEmail((await readObject(request, AUTH.bodyBytes))?.email);
  if (!email) return fail(400, "email_invalid");
  // Order: the IP limit counts every request, so the resend answer cannot be probed
  // for free; a request during the resend interval does not use up the address's limit.
  const blockedIp = await limited(ctx, cfg, RATE.codeIp, clientIp(request));
  if (blockedIp) return blockedIp;
  const waiting = await resendWait(ctx, email, "device");
  if (waiting) return waiting;
  const blocked = await limited(ctx, cfg, RATE.codeEmail, email);
  if (blocked) return blocked;
  await ctx.auth.pruneRateLimits(ctx.now - 2 * DAY);
  const user = await currentUser(ctx, cfg, email);
  if (user?.state === "revoked") return json(200, { state: "revoked" });
  if (user?.state === "allowed") {
    const failed = await sendCode(ctx, cfg, email, "device");
    return failed ?? json(200, { state: "code_sent", retry_after_seconds: AUTH.codeResend / SECOND });
  }
  // Not allowed: never send a code. Record the request and tell the owner once.
  await notifyOwner(ctx, cfg, await ctx.auth.requestAccess(email, ctx.now), origin);
  // Only the holder of this token can later read the request's state.
  await ctx.auth.pruneRequestTokens(ctx.now);
  const requestToken = token();
  await ctx.auth.addRequestToken(await sha256(requestToken), email, ctx.now + AUTH.requestTokenTtl);
  return json(200, { state: "pending_approval", request_token: requestToken });
}

async function authVerify(request: Request, ctx: CloudContext, cfg: AuthConfig) {
  const blocked = await limited(ctx, cfg, RATE.verifyIp, clientIp(request));
  if (blocked) return blocked;
  const body = await readObject(request, AUTH.bodyBytes);
  const email = normalizeEmail(body?.email);
  if (!email) return fail(400, "email_invalid");
  const failed = await verifyCode(ctx, cfg, email, body!.code, "device");
  if (failed) return failed;
  const user = await currentUser(ctx, cfg, email);
  if (user?.state !== "allowed") return fail(403, user?.state === "revoked" ? "revoked" : "pending_approval");
  // device_name is accepted for client compatibility but deliberately not stored.
  const device = token();
  const expires = ctx.now + AUTH.deviceTtl;
  await ctx.auth.addDevice(await sha256(device), email, ctx.now, expires);
  return json(200, { device_token: device, email, expires_at: new Date(expires).toISOString() });
}

async function authStatus(request: Request, ctx: CloudContext) {
  const result = await authenticate(request, ctx);
  if (result instanceof Response) return result;
  const usage = await ctx.auth.usage(result.email, month(ctx.now));
  return json(200, {
    state: "allowed", email: result.email, limits: result.limits,
    usage: { gpu_seconds: usage.gpu_seconds, proposal_usd: usage.proposal_usd }, resets_at: nextMonth(ctx.now),
  });
}

async function authRequest(request: Request, ctx: CloudContext, cfg: AuthConfig) {
  const blocked = await limited(ctx, cfg, RATE.requestIp, clientIp(request));
  if (blocked) return blocked;
  const value = (await readObject(request, AUTH.bodyBytes))?.request_token;
  // Unknown, malformed or expired tokens all read as "none": nothing else is revealed.
  if (typeof value !== "string" || !/^[A-Za-z0-9_-]{43}$/.test(value)) return json(200, { state: "none" });
  const found = await ctx.auth.requestTokenState(await sha256(value), ctx.now);
  if (!found) return json(200, { state: "none" });
  return json(200, { state: found.email === cfg.owner ? "allowed" : stateName(found.state ?? undefined) });
}

async function authLogout(request: Request, ctx: CloudContext) {
  const presented = bearer(request);
  if (!presented) return fail(401, "auth_required");
  await ctx.auth.removeDevice(await sha256(presented));
  return new Response(null, { status: 204, headers: { "cache-control": "no-store" } });
}

// ---------------------------------------------------------------------------
// GPU gateway

function gpuConfig(env: CloudEnv) {
  const cap = Number(env.GPU_MONTHLY_SECONDS);
  let upstream: URL;
  try { upstream = new URL(env.MODAL_URL ?? ""); } catch { return null; }
  if (upstream.protocol !== "https:" || upstream.username || upstream.password || upstream.search || upstream.hash
    || !env.MODAL_PROXY_TOKEN || !Number.isInteger(cap) || cap <= 0) return null;
  return { base: upstream.origin + upstream.pathname.replace(/\/+$/, ""), token: env.MODAL_PROXY_TOKEN, cap };
}

async function gateway(request: Request, url: URL, ctx: CloudContext) {
  const route = url.pathname.slice(GPU_PREFIX.length) || "/";
  const method = request.method as keyof typeof GPU_ROUTES;
  if (!(GPU_ROUTES[method] as readonly string[] | undefined)?.includes(route)) {
    return GPU_ROUTES.GET.includes(route as never) || GPU_ROUTES.POST.includes(route as never)
      ? fail(405, "method_not_allowed") : fail(404, "cellpose_remote_route_unknown");
  }
  const config = gpuConfig(ctx.env);
  if (!config) return fail(503, "gpu_service_disabled");
  const user = await authenticate(request, ctx);
  if (user instanceof Response) return user;
  const headers = new Headers({ authorization: `Bearer ${config.token}` });
  for (const name of ["content-type", "accept"]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  let body: ReadableStream<Uint8Array> | null = null;
  let length = 0;
  if (method === "POST") {
    length = Number(request.headers.get("content-length") ?? "");
    if (!request.headers.has("content-length") || !Number.isInteger(length) || length < 0) return fail(411, "cellpose_remote_input_invalid");
    if (length === 0 || length > GPU_MAX_BODY_BYTES) return fail(413, "cellpose_remote_input_too_large");
    headers.set("content-length", String(length));
  }

  const period = month(ctx.now);
  const resets = nextMonth(ctx.now);

  // One GPU request in flight per user, each holding time against the global cap, so
  // concurrent requests cannot together overrun either limit. Health checks are also
  // bounded by a deadline.
  const health = method === "GET";
  // Both kinds take the user's single slot. Admission needs room for one inference
  // (300 s) in both cases, so a health check is refused exactly when an inference
  // would be; a health check then holds only its own 30 s.
  const admitted = await ctx.auth.acquireGpuSlot(user.email, period, ctx.now,
    ctx.now + (health ? GPU_HEALTH_SLOT_MS : GPU_SLOT_STALE_MS), health ? "health" : "inference",
    health ? GPU_HEALTH_HOLD_SECONDS : GPU_GLOBAL_HOLD_SECONDS, GPU_GLOBAL_HOLD_SECONDS,
    user.limits.gpu_seconds_month, config.cap);
  // Another request of this user is in flight: answer at once without the upstream.
  if (admitted === "busy_health") return fail(503, "gpu_starting", { retry_after_seconds: 5 }, { "retry-after": "5" });
  if (admitted === "busy_inference") return fail(503, "gpu_busy", { retry_after_seconds: 5 }, { "retry-after": "5" });
  if (admitted !== "ok") return fail(429, "quota_exceeded", { resets_at: resets, scope: admitted });
  const deadline = health ? AbortSignal.timeout(ctx.healthTimeoutMs ?? GPU_HEALTH_TIMEOUT_MS) : null;
  // With the enable_request_signal flag, a client disconnect aborts the upstream call
  // at once, so the slot is released and the elapsed time recorded.
  const signal = deadline ? AbortSignal.any([request.signal, deadline]) : request.signal;

  if (method === "POST") {
    body = request.body;
    // The Modal server requires Content-Length: keep the stream's length known in Workers.
    const Fixed = (globalThis as { FixedLengthStream?: new (length: number) => TransformStream<Uint8Array, Uint8Array> }).FixedLengthStream;
    if (body && Fixed) {
      const fixed = new Fixed(length);
      void body.pipeTo(fixed.writable).catch(() => undefined);
      body = fixed.readable;
    }
  }
  const started = ctx.clock();
  const forward = (async () => {
    try {
      return await ctx.gpuFetcher(`${config.base}${route}`, {
        method, headers, body, redirect: "manual", signal,
        ...(body ? { duplex: "half" } : {}),
      } as RequestInit);
    } finally {
      const seconds = Math.max(1, Math.ceil((ctx.clock() - started) / SECOND));
      try {
        if (health) await ctx.auth.finishGpuRequest(user.email, period, Math.min(seconds, GPU_HEALTH_HOLD_SECONDS), ctx.now);
        else if (request.signal.aborted) {
          // The Modal server finishes an accepted inference even after the client
          // leaves. Count the whole hold and keep the slot (gpu_busy for this user)
          // until it ends, instead of the shorter time until the disconnect.
          await ctx.auth.abandonGpuRequest(user.email, period, Math.max(seconds, GPU_GLOBAL_HOLD_SECONDS), ctx.now,
            ctx.now + Math.max(seconds, GPU_GLOBAL_HOLD_SECONDS) * SECOND);
        } else await ctx.auth.finishGpuRequest(user.email, period, seconds, ctx.now);
      } catch {
        // Usage and release are one transaction: on failure the slot stays and keeps
        // counting as a hold until it expires. Fixed text only; no request details.
        console.error("gpu_usage_record_failed");
      }
    }
  })();
  // Keeps accounting and release alive briefly if the client disconnects.
  ctx.waitUntil?.(forward.catch(() => undefined));
  let upstream: Response;
  try {
    upstream = await forward;
  } catch {
    if (deadline?.aborted && !request.signal.aborted) {
      return fail(503, "gpu_starting", { retry_after_seconds: 5 }, { "retry-after": "5" });
    }
    return fail(502, "gpu_upstream_unreachable");
  }
  if (upstream.status >= 300 && upstream.status < 400) {
    await upstream.body?.cancel().catch(() => undefined);
    return fail(502, "gpu_upstream_invalid");
  }
  const out = new Headers({ "cache-control": "no-store" });
  for (const name of ["content-type", "content-length", "retry-after"]) {
    const value = upstream.headers.get(name);
    if (value) out.set(name, value);
  }
  // Status and body unchanged, including 503 while the GPU container starts.
  return new Response(upstream.body, { status: upstream.status, headers: out });
}

// ---------------------------------------------------------------------------
// Owner administration

function cookie(request: Request, name: string) {
  for (const part of (request.headers.get("cookie") ?? "").split(";")) {
    const [key, ...value] = part.trim().split("=");
    if (key === name) return value.join("=");
  }
  return null;
}

/** JSON from this origin only: forms and cross-site pages cannot send it with the cookie. */
function sameOriginJson(request: Request, url: URL) {
  const origin = request.headers.get("origin");
  return (request.headers.get("content-type") ?? "").split(";")[0].trim() === "application/json"
    && (origin === null || origin === url.origin);
}

async function adminEmail(request: Request, ctx: CloudContext, cfg: AuthConfig) {
  const value = cookie(request, ADMIN_COOKIE);
  if (!value || !/^[A-Za-z0-9_-]{43}$/.test(value)) return null;
  const email = await ctx.auth.adminSession(await sha256(value), ctx.now);
  return email === cfg.owner ? email : null;
}

const noContent = (headers: Record<string, string> = {}) =>
  new Response(null, { status: 204, headers: { "cache-control": "no-store", ...headers } });

const iso = (value: number | null) => value === null ? null : new Date(value).toISOString();

async function adminUsers(ctx: CloudContext, cfg: AuthConfig) {
  const period = month(ctx.now);
  const users = await ctx.auth.listUsers(period);
  const defaults = userLimits(ctx.env, { gpu_seconds_month: null, proposal_usd_month: null });
  return json(200, {
    owner: cfg.owner, month: period, resets_at: nextMonth(ctx.now), defaults,
    global: {
      gpu_seconds: await ctx.auth.globalGpuSeconds(period), gpu_seconds_month: gpuConfig(ctx.env)?.cap ?? 0,
      proposal_usd: await ctx.auth.globalProposalUsd(period),
    },
    users: users.map((user) => ({
      email: user.email, state: user.email === cfg.owner ? "allowed" : user.state,
      requested_at: iso(user.requested_at), approved_at: iso(user.approved_at), revoked_at: iso(user.revoked_at),
      limits: { ...userLimits(ctx.env, user), custom: user.gpu_seconds_month !== null || user.proposal_usd_month !== null },
      usage: { gpu_seconds: user.gpu_seconds, proposal_usd: user.proposal_usd },
    })),
  });
}

function limitValue(value: unknown, integer: boolean, max: number): number | null | undefined {
  if (value === null || value === undefined || value === "") return null;
  const number = typeof value === "number" ? value : Number.NaN;
  return Number.isFinite(number) && number >= 0 && number <= max && (!integer || Number.isInteger(number)) ? number : undefined;
}

async function adminChange(request: Request, ctx: CloudContext, cfg: AuthConfig) {
  const body = await readObject(request, AUTH.bodyBytes);
  const email = normalizeEmail(body?.email);
  if (!email) return fail(400, "email_invalid");
  if (body!.action === "allow") {
    const previous = await ctx.auth.allow(email, ctx.now);
    const notified = previous !== "allowed" && email !== cfg.owner ? await notifyAllowed(ctx, email) : false;
    return json(200, { email, state: "allowed", notified });
  }
  if (body!.action === "revoke") {
    if (email === cfg.owner) return fail(400, "owner_cannot_be_revoked");
    await ctx.auth.revoke(email, ctx.now);
    return json(200, { email, state: "revoked" });
  }
  if (body!.action === "limits") {
    const gpu = limitValue(body!.gpu_seconds_month, true, 100_000_000);
    const usd = limitValue(body!.proposal_usd_month, false, 10_000);
    if (gpu === undefined || usd === undefined) return fail(400, "limits_invalid");
    if (!(await ctx.auth.setLimits(email, gpu, usd))) return fail(404, "user_not_found");
    return json(200, { email, limits: userLimits(ctx.env, { gpu_seconds_month: gpu, proposal_usd_month: usd }) });
  }
  return fail(400, "action_invalid");
}

async function approvePage(request: Request, url: URL, ctx: CloudContext, cfg: AuthConfig) {
  if (request.method === "GET") {
    const value = url.searchParams.get("t");
    const link = await readApprovalToken(cfg, value, ctx.now);
    if (!link || !(await ctx.auth.approvalLinkUsable(link.hash, ctx.now))) {
      return messagePage(400, "リンクが無効です", "このリンクは期限切れか、すでに使われています。管理ページで申請を確認してください。");
    }
    // Opening the link only shows the request: mail scanners that follow links cannot approve.
    return messagePage(200, "利用申請の承認", `${link.email} に、GPU 推論と解析提案の利用を許可します。承認すると、申請者にメールで知らせます。`,
      { action: "/v1/admin/approve", token: value!, label: "承認する" });
  }
  const text = await boundedText(request.body, AUTH.bodyBytes);
  const form = text === null ? null : new URLSearchParams(text);
  const link = await readApprovalToken(cfg, form?.get("t"), ctx.now);
  const email = link && await ctx.auth.useApprovalLink(link.hash, ctx.now);
  if (!link || email !== link.email) {
    return messagePage(400, "リンクが無効です", "このリンクは期限切れか、すでに使われています。管理ページで申請を確認してください。");
  }
  const previous = await ctx.auth.allow(email, ctx.now, true);
  if (previous !== "pending") {
    return messagePage(409, "この申請は処理済みです", "この利用者の状態は、承認の前に変更されています。管理ページで確認してください。");
  }
  const notified = await notifyAllowed(ctx, email);
  return messagePage(200, "承認しました", `${email} は、クラウド機能を利用できます。`
    + (notified ? "申請者にメールで知らせました。" : "申請者へのメールは送れませんでした。直接お知らせください。"));
}

async function admin(request: Request, url: URL, ctx: CloudContext, cfg: AuthConfig) {
  const path = url.pathname, method = request.method;
  if (path === "/v1/admin/approve" && (method === "GET" || method === "POST")) return approvePage(request, url, ctx, cfg);
  if (path === "/v1/admin/users" && method === "GET") {
    return await adminEmail(request, ctx, cfg) ? adminUsers(ctx, cfg) : fail(401, "auth_required");
  }
  if (method !== "POST") return fail(405, "method_not_allowed");
  if (!sameOriginJson(request, url)) return fail(403, "forbidden");
  if (path === "/v1/admin/session/code") {
    const body = await readObject(request, AUTH.bodyBytes);
    const email = normalizeEmail(body?.email);
    if (!email) return fail(400, "email_invalid");
    const blocked = await limited(ctx, cfg, RATE.adminIp, clientIp(request));
    if (blocked) return blocked;
    // The same answer for every address, except that during the owner's resend
    // interval the owner's address alone gets 429. A code is sent to the owner only.
    const waiting = email === cfg.owner ? await resendWait(ctx, email, "admin") : null;
    if (waiting) return waiting;
    const failed = email === cfg.owner ? await sendCode(ctx, cfg, email, "admin") : null;
    return failed ?? json(200, { state: "code_sent", retry_after_seconds: AUTH.codeResend / SECOND });
  }
  if (path === "/v1/admin/session/verify") {
    const blocked = await limited(ctx, cfg, RATE.adminVerifyIp, clientIp(request));
    if (blocked) return blocked;
    const body = await readObject(request, AUTH.bodyBytes);
    const email = normalizeEmail(body?.email);
    if (!email) return fail(400, "email_invalid");
    const failed = await verifyCode(ctx, cfg, email, body!.code, "admin");
    if (failed) return failed;
    if (email !== cfg.owner) return fail(403, "forbidden");
    const session = token();
    await ctx.auth.addAdminSession(await sha256(session), email, ctx.now + AUTH.adminSessionTtl);
    return noContent({
      "set-cookie": `${ADMIN_COOKIE}=${session}; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age=${AUTH.adminSessionTtl / SECOND}`,
    });
  }
  if (path === "/v1/admin/session/logout") {
    const value = cookie(request, ADMIN_COOKIE);
    if (value) await ctx.auth.removeAdminSession(await sha256(value), ctx.now);
    return noContent({ "set-cookie": `${ADMIN_COOKIE}=; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age=0` });
  }
  if (path === "/v1/admin/users") {
    return await adminEmail(request, ctx, cfg) ? adminChange(request, ctx, cfg) : fail(401, "auth_required");
  }
  return fail(404, "not_found");
}

/** True for paths served by this module. */
export function isCloudPath(path: string) {
  return path === "/admin" || path.startsWith("/v1/auth/") || path === GPU_PREFIX || path.startsWith(`${GPU_PREFIX}/`)
    || (path.startsWith("/v1/admin/") && path !== "/v1/admin/invitations");
}

export async function handleCloud(request: Request, ctx: CloudContext): Promise<Response> {
  const url = new URL(request.url);
  const path = url.pathname, method = request.method;
  if (path === GPU_PREFIX || path.startsWith(`${GPU_PREFIX}/`)) return gateway(request, url, ctx);
  const cfg = authConfig(ctx.env);
  if (path === "/admin" || path.startsWith("/v1/admin/")) {
    const only = adminOrigin(ctx.env);
    if (only === null) return fail(503, "admin_origin_invalid");
    if (only !== undefined && url.origin !== only) return fail(404, "not_found");
  }
  if (path === "/admin") {
    if (method !== "GET") return fail(405, "method_not_allowed");
    return cfg ? adminPage() : messagePage(503, "管理ページは準備中です", "オーナーのメールアドレスと署名用の鍵が設定されていません。");
  }
  if (!cfg) return fail(503, "auth_unavailable");
  if (path.startsWith("/v1/admin/")) return admin(request, url, ctx, cfg);
  const routes: Record<string, [string, () => Promise<Response>]> = {
    "/v1/auth/code": ["POST", () => authCode(request, ctx, cfg, url.origin)],
    "/v1/auth/verify": ["POST", () => authVerify(request, ctx, cfg)],
    "/v1/auth/status": ["GET", () => authStatus(request, ctx)],
    "/v1/auth/request": ["POST", () => authRequest(request, ctx, cfg)],
    "/v1/auth/logout": ["POST", () => authLogout(request, ctx)],
  };
  const route = routes[path];
  if (!route) return fail(404, "not_found");
  return route[0] === method ? route[1]() : fail(405, "method_not_allowed");
}
