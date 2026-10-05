import { describe, expect, it, vi } from "vitest";
import { checkRequest, handle, readConfig, worstCaseUsd, type Env } from "./index";
import { hasDraftShape } from "./openai";
import { MemoryStore } from "./store";

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

const ENV: Env = {
  DB: undefined as never, OPENAI_API_KEY: "sk-test", OPENAI_MODEL: "gpt-6.1-sol", ADMIN_TOKEN: "admin-token-0123456789abcdef",
  MONTHLY_BUDGET_USD: "1", DEVICE_MONTHLY_REQUESTS: "3", PRICE_INPUT_USD_PER_MTOK: "2", PRICE_OUTPUT_USD_PER_MTOK: "10", PRICE_CACHED_INPUT_USD_PER_MTOK: "0.10", PRICE_CACHE_WRITE_USD_PER_MTOK: "2.50",
};

function modelReply(text: string, usage = { input_tokens: 1000, output_tokens: 200 }) {
  return new Response(JSON.stringify({ status: "completed", output: [{ type: "message", content: [{ type: "output_text", text }] }], usage }), { status: 200 });
}

function post(path: string, body: unknown, token?: string) {
  return new Request(`https://proposal.example${path}`, {
    method: "POST", body: JSON.stringify(body), headers: { "idempotency-key": crypto.randomUUID(), ...(token ? { authorization: `Bearer ${token}` } : {}) },
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
    expect(await response.json()).toEqual({ draft: DRAFT, model: "gpt-6.1-sol", prompt_version: "2026-10-05.2" });
    const sent = JSON.parse((fetcher.mock.calls[0] as unknown as [string, RequestInit])[1].body as string);
    expect(sent.store).toBe(false);
    expect(sent.reasoning).toEqual({ effort: "medium" });
    expect(sent.service_tier).toBe("default");
    expect(sent.text.format).toMatchObject({ type: "json_schema", strict: true, name: "cytellect_proposal" });
    expect(sent.input[1].content[0].text).toContain("核面積");
    expect([...store.spent.values()]).toEqual([(1000 * 2.5 + 200 * 10) / 1e6]);
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
    const refusal = vi.fn(async () => new Response(JSON.stringify({ status: "completed", output: [{ type: "message", content: [{ type: "refusal", refusal: "no" }] }] })));
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
    expect(hasDraftShape({ ...DRAFT, metrics: [{ metric: "invented", channel: null, region: null }] })).toBe(false);
  });

  it("refuses unknown models, underpriced or unreviewed reasoning settings and unbounded output", () => {
    expect(readConfig(ENV)?.maxOutputTokens).toBe(8000);
    for (const changed of [
      { OPENAI_MODEL: "another-model" }, { PRICE_INPUT_USD_PER_MTOK: "1" }, { PRICE_CACHE_WRITE_USD_PER_MTOK: "2" },
      { REASONING_EFFORT: "low" }, { REASONING_EFFORT: "high" }, { MAX_OUTPUT_TOKENS: "0" }, { MAX_OUTPUT_TOKENS: "16001" }, { DEVICE_MONTHLY_REQUESTS: "0.1" },
    ]) expect(readConfig({ ...ENV, ...changed })).toBeNull();
    expect(readConfig({ ...ENV, REASONING_EFFORT: "low", LOW_EFFORT_EVALUATED: "true" })?.reasoningEffort).toBe("low");
  });

  it("rejects unregistered context fields, malformed scalar values and duplicate channels", () => {
    for (const extra of [
      { secret: "unregistered" }, { goal: { text: "nested" } }, { field_count: 1.5 }, { condition_count: 101 },
      { units_known: "true" }, { channels: [...CONTEXT.channels, ...CONTEXT.channels] },
      { channels: [{ ...CONTEXT.channels[0], filename: "private.tif" }] },
    ]) expect(checkRequest({ context: { ...CONTEXT, ...extra } })).toBeNull();
  });

  it("claims duplicate actions before quota or any additional model call", async () => {
    const store = new MemoryStore();
    const token = await device(store);
    const fetcher = vi.fn(async () => modelReply(JSON.stringify(DRAFT)));
    const request = post("/v1/proposals", { context: CONTEXT }, token);
    const duplicate = request.clone();
    // UUID case cannot turn a transport resend into a different paid action.
    duplicate.headers.set("idempotency-key", duplicate.headers.get("idempotency-key")!.toUpperCase());
    expect((await handle(request, ENV, store, { fetcher })).status).toBe(200);
    const response = await handle(duplicate, ENV, store, { fetcher });
    expect([response.status, await response.json()]).toEqual([409, { code: "duplicate_request" }]);
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect([...store.requests.values()]).toEqual([1]);
  });

  it("accounts for both responses when a structural repair succeeds", async () => {
    const store = new MemoryStore();
    const token = await device(store);
    const fetcher = vi.fn()
      .mockResolvedValueOnce(modelReply("not-json"))
      .mockResolvedValueOnce(modelReply(JSON.stringify(DRAFT)));
    const response = await handle(post("/v1/proposals", { context: CONTEXT }, token), ENV, store, { fetcher });
    expect(response.status).toBe(200);
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect([...store.spent.values()][0]).toBe(2 * (1000 * 2.5 + 200 * 10) / 1e6);
    expect(JSON.parse(fetcher.mock.calls[1][1].body).input[1].content.at(-1).text).toContain("rejected");
  });

  it("rejects missing action IDs before quota or a paid request", async () => {
    const store = new MemoryStore();
    const token = await device(store);
    const fetcher = vi.fn();
    const request = post("/v1/proposals", { context: CONTEXT }, token);
    request.headers.delete("idempotency-key");
    const response = await handle(request, ENV, store, { fetcher });
    expect([response.status, await response.json()]).toEqual([400, { code: "request_id_required" }]);
    expect(store.requests.size).toBe(0);
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("bounds streams without trusting Content-Length and does not call the model", async () => {
    const store = new MemoryStore();
    const token = await device(store);
    const fetcher = vi.fn();
    const request = post("/v1/proposals", { context: CONTEXT, extra: "あ".repeat(2_100_000) }, token);
    request.headers.set("content-length", "1");
    expect((await handle(request, ENV, store, { fetcher })).status).toBe(400);
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("incomplete model output is classified without paying for an identical retry", async () => {
    const store = new MemoryStore();
    const token = await device(store);
    const fetcher = vi.fn(async () => new Response(JSON.stringify({ status: "incomplete", incomplete_details: { reason: "max_output_tokens" }, output: [] })));
    const response = await handle(post("/v1/proposals", { context: CONTEXT }, token), ENV, store, { fetcher });
    expect(await response.json()).toEqual({ code: "model_output_incomplete" });
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect([...store.spent.values()][0]).toBe(worstCaseUsd(readConfig(ENV)!, CONTEXT, []));
  });

  it("retains full reservation when a successful answer omits usage", async () => {
    const store = new MemoryStore();
    const token = await device(store);
    const fetcher = vi.fn(async () => new Response(JSON.stringify({ status: "completed", output: [{ type: "message", content: [{ type: "output_text", text: JSON.stringify(DRAFT) }] }] })));
    expect((await handle(post("/v1/proposals", { context: CONTEXT }, token), ENV, store, { fetcher })).status).toBe(200);
    expect([...store.spent.values()][0]).toBe(worstCaseUsd(readConfig(ENV)!, CONTEXT, []));
  });

  it.each([
    { input_tokens: 0, output_tokens: 0 },
    { input_tokens: 1000, output_tokens: 100_000 },
    { input_tokens: 1_000_000, output_tokens: 200 },
  ])("does not release a reservation based on contradictory usage %j", async (usage) => {
    const store = new MemoryStore();
    const token = await device(store);
    const fetcher = vi.fn(async () => modelReply(JSON.stringify(DRAFT), usage));
    expect((await handle(post("/v1/proposals", { context: CONTEXT }, token), ENV, store, { fetcher })).status).toBe(200);
    expect([...store.spent.values()][0]).toBe(worstCaseUsd(readConfig(ENV)!, CONTEXT, []));
    expect(store.usage.size).toBe(0);
  });

  it("does not accept a text result accompanied by a refusal", async () => {
    const store = new MemoryStore();
    const token = await device(store);
    const fetcher = vi.fn(async () => new Response(JSON.stringify({ status: "completed", output: [
      { type: "message", content: [{ type: "output_text", text: JSON.stringify(DRAFT) }, { type: "refusal", refusal: "no" }] },
    ] })));
    const response = await handle(post("/v1/proposals", { context: CONTEXT }, token), ENV, store, { fetcher });
    expect(await response.json()).toEqual({ code: "model_refused" });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("stops after an interrupted response body and retains the reservation", async () => {
    const store = new MemoryStore();
    const token = await device(store);
    const fetcher = vi.fn(async () => new Response(new ReadableStream({ start(controller) {
      controller.error(new DOMException("interrupted", "AbortError"));
    } })));
    const response = await handle(post("/v1/proposals", { context: CONTEXT }, token), ENV, store, { fetcher });
    expect(await response.json()).toEqual({ code: "model_unavailable" });
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect([...store.spent.values()][0]).toBe(worstCaseUsd(readConfig(ENV)!, CONTEXT, []));
  });

  it("reserves schema and UTF-8 input and applies conservative cache-aware accounting", async () => {
    const store = new MemoryStore();
    const token = await device(store);
    const usage = { input_tokens: 1000, output_tokens: 200, input_tokens_details: { cached_tokens: 700 } };
    const fetcher = vi.fn(async () => modelReply(JSON.stringify(DRAFT), usage));
    await handle(post("/v1/proposals", { context: CONTEXT }, token), ENV, store, { fetcher });
    expect([...store.spent.values()][0]).toBe((300 * 2.5 + 700 * 0.1 + 200 * 10) / 1e6);
    const config = readConfig(ENV)!;
    expect(worstCaseUsd(config, { ...CONTEXT, goal: "あ".repeat(1000) }, []))
      .toBeGreaterThan(worstCaseUsd(config, { ...CONTEXT, goal: "a".repeat(1000) }, []));
    const sent = (fetcher.mock.calls[0] as unknown as [string, RequestInit])[1];
    expect(sent.redirect).toBe("error");
    expect(sent.signal).toBeInstanceOf(AbortSignal);
  });
});
