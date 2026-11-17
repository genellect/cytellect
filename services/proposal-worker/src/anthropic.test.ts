import { describe, expect, it, vi } from "vitest";
import { normalizedUsage, toMessages, ANTHROPIC_URL } from "./anthropic";
import { ASSISTANT_INSTRUCTION, ASSISTANT_PROMPT_VERSION, draftProposal, hasDraftShape, ModelError, PROMPT_VERSION, requestPayload } from "./openai";
import { CLAUDE_PROMPT_VERSIONS, readConfig, selectProvider, type Env } from "./index";

const DRAFT = {
  recipe: "nuclear-intensity", channels: [{ token: "dapi", stain: "DAPI", role: "nuclear", reason: "Nuclear stain" }],
  metrics: [{ metric: "area", channel: null, region: "nucleus" }],
  statistics: { kind: "descriptive", test: null, omnibus: null, association: null, x: null, y: null }, additional_analyses: [],
  figures: [{ kind: "field-distribution", metric: "area", channel: null, region: "nucleus", analysis_index: 0 }],
  missing_information: [], reference_ids: ["senft-2023"], rationale: "Measure nuclear area.",
};
const SETTINGS = { apiKey: "test-only", provider: "anthropic" as const, model: "claude-opus-5-5", maxOutputTokens: 8000, promptVersion: "2026-10-06.1" };

function reply(body: Record<string, unknown>, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}
const message = (text: string, stop = "end_turn", usage: Record<string, number> = { input_tokens: 900, output_tokens: 300 }) =>
  reply({ type: "message", stop_reason: stop, usage, content: [{ type: "thinking", thinking: "" }, { type: "text", text }] });

describe("Anthropic request conversion", () => {
  it("keeps the system prompt, images, effort and the strict schema", () => {
    const payload = requestPayload({ ...SETTINGS, reasoningEffort: "low", promptVersion: PROMPT_VERSION }, { goal: "g" },
      [{ channel: "dapi", png_base64: "iVBORw0KGgoAAAA" }]);
    const body = toMessages(payload as never);
    expect(body.model).toBe("claude-opus-5-5");
    expect(body.max_tokens).toBe(8000);
    expect(body.system).toBe(payload.input[0].content[0].text);
    expect(body.messages).toHaveLength(1);
    expect(body.messages[0].content[0]).toEqual({ type: "text", text: JSON.stringify({ context: { goal: "g" } }) });
    expect(body.messages[0].content[2]).toEqual({ type: "image", source: { type: "base64", media_type: "image/png", data: "iVBORw0KGgoAAAA" } });
    expect(body.output_config).toEqual({ effort: "low", format: { type: "json_schema", schema: payload.text.format.schema } });
    expect(body).not.toHaveProperty("thinking");
    expect(body).not.toHaveProperty("temperature");
  });

  it("rejects an image that is not an inline PNG or JPEG", () => {
    expect(() => toMessages({ model: "m", max_output_tokens: 1, text: { format: { schema: {} } },
      input: [{ role: "user", content: [{ type: "input_image", image_url: "https://example.invalid/x.png" }] }] })).toThrow();
  });
});

describe("Anthropic usage", () => {
  it("counts cache writes and reads as input and reports reads as cached", () => {
    expect(normalizedUsage({ input_tokens: 100, output_tokens: 50, cache_creation_input_tokens: 400, cache_read_input_tokens: 500 }))
      .toEqual({ input: 1000, output: 50, cached: 500 });
    expect(normalizedUsage({ input_tokens: 100, output_tokens: 50 })).toEqual({ input: 100, output: 50, cached: 0 });
  });
  it("treats missing or malformed counts as unknown", () => {
    expect(normalizedUsage(undefined)).toBeNull();
    expect(normalizedUsage({ input_tokens: 1.5, output_tokens: 2 })).toBeNull();
    expect(normalizedUsage({ input_tokens: 10, output_tokens: 0 })).toBeNull();
  });
});

describe("Anthropic structured call", () => {
  it("returns a valid draft from the text block and sends the documented headers", async () => {
    const fetcher = vi.fn(async (_url: unknown, _init?: RequestInit) => message(JSON.stringify(DRAFT),
      "end_turn", { input_tokens: 100, output_tokens: 300, cache_creation_input_tokens: 0, cache_read_input_tokens: 800 }));
    const result = await draftProposal({ ...SETTINGS, fetcher: fetcher as unknown as typeof fetch }, {}, []);
    expect(result).toMatchObject({ draft: DRAFT, inputTokens: 900, cachedInputTokens: 800, outputTokens: 300, usageComplete: true, calls: 1 });
    const [url, init] = fetcher.mock.calls[0];
    expect(url).toBe(ANTHROPIC_URL);
    expect(init?.redirect).toBe("manual");
    expect(init?.headers).toMatchObject({ "x-api-key": "test-only", "anthropic-version": "2026-10-21" });
  });

  it("maps refusal and max_tokens without a hidden retry", async () => {
    for (const [stop, code] of [["refusal", "model_refused"], ["max_tokens", "model_output_incomplete"], ["pause_turn", "model_unavailable"]]) {
      const fetcher = vi.fn(async () => message("", stop));
      const error = await draftProposal({ ...SETTINGS, fetcher: fetcher as unknown as typeof fetch }, {}, []).catch((value: unknown) => value);
      expect((error as ModelError).code).toBe(code);
      expect(fetcher).toHaveBeenCalledTimes(1);
    }
  });

  it("repairs unparsable output once", async () => {
    const fetcher = vi.fn()
      .mockResolvedValueOnce(message("not json"))
      .mockResolvedValueOnce(message(JSON.stringify(DRAFT)));
    const result = await draftProposal({ ...SETTINGS, fetcher: fetcher as unknown as typeof fetch }, {}, []);
    expect(result.calls).toBe(2);
    const second = JSON.parse(fetcher.mock.calls[1][1].body);
    expect(second.messages[0].content.at(-1).text).toContain("The previous output was rejected");
  });

  it("keeps only the allowlisted Anthropic error type", async () => {
    const fetcher = vi.fn(async () => reply({ type: "error", error: { type: "rate_limit_error", message: "private detail" } }, 429));
    const error = await draftProposal({ ...SETTINGS, fetcher: fetcher as unknown as typeof fetch }, {}, []).catch((value: unknown) => value) as ModelError;
    expect(error.code).toBe("model_unavailable");
    expect(error.providerHttpStatus).toBe(429);
    expect(error.providerErrorCode).toBe("rate_limit_error");
    expect(JSON.stringify(error)).not.toContain("private");
  });
});

const BASE: Env = {
  DB: undefined as never, MONTHLY_BUDGET_USD: "5", DEVICE_MONTHLY_REQUESTS: "50", REASONING_EFFORT: "medium",
  OPENAI_API_KEY: "sk-test", OPENAI_MODEL: "gpt-6.1-sol", PRICE_INPUT_USD_PER_MTOK: "2", PRICE_OUTPUT_USD_PER_MTOK: "10",
  PRICE_CACHED_INPUT_USD_PER_MTOK: "0.1", PRICE_CACHE_WRITE_USD_PER_MTOK: "2.5",
};
const CLAUDE: Partial<Env> = {
  ANTHROPIC_API_KEY: "test-only", ANTHROPIC_MODEL: "claude-opus-5-5", ANTHROPIC_PRICE_INPUT_USD_PER_MTOK: "4",
  ANTHROPIC_PRICE_OUTPUT_USD_PER_MTOK: "20", ANTHROPIC_PRICE_CACHED_INPUT_USD_PER_MTOK: "0.2", ANTHROPIC_PRICE_CACHE_WRITE_USD_PER_MTOK: "5",
};

describe("provider configuration and routing", () => {
  it("accepts only listed Claude models at no less than their tariffs", () => {
    expect(readConfig({ ...BASE, ...CLAUDE })?.providers.anthropic?.model).toBe("claude-opus-5-5");
    for (const changed of [{ ANTHROPIC_MODEL: "claude-unknown" }, { ANTHROPIC_PRICE_OUTPUT_USD_PER_MTOK: "10" },
      { ANTHROPIC_PRICE_CACHE_WRITE_USD_PER_MTOK: "3" }, { ANTHROPIC_API_KEY: "" }]) {
      expect(readConfig({ ...BASE, ...CLAUDE, ...changed })?.providers.anthropic).toBeUndefined();
    }
    expect(readConfig({ ...BASE, ...CLAUDE, ANTHROPIC_MODEL: "claude-sonnet-5-5", ANTHROPIC_PRICE_INPUT_USD_PER_MTOK: "2",
      ANTHROPIC_PRICE_OUTPUT_USD_PER_MTOK: "10", ANTHROPIC_PRICE_CACHED_INPUT_USD_PER_MTOK: "0.1",
      ANTHROPIC_PRICE_CACHE_WRITE_USD_PER_MTOK: "2.5" })?.providers.anthropic?.model).toBe("claude-sonnet-5-5");
  });

  it("keeps installed clients' prompt versions on OpenAI and moves redesigned ones to Claude when configured", () => {
    const redesigned = "test-redesigned-version";
    CLAUDE_PROMPT_VERSIONS.add(redesigned);
    try {
      const both = readConfig({ ...BASE, ...CLAUDE })!;
      expect(selectProvider(both, redesigned)?.model).toBe("claude-opus-5-5");
      expect(selectProvider(both, "2026-10-09.1")?.model).toBe("gpt-6.1-sol");
      const openaiOnly = readConfig(BASE)!;
      expect(selectProvider(openaiOnly, redesigned)?.model).toBe("gpt-6.1-sol");
      const claudeOnly = readConfig({ ...BASE, ...CLAUDE, OPENAI_API_KEY: undefined })!;
      expect(selectProvider(claudeOnly, redesigned)?.provider).toBe("anthropic");
      expect(selectProvider(claudeOnly, "2026-10-09.1")).toBeNull();
    } finally {
      CLAUDE_PROMPT_VERSIONS.delete(redesigned);
    }
  });
});

describe("assistant prompt version", () => {
  it("keeps the latest rules and schema and adds the records-and-images instruction", () => {
    const latest = requestPayload({ ...SETTINGS, promptVersion: PROMPT_VERSION }, {}, []);
    const assistant = requestPayload({ ...SETTINGS, promptVersion: ASSISTANT_PROMPT_VERSION }, {}, []);
    expect(assistant.input[0].content[0].text).toBe(`${latest.input[0].content[0].text}\n${ASSISTANT_INSTRUCTION}`);
    expect(assistant.text.format.schema).toEqual(latest.text.format.schema);
    expect(hasDraftShape(DRAFT, ASSISTANT_PROMPT_VERSION)).toBe(hasDraftShape(DRAFT, PROMPT_VERSION));
  });
  it("is routed to Claude", () => {
    expect(CLAUDE_PROMPT_VERSIONS.has(ASSISTANT_PROMPT_VERSION)).toBe(true);
    expect(selectProvider(readConfig({ ...BASE, ...CLAUDE })!, ASSISTANT_PROMPT_VERSION)?.model).toBe("claude-opus-5-5");
  });
});

describe("Claude output ceiling", () => {
  it("uses ANTHROPIC_MAX_OUTPUT_TOKENS for Claude and the shared ceiling otherwise", () => {
    const config = readConfig({ ...BASE, ...CLAUDE, MAX_OUTPUT_TOKENS: "8000", ANTHROPIC_MAX_OUTPUT_TOKENS: "16000" })!;
    expect(selectProvider(config, ASSISTANT_PROMPT_VERSION)?.maxOutputTokens).toBe(16000);
    expect(selectProvider(config, "2026-10-09.1")?.maxOutputTokens).toBe(8000);
    expect(selectProvider(readConfig({ ...BASE, ...CLAUDE })!, ASSISTANT_PROMPT_VERSION)?.maxOutputTokens).toBe(8000);
    expect(readConfig({ ...BASE, ...CLAUDE, ANTHROPIC_MAX_OUTPUT_TOKENS: "64000" })?.providers.anthropic).toBeUndefined();
  });
});

