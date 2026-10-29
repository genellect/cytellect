/** Small helpers shared by the proposal relay and the cloud-access routes. */
import { boundedJson } from "./schema";

export function json(status: number, body: unknown, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status, headers: { "content-type": "application/json", "cache-control": "no-store", ...headers },
  });
}

export async function sha256(text: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return hex(new Uint8Array(digest));
}

const hex = (bytes: Uint8Array) => [...bytes].map((byte) => byte.toString(16).padStart(2, "0")).join("");

export function base64url(bytes: Uint8Array): string {
  return btoa(String.fromCharCode(...bytes)).replaceAll("+", "-").replaceAll("/", "_").replace(/=+$/, "");
}

export function fromBase64url(text: string): Uint8Array | null {
  if (!/^[A-Za-z0-9_-]*$/.test(text)) return null;
  try {
    return Uint8Array.from(atob(text.replaceAll("-", "+").replaceAll("_", "/")), (c) => c.charCodeAt(0));
  } catch { return null; }
}

/** 256-bit random URL-safe token. */
export function token(): string {
  return base64url(crypto.getRandomValues(new Uint8Array(32)));
}

export function bearer(request: Request): string | null {
  const match = /^Bearer ([A-Za-z0-9_-]{20,200})$/.exec(request.headers.get("authorization") ?? "");
  return match ? match[1] : null;
}

/** Constant-time comparison of equal-length strings. */
export function equal(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let difference = 0;
  for (let index = 0; index < a.length; index += 1) difference |= a.charCodeAt(index) ^ b.charCodeAt(index);
  return difference === 0;
}

/** HMAC-SHA256 with domain separation; hex output. */
export async function hmac(key: string, domain: string, message: string): Promise<string> {
  const imported = await crypto.subtle.importKey("raw", new TextEncoder().encode(key), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const signature = await crypto.subtle.sign("HMAC", imported, new TextEncoder().encode(`${domain}\u0000${message}`));
  return hex(new Uint8Array(signature));
}

/** JSON object body bounded in bytes, or null. */
export async function readObject(request: Request, limit: number): Promise<Record<string, unknown> | null> {
  const length = Number(request.headers.get("content-length") ?? "0");
  if (length > limit) return null;
  try {
    const value = await boundedJson(request.body, limit);
    return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : null;
  } catch {
    return null;
  }
}

export const month = (now: number) => new Date(now).toISOString().slice(0, 7);

/** First instant of the next UTC calendar month, when monthly usage resets. */
export function nextMonth(now: number): string {
  const date = new Date(now);
  return new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth() + 1, 1)).toISOString();
}

export function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;" })[c]!);
}
