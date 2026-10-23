import { describe, expect, it, vi } from "vitest";
import { handle, readCellposeConfig, type Env } from "./index";
import { MemoryStore } from "./store";

const ADMIN = "admin-token-0123456789abcdef";
const UPSTREAM_TOKEN = "wk-upstream0123456789.ws-upstream0123456789";
const ENV: Env = {
  DB: undefined as never, ADMIN_TOKEN: ADMIN,
  CELLPOSE_UPSTREAM_URL: "https://gpu.example", CELLPOSE_UPSTREAM_TOKEN: UPSTREAM_TOKEN,
  DEVICE_MONTHLY_CELLPOSE_FIELDS: "2", MONTHLY_CELLPOSE_FIELDS: "3",
};
const FIELD = new Uint8Array([80, 75, 3, 4, 1, 2, 3]);

function post(path: string, body: unknown, token?: string, headers: Record<string, string> = {}) {
  return new Request(`https://access.example${path}`, {
    method: "POST", body: body instanceof Uint8Array ? body as unknown as BodyInit : JSON.stringify(body),
    headers: { ...(token ? { authorization: `Bearer ${token}` } : {}), ...headers },
  });
}

const field = (token: string) => post("/v1/cellpose", FIELD, token, { "content-length": String(FIELD.length) });

async function enrol(store: MemoryStore, label = "") {
  const issued = await handle(post(`/v1/admin/invitations?hours=1${label ? `&label=${encodeURIComponent(label)}` : ""}`, {}, ADMIN), ENV, store);
  expect(issued.status).toBe(201);
  const { invitation } = await issued.json() as { invitation: string };
  const redeemed = await handle(post("/v1/devices", { invitation }), ENV, store);
  expect(redeemed.status).toBe(201);
  return await redeemed.json() as { device_token: string; device_id: string };
}

describe("access codes", () => {
  it("lists labelled devices for the operator without tokens, and revokes one device at a time", async () => {
    const store = new MemoryStore();
    const first = await enrol(store, "研究室PC-1"), second = await enrol(store);
    expect(first.device_id).toMatch(/^[0-9a-f]{16}$/);
    expect((await handle(post("/v1/admin/devices", {}), ENV, store)).status).toBe(401);
    const listed = await (await handle(post("/v1/admin/devices", {}, ADMIN), ENV, store)).json() as { devices: Record<string, unknown>[] };
    expect(listed.devices.map((device) => device.label)).toEqual(["研究室PC-1", null]);
    expect(JSON.stringify(listed)).not.toContain(first.device_token);
    const revoked = await handle(post("/v1/admin/devices/revoke", { id: first.device_id }, ADMIN), ENV, store);
    expect(revoked.status).toBe(200);
    expect((await handle(post("/v1/status", {}, first.device_token), ENV, store)).status).toBe(401);
    expect((await handle(field(first.device_token), ENV, store)).status).toBe(401);
    expect((await handle(post("/v1/status", {}, second.device_token), ENV, store)).status).toBe(200);
    expect((await handle(post("/v1/admin/devices/revoke", { id: first.device_id }, ADMIN), ENV, store)).status).toBe(404);
  });

  it("rejects control characters and long labels", async () => {
    const store = new MemoryStore();
    for (const label of ["a\nb", "x".repeat(61)]) {
      const response = await handle(post(`/v1/admin/invitations?label=${encodeURIComponent(label)}`, {}, ADMIN), ENV, store);
      expect(response.status).toBe(400);
    }
  });

  it("reports which paid features this device can use and its monthly use", async () => {
    const store = new MemoryStore(), { device_token } = await enrol(store, "PC");
    const status = await (await handle(post("/v1/status", {}, device_token), ENV, store)).json();
    expect(status).toMatchObject({ label: "PC", proposals: { enabled: false, used: 0, limit: 0 },
      cellpose: { enabled: true, used: 0, limit: 2 } });
  });
});

describe("Cellpose relay", () => {
  it("forwards the unchanged field with the operator's GPU token and counts it only on success", async () => {
    const store = new MemoryStore(), { device_token } = await enrol(store);
    const fetcher = vi.fn(async (_url: string, init: RequestInit) => {
      expect(new Uint8Array(await new Response(init.body).arrayBuffer())).toEqual(FIELD);
      return new Response(new Uint8Array([9, 9]), { status: 200, headers: { "set-cookie": "private" } });
    });
    const response = await handle(field(device_token), ENV, store, { fetcher: fetcher as unknown as typeof fetch });
    expect(response.status).toBe(200);
    expect(new Uint8Array(await response.arrayBuffer())).toEqual(new Uint8Array([9, 9]));
    expect(response.headers.get("set-cookie")).toBeNull();
    const [url, init] = fetcher.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("https://gpu.example/v1/cellpose");
    const headers = new Headers(init.headers);
    expect(headers.get("authorization")).toBe(`Bearer ${UPSTREAM_TOKEN}`);
    expect(JSON.stringify([...headers])).not.toContain(device_token);
    const status = await (await handle(post("/v1/status", {}, device_token), ENV, store)).json() as { cellpose: { used: number } };
    expect(status.cellpose.used).toBe(1);
  });

  it("returns the field when the GPU is starting and keeps transient statuses retryable", async () => {
    const store = new MemoryStore(), { device_token } = await enrol(store);
    const starting = vi.fn(async () => new Response("<html>starting</html>", { status: 503 }));
    const response = await handle(field(device_token), ENV, store, { fetcher: starting as unknown as typeof fetch });
    expect(response.status).toBe(503);
    expect(await response.json()).toEqual({ error: "cellpose_remote_unavailable" });
    const status = await (await handle(post("/v1/status", {}, device_token), ENV, store)).json() as { cellpose: { used: number } };
    expect(status.cellpose.used).toBe(0);
  });

  it("passes the service's own error codes and hides upstream authentication failures", async () => {
    const store = new MemoryStore(), { device_token } = await enrol(store);
    const invalid = vi.fn(async () => Response.json({ error: "cellpose_remote_input_invalid" }, { status: 400 }));
    const rejected = await handle(field(device_token), ENV, store, { fetcher: invalid as unknown as typeof fetch });
    expect([rejected.status, await rejected.json()]).toEqual([400, { error: "cellpose_remote_input_invalid" }]);
    const unauthorized = vi.fn(async () => new Response("modal-auth-detail", { status: 401 }));
    const hidden = await handle(field(device_token), ENV, store, { fetcher: unauthorized as unknown as typeof fetch });
    expect([hidden.status, await hidden.json()]).toEqual([500, { error: "cellpose_service_unavailable" }]);
  });

  it("enforces per-device and service-wide monthly field limits", async () => {
    const store = new MemoryStore(), a = await enrol(store), b = await enrol(store);
    const ok = vi.fn(async () => new Response(new Uint8Array([1]), { status: 200 })) as unknown as typeof fetch;
    for (const token of [a.device_token, a.device_token, b.device_token]) {
      expect((await handle(field(token), ENV, store, { fetcher: ok })).status).toBe(200);
    }
    const device = await handle(field(a.device_token), ENV, store, { fetcher: ok });
    expect([device.status, await device.json()]).toEqual([429, { error: "cellpose_quota_exhausted" }]);
    expect((await handle(field(b.device_token), ENV, store, { fetcher: ok })).status).toBe(429);
  });

  it("is disabled, not transiently unavailable, until the operator configures it", async () => {
    const store = new MemoryStore(), { device_token } = await enrol(store);
    for (const missing of ["CELLPOSE_UPSTREAM_TOKEN", "DEVICE_MONTHLY_CELLPOSE_FIELDS", "MONTHLY_CELLPOSE_FIELDS"] as const) {
      const env = { ...ENV, [missing]: "" };
      expect(readCellposeConfig(env)).toBeNull();
      const response = await handle(field(device_token), env, store);
      expect([response.status, await response.json()]).toEqual([409, { error: "cellpose_service_disabled" }]);
    }
    expect(readCellposeConfig({ ...ENV, CELLPOSE_UPSTREAM_URL: "http://gpu.example" })).toBeNull();
    expect((await handle(field("x".repeat(43)), ENV, store)).status).toBe(401);
  });

  it("requires a declared body size within the service limit", async () => {
    const store = new MemoryStore(), { device_token } = await enrol(store);
    const big = post("/v1/cellpose", FIELD, device_token, { "content-length": String(256 * 1024 * 1024 + 1) });
    expect((await handle(big, ENV, store)).status).toBe(413);
  });
});

describe("rate limiting", () => {
  it("refuses a client address over the configured rate before any other work", async () => {
    const limit = vi.fn(async () => ({ success: false }));
    const response = await handle(post("/v1/devices", { invitation: "x".repeat(30) }, undefined, { "cf-connecting-ip": "192.0.2.1" }),
      { ...ENV, LIMITER: { limit } }, new MemoryStore());
    expect(response.status).toBe(429);
    expect(limit).toHaveBeenCalledWith({ key: "192.0.2.1" });
  });
});
