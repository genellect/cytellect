/** Cloud access routes against real SQLite with every migration (requirements A1–A6, C1–C3, C5). */
import { afterEach, describe, expect, it, vi } from "vitest";
import { D1AuthStore } from "./auth-store";
import { ipBucket } from "./cloud";
import { handle, type Env } from "./index";
import { configuredMailer, MailError, RESEND_ENDPOINT, type MailMessage, type Mailer } from "./mail";
import { D1Store, type D1Database } from "./store";
import { sqliteDatabase } from "./test-support";

const ORIGIN = "https://api.example.test";
const OWNER = "owner@example.org";
const USER = "researcher@example.org";
const MODAL = "https://gpu.example.test";
const MODAL_TOKEN = "wk-test-proxy.ws-test-proxy";
const DRAFT = {
  recipe: "nuclear-intensity",
  channels: [{ token: "dapi", stain: "DAPI", role: "nuclear", reason: "核染色" }],
  metrics: [{ metric: "area", channel: null, region: "nucleus" }],
  statistics: { kind: "descriptive", test: null, omnibus: null, association: null, x: null, y: null },
  additional_analyses: [],
  figures: [{ kind: "field-distribution", metric: "area", channel: null, region: "nucleus", analysis_index: 0 }],
  missing_information: [],
  reference_ids: ["senft-2023"],
  rationale: "核面積の分布を視野ごとに示す。",
};
const CONTEXT = { protocol: "1.1.0", goal: "核面積", channels: [{ token: "dapi", stain: "DAPI", role: "nuclear" }], field_count: 2 };
const BASE_ENV: Env = {
  DB: undefined as never, OWNER_EMAIL: " Owner@Example.org ", ADMIN_SIGNING_KEY: "s".repeat(48),
  MODAL_URL: MODAL, MODAL_PROXY_TOKEN: MODAL_TOKEN, GPU_MONTHLY_SECONDS: "7200",
  OPENAI_API_KEY: "sk-test", OPENAI_MODEL: "gpt-6.1-sol", ADMIN_TOKEN: "admin-token-0123456789abcdef",
  MONTHLY_BUDGET_USD: "1", DEVICE_MONTHLY_REQUESTS: "10", PRICE_INPUT_USD_PER_MTOK: "2", PRICE_OUTPUT_USD_PER_MTOK: "10",
  PRICE_CACHED_INPUT_USD_PER_MTOK: "0.10", PRICE_CACHE_WRITE_USD_PER_MTOK: "2.50",
};

class FakeMailer implements Mailer {
  sent: MailMessage[] = [];
  failing = false;
  async send(message: MailMessage) {
    if (this.failing) throw new MailError();
    this.sent.push(message);
  }
  to(address: string) { return this.sent.filter((message) => message.to === address); }
  code(address: string) { return /(\d{6})/.exec(this.to(address).at(-1)?.text ?? "")?.[1] ?? ""; }
  link() { return /(https:\/\/\S+\/v1\/admin\/approve\?t=\S+)/.exec(this.to(OWNER).at(-1)?.text ?? "")?.[1] ?? ""; }
}

type Upstream = (url: string, init: RequestInit) => Promise<Response>;

async function setup(env: Env = BASE_ENV, upstream?: Upstream) {
  const db = await sqliteDatabase();
  const auth = new D1AuthStore(db), store = new D1Store(db), mailer = new FakeMailer();
  const time = { now: Date.UTC(2026, 9, 15, 12), wall: 1_000_000 };
  const gpuCalls: { url: string; init: RequestInit; body: Uint8Array | null }[] = [];
  const gpuFetcher = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const body = init?.body ? new Uint8Array(await new Response(init.body as BodyInit).arrayBuffer()) : null;
    gpuCalls.push({ url: String(input), init: init!, body });
    if (upstream) return upstream(String(input), init!);
    time.wall += 12_300;
    return new Response(body ? new Uint8Array([...body].reverse()) : "{\"status\":\"ok\"}", {
      status: 200, headers: { "content-type": body ? "application/octet-stream" : "application/json", "set-cookie": "upstream=1", "x-modal": "private" },
    });
  });
  const modelFetcher = vi.fn(async () => new Response(JSON.stringify({ status: "completed",
    output: [{ type: "message", content: [{ type: "output_text", text: JSON.stringify(DRAFT) }] }], usage: { input_tokens: 1000, output_tokens: 200 } })));
  let currentEnv = env;
  const call = (request: Request, mailerOverride: Mailer | null = mailer) => handle(request, currentEnv, store, {
    auth, mailer: mailerOverride, now: () => time.now, clock: () => time.wall, gpuFetcher, fetcher: modelFetcher,
  });
  const send = (method: string, path: string, body?: unknown, headers: Record<string, string> = {}) => call(new Request(`${ORIGIN}${path}`, {
    method, headers: { "cf-connecting-ip": "192.0.2.1", ...(body === undefined ? {} : { "content-type": "application/json" }), ...headers },
    body: body === undefined ? undefined : JSON.stringify(body),
  }));
  const login = async (email: string, device_name = "lab-pc") => {
    expect(await (await send("POST", "/v1/auth/code", { email })).json()).toEqual({ state: "code_sent", retry_after_seconds: 60 });
    const response = await send("POST", "/v1/auth/verify", { email, code: mailer.code(email), device_name });
    expect(response.status).toBe(200);
    return (await response.json() as { device_token: string }).device_token;
  };
  const adminLogin = async () => {
    expect((await send("POST", "/v1/admin/session/code", { email: OWNER })).status).toBe(200);
    const response = await send("POST", "/v1/admin/session/verify", { email: OWNER, code: mailer.code(OWNER) });
    expect(response.status).toBe(204);
    return response.headers.get("set-cookie")!.split(";")[0];
  };
  const adminChange = async (cookie: string, body: unknown) =>
    send("POST", "/v1/admin/users", body, { cookie, origin: ORIGIN });
  const bearer = (value: string) => ({ authorization: `Bearer ${value}` });
  const requestState = async (request_token: unknown) =>
    (await (await send("POST", "/v1/auth/request", { request_token })).json() as { state: string }).state;
  const requestAccess = async (email: string) => {
    const body = await (await send("POST", "/v1/auth/code", { email })).json() as { state: string; request_token: string };
    expect(body.state).toBe("pending_approval");
    return body.request_token;
  };
  return {
    db, auth, store, mailer, time, gpuCalls, gpuFetcher, modelFetcher, call, send, login, adminLogin, adminChange, bearer,
    requestState, requestAccess,
    setEnv: (next: Env) => { currentEnv = next; },
  };
}

async function dump(db: D1Database) {
  const tables = ["users", "login_codes", "user_devices", "admin_sessions", "approval_links", "rate_limits", "user_usage",
    "reservations", "settlements", "proposal_requests", "device_usage", "devices", "invitations"];
  const rows: Record<string, unknown> = {};
  for (const table of tables) rows[table] = (await db.prepare(`SELECT * FROM ${table}`).all()).results;
  return JSON.stringify(rows);
}

const proposal = (token: string) => new Request(`${ORIGIN}/v1/proposals`, {
  method: "POST", body: JSON.stringify({ context: CONTEXT }),
  headers: { "idempotency-key": crypto.randomUUID(), authorization: `Bearer ${token}` },
});

afterEach(() => vi.restoreAllMocks());

describe("e-mail code login", () => {
  it("issues a hashed 6-digit code to an allowed address and exchanges it once for a device token", async () => {
    const t = await setup();
    await t.auth.allow(USER, t.time.now);
    const sent = await t.send("POST", "/v1/auth/code", { email: "  Researcher@Example.ORG " });
    expect([sent.status, await sent.json()]).toEqual([200, { state: "code_sent", retry_after_seconds: 60 }]);
    const code = t.mailer.code(USER);
    expect(code).toMatch(/^\d{6}$/);
    expect(await dump(t.db)).not.toContain(code);
    const wrong = await t.send("POST", "/v1/auth/verify", { email: USER, code: code === "000000" ? "111111" : "000000" });
    expect([wrong.status, await wrong.json()]).toEqual([400, { error: "code_invalid", attempts_left: 4 }]);
    const verified = await t.send("POST", "/v1/auth/verify", { email: USER, code, device_name: "private-lab-pc-name" });
    expect(verified.status).toBe(200);
    const body = await verified.json() as { device_token: string; email: string; expires_at: string };
    expect(body.email).toBe(USER);
    expect(body.device_token).toMatch(/^[A-Za-z0-9_-]{43}$/);
    expect(body.expires_at).toBe(new Date(t.time.now + 90 * 86_400_000).toISOString());
    const stored = await dump(t.db);
    expect(stored).not.toContain(body.device_token);
    expect(stored).not.toContain("private-lab-pc-name");
    const again = await t.send("POST", "/v1/auth/verify", { email: USER, code });
    expect([again.status, await again.json()]).toEqual([400, { error: "code_expired" }]);
    const status = await t.send("GET", "/v1/auth/status", undefined, t.bearer(body.device_token));
    expect([status.status, await status.json()]).toEqual([200, {
      state: "allowed", email: USER, limits: { gpu_seconds_month: 3600, proposal_usd_month: 5 },
      usage: { gpu_seconds: 0, proposal_usd: 0 }, resets_at: "2026-11-01T00:00:00.000Z",
    }]);
  });

  it("enforces the resend interval, the 10-minute expiry and five attempts", async () => {
    const t = await setup();
    await t.auth.allow(USER, t.time.now);
    await t.send("POST", "/v1/auth/code", { email: USER });
    t.time.now += 30_000;
    const early = await t.send("POST", "/v1/auth/code", { email: USER });
    expect([early.status, await early.json()]).toEqual([429, { error: "rate_limited", retry_after_seconds: 30 }]);
    t.time.now += 10 * 60_000;
    const expired = await t.send("POST", "/v1/auth/verify", { email: USER, code: t.mailer.code(USER) });
    expect([expired.status, await expired.json()]).toEqual([400, { error: "code_expired" }]);

    await t.send("POST", "/v1/auth/code", { email: USER });
    const code = t.mailer.code(USER);
    const wrong = code === "123456" ? "654321" : "123456";
    const results = [];
    for (let index = 0; index < 5; index += 1) results.push(await (await t.send("POST", "/v1/auth/verify", { email: USER, code: wrong })).json());
    expect(results).toEqual([...[4, 3, 2, 1].map((left) => ({ error: "code_invalid", attempts_left: left })), { error: "too_many_attempts" }]);
    const voided = await t.send("POST", "/v1/auth/verify", { email: USER, code });
    expect([voided.status, await voided.json()]).toEqual([400, { error: "too_many_attempts" }]);
  });

  it("never sends a code to an address the owner has not allowed, and asks the owner once", async () => {
    const t = await setup();
    const stranger = "new.person@example.org";
    const tokens: string[] = [];
    for (let index = 0; index < 2; index += 1) {
      const response = await t.send("POST", "/v1/auth/code", { email: stranger });
      const body = await response.json() as { state: string; request_token: string };
      expect([response.status, Object.keys(body).sort(), body.state]).toEqual([200, ["request_token", "state"], "pending_approval"]);
      expect(body.request_token).toMatch(/^[A-Za-z0-9_-]{43}$/);
      tokens.push(body.request_token);
      t.time.now += 61_000;
    }
    expect(tokens[0]).not.toBe(tokens[1]);
    const stored = await dump(t.db);
    for (const value of tokens) expect(stored).not.toContain(value);
    expect(t.mailer.to(stranger)).toEqual([]);
    expect(t.mailer.to(OWNER)).toHaveLength(1);
    expect(t.mailer.to(OWNER)[0].text).toContain(stranger);
    expect(t.mailer.link()).toContain(`${ORIGIN}/v1/admin/approve?t=`);
    expect((await t.db.prepare("SELECT COUNT(*) AS n FROM login_codes").first())).toEqual({ n: 0 });
    const verify = await t.send("POST", "/v1/auth/verify", { email: stranger, code: "123456" });
    expect([verify.status, await verify.json()]).toEqual([400, { error: "code_expired" }]);
    for (const value of tokens) expect(await t.requestState(value)).toBe("pending_approval");
    // Unknown, malformed and missing tokens reveal nothing.
    for (const value of ["x".repeat(43), "short", 42, undefined]) expect(await t.requestState(value)).toBe("none");
    // The address is no longer accepted in the URL.
    expect((await t.send("GET", `/v1/auth/request?email=${encodeURIComponent(stranger)}`)).status).toBe(405);
    // Tokens expire after 14 days.
    t.time.now += 14 * 86_400_000;
    expect(await t.requestState(tokens[1])).toBe("none");
  });

  it("approves through the signed one-time link, notifies the requester and then allows login", async () => {
    const t = await setup();
    const requestToken = await t.requestAccess(USER);
    const link = new URL(t.mailer.link());
    const page = await t.call(new Request(link));
    expect(page.status).toBe(200);
    expect(page.headers.get("content-security-policy")).toContain("default-src 'none'");
    expect(page.headers.get("referrer-policy")).toBe("no-referrer");
    const html = await page.text();
    expect(html).toContain(USER);
    expect(html).toContain("承認する");
    // Following the link (for example by a mail scanner) does not approve.
    expect(await t.requestState(requestToken)).toBe("pending_approval");
    const token = link.searchParams.get("t")!;
    const tampered = token.slice(0, -1) + (token.endsWith("0") ? "1" : "0");
    const form = (value: string) => t.call(new Request(`${ORIGIN}/v1/admin/approve`, {
      method: "POST", headers: { "content-type": "application/x-www-form-urlencoded" }, body: new URLSearchParams({ t: value }).toString(),
    }));
    expect((await form(tampered)).status).toBe(400);
    const approved = await form(token);
    expect(approved.status).toBe(200);
    expect(await approved.text()).toContain("承認しました");
    expect(t.mailer.to(USER).at(-1)?.text).toContain("利用できるようになりました");
    expect((await form(token)).status).toBe(400);
    expect((await t.call(new Request(link))).status).toBe(400);
    expect(await t.requestState(requestToken)).toBe("allowed");
    expect(await t.login(USER)).toMatch(/^[A-Za-z0-9_-]{43}$/);
  });

  it("expires approval links after seven days and keeps a revoked user from being re-approved by an old link", async () => {
    const t = await setup();
    await t.send("POST", "/v1/auth/code", { email: USER });
    const first = t.mailer.link();
    t.time.now += 7 * 86_400_000;
    expect((await t.call(new Request(first))).status).toBe(400);
    t.time.now += 61_000;
    const requestToken = await t.requestAccess(USER);
    const second = new URL(t.mailer.link());
    expect(second.href).not.toBe(first);
    const cookie = await t.adminLogin();
    await t.adminChange(cookie, { email: USER, action: "revoke" });
    const response = await t.call(new Request(`${ORIGIN}/v1/admin/approve`, {
      method: "POST", headers: { "content-type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ t: second.searchParams.get("t")! }).toString(),
    }));
    expect(response.status).toBe(409);
    expect(await t.requestState(requestToken)).toBe("revoked");
  });

  it("expires a device after 90 days unused, extends it on use and logs out", async () => {
    const t = await setup();
    await t.auth.allow(USER, t.time.now);
    const device = await t.login(USER);
    t.time.now += 80 * 86_400_000;
    expect((await t.send("GET", "/v1/auth/status", undefined, t.bearer(device))).status).toBe(200);
    t.time.now += 80 * 86_400_000;
    expect((await t.send("GET", "/v1/auth/status", undefined, t.bearer(device))).status).toBe(200);
    t.time.now += 91 * 86_400_000;
    const expired = await t.send("GET", "/v1/auth/status", undefined, t.bearer(device));
    expect([expired.status, await expired.json()]).toEqual([401, { error: "auth_required" }]);
    const fresh = await t.login(USER);
    expect((await t.send("POST", "/v1/auth/logout", undefined, t.bearer(fresh))).status).toBe(204);
    expect((await t.send("GET", "/v1/auth/status", undefined, t.bearer(fresh))).status).toBe(401);
    expect((await t.send("GET", "/v1/auth/status")).status).toBe(401);
  });

  it("fails closed without a mail sender or when sending fails, and never logs codes", async () => {
    const t = await setup();
    const logs = (["log", "info", "warn", "error", "debug"] as const).map((name) => vi.spyOn(console, name));
    await t.auth.allow(USER, t.time.now);
    const unconfigured = await t.call(new Request(`${ORIGIN}/v1/auth/code`, { method: "POST", body: JSON.stringify({ email: USER }) }), null);
    expect([unconfigured.status, await unconfigured.json()]).toEqual([503, { error: "mail_unavailable" }]);
    t.mailer.failing = true;
    const failed = await t.send("POST", "/v1/auth/code", { email: USER });
    expect([failed.status, await failed.json()]).toEqual([502, { error: "mail_failed" }]);
    expect(await t.db.prepare("SELECT COUNT(*) AS n FROM login_codes").first()).toEqual({ n: 0 });
    t.mailer.failing = false;
    // A failed send does not start the resend interval.
    expect((await t.send("POST", "/v1/auth/code", { email: USER })).status).toBe(200);
    for (const spy of logs) expect(spy).not.toHaveBeenCalled();
    expect(configuredMailer({ MAIL_FROM: "Cytellect <noreply@mail.example.org>" })).toBeNull();
    expect(configuredMailer({ RESEND_API_KEY: "re_test", MAIL_FROM: "" })).toBeNull();
  });

  it("rate-limits code requests per IP and per address", async () => {
    const t = await setup();
    for (let index = 0; index < 6; index += 1) {
      expect((await t.send("POST", "/v1/auth/code", { email: USER }, { "cf-connecting-ip": "198.51.100.7" })).status).toBe(200);
    }
    const perEmail = await t.send("POST", "/v1/auth/code", { email: USER }, { "cf-connecting-ip": "198.51.100.8" });
    expect(perEmail.status).toBe(429);
    expect((await perEmail.json() as { error: string; retry_after_seconds: number })).toMatchObject({ error: "rate_limited" });
    for (let index = 0; index < 14; index += 1) {
      await t.send("POST", "/v1/auth/code", { email: `person${index}@example.org` }, { "cf-connecting-ip": "198.51.100.7" });
    }
    const perIp = await t.send("POST", "/v1/auth/code", { email: "late@example.org" }, { "cf-connecting-ip": "198.51.100.7" });
    expect(perIp.status).toBe(429);
    expect(await dump(t.db)).not.toContain("198.51.100");
    t.time.now += 3_600_000;
    expect((await t.send("POST", "/v1/auth/code", { email: "late@example.org" }, { "cf-connecting-ip": "198.51.100.7" })).status).toBe(200);
  });

  it("serves the admin page and its APIs only on ADMIN_ORIGIN and links approvals there", async () => {
    const other = "https://cytellect-proposal.example.workers.dev";
    const t = await setup({ ...BASE_ENV, ADMIN_ORIGIN: ORIGIN });
    const at = (origin: string, path: string, init?: RequestInit) => t.call(new Request(`${origin}${path}`, init));
    const post = (origin: string, path: string, body: unknown) => at(origin, path, {
      method: "POST", headers: { "content-type": "application/json", origin }, body: JSON.stringify(body),
    });
    // Another origin of the same Worker answers 404 for every admin path and sends nothing.
    expect((await at(other, "/admin")).status).toBe(404);
    expect((await post(other, "/v1/admin/session/code", { email: OWNER })).status).toBe(404);
    expect((await post(other, "/v1/admin/session/verify", { email: OWNER, code: "000000" })).status).toBe(404);
    expect((await at(other, "/v1/admin/users")).status).toBe(404);
    expect((await at(other, "/v1/admin/approve?t=x")).status).toBe(404);
    expect(t.mailer.to(OWNER)).toEqual([]);
    // Login itself still works on any origin, and an access request made through the
    // other origin links the owner to the admin origin.
    const response = await post(other, "/v1/auth/code", { email: USER });
    expect((await response.json() as { state: string }).state).toBe("pending_approval");
    expect(t.mailer.link().startsWith(`${ORIGIN}/v1/admin/approve?t=`)).toBe(true);
    expect(t.mailer.to(OWNER)[0].text).toContain(`${ORIGIN}/admin`);
    expect(t.mailer.to(OWNER)[0].text).not.toContain(other);
    // The admin origin itself works as before.
    expect((await at(ORIGIN, "/admin")).status).toBe(200);
    expect(await t.adminLogin()).toBeTruthy();
  });

  it("closes the admin paths when ADMIN_ORIGIN is malformed", async () => {
    for (const value of ["api.example.test", "http://api.example.test", "https://api.example.test/admin"]) {
      const t = await setup({ ...BASE_ENV, ADMIN_ORIGIN: value });
      const response = await t.call(new Request(`${ORIGIN}/admin`));
      expect([value, response.status, await response.json()]).toEqual([value, 503, { error: "admin_origin_invalid" }]);
      expect((await t.send("POST", "/v1/auth/code", { email: OWNER })).status).toBe(200);
    }
  });

  it("closes login without the owner address or signing key", async () => {
    const t = await setup({ ...BASE_ENV, ADMIN_SIGNING_KEY: "short" });
    const response = await t.send("POST", "/v1/auth/code", { email: USER });
    expect([response.status, await response.json()]).toEqual([503, { error: "auth_unavailable" }]);
    expect((await t.send("POST", "/v1/auth/code", {})).status).toBe(503);
    expect(t.mailer.sent).toEqual([]);
  });
});

describe("revocation", () => {
  it("immediately blocks status, the GPU gateway and proposals on every device", async () => {
    const t = await setup();
    await t.auth.allow(USER, t.time.now);
    const first = await t.login(USER);
    t.time.now += 61_000;
    const second = await t.login(USER);
    expect((await t.call(proposal(first))).status).toBe(200);
    const cookie = await t.adminLogin();
    expect((await t.adminChange(cookie, { email: USER, action: "revoke" })).status).toBe(200);
    for (const device of [first, second]) {
      const status = await t.send("GET", "/v1/auth/status", undefined, t.bearer(device));
      expect([status.status, await status.json()]).toEqual([403, { error: "revoked" }]);
      const gpu = await t.send("GET", "/v1/cellpose/health", undefined, t.bearer(device));
      expect([gpu.status, await gpu.json()]).toEqual([403, { error: "revoked" }]);
      const denied = await t.call(proposal(device));
      expect([denied.status, await denied.json()]).toEqual([403, { code: "revoked" }]);
    }
    expect(t.gpuFetcher).not.toHaveBeenCalled();
    expect(t.modelFetcher).toHaveBeenCalledTimes(1);
    expect(await (await t.send("POST", "/v1/auth/code", { email: USER })).json()).toEqual({ state: "revoked" });
    expect((await t.auth.user(USER))?.state).toBe("revoked");
    // Re-allowing requires a new login: revoked devices stay revoked.
    await t.adminChange(cookie, { email: USER, action: "allow" });
    expect((await t.send("GET", "/v1/auth/status", undefined, t.bearer(first))).status).toBe(401);
  });
});

describe("GPU gateway", () => {
  it("streams the body to Modal with the Worker's key and returns the response unchanged", async () => {
    const t = await setup();
    const logs = (["log", "info", "warn", "error", "debug"] as const).map((name) => vi.spyOn(console, name));
    await t.auth.allow(USER, t.time.now);
    const device = await t.login(USER);
    const payload = new TextEncoder().encode("PRIVATE-PIXELS-0123456789");
    const response = await t.call(new Request(`${ORIGIN}/v1/cellpose/v1/cellpose`, {
      method: "POST", body: payload,
      headers: { ...t.bearer(device), "content-type": "application/octet-stream", accept: "application/octet-stream",
        "content-length": String(payload.length), "x-cytellect-secret": "client-secret", cookie: "private=1" },
    }));
    expect(response.status).toBe(200);
    expect(new Uint8Array(await response.arrayBuffer())).toEqual(new Uint8Array([...payload].reverse()));
    expect(response.headers.get("set-cookie")).toBeNull();
    expect(response.headers.get("x-modal")).toBeNull();
    expect(response.headers.get("cache-control")).toBe("no-store");
    const [forwarded] = t.gpuCalls;
    expect(forwarded.url).toBe(`${MODAL}/v1/cellpose`);
    expect(forwarded.body).toEqual(payload);
    const headers = new Headers(forwarded.init.headers);
    expect(headers.get("authorization")).toBe(`Bearer ${MODAL_TOKEN}`);
    expect(headers.get("content-length")).toBe(String(payload.length));
    expect(headers.get("content-type")).toBe("application/octet-stream");
    expect(headers.get("x-cytellect-secret")).toBeNull();
    expect(headers.get("cookie")).toBeNull();
    expect(forwarded.init.redirect).toBe("manual");
    // 12.3 s of wall time counts as 13 GPU seconds.
    const status = await (await t.send("GET", "/v1/auth/status", undefined, t.bearer(device))).json() as { usage: { gpu_seconds: number } };
    expect(status.usage.gpu_seconds).toBe(13);
    const health = await t.send("GET", "/v1/cellpose/health", undefined, t.bearer(device));
    expect([health.status, await health.json()]).toEqual([200, { status: "ok" }]);
    expect(t.gpuCalls[1].url).toBe(`${MODAL}/health`);
    expect(t.gpuCalls[1].init.method).toBe("GET");
    const stored = await dump(t.db);
    expect(stored).not.toContain("PRIVATE-PIXELS");
    expect(stored).not.toContain(MODAL_TOKEN);
    for (const spy of logs) expect(spy).not.toHaveBeenCalled();
  });

  it("passes an upstream 503 through unchanged so the client can retry", async () => {
    const t = await setup(BASE_ENV, async () => new Response("{\"error\":\"starting\"}", {
      status: 503, headers: { "content-type": "application/json", "retry-after": "5" },
    }));
    await t.auth.allow(USER, t.time.now);
    const device = await t.login(USER);
    const response = await t.send("GET", "/v1/cellpose/health", undefined, t.bearer(device));
    expect(response.status).toBe(503);
    expect(response.headers.get("retry-after")).toBe("5");
    expect(await response.text()).toBe("{\"error\":\"starting\"}");
  });

  it("requires a user token, a known route and a configured upstream before any GPU call", async () => {
    const t = await setup();
    await t.auth.allow(USER, t.time.now);
    const device = await t.login(USER);
    const legacy = await (await t.call(new Request(`${ORIGIN}/v1/admin/invitations`, { method: "POST", headers: t.bearer(BASE_ENV.ADMIN_TOKEN!) }))).json() as { invitation: string };
    const redeemed = await (await t.call(new Request(`${ORIGIN}/v1/devices`, { method: "POST", body: JSON.stringify(legacy) }))).json() as { device_token: string };
    expect((await t.send("GET", "/v1/cellpose/health")).status).toBe(401);
    expect((await t.send("GET", "/v1/cellpose/health", undefined, t.bearer(redeemed.device_token))).status).toBe(401);
    expect((await t.send("GET", "/v1/cellpose/other", undefined, t.bearer(device))).status).toBe(404);
    expect((await t.send("GET", "/v1/cellpose/v1/cellpose", undefined, t.bearer(device))).status).toBe(405);
    const noLength = await t.call(new Request(`${ORIGIN}/v1/cellpose/v1/cellpose`, {
      method: "POST", headers: t.bearer(device), body: new ReadableStream({ start(c) { c.enqueue(new Uint8Array([1])); c.close(); } }),
      duplex: "half",
    } as RequestInit));
    expect(noLength.status).toBe(411);
    t.setEnv({ ...BASE_ENV, MODAL_URL: "http://gpu.example.test" });
    expect(await (await t.send("GET", "/v1/cellpose/health", undefined, t.bearer(device))).json()).toEqual({ error: "gpu_service_disabled" });
    t.setEnv({ ...BASE_ENV, GPU_MONTHLY_SECONDS: "" });
    expect((await t.send("GET", "/v1/cellpose/health", undefined, t.bearer(device))).status).toBe(503);
    expect(t.gpuFetcher).not.toHaveBeenCalled();
  });

  it("stops at the user's monthly limit and at the global monthly cap", async () => {
    const t = await setup({ ...BASE_ENV, GPU_MONTHLY_SECONDS: "320" });
    await t.auth.allow(USER, t.time.now);
    await t.auth.allow("second@example.org", t.time.now);
    const device = await t.login(USER);
    const other = await t.login("second@example.org");
    const cookie = await t.adminLogin();
    expect((await t.adminChange(cookie, { email: USER, action: "limits", gpu_seconds_month: 10, proposal_usd_month: null })).status).toBe(200);
    expect((await t.send("GET", "/v1/cellpose/health", undefined, t.bearer(device))).status).toBe(200);
    const over = await t.send("GET", "/v1/cellpose/health", undefined, t.bearer(device));
    expect([over.status, await over.json()]).toEqual([429, { error: "quota_exceeded", resets_at: "2026-11-01T00:00:00.000Z", scope: "user" }]);
    expect((await t.send("GET", "/v1/cellpose/health", undefined, t.bearer(other))).status).toBe(200);
    const global = await t.send("GET", "/v1/cellpose/health", undefined, t.bearer(other));
    expect([global.status, await global.json()]).toMatchObject([429, { error: "quota_exceeded", scope: "global" }]);
    expect(t.gpuFetcher).toHaveBeenCalledTimes(2);
    // Usage resets with the UTC calendar month.
    t.time.now = Date.UTC(2026, 10, 1);
    expect((await t.send("GET", "/v1/cellpose/health", undefined, t.bearer(device))).status).toBe(200);
  });
});

describe("proposals with user-bound tokens", () => {
  it("accepts the login token, counts cost against the user and enforces the user's limit", async () => {
    const t = await setup();
    await t.auth.allow(USER, t.time.now);
    const device = await t.login(USER);
    const response = await t.call(proposal(device));
    expect(response.status).toBe(200);
    expect((await response.json() as { draft: unknown }).draft).toEqual(DRAFT);
    const status = await (await t.send("GET", "/v1/auth/status", undefined, t.bearer(device))).json() as { usage: { proposal_usd: number } };
    expect(status.usage.proposal_usd).toBeCloseTo((1000 * 2.5 + 200 * 10) / 1e6);
    const cookie = await t.adminLogin();
    await t.adminChange(cookie, { email: USER, action: "limits", gpu_seconds_month: null, proposal_usd_month: 0.001 });
    const limited = await t.call(proposal(device));
    expect([limited.status, await limited.json()]).toEqual([429, { code: "quota_exceeded", resets_at: "2026-11-01T00:00:00.000Z" }]);
    expect(t.modelFetcher).toHaveBeenCalledTimes(1);
    expect(await dump(t.db)).not.toContain("核面積");
  });

  it("closes the invitation flow and its tokens when the migration flag is off", async () => {
    const t = await setup();
    const invited = await (await t.call(new Request(`${ORIGIN}/v1/admin/invitations`, { method: "POST", headers: t.bearer(BASE_ENV.ADMIN_TOKEN!) }))).json() as { invitation: string };
    const { device_token } = await (await t.call(new Request(`${ORIGIN}/v1/devices`, { method: "POST", body: JSON.stringify(invited) }))).json() as { device_token: string };
    expect((await t.call(proposal(device_token))).status).toBe(200);
    t.setEnv({ ...BASE_ENV, LEGACY_INVITATIONS: "false" });
    expect((await t.call(proposal(device_token))).status).toBe(401);
    expect((await t.call(new Request(`${ORIGIN}/v1/admin/invitations`, { method: "POST", headers: t.bearer(BASE_ENV.ADMIN_TOKEN!) }))).status).toBe(404);
  });
});

describe("admin page", () => {
  it("serves a script-nonce page and authenticates only the owner address", async () => {
    const t = await setup();
    const page = await t.send("GET", "/admin");
    expect(page.status).toBe(200);
    const csp = page.headers.get("content-security-policy")!;
    const nonce = /script-src 'nonce-([^']+)'/.exec(csp)?.[1];
    expect(await page.text()).toContain(`<script nonce="${nonce}">`);
    expect((await t.send("GET", "/v1/admin/users")).status).toBe(401);
    await t.auth.allow(USER, t.time.now);
    const intruder = await t.send("POST", "/v1/admin/session/code", { email: USER });
    expect([intruder.status, await intruder.json()]).toEqual([200, { state: "code_sent", retry_after_seconds: 60 }]);
    expect(t.mailer.to(USER)).toEqual([]);
    const userCode = await t.send("POST", "/v1/admin/session/verify", { email: USER, code: "123456" });
    expect(userCode.status).toBe(400);
    // An installation token is not an admin credential.
    const device = await t.login(USER);
    expect((await t.send("GET", "/v1/admin/users", undefined, t.bearer(device))).status).toBe(401);
    // A device login code cannot open the admin page either.
    await t.send("POST", "/v1/auth/code", { email: OWNER });
    expect((await t.send("POST", "/v1/admin/session/verify", { email: OWNER, code: t.mailer.code(OWNER) })).status).toBe(400);
    t.time.now += 61_000;
    const cookie = await t.adminLogin();
    expect(cookie).toMatch(/^__Host-cytellect_admin=[A-Za-z0-9_-]{43}$/);
    const listing = await t.send("GET", "/v1/admin/users", undefined, { cookie });
    expect(listing.status).toBe(200);
    const data = await listing.json() as { owner: string; users: { email: string; state: string; limits: unknown; usage: unknown }[] };
    expect(data.owner).toBe(OWNER);
    expect(data.users.find((user) => user.email === USER)).toMatchObject({
      state: "allowed", limits: { gpu_seconds_month: 3600, proposal_usd_month: 5, custom: false }, usage: { gpu_seconds: 0, proposal_usd: 0 },
    });
    const owner = await t.adminChange(cookie, { email: OWNER, action: "revoke" });
    expect([owner.status, await owner.json()]).toEqual([400, { error: "owner_cannot_be_revoked" }]);
    // Changing the owner address invalidates existing admin sessions.
    t.setEnv({ ...BASE_ENV, OWNER_EMAIL: "next-owner@example.org" });
    expect((await t.send("GET", "/v1/admin/users", undefined, { cookie })).status).toBe(401);
  });

  it("refuses cross-site and form submissions, pre-registers and logs out", async () => {
    const t = await setup();
    const cookie = await t.adminLogin();
    const crossSite = await t.send("POST", "/v1/admin/users", { email: USER, action: "allow" }, { cookie, origin: "https://attacker.example" });
    expect(crossSite.status).toBe(403);
    const form = await t.call(new Request(`${ORIGIN}/v1/admin/users`, {
      method: "POST", headers: { cookie, "content-type": "application/x-www-form-urlencoded" }, body: "email=x%40example.org&action=allow",
    }));
    expect(form.status).toBe(403);
    expect(await t.auth.user(USER)).toBeNull();
    const allowed = await t.adminChange(cookie, { email: " Researcher@Example.org", action: "allow" });
    expect([allowed.status, await allowed.json()]).toEqual([200, { email: USER, state: "allowed", notified: true }]);
    expect(t.mailer.to(USER).at(-1)?.subject).toContain("利用できるようになりました");
    expect((await t.adminChange(cookie, { email: USER, action: "limits", gpu_seconds_month: -1 })).status).toBe(400);
    expect((await t.adminChange(cookie, { email: "unknown@example.org", action: "limits", gpu_seconds_month: 60 })).status).toBe(404);
    expect((await t.send("POST", "/v1/admin/session/logout", {}, { cookie, origin: ORIGIN })).status).toBe(204);
    expect((await t.send("GET", "/v1/admin/users", undefined, { cookie })).status).toBe(401);
  });
});

describe("Resend sender", () => {
  it("posts one message to the Resend API and reduces failures to a fixed error", async () => {
    const fetcher = vi.fn(async () => new Response("{\"id\":\"x\"}", { status: 200 }));
    const mailer = configuredMailer({ RESEND_API_KEY: "re_test_key", MAIL_FROM: "Cytellect <noreply@mail.example.org>" }, fetcher)!;
    await mailer.send({ to: USER, subject: "件名", text: "本文" });
    const [url, init] = fetcher.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe(RESEND_ENDPOINT);
    expect(new Headers(init.headers).get("authorization")).toBe("Bearer re_test_key");
    expect(JSON.parse(init.body as string)).toEqual({ from: "Cytellect <noreply@mail.example.org>", to: [USER], subject: "件名", text: "本文" });
    const failing = configuredMailer({ RESEND_API_KEY: "re_test_key", MAIL_FROM: "noreply@mail.example.org" },
      vi.fn(async () => new Response("{\"message\":\"private provider detail\"}", { status: 422 })))!;
    await expect(failing.send({ to: USER, subject: "s", text: "t" })).rejects.toThrow(/^mail_failed$/);
  });
});

describe("brute-force limits", () => {
  it("buckets IPv6 clients by /64", async () => {
    expect(ipBucket("2001:DB8:1:2:3:4:5:6")).toBe("2001:db8:1:2::/64");
    expect(ipBucket("2001:db8::1")).toBe("2001:db8:0:0::/64");
    expect(ipBucket("2001:db8:0:0:ffff::")).toBe("2001:db8:0:0::/64");
    expect(ipBucket("::ffff:192.0.2.1")).toBe("0:0:0:0::/64");
    expect(ipBucket("192.0.2.1")).toBe("192.0.2.1");
    expect(ipBucket("not-an-ip")).toBe("not-an-ip");
    const t = await setup();
    for (let index = 0; index < 20; index += 1) {
      const ip = `2001:db8:5:6:${index.toString(16)}::1`;
      expect((await t.send("POST", "/v1/auth/code", { email: `p${index}@example.org` }, { "cf-connecting-ip": ip })).status).toBe(200);
    }
    const rotated = await t.send("POST", "/v1/auth/code", { email: "late@example.org" }, { "cf-connecting-ip": "2001:db8:5:6:ffff::9" });
    expect(rotated.status).toBe(429);
    expect((await t.send("POST", "/v1/auth/code", { email: "late@example.org" }, { "cf-connecting-ip": "2001:db8:5:7::1" })).status).toBe(200);
  });

  it("caps admin codes per recipient whatever the IP: 5 per hour and 10 per day", async () => {
    const t = await setup();
    const statuses: number[] = [];
    for (let index = 0; index < 6; index += 1) {
      statuses.push((await t.send("POST", "/v1/admin/session/code", { email: OWNER }, { "cf-connecting-ip": `203.0.113.${index}`, origin: ORIGIN })).status);
      t.time.now += 61_000;
    }
    expect(statuses).toEqual([200, 200, 200, 200, 200, 429]);
    t.time.now += 3_600_000;
    for (let index = 0; index < 6; index += 1) {
      statuses.push((await t.send("POST", "/v1/admin/session/code", { email: OWNER }, { "cf-connecting-ip": `198.51.100.${index}` })).status);
      t.time.now += 61_000;
    }
    expect(statuses.slice(6)).toEqual([200, 200, 200, 200, 200, 429]);
    t.time.now += 3_600_000;
    expect((await t.send("POST", "/v1/admin/session/code", { email: OWNER }, { "cf-connecting-ip": "192.0.2.200" })).status).toBe(429);
    expect(t.mailer.to(OWNER)).toHaveLength(10);
  });

  it.each(["admin", "device"] as const)("locks the address for a day after 20 wrong %s codes from any IP", async (purpose) => {
    const t = await setup();
    await t.auth.allow(USER, t.time.now);
    const email = purpose === "admin" ? OWNER : USER;
    const codePath = purpose === "admin" ? "/v1/admin/session/code" : "/v1/auth/code";
    const verifyPath = purpose === "admin" ? "/v1/admin/session/verify" : "/v1/auth/verify";
    let ip = 0;
    const from = () => ({ "cf-connecting-ip": `203.0.113.${ip++}`, origin: ORIGIN });
    let last: Response | undefined;
    let code = "";
    for (let round = 0; round < 5; round += 1) {
      expect((await t.send("POST", codePath, { email }, from())).status).toBe(200);
      code = t.mailer.code(email);
      const wrong = code === "000000" ? "111111" : "000000";
      for (let guess = 0; guess < 4; guess += 1) last = await t.send("POST", verifyPath, { email, code: wrong }, from());
      t.time.now += 61_000;
    }
    expect([last!.status, await last!.json()]).toEqual([429, { error: "rate_limited", retry_after_seconds: 86_400 }]);
    // Even the right code and a new code are refused until the lock ends.
    expect((await t.send("POST", verifyPath, { email, code }, from())).status).toBe(429);
    expect((await t.send("POST", codePath, { email }, from())).status).toBe(429);
    expect(t.mailer.to(email)).toHaveLength(5);
    t.time.now += 86_400_000;
    expect((await t.send("POST", codePath, { email }, from())).status).toBe(200);
    expect((await t.send("POST", verifyPath, { email, code: t.mailer.code(email) }, from())).status).toBe(purpose === "admin" ? 204 : 200);
  });

  it("sends at most 10 device codes per address per day", async () => {
    const t = await setup();
    await t.auth.allow(USER, t.time.now);
    const statuses: number[] = [];
    for (let index = 0; index < 12; index += 1) {
      if (index === 6) t.time.now += 3_600_000;
      statuses.push((await t.send("POST", "/v1/auth/code", { email: USER }, { "cf-connecting-ip": `203.0.113.${index}` })).status);
      t.time.now += 61_000;
    }
    expect(statuses).toEqual([200, 200, 200, 200, 200, 200, 200, 200, 200, 200, 429, 429]);
    expect(t.mailer.to(USER)).toHaveLength(10);
  });
});

describe("GPU admission under concurrency", () => {
  const infer = (t: Awaited<ReturnType<typeof setup>>, device: string, signal?: AbortSignal) => {
    const payload = new Uint8Array([1, 2, 3, 4]);
    return t.call(new Request(`${ORIGIN}/v1/cellpose/v1/cellpose`, {
      method: "POST", body: payload, signal,
      headers: { ...t.bearer(device), "content-type": "application/octet-stream", "content-length": String(payload.length) },
    }));
  };
  const waitForAbort = (init: RequestInit) => new Promise<Response>((_resolve, reject) => {
    init.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
  });
  const tick = () => new Promise((resolve) => setTimeout(resolve, 20));

  it("lets one inference per user run and refuses the rest, so concurrent requests cannot overrun the limit", async () => {
    let open!: () => void;
    const gate = new Promise<void>((resolve) => { open = resolve; });
    const t = await setup(BASE_ENV, async () => { await gate; return new Response(new Uint8Array([9]), { status: 200 }); });
    await t.auth.allow(USER, t.time.now);
    const device = await t.login(USER);
    await t.auth.addGpuSeconds(USER, "2026-10", 3599);
    const pending = Array.from({ length: 20 }, () => infer(t, device));
    await tick();
    t.time.wall += 4_000;
    open();
    const responses = await Promise.all(pending);
    const statuses = responses.map((response) => response.status);
    expect(statuses.filter((status) => status === 200)).toHaveLength(1);
    expect(statuses.filter((status) => status === 503)).toHaveLength(19);
    const busy = responses.find((response) => response.status === 503)!;
    expect(busy.headers.get("retry-after")).toBe("5");
    expect(await busy.json()).toEqual({ error: "gpu_busy", retry_after_seconds: 5 });
    expect(t.gpuFetcher).toHaveBeenCalledTimes(1);
    const after = await infer(t, device);
    expect([after.status, await after.json()]).toMatchObject([429, { error: "quota_exceeded", scope: "user" }]);
    expect((await t.auth.usage(USER, "2026-10")).gpu_seconds).toBe(3603);
  });

  it("holds 300 s per inference in flight, the admitted one included, against the global cap", async () => {
    let open!: () => void;
    const gate = new Promise<void>((resolve) => { open = resolve; });
    const t = await setup({ ...BASE_ENV, GPU_MONTHLY_SECONDS: "400" }, async () => { await gate; return new Response("{}", { status: 200 }); });
    await t.auth.allow(USER, t.time.now);
    await t.auth.allow("second@example.org", t.time.now);
    const first = await t.login(USER);
    const second = await t.login("second@example.org");
    const running = infer(t, first);
    await tick();
    // 0 used + 300 (running) + 300 (this one) > 400.
    const refused = await infer(t, second);
    expect([refused.status, await refused.json()]).toMatchObject([429, { error: "quota_exceeded", scope: "global" }]);
    open();
    expect((await running).status).toBe(200);
    expect((await infer(t, second)).status).toBe(200);
    expect(t.gpuFetcher).toHaveBeenCalledTimes(2);
    // An inference needs room for its own hold: 300 s left of a 300 s cap is enough, less is not.
    const tight = await setup({ ...BASE_ENV, GPU_MONTHLY_SECONDS: "300" });
    await tight.auth.allow(USER, tight.time.now);
    const device = await tight.login(USER);
    expect((await infer(tight, device)).status).toBe(200);
    expect((await infer(tight, device)).status).toBe(429);
  });

  it("answers a health check at once while the user's request is in flight, and bounds it by a deadline", async () => {
    let open!: () => void;
    const gate = new Promise<void>((resolve) => { open = resolve; });
    const t = await setup(BASE_ENV, async (url, init) => {
      if (url.endsWith("/health")) return waitForAbort(init);
      await gate;
      return new Response(new Uint8Array([9]), { status: 200 });
    });
    await t.auth.allow(USER, t.time.now);
    const device = await t.login(USER);
    const call = (request: Request) => handle(request, BASE_ENV, t.store, {
      auth: t.auth, mailer: t.mailer, now: () => t.time.now, clock: () => t.time.wall, gpuFetcher: t.gpuFetcher, healthTimeoutMs: 200,
    });
    const health = () => call(new Request(`${ORIGIN}/v1/cellpose/health`, { headers: t.bearer(device) }));
    // During the user's inference: 503 gpu_busy, nothing sent upstream.
    const running = infer(t, device);
    await tick();
    const duringInference = await health();
    expect([duringInference.status, duringInference.headers.get("retry-after"), await duringInference.json()])
      .toEqual([503, "5", { error: "gpu_busy", retry_after_seconds: 5 }]);
    expect(t.gpuFetcher).toHaveBeenCalledTimes(1);
    open();
    expect((await running).status).toBe(200);
    // During the user's own health check: 503 gpu_starting at once; the probe itself
    // ends at its deadline with the same answer and counts its time.
    const probing = health();
    await tick();
    const second = await health();
    expect([second.status, await second.json()]).toEqual([503, { error: "gpu_starting", retry_after_seconds: 5 }]);
    t.time.wall += 25_000;
    const probe = await probing;
    expect([probe.status, probe.headers.get("retry-after"), await probe.json()]).toEqual([503, "5", { error: "gpu_starting", retry_after_seconds: 5 }]);
    expect(t.gpuFetcher).toHaveBeenCalledTimes(2);
    expect((await t.auth.usage(USER, "2026-10")).gpu_seconds).toBe(26);
    expect(await t.db.prepare("SELECT COUNT(*) AS n FROM gpu_slots").first()).toEqual({ n: 0 });
  });

  it("sends only one of many concurrent health checks per user upstream and holds 30 s for each against the global cap", async () => {
    let open!: () => void;
    const gate = new Promise<void>((resolve) => { open = resolve; });
    const t = await setup({ ...BASE_ENV, GPU_MONTHLY_SECONDS: "400" }, async () => { await gate; return new Response("{}", { status: 200 }); });
    const emails = Array.from({ length: 6 }, (_, index) => `user${index}@example.org`);
    const devices: string[] = [];
    for (const email of emails) {
      await t.auth.allow(email, t.time.now);
      devices.push(await t.login(email));
    }
    const probe = (device: string) => t.send("GET", "/v1/cellpose/health", undefined, t.bearer(device));
    // 305 at once from one user: one reaches the upstream.
    const same = Array.from({ length: 305 }, () => probe(devices[0]));
    await tick();
    // Other users: admitted while 300 s still fit after the 30-s holds in flight
    // (0, 30, 60, 90 ≤ 100), then 429 global.
    const others = [];
    for (const device of devices.slice(1)) { others.push(probe(device)); await tick(); }
    t.time.wall += 2_000;
    open();
    const sameResults = await Promise.all(same);
    expect(sameResults.filter((response) => response.status === 200)).toHaveLength(1);
    expect(sameResults.filter((response) => response.status === 503)).toHaveLength(304);
    expect(await sameResults.find((response) => response.status === 503)!.json()).toEqual({ error: "gpu_starting", retry_after_seconds: 5 });
    const otherStatuses = (await Promise.all(others)).map((response) => response.status);
    expect(otherStatuses).toEqual([200, 200, 200, 429, 429]);
    expect(t.gpuFetcher).toHaveBeenCalledTimes(4);
    const total = (await t.db.prepare("SELECT SUM(gpu_seconds) AS seconds FROM user_usage").first<{ seconds: number }>())!.seconds;
    expect(total).toBeLessThanOrEqual(400);
    expect(await t.db.prepare("SELECT COUNT(*) AS n FROM gpu_slots").first()).toEqual({ n: 0 });
  });

  it("on client disconnect aborts the upstream call, counts the full hold and keeps the slot until it ends", async () => {
    let calls = 0;
    const t = await setup(BASE_ENV, async (_url, init) => {
      calls += 1;
      return calls === 1 ? waitForAbort(init) : new Response(new Uint8Array([9]), { status: 200 });
    });
    await t.auth.allow(USER, t.time.now);
    const device = await t.login(USER);
    const client = new AbortController();
    const pending = infer(t, device, client.signal);
    await tick();
    t.time.wall += 7_000;
    client.abort();
    expect((await pending).status).toBe(502);
    expect(t.gpuCalls[0].init.signal!.aborted).toBe(true);
    // The Modal server keeps computing: 300 s are counted, not the 7 s until the disconnect.
    expect((await t.auth.usage(USER, "2026-10")).gpu_seconds).toBe(300);
    const start = t.time.now;
    expect(await t.db.prepare("SELECT started_at, expires_at FROM gpu_slots WHERE email = ?").bind(USER).first())
      .toEqual({ started_at: start, expires_at: start + 300_000 });
    t.time.now = start + 299_000;
    const busy = await infer(t, device);
    expect([busy.status, (await busy.json() as { error: string }).error]).toEqual([503, "gpu_busy"]);
    t.time.now = start + 300_000;
    expect((await infer(t, device)).status).toBe(200);
    expect(t.gpuFetcher).toHaveBeenCalledTimes(2);
    expect(await t.db.prepare("SELECT COUNT(*) AS n FROM gpu_slots").first()).toEqual({ n: 0 });
  });

  it("keeps the slot when recording the usage fails, so neither the usage nor the hold is lost", async () => {
    const t = await setup(BASE_ENV, async () => new Response(new Uint8Array([9]), { status: 200 }));
    await t.auth.allow(USER, t.time.now);
    const device = await t.login(USER);
    const errors = vi.spyOn(console, "error").mockImplementation(() => undefined);
    await t.db.prepare("CREATE TRIGGER fail_usage BEFORE INSERT ON user_usage BEGIN SELECT RAISE(ABORT, 'test'); END").run();
    const response = await infer(t, device);
    // The finished result is still returned.
    expect(response.status).toBe(200);
    expect(errors).toHaveBeenCalledWith("gpu_usage_record_failed");
    expect(await t.db.prepare("SELECT expires_at FROM gpu_slots WHERE email = ?").bind(USER).first())
      .toEqual({ expires_at: t.time.now + 35 * 60_000 });
    const busy = await infer(t, device);
    expect([busy.status, (await busy.json() as { error: string }).error]).toEqual([503, "gpu_busy"]);
    await t.db.prepare("DROP TRIGGER fail_usage").run();
    t.time.now += 35 * 60_000;
    expect((await infer(t, device)).status).toBe(200);
    expect(await t.db.prepare("SELECT COUNT(*) AS n FROM gpu_slots").first()).toEqual({ n: 0 });
    expect((await t.auth.usage(USER, "2026-10")).gpu_seconds).toBe(1);
  });

  it("releases the slot when the upstream fails and takes over a stale slot", async () => {
    let failing = true;
    const t = await setup(BASE_ENV, async () => {
      if (failing) throw new TypeError("network");
      return new Response(new Uint8Array([9]), { status: 200 });
    });
    await t.auth.allow(USER, t.time.now);
    const device = await t.login(USER);
    expect(await (await infer(t, device)).json()).toEqual({ error: "gpu_upstream_unreachable" });
    failing = false;
    expect((await infer(t, device)).status).toBe(200);
    // A Worker stopped mid-request leaves its slot; it stops blocking after 35 minutes.
    await t.db.prepare("INSERT INTO gpu_slots (email, kind, hold_seconds, started_at, expires_at) VALUES (?, 'inference', 300, ?, ?)").bind(USER, t.time.now - 34 * 60_000, t.time.now + 60_000).run();
    expect((await infer(t, device)).status).toBe(503);
    t.time.now += 2 * 60_000;
    expect((await infer(t, device)).status).toBe(200);
  });
});

it("reads the approval form body within a bound even without Content-Length", async () => {
  const t = await setup();
  await t.send("POST", "/v1/auth/code", { email: USER });
  const token = new URL(t.mailer.link()).searchParams.get("t")!;
  const chunk = new TextEncoder().encode(`t=${token}&pad=${"x".repeat(8192)}`);
  const response = await t.call(new Request(`${ORIGIN}/v1/admin/approve`, {
    method: "POST", headers: { "content-type": "application/x-www-form-urlencoded" },
    body: new ReadableStream({ start(controller) { controller.enqueue(chunk); controller.close(); } }), duplex: "half",
  } as RequestInit));
  expect(response.status).toBe(400);
  expect((await t.auth.user(USER))?.state).toBe("pending");
});

it("rate-limits request-state checks per IPv6 /64", async () => {
  const t = await setup();
  const requestToken = await t.requestAccess(USER);
  const check = (ip: string) => t.send("POST", "/v1/auth/request", { request_token: requestToken }, { "cf-connecting-ip": ip });
  for (let index = 0; index < 240; index += 1) expect((await check(`2001:db8:9:9:${index.toString(16)}::1`)).status).toBe(200);
  const limited = await check("2001:db8:9:9:ffff::2");
  expect([limited.status, (await limited.json() as { error: string }).error]).toEqual([429, "rate_limited"]);
  expect((await check("2001:db8:9:a::1")).status).toBe(200);
});

it("counts requests during the resend interval against the IP but not against the address", async () => {
  const t = await setup();
  await t.auth.allow(USER, t.time.now);
  let ip = 0;
  const from = () => ({ "cf-connecting-ip": `203.0.113.${ip++}`, origin: ORIGIN });
  expect((await t.send("POST", "/v1/auth/code", { email: USER }, from())).status).toBe(200);
  for (let index = 0; index < 10; index += 1) {
    t.time.now += 5_000;
    const waiting = await t.send("POST", "/v1/auth/code", { email: USER }, from());
    expect(waiting.status).toBe(429);
    expect((await waiting.json() as { retry_after_seconds: number }).retry_after_seconds).toBeLessThanOrEqual(60);
  }
  // Six per hour per address: the ten waiting requests above were not counted.
  const sent = [];
  for (let index = 0; index < 6; index += 1) {
    t.time.now += 61_000;
    sent.push((await t.send("POST", "/v1/auth/code", { email: USER }, from())).status);
  }
  expect(sent).toEqual([200, 200, 200, 200, 200, 429]);

  // From one IP, waiting requests do count: 1 code + 19 waiting use up 20 per hour.
  const other = "second@example.org";
  await t.auth.allow(other, t.time.now);
  const fixed = { "cf-connecting-ip": "198.51.100.77" };
  expect((await t.send("POST", "/v1/auth/code", { email: other }, fixed)).status).toBe(200);
  for (let index = 0; index < 19; index += 1) expect((await t.send("POST", "/v1/auth/code", { email: other }, fixed)).status).toBe(429);
  t.time.now += 61_000;
  const byIp = await t.send("POST", "/v1/auth/code", { email: other }, fixed);
  expect(byIp.status).toBe(429);
  expect((await byIp.json() as { retry_after_seconds: number }).retry_after_seconds).toBeGreaterThan(60);

  // Admin: the owner's waiting requests count against the IP (10 per hour); other
  // addresses get the usual answer meanwhile.
  const admin = { "cf-connecting-ip": "192.0.2.50", origin: ORIGIN };
  expect((await t.send("POST", "/v1/admin/session/code", { email: OWNER }, admin)).status).toBe(200);
  for (let index = 0; index < 8; index += 1) expect((await t.send("POST", "/v1/admin/session/code", { email: OWNER }, admin)).status).toBe(429);
  expect(await (await t.send("POST", "/v1/admin/session/code", { email: USER }, admin)).json()).toEqual({ state: "code_sent", retry_after_seconds: 60 });
  t.time.now += 61_000;
  expect((await t.send("POST", "/v1/admin/session/code", { email: OWNER }, admin)).status).toBe(429);
  expect(t.mailer.to(OWNER)).toHaveLength(1);
});

it("holds 300 s for each other user's inference in flight when admitting a health check", async () => {
  // An instant upstream: each health check counts its 1-second minimum.
  const t = await setup({ ...BASE_ENV, GPU_MONTHLY_SECONDS: "750" }, async () => new Response("{}", { status: 200 }));
  await t.auth.allow(USER, t.time.now);
  const device = await t.login(USER);
  await t.auth.addGpuSeconds("other@example.org", "2026-10", 150);
  // 150 + 300 × (0 others + 1) = 450 ≤ 750.
  expect((await t.send("GET", "/v1/cellpose/health", undefined, t.bearer(device))).status).toBe(200);
  // Another user's inference in flight moves the boundary by 300 s: 150 + 1 (above) + 300 × 2 = 751 > 750.
  await t.db.prepare("INSERT INTO gpu_slots (email, kind, hold_seconds, started_at, expires_at) VALUES (?, 'inference', 300, ?, ?)").bind("other@example.org", t.time.now, t.time.now + 2_100_000).run();
  const refused = await t.send("GET", "/v1/cellpose/health", undefined, t.bearer(device));
  expect([refused.status, (await refused.json() as { scope: string }).scope]).toEqual([429, "global"]);
  t.setEnv({ ...BASE_ENV, GPU_MONTHLY_SECONDS: "751" });
  expect((await t.send("GET", "/v1/cellpose/health", undefined, t.bearer(device))).status).toBe(200);
  // A health check holds only 30 s: another user's health check in flight moves the
  // boundary by 30 s, not 300 s: 152 + 30 + 300 = 482.
  await t.db.prepare("UPDATE gpu_slots SET kind = 'health', hold_seconds = 30").run();
  t.setEnv({ ...BASE_ENV, GPU_MONTHLY_SECONDS: "481" });
  expect((await t.send("GET", "/v1/cellpose/health", undefined, t.bearer(device))).status).toBe(429);
  t.setEnv({ ...BASE_ENV, GPU_MONTHLY_SECONDS: "482" });
  expect((await t.send("GET", "/v1/cellpose/health", undefined, t.bearer(device))).status).toBe(200);
  // The user's own inference in flight: the health check is answered at once.
  await t.db.prepare("INSERT INTO gpu_slots (email, kind, hold_seconds, started_at, expires_at) VALUES (?, 'inference', 300, ?, ?)").bind(USER, t.time.now, t.time.now + 2_100_000).run();
  expect(await (await t.send("GET", "/v1/cellpose/health", undefined, t.bearer(device))).json()).toEqual({ error: "gpu_busy", retry_after_seconds: 5 });
});

it("refuses a health check with the inference's global 429 when one more inference would not fit", async () => {
  const t = await setup({ ...BASE_ENV, GPU_MONTHLY_SECONDS: "400" });
  await t.auth.allow(USER, t.time.now);
  const device = await t.login(USER);
  await t.auth.addGpuSeconds("other@example.org", "2026-10", 150);
  const health = await t.send("GET", "/v1/cellpose/health", undefined, t.bearer(device));
  expect([health.status, await health.json()]).toEqual([429, { error: "quota_exceeded", resets_at: "2026-11-01T00:00:00.000Z", scope: "global" }]);
  const payload = new Uint8Array([1]);
  const inference = await t.call(new Request(`${ORIGIN}/v1/cellpose/v1/cellpose`, {
    method: "POST", body: payload, headers: { ...t.bearer(device), "content-length": "1" },
  }));
  expect([inference.status, (await inference.json() as { scope: string }).scope]).toEqual([429, "global"]);
  t.setEnv({ ...BASE_ENV, GPU_MONTHLY_SECONDS: "450" });
  expect((await t.send("GET", "/v1/cellpose/health", undefined, t.bearer(device))).status).toBe(200);
  expect(t.gpuFetcher).toHaveBeenCalledTimes(1);
});
