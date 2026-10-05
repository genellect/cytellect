import { describe, expect, it, vi } from "vitest";
import { handle, readConfig, type Env } from "./index";
import { hasDraftShape } from "./openai";
import { MemoryStore } from "./store";

const DRAFT = {
  recipe: "nuclear-intensity",
  channels: [{ token: "dapi", stain: "DAPI", role: "nuclear", reason: "核染色" }],
  metrics: [{ metric: "area", channel: null }],
  statistics: { kind: "descriptive", test: null, omnibus: null, association: null },
  figures: [{ kind: "field-distribution", metric: "area", channel: null }],
  missing_information: [],
  reference_ids: ["senft-2023"],
  rationale: "核面積の分布を視野ごとに示す。",
};
const CONTEXT = { protocol: "1.0.0", goal: "核面積", channels: [{ token: "dapi", stain: "DAPI", role: "nuclear" }], field_count: 2 };

const ENV: Env = {
  DB: undefined as never, OPENAI_API_KEY: "sk-test", OPENAI_MODEL: "test-model", ADMIN_TOKEN: "admin-token-0123456789abcdef",
  MONTHLY_BUDGET_USD: "1", DEVICE_MONTHLY_REQUESTS: "3", PRICE_INPUT_USD_PER_MTOK: "1", PRICE_OUTPUT_USD_PER_MTOK: "4",
};

function modelReply(text: string, usage = { input_tokens: 1000, output_tokens: 200 }) {
  return new Response(JSON.stringify({ output: [{ type: "message", content: [{ type: "output_text", text }] }], usage }), { status: 200 });
}

function post(path: string, body: unknown, token?: string) {
  return new Request(`https://proposal.example${path}`, {
    method: "POST", body: JSON.stringify(body), headers: token ? { authorization: `Bearer ${token}` } : {},
  });
}

async function device(store: MemoryStore, env = ENV) {
  const invited = await handle(post("/v1/admin/invitations", {}, env.ADMIN_TOKEN), env, store);
  const { invitation } = await invited.json() as { invitation: string };
  const redeemed = await handle(post("/v1/devices", { invitation }), env, store);
  expect(redeemed.status).toBe(201);
  // One-use invitation.
  expect((await handle(post("/v1/devices", { invitation }), env, store)).status).toBe(403);
  return (await redeemed.json() as { device_token: string }).device_token;
}

describe("proposal service", () => {
  it("returns a draft with store:false, the strict schema and no stored content", async () => {
    const store = new MemoryStore();
    const token = await device(store);
    const fetcher = vi.fn(async () => modelReply(JSON.stringify(DRAFT)));
    const log = vi.spyOn(console, "log");
    const response = await handle(post("/v1/proposals", { context: CONTEXT }, token), ENV, store, { fetcher });
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ draft: DRAFT, model: "test-model", prompt_version: "2026-10-05.1" });
    const sent = JSON.parse((fetcher.mock.calls[0] as unknown as [string, RequestInit])[1].body as string);
    expect(sent.store).toBe(false);
    expect(sent.text.format).toMatchObject({ type: "json_schema", strict: true, name: "cytellect_proposal" });
    expect(sent.input[1].content[0].text).toContain("核面積");
    expect([...store.spent.values()]).toEqual([(1000 * 1 + 200 * 4) / 1e6]);
    expect(store.reservations.size).toBe(0);
    expect(log).not.toHaveBeenCalled();
    expect(JSON.stringify([...store.invitations, ...store.devices, ...store.requests])).not.toContain("核面積");
  });

  it("is disabled without a complete operator configuration and rejects unknown devices", async () => {
    expect(readConfig({ ...ENV, MONTHLY_BUDGET_USD: "" })).toBeNull();
    expect(readConfig({ ...ENV, OPENAI_API_KEY: undefined })).toBeNull();
    const store = new MemoryStore();
    const token = await device(store);
    const fetcher = vi.fn();
    expect((await handle(post("/v1/proposals", { context: CONTEXT }, token), { ...ENV, PRICE_OUTPUT_USD_PER_MTOK: "0" }, store, { fetcher })).status).toBe(503);
    expect((await handle(post("/v1/proposals", { context: CONTEXT }, "x".repeat(43)), ENV, store, { fetcher })).status).toBe(401);
    expect((await handle(post("/v1/admin/invitations", {}, "wrong-admin-token-000000"), ENV, store)).status).toBe(401);
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("enforces the per-device quota and the monthly budget before calling the model", async () => {
    const store = new MemoryStore();
    const token = await device(store);
    const fetcher = vi.fn(async () => modelReply(JSON.stringify(DRAFT)));
    for (let index = 0; index < 3; index += 1) {
      expect((await handle(post("/v1/proposals", { context: CONTEXT }, token), ENV, store, { fetcher })).status).toBe(200);
    }
    const over = await handle(post("/v1/proposals", { context: CONTEXT }, token), ENV, store, { fetcher });
    expect([over.status, (await over.json() as { code: string }).code]).toEqual([429, "device_quota_exhausted"]);
    const tight = { ...ENV, MONTHLY_BUDGET_USD: "0.0001" };
    const second = await device(store, tight);
    const budget = await handle(post("/v1/proposals", { context: CONTEXT }, second), tight, store, { fetcher });
    expect([budget.status, (await budget.json() as { code: string }).code]).toEqual([429, "monthly_budget_exhausted"]);
    expect(fetcher).toHaveBeenCalledTimes(3);
  });

  it("concurrent reservations cannot together exceed the budget, and unsettled ones keep counting", async () => {
    const store = new MemoryStore();
    expect(await store.reserve("a", "2026-10", 0.6, 1, 0)).toBe(true);
    expect(await store.reserve("b", "2026-10", 0.6, 1, 1)).toBe(false);
    // A crashed request never settles; its possible cost still holds budget hours later.
    expect(await store.reserve("c", "2026-10", 0.6, 1, 86_400_000)).toBe(false);
    expect(await store.unsettled("2026-10")).toBeCloseTo(0.6);
  });

  it("repairs unusable output at most once and settles the reservation on failure", async () => {
    const store = new MemoryStore();
    const token = await device(store);
    const fetcher = vi.fn(async () => modelReply("{\"recipe\": \"none\"}"));
    const response = await handle(post("/v1/proposals", { context: CONTEXT }, token), ENV, store, { fetcher });
    expect([response.status, (await response.json() as { code: string }).code]).toEqual([502, "model_output_invalid"]);
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(store.reservations.size).toBe(0);
    expect([...store.spent.values()][0]).toBeGreaterThan(0);
    const refusal = vi.fn(async () => new Response(JSON.stringify({ output: [{ type: "message", content: [{ type: "refusal", refusal: "no" }] }] })));
    const refused = await handle(post("/v1/proposals", { context: CONTEXT }, token), ENV, store, { fetcher: refusal });
    expect([refused.status, refusal.mock.calls.length]).toEqual([502, 1]);
  });

  it("rejects oversize goals, extra fields and non-PNG previews before any call", async () => {
    const store = new MemoryStore();
    const token = await device(store);
    const fetcher = vi.fn();
    const cases = [
      { context: { ...CONTEXT, goal: "x".repeat(2001) } },
      { context: CONTEXT, path: "C:/private/a.tif" },
      { context: CONTEXT, previews: [{ channel: "dapi", png_base64: "/9j/4AAQSkZJRg==" }] },
      { context: CONTEXT, previews: Array.from({ length: 7 }, () => ({ channel: "dapi", png_base64: "iVBORw0KGgo=" })) },
    ];
    for (const body of cases) expect((await handle(post("/v1/proposals", body, token), ENV, store, { fetcher })).status).toBe(400);
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("checks the draft's top-level keys against the shared contract", () => {
    expect(hasDraftShape(DRAFT)).toBe(true);
    expect(hasDraftShape({ ...DRAFT, code: "run()" })).toBe(false);
    expect(hasDraftShape([])).toBe(false);
  });
});
