import { describe, expect, it, vi } from "vitest";
import { handle, type Env } from "./index";
import { DISCUSSION_PROMPT_VERSION, discussionPayload, hasDiscussionShape } from "./discussion";
import { MemoryStore } from "./store";

// A stand-in model: no request leaves the test.
const ENV: Env = {
  DB: undefined as never, OPENAI_API_KEY: "sk-test", OPENAI_MODEL: "gpt-6.1-sol", ADMIN_TOKEN: "admin-token-0123456789abcdef",
  MONTHLY_BUDGET_USD: "1", DEVICE_MONTHLY_REQUESTS: "3", PRICE_INPUT_USD_PER_MTOK: "2", PRICE_OUTPUT_USD_PER_MTOK: "10",
  PRICE_CACHED_INPUT_USD_PER_MTOK: "0.10", PRICE_CACHE_WRITE_USD_PER_MTOK: "2.50",
};
const CONTEXT = {
  protocol: "result-discussion/1.0.0", language: "ja",
  experiment: { purpose: "処理で核小体が変わるかを見る", cells: "U2OS", stains: ["NPM1"] },
  result: {
    metric: "nucleolar_area_px", region: "nucleoplasm", stain: null, unit: "px²", scale: "ratio", control: "Untreated",
    treatment: "Oxaliplatin 10 µM", design: "paired", test: "none", exploratory_threshold: false, n_control: 3,
    n_treatment: 3, n_runs: 3, p_value: null, effect: null,
    groups: [{ condition: "Untreated", mean: 623.8 }, { condition: "Oxaliplatin 10 µM", mean: 450.8 }],
    difference: null, ratio: null,
    runs: [{ run: "run 1", control: 566.5, treatment: 469.8, difference: -96.7, ratio: 0.83 }],
    warnings: ["descriptive_comparison_no_test_or_interval"], heading: null,
  },
};
const DRAFT = { implications: ["核小体が小さくなる可能性がある。"], alternatives: [], next_steps: ["視野を増やして確かめる。"] };

function modelReply(text: string) {
  return new Response(JSON.stringify({ status: "completed", output: [{ type: "message", content: [{ type: "output_text", text }] }],
    usage: { input_tokens: 1000, output_tokens: 200 } }), { status: 200 });
}

function post(path: string, body: unknown, token?: string) {
  return new Request(`https://proposal.example${path}`, {
    method: "POST", body: JSON.stringify(body),
    headers: { "idempotency-key": crypto.randomUUID(), ...(token ? { authorization: `Bearer ${token}` } : {}) },
  });
}

async function device(store: MemoryStore) {
  const invited = await handle(post("/v1/admin/invitations", {}, ENV.ADMIN_TOKEN), ENV, store);
  const { invitation } = await invited.json() as { invitation: string };
  const redeemed = await handle(post("/v1/devices", { invitation }), ENV, store);
  return (await redeemed.json() as { device_token: string }).device_token;
}

describe("result discussion route", () => {
  it("relays the saved result only, with store:false and the strict three-heading schema", async () => {
    const store = new MemoryStore(), token = await device(store);
    const fetcher = vi.fn(async () => modelReply(JSON.stringify(DRAFT)));
    const response = await handle(post("/v1/discussions", { context: CONTEXT, prompt_version: DISCUSSION_PROMPT_VERSION }, token), ENV, store, { fetcher });
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ draft: DRAFT, model: "gpt-6.1-sol", prompt_version: DISCUSSION_PROMPT_VERSION });
    expect(fetcher).toHaveBeenCalledTimes(1);
    const sent = JSON.parse((fetcher.mock.calls[0] as unknown as [string, RequestInit])[1].body as string);
    expect(sent.store).toBe(false);
    expect(sent.text.format).toMatchObject({ type: "json_schema", strict: true, name: "cytellect_result_discussion" });
    expect(sent.input[0].content[0].text).toContain("Do not compute");
    expect(JSON.parse(sent.input[1].content[0].text)).toEqual({ context: CONTEXT });
  });

  it("refuses before any call: no token, a context with extra fields, an unknown prompt version", async () => {
    const store = new MemoryStore(), token = await device(store);
    const fetcher = vi.fn(async () => modelReply(JSON.stringify(DRAFT)));
    expect((await handle(post("/v1/discussions", { context: CONTEXT, prompt_version: DISCUSSION_PROMPT_VERSION }), ENV, store, { fetcher })).status).toBe(401);
    const withPath = { ...CONTEXT, result: { ...CONTEXT.result, file: "/private/field.tif" } };
    expect((await handle(post("/v1/discussions", { context: withPath, prompt_version: DISCUSSION_PROMPT_VERSION }, token), ENV, store, { fetcher })).status).toBe(400);
    expect((await handle(post("/v1/discussions", { context: CONTEXT, previews: [] , prompt_version: DISCUSSION_PROMPT_VERSION}, token), ENV, store, { fetcher })).status).toBe(400);
    expect((await handle(post("/v1/discussions", { context: CONTEXT, prompt_version: "2026-10-09.1" }, token), ENV, store, { fetcher })).status).toBe(400);
    expect((await handle(post("/v1/discussions", { context: CONTEXT }, token), ENV, store, { fetcher })).status).toBe(400);
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("is disabled without the configured limits, like proposals", async () => {
    const store = new MemoryStore(), token = await device(store);
    const fetcher = vi.fn();
    const response = await handle(post("/v1/discussions", { context: CONTEXT, prompt_version: DISCUSSION_PROMPT_VERSION }, token),
      { ...ENV, MONTHLY_BUDGET_USD: undefined }, store, { fetcher });
    expect(response.status).toBe(503);
    expect(await response.json()).toEqual({ code: "proposal_service_disabled" });
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("repairs once and then reports invalid output", async () => {
    const store = new MemoryStore(), token = await device(store);
    const fetcher = vi.fn(async () => modelReply(JSON.stringify({ implications: "not a list" })));
    const response = await handle(post("/v1/discussions", { context: CONTEXT, prompt_version: DISCUSSION_PROMPT_VERSION }, token), ENV, store, { fetcher });
    expect(response.status).toBe(502);
    expect(await response.json()).toEqual({ code: "model_output_invalid" });
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("checks the shape only; numbers and claims are checked by the local API", () => {
    expect(hasDiscussionShape(DRAFT)).toBe(true);
    expect(hasDiscussionShape({ ...DRAFT, references: ["doi"] })).toBe(false);
    expect(discussionPayload({ apiKey: "k", model: "m", maxOutputTokens: 2000 }, CONTEXT).text.format.schema)
      .toMatchObject({ additionalProperties: false, required: ["implications", "alternatives", "next_steps"] });
  });
});
