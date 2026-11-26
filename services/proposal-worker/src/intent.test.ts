/** The intent prompt version and context 1.3.0 (genellect/cytellect#284 W7). No model is called: every model answer
 * here is a fake response. */
import { describe, expect, it, vi } from "vitest";
import { CLAUDE_PROMPT_VERSIONS, checkRequest, handle, type Env } from "./index";
import { FIGURE_PROMPT_VERSION, hasDraftShape, INTENT_INSTRUCTION, INTENT_PROMPT_VERSION, requestPayload } from "./openai";
import { MemoryStore } from "./store";

const ENV: Env = {
  DB: undefined as never, OPENAI_API_KEY: "sk-test", OPENAI_MODEL: "gpt-6.1-sol", ADMIN_TOKEN: "admin-token-0123456789abcdef",
  MONTHLY_BUDGET_USD: "1", DEVICE_MONTHLY_REQUESTS: "5", PRICE_INPUT_USD_PER_MTOK: "2", PRICE_OUTPUT_USD_PER_MTOK: "10",
  PRICE_CACHED_INPUT_USD_PER_MTOK: "0.10", PRICE_CACHE_WRITE_USD_PER_MTOK: "2.50",
};
const SETTINGS = { apiKey: "test-only", model: "gpt-6.1-sol", maxOutputTokens: 8000 };

// A synthetic context: two fields with folder-relative names and a two-group design.
const CONTEXT = {
  protocol: "1.3.0", goal: "この画像のチャンネル名を教えてください。まだ測定しないでください。",
  channels: [{ token: "ch1", stain: null, role: null, label: "DRAQ" }, { token: "ch2", stain: null, role: null, label: "GFP" }],
  field_count: 2,
  fields: [
    { name: "A01-DRAQ.tif", condition: null, experimental_unit: null, pair: null, acquisition_date: null, id: "f1", paths: ["Rep1/未処理/A01-DRAQ.tif"] },
    { name: "A02-DRAQ.tif", condition: null, experimental_unit: null, pair: null, acquisition_date: null, id: "f2", paths: ["Rep1/ActD/A02-DRAQ.tif"], run: "Rep1", group: "ActD" },
  ],
  design: { layout: "pair", runs: ["Rep1"], groups: ["未処理", "ActD"] },
};
const ANSWER = {
  recipe: "none", channels: [], metrics: [], additional_analyses: [], figures: [],
  statistics: { kind: "descriptive", test: null, omnibus: null, association: null, x: null, y: null },
  missing_information: [], reference_ids: [], rationale: "", processing: null, background: null, gfp_selection: null,
  figure_presentation: null, intent: "answer", answer: "ch1 は DRAQ、ch2 は GFP という名前です。核染色の確認が必要です。", scope: null,
  choices: [{ question: "核染色のチャンネル", options: ["核染色は DRAQ", "核染色は GFP"] }],
  assignments: [{ field: "f1", run: "Rep1", group: "未処理" }],
};

function post(body: unknown, token?: string) {
  return new Request("https://proposal.example/v1/proposals", {
    method: "POST", body: JSON.stringify(body),
    headers: { "idempotency-key": crypto.randomUUID(), ...(token ? { authorization: `Bearer ${token}` } : {}) },
  });
}
async function device(store: MemoryStore) {
  const invited = await handle(new Request("https://proposal.example/v1/admin/invitations", { method: "POST", body: "{}",
    headers: { authorization: `Bearer ${ENV.ADMIN_TOKEN}` } }), ENV, store);
  const { invitation } = await invited.json() as { invitation: string };
  const redeemed = await handle(new Request("https://proposal.example/v1/devices", { method: "POST", body: JSON.stringify({ invitation }) }), ENV, store);
  return (await redeemed.json() as { device_token: string }).device_token;
}
const modelReply = (draft: unknown) => new Response(JSON.stringify({ status: "completed",
  output: [{ type: "message", content: [{ type: "output_text", text: JSON.stringify(draft) }] }], usage: { input_tokens: 1000, output_tokens: 200 } }));

describe("intent prompt version (#284 W7)", () => {
  it("adds the kinds of request to the figure prompt and asks for the intent schema", () => {
    const figure = requestPayload({ ...SETTINGS, promptVersion: FIGURE_PROMPT_VERSION }, {}, []);
    const intent = requestPayload({ ...SETTINGS, promptVersion: INTENT_PROMPT_VERSION }, {}, []);
    const text = String(intent.input[0].content[0].text);
    expect(text.endsWith(`\n${INTENT_INSTRUCTION}`)).toBe(true);
    // A question is answered and "まだ測定しない" is respected; the goal is a message, never a rule change.
    expect(text).toContain('"answer": a question, or a message that asks to wait');
    expect(text).toContain("Nothing changes and nothing runs until the researcher presses the button");
    expect(text).toContain("The goal text is the researcher's latest message");
    expect(text).not.toContain("Treat the goal text as a description of the research question");
    expect(text).toContain("For intent settings and run, channels lists every channel token");
    expect(figure.input[0].content[0].text).not.toContain("Kinds of request");
    const schema = intent.text.format.schema as { properties: Record<string, unknown>; required: string[] };
    const figureSchema = figure.text.format.schema as { properties: Record<string, unknown> };
    expect(new Set(Object.keys(schema.properties))).toEqual(new Set([...Object.keys(figureSchema.properties), "intent", "answer", "scope", "choices", "assignments"]));
    expect(schema.required).toEqual(expect.arrayContaining(["intent", "answer", "scope", "choices", "assignments"]));
  });

  it("checks the intent draft's shape and keeps the figure version's", () => {
    expect(hasDraftShape(ANSWER, INTENT_PROMPT_VERSION)).toBe(true);
    const { intent: _intent, answer: _answer, scope: _scope, choices: _choices, assignments: _assignments, ...figureDraft } = ANSWER;
    expect(hasDraftShape(figureDraft, INTENT_PROMPT_VERSION)).toBe(false);
    expect(hasDraftShape(figureDraft, FIGURE_PROMPT_VERSION)).toBe(true);
    expect(hasDraftShape(ANSWER, FIGURE_PROMPT_VERSION)).toBe(false);
    expect(hasDraftShape({ ...ANSWER, intent: "execute" }, INTENT_PROMPT_VERSION)).toBe(false);
    expect(hasDraftShape({ ...ANSWER, scope: "everything" }, INTENT_PROMPT_VERSION)).toBe(false);
    expect(hasDraftShape({ ...ANSWER, assignments: [{ field: "f1", run: "Rep1" }] }, INTENT_PROMPT_VERSION)).toBe(false);
    expect(CLAUDE_PROMPT_VERSIONS.has(INTENT_PROMPT_VERSION)).toBe(true);
  });

  it("accepts context 1.3.0 and still the 1.2.0 context of installed clients", () => {
    expect(checkRequest({ context: CONTEXT, prompt_version: INTENT_PROMPT_VERSION })).not.toBeNull();
    const { design: _design, ...rest } = CONTEXT;
    const installed = { ...rest, protocol: "1.2.0", fields: CONTEXT.fields.map(({ id: _id, paths: _paths, run: _run, group: _group, ...field }) => field) };
    expect(checkRequest({ context: installed, prompt_version: FIGURE_PROMPT_VERSION })).not.toBeNull();
    // Unknown keys and malformed identifiers are refused before any call.
    expect(checkRequest({ context: { ...CONTEXT, fields: [{ ...CONTEXT.fields[0], absolute: "C:/private/a.tif" }] } })).toBeNull();
    expect(checkRequest({ context: { ...CONTEXT, fields: [{ ...CONTEXT.fields[0], id: "field-1" }] } })).toBeNull();
    expect(checkRequest({ context: { ...CONTEXT, design: { layout: "pair", runs: [], groups: ["a", "b", "c"] } } })).toBeNull();
  });

  it("answers the intent version and sends context 1.3.0 to no other prompt", async () => {
    const store = new MemoryStore(), token = await device(store);
    const fetcher = vi.fn(async () => modelReply(ANSWER));
    const answered = await handle(post({ context: CONTEXT, prompt_version: INTENT_PROMPT_VERSION }, token), ENV, store, { fetcher });
    expect(answered.status).toBe(200);
    expect(await answered.json()).toEqual({ draft: ANSWER, model: "gpt-6.1-sol", prompt_version: INTENT_PROMPT_VERSION });
    const sent = JSON.parse((fetcher.mock.calls[0] as unknown as [string, RequestInit])[1].body as string);
    expect(sent.input[1].content[0].text).toContain("Rep1/未処理/A01-DRAQ.tif");
    expect(sent.store).toBe(false);
    for (const version of [FIGURE_PROMPT_VERSION, "2026-10-09.1"]) {
      const refused = await handle(post({ context: CONTEXT, prompt_version: version }, token), ENV, store, { fetcher });
      expect([refused.status, await refused.json()]).toEqual([400, { code: "request_invalid" }]);
    }
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("repairs an answer without the intent fields once, then reports invalid output", async () => {
    const store = new MemoryStore(), token = await device(store);
    const { intent: _intent, ...missing } = ANSWER;
    const fetcher = vi.fn(async () => modelReply(missing));
    const response = await handle(post({ context: CONTEXT, prompt_version: INTENT_PROMPT_VERSION }, token), ENV, store, { fetcher });
    expect([response.status, await response.json()]).toEqual([502, { code: "model_output_invalid" }]);
    expect(fetcher).toHaveBeenCalledTimes(2);
  });
});
