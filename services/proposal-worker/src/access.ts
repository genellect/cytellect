/**
 * Owner sign-in through Cloudflare Access. When ACCESS_TEAM_DOMAIN and ACCESS_AUD are set,
 * the admin page and every /v1/admin/* route accept only a request whose
 * Cf-Access-Jwt-Assertion header is a valid Access token for this application and the
 * owner's address. The Worker verifies the token itself (RS256 signature against the
 * team's published keys, issuer, audience, expiry), so a request that reaches the Worker
 * by another route, such as workers.dev, cannot pass without one.
 */

export interface AccessEnv {
  /** The Access team domain, "<team>.cloudflareaccess.com". */
  ACCESS_TEAM_DOMAIN?: string;
  /** The Application Audience (AUD) tag of the Access application for the admin page. */
  ACCESS_AUD?: string;
}

export interface AccessConfig { issuer: string; audience: string }

/** Undefined when Access is not configured, null when only half set or malformed. */
export function accessConfig(env: AccessEnv): AccessConfig | null | undefined {
  // "https://" and a trailing slash, as copied from the dashboard, are tolerated.
  const team = (env.ACCESS_TEAM_DOMAIN?.trim().toLowerCase() ?? "").replace(/^https:\/\//, "").replace(/\/$/, "");
  const audience = env.ACCESS_AUD?.trim() ?? "";
  if (!team && !audience) return undefined;
  if (!/^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.cloudflareaccess\.com$/.test(team) || !/^[A-Za-z0-9]{16,128}$/.test(audience)) return null;
  return { issuer: `https://${team}`, audience };
}

interface Jwk { kid?: unknown; kty?: unknown; alg?: unknown; use?: unknown; n?: unknown; e?: unknown }

const CERTS_TTL_MS = 10 * 60 * 1000;
/** An unknown key id refetches the keys at most this often, so forged ids cannot drive fetches. */
const REFRESH_MIN_MS = 30 * 1000;
/** Allowed clock difference with Cloudflare, in seconds. */
const SKEW_SECONDS = 60;
/** Access tokens are about 1 KB; anything far larger is refused before parsing. */
const MAX_TOKEN_CHARS = 8192;
const MAX_KEYS = 16;
/** Keyed by issuer: keys of one team are never used for another. */
const keyCache = new Map<string, { keys: Map<string, CryptoKey>; fetched: number }>();

function decodeSegment(value: string): Uint8Array | null {
  if (!/^[A-Za-z0-9_-]*$/.test(value)) return null;
  try {
    const padded = value.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - (value.length % 4)) % 4);
    return Uint8Array.from(atob(padded), (char) => char.charCodeAt(0));
  } catch {
    return null;
  }
}

function decodeJson(value: string): Record<string, unknown> | null {
  const bytes = decodeSegment(value);
  if (!bytes) return null;
  try {
    const parsed: unknown = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed as Record<string, unknown> : null;
  } catch {
    return null;
  }
}

async function fetchKeys(config: AccessConfig, fetcher: typeof fetch, now: number) {
  // Workers accept only "follow" or "manual" (not "error"): a redirect is a non-200 answer here.
  const response = await fetcher(`${config.issuer}/cdn-cgi/access/certs`, { redirect: "manual" });
  if (response.status !== 200) {
    await response.body?.cancel().catch(() => undefined);
    throw new Error("access_certs_unavailable");
  }
  const body = await response.json() as { keys?: unknown };
  const keys = new Map<string, CryptoKey>();
  for (const jwk of (Array.isArray(body?.keys) ? body.keys as (Jwk | null)[] : []).slice(0, MAX_KEYS)) {
    if (!jwk || jwk.kty !== "RSA" || typeof jwk.kid !== "string" || typeof jwk.n !== "string" || typeof jwk.e !== "string") continue;
    if ((jwk.alg !== undefined && jwk.alg !== "RS256") || (jwk.use !== undefined && jwk.use !== "sig")) continue;
    try {
      keys.set(jwk.kid, await crypto.subtle.importKey("jwk", { kty: "RSA", n: jwk.n, e: jwk.e, alg: "RS256", ext: true },
        { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["verify"]));
    } catch {
      // One unusable key does not discard the others.
    }
  }
  keyCache.set(config.issuer, { keys, fetched: now });
  return keys;
}

/** The team's key for kid: cached for 10 minutes, refetched once when the id is unknown (a rotation). */
async function teamKey(config: AccessConfig, kid: string, fetcher: typeof fetch, now: number) {
  const cached = keyCache.get(config.issuer);
  let keys = cached && now - cached.fetched < CERTS_TTL_MS ? cached.keys : await fetchKeys(config, fetcher, now);
  if (!keys.has(kid) && now - (keyCache.get(config.issuer)?.fetched ?? 0) >= REFRESH_MIN_MS) keys = await fetchKeys(config, fetcher, now);
  return keys.get(kid) ?? null;
}

/**
 * Returns the e-mail claim of the request's Access token once its signature, issuer,
 * audience and validity period are verified; null when the token is missing, malformed,
 * signed by an unknown key, not valid for this application now, or carries no e-mail
 * (a service token). The caller compares the address with the owner's.
 */
export async function accessEmail(request: Request, config: AccessConfig, fetcher: typeof fetch, now: number): Promise<string | null> {
  const token = request.headers.get("cf-access-jwt-assertion") ?? "";
  if (!token || token.length > MAX_TOKEN_CHARS) return null;
  const parts = token.split(".");
  if (parts.length !== 3) return null;
  const header = decodeJson(parts[0]), claims = decodeJson(parts[1]), signature = decodeSegment(parts[2]);
  // Only RS256: "none", HMAC or any other algorithm named by the token is never honoured.
  if (!header || !claims || !signature || header.alg !== "RS256" || typeof header.kid !== "string" || !header.kid) return null;
  let key: CryptoKey | null;
  try {
    key = await teamKey(config, header.kid, fetcher, now);
  } catch {
    return null;
  }
  if (!key) return null;
  const signed = new TextEncoder().encode(`${parts[0]}.${parts[1]}`);
  if (!(await crypto.subtle.verify("RSASSA-PKCS1-v1_5", key, signature as Uint8Array<ArrayBuffer>, signed))) return null;
  const seconds = Math.floor(now / 1000);
  const audiences = Array.isArray(claims.aud) ? claims.aud : [claims.aud];
  if (claims.iss !== config.issuer || !audiences.includes(config.audience)) return null;
  if (typeof claims.exp !== "number" || claims.exp + SKEW_SECONDS <= seconds) return null;
  if (claims.nbf !== undefined && (typeof claims.nbf !== "number" || claims.nbf - SKEW_SECONDS > seconds)) return null;
  return typeof claims.email === "string" ? claims.email : null;
}

/** For tests: forget the cached keys. */
export function clearAccessKeyCache() {
  keyCache.clear();
}
