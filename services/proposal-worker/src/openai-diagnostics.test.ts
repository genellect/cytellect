import { describe, expect, it, vi } from "vitest";
import { draftProposal, MODEL, ModelError } from "./openai";

async function failed(response: Response) {
  const fetcher = vi.fn(async () => response) as unknown as typeof fetch;
  const error = await draftProposal({ apiKey: "private-key", model: MODEL, maxOutputTokens: 8000, fetcher }, {}, [])
    .catch((value: unknown) => value);
  expect(fetcher).toHaveBeenCalledTimes(1);
  expect(error).toBeInstanceOf(ModelError);
  return error as ModelError;
}

describe("sanitized provider diagnostics", () => {
  it("does not serialize a recoverable billed draft into error diagnostics", () => {
    const draft = { rationale: "private research context" };
    const error = new ModelError("model_usage_exceeded", undefined,
      { inputTokens: 1000, outputTokens: 9000, cachedInputTokens: 0, calls: 1 }, draft);
    expect(error.validatedDraft).toEqual(draft);
    expect(JSON.stringify(error)).not.toContain("private research context");
  });
  it("retains HTTP status and allowlisted code without private messages or headers", async () => {
    const error = await failed(Response.json({ error: { code: "model_not_found", message: "private-key secret context", param: "private-field" } },
      { status: 404, headers: { "x-request-id": "private-id" } }));
    expect(error.providerHttpStatus).toBe(404);
    expect(error.providerErrorCode).toBe("model_not_found");
    expect(error.message).toBe("model_unavailable");
    expect(JSON.stringify(error)).not.toMatch(/private|secret/);
  });

  it("uses a fixed error type when a schema failure has no code", async () => {
    const error = await failed(Response.json({ error: { code: null, type: "invalid_request_error", message: "private schema" } }, { status: 400 }));
    expect(error.providerErrorCode).toBe("invalid_request_error");
  });

  it.each([
    JSON.stringify({ error: { code: "private-context", type: "private-type", message: "private-key" } }),
    "<html>private upstream error</html>",
    JSON.stringify({ error: { code: "invalid_api_key", message: "x".repeat(17000) } }),
  ])("discards unknown, malformed and oversized error bodies", async (body) => {
    const error = await failed(new Response(body, { status: 401 }));
    expect(error.providerHttpStatus).toBe(401);
    expect(error.providerErrorCode).toBeUndefined();
    expect(JSON.stringify(error)).not.toMatch(/private|upstream|xxxxx/);
  });

  it("never propagates transport error messages or creates HTTP diagnostics", async () => {
    const fetcher = vi.fn(async () => { throw new Error("private-key transport"); }) as unknown as typeof fetch;
    const error = await draftProposal({ apiKey: "private-key", model: MODEL, maxOutputTokens: 8000, fetcher }, {}, [])
      .catch((value: unknown) => value) as ModelError;
    expect(error.code).toBe("model_unavailable");
    expect(error.providerHttpStatus).toBeUndefined();
    expect(error.providerErrorCode).toBeUndefined();
    expect(error.message).not.toContain("private");
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
});
