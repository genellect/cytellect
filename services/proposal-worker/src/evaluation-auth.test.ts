import { describe, expect, it, vi } from "vitest";
import { evaluationAuth } from "./evaluation-auth";
import { draftProposal, MODEL } from "./openai";

const proxyEnv = { CLAUDE_CODE_REMOTE: "true", CYTELLECT_EVAL_PROXY_AUTH: "true", CYTELLECT_ALLOW_PAID_PUBLIC_EVAL: "true" };

describe("evaluation authentication", () => {
  it("keeps direct private-key mode and rejects missing credentials", () => {
    expect(evaluationAuth({ OPENAI_API_KEY: "fixture" })).toEqual({ apiKey: "fixture", provider: "openai" });
    expect(evaluationAuth({ CYTELLECT_EVAL_PROVIDER: "anthropic", ANTHROPIC_API_KEY: "fixture" }))
      .toEqual({ apiKey: "fixture", provider: "anthropic" });
    expect(() => evaluationAuth({ CYTELLECT_EVAL_PROVIDER: "anthropic", OPENAI_API_KEY: "fixture" })).toThrow("private_key_required");
    expect(() => evaluationAuth({ CYTELLECT_EVAL_PROVIDER: "other", OPENAI_API_KEY: "fixture" })).toThrow("provider_unknown");
    expect(() => evaluationAuth({ CYTELLECT_EVAL_PROVIDER: "constructor", OPENAI_API_KEY: "fixture" })).toThrow("provider_unknown");
    expect(() => evaluationAuth({})).toThrow("private_key_required");
  });
  it.each([
    { ...proxyEnv, CLAUDE_CODE_REMOTE: "false" },
    { ...proxyEnv, CYTELLECT_ALLOW_PAID_PUBLIC_EVAL: "false" },
    { ...proxyEnv, CI: "true" },
    { ...proxyEnv, OPENAI_API_KEY: "fixture" },
  ])("refuses ambiguous, local or CI proxy mode", (env) => {
    expect(() => evaluationAuth(env)).toThrow("not_authorized");
  });
  it("uses the actual provider call without sending any credential from the VM", async () => {
    const transport = vi.fn(async () => Response.json({ error: { code: "invalid_api_key" } }, { status: 401 }));
    const auth = evaluationAuth(proxyEnv, transport as typeof fetch);
    await expect(draftProposal({ ...auth, model: MODEL, maxOutputTokens: 8000 }, {}, [])).rejects.toThrow("model_unavailable");
    const [url, init] = transport.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("https://api.openai.com/v1/responses");
    expect(new Headers(init.headers).has("authorization")).toBe(false);
    expect(new Headers(init.headers).get("content-type")).toBe("application/json");
    expect(init.redirect).toBe("error");
    expect(JSON.parse(init.body as string).store).toBe(false);
    expect(transport).toHaveBeenCalledTimes(1);
  });
  it("proxies Claude without sending the key header from the VM", async () => {
    const transport = vi.fn(async () => Response.json({ type: "error", error: { type: "authentication_error" } }, { status: 401 }));
    const auth = evaluationAuth({ ...proxyEnv, CYTELLECT_EVAL_PROVIDER: "anthropic" }, transport as typeof fetch);
    await expect(draftProposal({ ...auth, model: "claude-opus-5-5", maxOutputTokens: 8000 }, {}, [])).rejects.toThrow("model_unavailable");
    const [url, init] = transport.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("https://api.anthropic.com/v1/messages");
    expect(new Headers(init.headers).has("x-api-key")).toBe(false);
    expect(new Headers(init.headers).get("anthropic-version")).toBe("2026-10-21");
    expect(init.redirect).toBe("error");
    expect(await auth.fetcher!("https://api.openai.com/v1/responses", { method: "POST", redirect: "manual" }).catch((e: Error) => e.message))
      .toBe("evaluation_proxy_destination_rejected");
  });
  it.each([
    ["https://other.example/v1/responses", { method: "POST", redirect: "error" }],
    ["https://api.openai.com/v1/responses", { method: "POST", redirect: "follow" }],
    ["https://api.openai.com/v1/responses", { method: "GET", redirect: "error" }],
  ])("blocks other destinations and redirect modes before transport", async (url, init) => {
    const transport = vi.fn();
    const auth = evaluationAuth(proxyEnv, transport);
    await expect(auth.fetcher!(url as string, init as RequestInit)).rejects.toThrow("destination_rejected");
    expect(transport).not.toHaveBeenCalled();
  });
});
