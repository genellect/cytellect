/** Anthropic Messages API call (docs/drafts/llm-assistant/plan.md).
 *
 * The answer's format is described to Claude, not forced on it (2026-11-17, the owner's decision): the system prompt
 * carries the JSON Schema, and the relay checks the answer against it and asks once for a correction, as for any
 * answer. Grammar-constrained output is not used: it limits what the model may write, and the analysis proposal's
 * schema (47 union-typed fields) exceeds its compilation limits (16).
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

/** How the answer is described to Claude: one JSON object conforming to the request's schema. */
export function answerFormat(schema: unknown): string {
  return "Answer format: reply with exactly one JSON object and no other text. It must conform to this JSON Schema "
    + "(every listed property present, no other properties):\n" + JSON.stringify(schema);
}

/** The same request as a Messages body: system prompt with the answer's format, one user turn and effort. */
export function toMessages(payload: ResponsesPayload) {
  const system = [...payload.input.filter((item) => item.role === "system")
    .flatMap((item) => item.content.map((part) => part.text ?? "")), answerFormat(payload.text.format.schema)].join("\n\n");
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
    ...(payload.reasoning?.effort ? { output_config: { effort: payload.reasoning.effort } } : {}),
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

/** The final answer's text: thinking blocks are skipped and the text blocks joined. */
export function messagesText(body: MessagesBody): string {
  const texts = (body.content ?? []).filter((block) => block.type === "text" && typeof block.text === "string")
    .map((block) => block.text as string);
  if (!texts.length) throw new Error("output_text_count");
  return texts.join("");
}

/** The JSON object in an answer whose format was described, not forced: a Markdown fence or a sentence around the
 * object is set aside; what remains is parsed and checked against the schema by the caller. */
export function answerJson(text: string): string {
  const fenced = /```(?:json)?\s*([\s\S]*?)```/i.exec(text);
  const body = (fenced ? fenced[1] : text).trim();
  const start = body.indexOf("{"), end = body.lastIndexOf("}");
  return start >= 0 && end > start ? body.slice(start, end + 1) : body;
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
