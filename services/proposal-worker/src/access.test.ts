/** Owner sign-in through Cloudflare Access: the Worker verifies the Access token itself. */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { accessConfig, clearAccessKeyCache } from "./access";
import { D1AuthStore } from "./auth-store";
import { handle, type Env } from "./index";
import type { MailMessage, Mailer } from "./mail";
import { D1Store } from "./store";
import { sqliteDatabase } from "./test-support";

const ORIGIN = "https://api.example.test";
const WORKERS_DEV = "https://cytellect-proposal.example.workers.dev";
const OWNER = "owner@example.org";
const USER = "researcher@example.org";
const TEAM = "example-team.cloudflareaccess.com";
const ISSUER = `https://${TEAM}`;
const AUD = "a".repeat(32) + "0123456789abcdef0123456789abcdef";
const ADMIN_TOKEN = "admin-token-0123456789abcdef";
const BASE_ENV: Env = {
  DB: undefined as never, OWNER_EMAIL: " Owner@Example.org ", ADMIN_SIGNING_KEY: "s".repeat(48), ADMIN_ORIGIN: ORIGIN,
  ADMIN_TOKEN, ACCESS_TEAM_DOMAIN: TEAM, ACCESS_AUD: AUD,
};
const NO_ACCESS: Env = { ...BASE_ENV, ACCESS_TEAM_DOMAIN: "", ACCESS_AUD: "" };

class FakeMailer implements Mailer {
  sent: MailMessage[] = [];
  async send(message: MailMessage) { this.sent.push(message); }
  to(address: string) { return this.sent.filter((message) => message.to === address); }
  code(address: string) { return /(\d{6})/.exec(this.to(address).at(-1)?.text ?? "")?.[1] ?? ""; }
  link() { return /(https:\/\/\S+\/v1\/admin\/approve\?t=\S+)/.exec(this.to(OWNER).at(-1)?.text ?? "")?.[1] ?? ""; }
}

const text = (value: string) => new TextEncoder().encode(value);
const b64url = (bytes: Uint8Array) => btoa(String.fromCharCode(...bytes)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const segment = (value: unknown) => b64url(text(JSON.stringify(value)));

async function keyPair(kid: string) {
  const pair = await crypto.subtle.generateKey(
    { name: "RSASSA-PKCS1-v1_5", modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: "SHA-256" }, true, ["sign", "verify"]);
  const jwk = await crypto.subtle.exportKey("jwk", pair.publicKey);
  return { kid, privateKey: pair.privateKey, jwk: { kid, kty: "RSA", alg: "RS256", use: "sig", n: jwk.n, e: jwk.e } };
}
type Key = Awaited<ReturnType<typeof keyPair>>;

async function sign(key: Key, claims: Record<string, unknown>, header: Record<string, unknown> = {}) {
  const signed = `${segment({ alg: "RS256", kid: key.kid, typ: "JWT", ...header })}.${segment(claims)}`;
  const signature = new Uint8Array(await crypto.subtle.sign("RSASSA-PKCS1-v1_5", key.privateKey, text(signed)));
  return `${signed}.${b64url(signature)}`;
}

async function setup(env: Env = BASE_ENV) {
  const db = await sqliteDatabase();
  const auth = new D1AuthStore(db), store = new D1Store(db), mailer = new FakeMailer();
  const time = { now: Date.UTC(2026, 9, 15, 12) };
  const key = await keyPair("key-1");
  // What each team's certs endpoint publishes.
  const published: Record<string, Key[]> = { [ISSUER]: [key] };
  const certs: { url: string; init?: RequestInit }[] = [];
  const accessFetcher = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    certs.push({ url, init });
    const team = Object.keys(published).find((issuer) => url === `${issuer}/cdn-cgi/access/certs`);
    if (!team) return new Response("not found", { status: 404 });
    return Response.json({ keys: published[team].map((item) => item.jwk), public_cert: { kid: "x", cert: "-" } });
  });
  let currentEnv = env;
  const call = (request: Request) => handle(request, currentEnv, store, { auth, mailer, now: () => time.now, accessFetcher });
  const seconds = () => Math.floor(time.now / 1000);
  const claims = (extra: Record<string, unknown> = {}) => ({
    aud: [AUD], email: OWNER, exp: seconds() + 3600, iat: seconds(), nbf: seconds(), iss: ISSUER, type: "app",
    identity_nonce: "nonce", sub: "00000000-0000-4000-8000-000000000000", country: "JP", ...extra,
  });
  const ownerToken = (extra: Record<string, unknown> = {}) => sign(key, claims(extra));
  const send = (method: string, path: string, options: { token?: string; body?: unknown; origin?: string; headers?: Record<string, string> } = {}) => {
    const origin = options.origin ?? ORIGIN;
    const headers: Record<string, string> = { "cf-connecting-ip": "192.0.2.1", ...options.headers };
    if (options.token !== undefined) headers["cf-access-jwt-assertion"] = options.token;
    if (options.body !== undefined) { headers["content-type"] = "application/json"; headers.origin = origin; }
    return call(new Request(`${origin}${path}`, {
      method, headers, body: options.body === undefined ? undefined : JSON.stringify(options.body),
    }));
  };
  const users = async (token?: string) => {
    const response = await send("GET", "/v1/admin/users", { token });
    return [response.status, await response.json()];
  };
  return {
    db, auth, mailer, time, key, published, certs, accessFetcher, call, send, claims, ownerToken, users, seconds,
    setEnv: (next: Env) => { currentEnv = next; },
  };
}

beforeEach(() => clearAccessKeyCache());
afterEach(() => vi.restoreAllMocks());

describe("Access configuration", () => {
  it("is off when both values are empty, and invalid when half set or malformed", () => {
    expect(accessConfig({})).toBeUndefined();
    expect(accessConfig({ ACCESS_TEAM_DOMAIN: "", ACCESS_AUD: " " })).toBeUndefined();
    expect(accessConfig({ ACCESS_TEAM_DOMAIN: TEAM, ACCESS_AUD: AUD })).toEqual({ issuer: ISSUER, audience: AUD });
    // Copied from the dashboard with the scheme or a trailing slash, in any case.
    expect(accessConfig({ ACCESS_TEAM_DOMAIN: ` https://Example-Team.CloudflareAccess.com/ `, ACCESS_AUD: AUD })).toEqual({ issuer: ISSUER, audience: AUD });
    for (const env of [
      { ACCESS_TEAM_DOMAIN: TEAM }, { ACCESS_AUD: AUD }, { ACCESS_TEAM_DOMAIN: TEAM, ACCESS_AUD: "" },
      { ACCESS_TEAM_DOMAIN: "example-team.cloudflareaccess.com.evil.example", ACCESS_AUD: AUD },
      { ACCESS_TEAM_DOMAIN: "evil.example/x.cloudflareaccess.com", ACCESS_AUD: AUD },
      { ACCESS_TEAM_DOMAIN: "http://example-team.cloudflareaccess.com", ACCESS_AUD: AUD },
      { ACCESS_TEAM_DOMAIN: TEAM, ACCESS_AUD: "short" }, { ACCESS_TEAM_DOMAIN: TEAM, ACCESS_AUD: `${AUD}/x` },
    ]) expect(accessConfig(env)).toBeNull();
  });

  it("closes every admin path with 503 when half set, malformed or without ADMIN_ORIGIN, and leaves login open", async () => {
    for (const env of [
      { ...BASE_ENV, ACCESS_AUD: "" }, { ...BASE_ENV, ACCESS_TEAM_DOMAIN: "" },
      { ...BASE_ENV, ACCESS_TEAM_DOMAIN: "example.org" }, { ...BASE_ENV, ADMIN_ORIGIN: "" },
    ]) {
      const t = await setup(env);
      const token = await t.ownerToken();
      for (const [method, path] of [["GET", "/admin"], ["GET", "/v1/admin/users"], ["GET", "/v1/admin/approve?t=x"], ["POST", "/v1/admin/session/code"]]) {
        const response = await t.send(method, path, { token });
        expect([path, response.status, await response.json()]).toEqual([path, 503, { error: "access_config_invalid" }]);
      }
      const invite = await t.call(new Request(`${ORIGIN}/v1/admin/invitations`, {
        method: "POST", headers: { authorization: `Bearer ${ADMIN_TOKEN}`, "cf-access-jwt-assertion": token },
      }));
      expect([invite.status, await invite.json()]).toEqual([503, { code: "access_config_invalid" }]);
      expect((await t.send("POST", "/v1/auth/code", { body: { email: USER } })).status).toBe(200);
      expect(t.accessFetcher).not.toHaveBeenCalled();
    }
  });
});

describe("Access token verification", () => {
  it("lets the owner in with a valid token, whatever the case of the address and the form of aud", async () => {
    const t = await setup();
    const page = await t.send("GET", "/admin", { token: await t.ownerToken() });
    expect(page.status).toBe(200);
    const html = await page.text();
    expect(html).toContain("const ACCESS = true;");
    expect(html).toContain("/cdn-cgi/access/logout");
    for (const token of [
      await t.ownerToken(), await t.ownerToken({ email: "Owner@Example.ORG" }), await t.ownerToken({ aud: AUD }),
      await t.ownerToken({ aud: ["other-application-aud-0000000000", AUD] }), await t.ownerToken({ nbf: undefined }),
      // Within the 60-second clock allowance.
      await t.ownerToken({ exp: t.seconds() - 30, nbf: t.seconds() + 30 }),
    ]) {
      const [status, body] = await t.users(token);
      expect(status).toBe(200);
      expect(body).toMatchObject({ owner: OWNER });
    }
    // No admin cookie is involved: the token alone authorizes changes.
    const allowed = await t.send("POST", "/v1/admin/users", { token: await t.ownerToken(), body: { email: USER, action: "allow" } });
    expect([allowed.status, await allowed.json()]).toEqual([200, { email: USER, state: "allowed", notified: true }]);
    // The keys were fetched once, from the team's certs URL, without following redirects.
    expect(t.certs).toEqual([{ url: `${ISSUER}/cdn-cgi/access/certs`, init: { redirect: "manual" } }]);
  });

  it("refuses wrong audience, issuer, period, signature, algorithm and identity, and missing or malformed tokens", async () => {
    const t = await setup();
    const valid = await t.ownerToken();
    const [head, body, signature] = valid.split(".");
    const other = await keyPair("key-1");
    const refused: Record<string, string | undefined> = {
      "missing header": undefined,
      "empty header": "",
      "wrong aud": await t.ownerToken({ aud: ["other-application-aud-0000000000"] }),
      "wrong aud string": await t.ownerToken({ aud: "other-application-aud-0000000000" }),
      "aud missing": await t.ownerToken({ aud: undefined }),
      "aud nested": await t.ownerToken({ aud: [[AUD]] }),
      "wrong iss": await t.ownerToken({ iss: "https://other-team.cloudflareaccess.com" }),
      "iss without scheme": await t.ownerToken({ iss: TEAM }),
      "expired": await t.ownerToken({ exp: t.seconds() - 61 }),
      "exp missing": await t.ownerToken({ exp: undefined }),
      "exp as text": await t.ownerToken({ exp: String(t.seconds() + 3600) }),
      "nbf in the future": await t.ownerToken({ nbf: t.seconds() + 120 }),
      "nbf as text": await t.ownerToken({ nbf: "0" }),
      "non-owner email": await t.ownerToken({ email: USER }),
      "owner as a prefix": await t.ownerToken({ email: `${OWNER}.evil.example` }),
      "service token without email": await t.ownerToken({ email: undefined, common_name: "service-token-client-id.access" }),
      "email not a string": await t.ownerToken({ email: [OWNER] }),
      "bad signature": `${head}.${body}.${signature.slice(0, -4)}${signature.endsWith("AAAA") ? "BBBB" : "AAAA"}`,
      "claims swapped after signing": `${head}.${b64url(text(JSON.stringify(t.claims({ email: OWNER, exp: t.seconds() + 999_999 }))))}.${signature}`,
      "signed by another key with the same kid": await sign(other, t.claims()),
      "alg none": `${b64url(text(JSON.stringify({ alg: "none", kid: "key-1" })))}.${body}.`,
      "alg HS256": await sign(t.key, t.claims(), { alg: "HS256" }),
      "alg RS512": await sign(t.key, t.claims(), { alg: "RS512" }),
      "alg PS256": await sign(t.key, t.claims(), { alg: "PS256" }),
      "kid missing": await sign(t.key, t.claims(), { kid: undefined }),
      "kid not a string": await sign(t.key, t.claims(), { kid: 1 }),
      "two segments": `${head}.${body}`,
      "four segments": `${valid}.x`,
      "not base64url": `${head}.${body}.${signature.slice(0, -1)}+`,
      "header not JSON": `${b64url(text("{alg"))}.${body}.${signature}`,
      "claims an array": `${head}.${b64url(text("[1]"))}.${signature}`,
      "bearer prefix": `Bearer ${valid}`,
      "oversized": `${head}.${b64url(text(JSON.stringify(t.claims({ pad: "x".repeat(9000) }))))}.${signature}`,
    };
    for (const [name, token] of Object.entries(refused)) {
      expect([name, ...(await t.users(token))]).toEqual([name, 401, { error: "auth_required" }]);
      const page = await t.send("GET", "/admin", { token });
      expect([name, page.status]).toEqual([name, 403]);
      expect(await page.text()).toContain("Cloudflare Access");
    }
    // The owner's valid token still works afterwards.
    expect((await t.users(valid))[0]).toBe(200);
  });

  it("refetches the keys once for an unknown kid, so a rotated key is accepted, but no more than every 30 s", async () => {
    const t = await setup();
    expect((await t.users(await t.ownerToken()))[0]).toBe(200);
    expect(t.accessFetcher).toHaveBeenCalledTimes(1);
    const rotated = await keyPair("key-2");
    t.published[ISSUER] = [t.key, rotated];
    t.time.now += 60_000;
    expect((await t.users(await sign(rotated, t.claims())))[0]).toBe(200);
    expect(t.accessFetcher).toHaveBeenCalledTimes(2);
    // An id the team never published: within 30 s of the last fetch, nothing is fetched.
    const forged = await keyPair("key-forged");
    t.time.now += 10_000;
    expect(await t.users(await sign(forged, t.claims()))).toEqual([401, { error: "auth_required" }]);
    expect(await t.users(await sign(forged, t.claims()))).toEqual([401, { error: "auth_required" }]);
    expect(t.accessFetcher).toHaveBeenCalledTimes(2);
    // Later, one refetch, which does not find it either.
    t.time.now += 30_000;
    expect(await t.users(await sign(forged, t.claims()))).toEqual([401, { error: "auth_required" }]);
    expect(t.accessFetcher).toHaveBeenCalledTimes(3);
    // Known keys are served from the cache for 10 minutes, then fetched again.
    expect((await t.users(await t.ownerToken()))[0]).toBe(200);
    expect(t.accessFetcher).toHaveBeenCalledTimes(3);
    t.time.now += 10 * 60_000;
    expect((await t.users(await t.ownerToken()))[0]).toBe(200);
    expect(t.accessFetcher).toHaveBeenCalledTimes(4);
  });

  it("fails closed when the keys cannot be fetched, and skips unusable published keys", async () => {
    const t = await setup();
    t.accessFetcher.mockImplementationOnce(async () => new Response(null, { status: 302, headers: { location: "https://elsewhere.example/certs" } }));
    expect(await t.users(await t.ownerToken())).toEqual([401, { error: "auth_required" }]);
    t.accessFetcher.mockImplementationOnce(async () => { throw new TypeError("network"); });
    expect(await t.users(await t.ownerToken())).toEqual([401, { error: "auth_required" }]);
    t.accessFetcher.mockImplementationOnce(async () => new Response("not json", { status: 200 }));
    expect(await t.users(await t.ownerToken())).toEqual([401, { error: "auth_required" }]);
    // A broken key, a key for another algorithm or for encryption, and the real one.
    t.accessFetcher.mockImplementationOnce(async () => Response.json({ keys: [
      null, { kid: "broken", kty: "RSA", n: "!!", e: "AQAB" }, { ...t.key.jwk, alg: "RS512" }, { ...t.key.jwk, use: "enc" },
      { kid: "ec", kty: "EC", crv: "P-256", x: "x", y: "y" }, t.key.jwk,
    ] }));
    expect((await t.users(await t.ownerToken()))[0]).toBe(200);
  });

  it("keeps each team's keys apart, so a key cached for one team never verifies another team's token", async () => {
    const t = await setup();
    expect((await t.users(await t.ownerToken()))[0]).toBe(200);
    const otherTeam = "other-team.cloudflareaccess.com";
    const otherKey = await keyPair("key-1");
    t.published[`https://${otherTeam}`] = [otherKey];
    t.setEnv({ ...BASE_ENV, ACCESS_TEAM_DOMAIN: otherTeam });
    // Signed with the first team's key under the same kid, claiming the second team.
    expect(await t.users(await t.ownerToken({ iss: `https://${otherTeam}` }))).toEqual([401, { error: "auth_required" }]);
    expect(t.certs.at(-1)?.url).toBe(`https://${otherTeam}/cdn-cgi/access/certs`);
    expect((await t.users(await sign(otherKey, t.claims({ iss: `https://${otherTeam}` }))))[0]).toBe(200);
  });
});

describe("admin routes under Access", () => {
  it("refuses the workers.dev host even with the owner's valid token, before fetching any key", async () => {
    const t = await setup();
    const token = await t.ownerToken();
    for (const [method, path] of [["GET", "/admin"], ["GET", "/v1/admin/users"], ["GET", "/v1/admin/approve?t=x"], ["POST", "/v1/admin/users"]]) {
      expect([path, (await t.send(method, path, { token, origin: WORKERS_DEV, body: method === "POST" ? { email: USER, action: "allow" } : undefined })).status])
        .toEqual([path, 404]);
    }
    const invite = await t.call(new Request(`${WORKERS_DEV}/v1/admin/invitations`, {
      method: "POST", headers: { authorization: `Bearer ${ADMIN_TOKEN}`, "cf-access-jwt-assertion": token },
    }));
    expect(invite.status).toBe(404);
    expect(t.accessFetcher).not.toHaveBeenCalled();
    expect(await t.auth.user(USER)).toBeNull();
  });

  it("answers 404 on every e-mail code session route and ignores an earlier admin session cookie", async () => {
    const t = await setup(NO_ACCESS);
    // An admin session from before Access was configured.
    expect((await t.send("POST", "/v1/admin/session/code", { body: { email: OWNER } })).status).toBe(200);
    const verified = await t.send("POST", "/v1/admin/session/verify", { body: { email: OWNER, code: t.mailer.code(OWNER) } });
    expect(verified.status).toBe(204);
    const cookie = verified.headers.get("set-cookie")!.split(";")[0];
    t.setEnv(BASE_ENV);
    t.mailer.sent = [];
    const token = await t.ownerToken();
    for (const path of ["/v1/admin/session/code", "/v1/admin/session/verify", "/v1/admin/session/logout", "/v1/admin/session/other"]) {
      for (const method of ["GET", "POST"]) {
        const response = await t.send(method, path, { token, body: method === "POST" ? { email: OWNER, code: "000000" } : undefined });
        expect([path, method, response.status, await response.json()]).toEqual([path, method, 404, { error: "not_found" }]);
      }
      // Without a token the gate answers first.
      expect((await t.send("POST", path, { body: { email: OWNER } })).status).toBe(401);
    }
    expect(t.mailer.sent).toEqual([]);
    const withCookie = await t.send("GET", "/v1/admin/users", { headers: { cookie } });
    expect([withCookie.status, await withCookie.json()]).toEqual([401, { error: "auth_required" }]);
    const change = await t.send("POST", "/v1/admin/users", { headers: { cookie }, body: { email: USER, action: "allow" } });
    expect(change.status).toBe(401);
    expect(await t.auth.user(USER)).toBeNull();
  });

  it("checks every method and keeps the same-origin rule for changes", async () => {
    const t = await setup();
    for (const method of ["GET", "HEAD", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]) {
      for (const path of ["/admin", "/v1/admin/users", "/v1/admin/approve", "/v1/admin/unknown"]) {
        const response = await t.send(method, path);
        expect([method, path, response.status]).toEqual([method, path, path === "/admin" || path === "/v1/admin/approve" ? 403 : 401]);
      }
    }
    const crossSite = await t.call(new Request(`${ORIGIN}/v1/admin/users`, {
      method: "POST", body: JSON.stringify({ email: USER, action: "allow" }),
      headers: { "content-type": "application/json", origin: "https://attacker.example", "cf-access-jwt-assertion": await t.ownerToken() },
    }));
    expect(crossSite.status).toBe(403);
    expect(await t.auth.user(USER)).toBeNull();
  });

  it("requires the owner's token, besides ADMIN_TOKEN, for the legacy invitation route", async () => {
    const t = await setup();
    const invite = (headers: Record<string, string>, method = "POST") =>
      t.call(new Request(`${ORIGIN}/v1/admin/invitations`, { method, headers }));
    const missing = await invite({ authorization: `Bearer ${ADMIN_TOKEN}` });
    expect([missing.status, await missing.json()]).toEqual([401, { code: "unauthorized" }]);
    expect((await invite({ authorization: `Bearer ${ADMIN_TOKEN}`, "cf-access-jwt-assertion": await t.ownerToken({ email: USER }) })).status).toBe(401);
    expect((await invite({ authorization: `Bearer ${ADMIN_TOKEN}`, "cf-access-jwt-assertion": await t.ownerToken({ exp: t.seconds() - 120 }) })).status).toBe(401);
    expect((await invite({ authorization: "Bearer wrong-admin-token-000000", "cf-access-jwt-assertion": await t.ownerToken() })).status).toBe(401);
    expect((await invite({ "cf-access-jwt-assertion": await t.ownerToken() }, "GET")).status).toBe(405);
    expect((await invite({ "cf-access-jwt-assertion": await t.ownerToken({ email: "OWNER@example.org" }), authorization: `Bearer ${ADMIN_TOKEN}` })).status).toBe(201);
    expect(await t.db.prepare("SELECT COUNT(*) AS n FROM invitations").first()).toEqual({ n: 1 });
  });

  it("opens and submits the e-mailed approval link only with the owner's token", async () => {
    const t = await setup();
    const requested = await (await t.send("POST", "/v1/auth/code", { body: { email: USER }, origin: WORKERS_DEV })).json() as { state: string; request_token: string };
    expect(requested.state).toBe("pending_approval");
    const link = new URL(t.mailer.link());
    // The link points to ADMIN_ORIGIN, which the Access application covers.
    expect(link.origin).toBe(ORIGIN);
    const open = (token?: string) => t.call(new Request(link, { headers: token === undefined ? {} : { "cf-access-jwt-assertion": token } }));
    const submit = (token?: string) => t.call(new Request(`${ORIGIN}/v1/admin/approve`, {
      method: "POST", body: new URLSearchParams({ t: link.searchParams.get("t")! }).toString(),
      headers: { "content-type": "application/x-www-form-urlencoded", ...(token === undefined ? {} : { "cf-access-jwt-assertion": token }) },
    }));
    const state = async () => (await (await t.send("POST", "/v1/auth/request", { body: { request_token: requested.request_token } })).json() as { state: string }).state;
    // A signed link alone, or with another person's token, neither opens nor approves.
    for (const token of [undefined, await t.ownerToken({ email: USER })]) {
      const page = await open(token);
      expect(page.status).toBe(403);
      expect(await page.text()).not.toContain(USER);
      expect((await submit(token)).status).toBe(403);
    }
    expect(await state()).toBe("pending_approval");
    const page = await open(await t.ownerToken());
    expect(page.status).toBe(200);
    expect(await page.text()).toContain("承認する");
    const approved = await submit(await t.ownerToken());
    expect(approved.status).toBe(200);
    expect(await approved.text()).toContain("承認しました");
    expect(await state()).toBe("allowed");
    // Still single-use.
    expect((await submit(await t.ownerToken())).status).toBe(400);
  });
});

describe("without Access", () => {
  it("keeps the e-mail code login exactly as before and never reads an Access header", async () => {
    for (const env of [NO_ACCESS, { ...NO_ACCESS, ACCESS_TEAM_DOMAIN: undefined, ACCESS_AUD: undefined }, { ...NO_ACCESS, ADMIN_ORIGIN: "" }]) {
      const t = await setup(env);
      const token = await t.ownerToken();
      const page = await t.send("GET", "/admin", { token });
      expect(page.status).toBe(200);
      expect(await page.text()).toContain("const ACCESS = false;");
      // A valid Access token is not a credential when Access is not configured.
      expect(await t.users(token)).toEqual([401, { error: "auth_required" }]);
      expect((await t.send("POST", "/v1/admin/session/code", { body: { email: OWNER } })).status).toBe(200);
      const verified = await t.send("POST", "/v1/admin/session/verify", { body: { email: OWNER, code: t.mailer.code(OWNER) } });
      expect(verified.status).toBe(204);
      const cookie = verified.headers.get("set-cookie")!.split(";")[0];
      expect((await t.send("GET", "/v1/admin/users", { headers: { cookie } })).status).toBe(200);
      expect((await t.send("POST", "/v1/admin/session/logout", { headers: { cookie }, body: {} })).status).toBe(204);
      expect((await t.send("GET", "/v1/admin/users", { headers: { cookie } })).status).toBe(401);
      const invite = await t.call(new Request(`${ORIGIN}/v1/admin/invitations`, { method: "POST", headers: { authorization: `Bearer ${ADMIN_TOKEN}` } }));
      expect(invite.status).toBe(201);
      expect(t.accessFetcher).not.toHaveBeenCalled();
    }
  });
});
