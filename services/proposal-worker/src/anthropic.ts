/** Anthropic Messages API call with JSON-schema structured output (docs/drafts/llm-assistant/plan.md).
 *
 * The prompts stay in one place: every route builds the Responses-API payload as before, and this module
 * converts it to a Messages request just before the call. Usage is normalized to the relay's ledger
 * convention, where `inputTokens` counts every input token and `cachedInputTokens` the cache reads.
 */
import { boundedJson } from "./schema";

export const ANTHROPIC_URL = "https://api.anthropic.com/v1/messages";
export const ANTHROPIC_VERSION = "2026-10-21";
/** Models the relay may call, with the lowest tariffs (USD per million tokens) the operator may configure. */
export const ANTHROPIC_MODELS: Record<string, { input: number; output: number; cachedInput: number; cacheWrite: number }> = {
  "claude-opus-5-5": { input: 4, output: 20, cachedInput: 0.2, cacheWrite: 5 },
  "claude-sonnet-5-5": { input: 2, output: 10, cachedInput: 0.1, cacheWrite: 2.5 },
};

type ResponsesPart = { type: string; text?: string; image_url?: string };
export interface ResponsesPayload {
  model: string;
  reasoning?: { effort?: string };
  max_output_tokens: number;
  input: { role: string; content: ResponsesPart[] }[];
  text: { format: { schema: unknown } };
}

/** The same request as a Messages body: system prompt, one user turn, effort and the strict schema. */
export function toMessages(payload: ResponsesPayload) {
  const system = payload.input.filter((item) => item.role === "system")
    .flatMap((item) => item.content.map((part) => part.text ?? "")).join("\n");
  const content = payload.input.filter((item) => item.role === "user").flatMap((item) => item.content.map((part) => {
    if (part.type === "input_image" && typeof part.image_url === "string") {
      const match = /^data:(image\/(?:png|jpeg));base64,(.+)$/.exec(part.image_url);
      if (!match) throw new Error("unsupported_image");
      return { type: "image", source: { type: "base64", media_type: match[1], data: match[2] } };
    }
    return { type: "text", text: part.text ?? "" };
  }));
  return {
    model: payload.model,
    max_tokens: payload.max_output_tokens,
    system,
    messages: [{ role: "user", content }],
    output_config: {
      ...(payload.reasoning?.effort ? { effort: payload.reasoning.effort } : {}),
      format: { type: "json_schema", schema: payload.text.format.schema },
    },
  };
}

export interface MessagesUsage {
  input_tokens?: number;
  output_tokens?: number;
  cache_creation_input_tokens?: number | null;
  cache_read_input_tokens?: number | null;
}

/** Ledger usage: every input token (uncached, cache writes and cache reads) and the cache reads alone. */
export function normalizedUsage(usage: MessagesUsage | undefined):
  { input: number; output: number; cached: number } | null {
  const fresh = usage?.input_tokens;
  const output = usage?.output_tokens;
  const written = usage?.cache_creation_input_tokens ?? 0;
  const read = usage?.cache_read_input_tokens ?? 0;
  const counts = [fresh, output, written, read];
  if (counts.some((value) => typeof value !== "number" || !Number.isSafeInteger(value) || value < 0)) return null;
  const input = (fresh as number) + written + read;
  if (input <= 0 || (output as number) <= 0) return null;
  return { input, output: output as number, cached: read };
}

export type MessagesBody = {
  type?: string;
  stop_reason?: string | null;
  content?: { type: string; text?: string }[];
  usage?: MessagesUsage;
};

/** The final answer's text: thinking blocks are skipped; exactly one text answer is expected. */
export function messagesText(body: MessagesBody): string {
  const texts = (body.content ?? []).filter((block) => block.type === "text" && typeof block.text === "string")
    .map((block) => block.text as string);
  if (texts.length !== 1) throw new Error("output_text_count");
  return texts[0];
}

export async function postMessages(fetcher: typeof fetch, apiKey: string, payload: ResponsesPayload): Promise<Response> {
  return fetcher(ANTHROPIC_URL, {
    method: "POST",
    // Manual redirects are returned as non-OK responses without forwarding the key to Location.
    redirect: "manual",
    // Two calls (initial and repair) must finish within the local API's 300 s request timeout.
    signal: AbortSignal.timeout(120_000),
    headers: { "x-api-key": apiKey, "anthropic-version": ANTHROPIC_VERSION, "content-type": "application/json" },
    body: JSON.stringify(toMessages(payload)),
  });
}

export async function readMessages(response: Response): Promise<MessagesBody> {
  const body = await boundedJson(response.body, 512 * 1024) as MessagesBody | null;
  if (!body || typeof body !== "object") throw new Error("invalid_body");
  return body;
}
