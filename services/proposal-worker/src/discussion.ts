/** Result discussion drafts (protocol result-discussion/1.0.0, requirements AC-01–AC-09).
 *
 * The model receives one saved two-group comparison (numbers, fixed identifiers, warning codes) and the
 * researcher's short description, and returns three lists of sentences. It never computes values. The
 * local API checks every number and forbidden claim before anything is shown; this relay checks only the
 * shape. Prompt and context are never logged or stored.
 */
import contract from "./contract.json";
import { matchesSchema } from "./schema";
import { structuredCall, type ModelResult, type ModelSettings } from "./openai";

export const DISCUSSION_PROMPT_VERSION = "2026-11-12.2";
export const DISCUSSION_PROTOCOL = "result-discussion/1.0.0";

export const DISCUSSION_SYSTEM_PROMPT = `You write a short discussion of one saved microscopy comparison for Cytellect, in Japanese.
The input is the saved result only: metric, region, stain, groups, group means, the treatment-minus-control difference or ratio with its 95% interval when one was computed, per-run values, n, the test and its p value, warning codes, and the researcher's optional purpose, cells and stains.
Return three lists, one plain sentence per item:
- implications (1 to 3): what the result may suggest biologically.
- alternatives (0 to 2): other explanations and what this experiment cannot tell.
- next_steps (0 to 3): concrete experiments, controls or measurements that would check it.
Rules, all checked after your answer:
- Do not compute, round differently or invent numbers. State a number only if it appears in the input exactly as a value, a percent change of a ratio, n or a run count. Prefer words to numbers.
- When test is "none", the result is descriptive: never say significant, proven, shown, established or confirmed. Use 可能性がある, 〜と整合する, 〜を示唆する.
- When the interval includes 0 or a rank test has p of at least 0.05, the difference is unclear: never say there is no change, no effect or no difference.
- When runs disagree in direction, say so and do not choose one.
- Do not cite papers, authors, DOIs or links, and do not name genes, pathways or drugs that are not in the input.
- Warning codes describe limits of the data (few independent runs, independence not confirmed, exploratory threshold, missing values); use them in alternatives rather than repeating them.
- Style: concise academic Japanese, as in the discussion section of a paper. End with である or a noun; about 60 characters per item; no polite form, no filler such as 「〜と言えるでしょう」, no repeated caveats across items. Use standard terms (独立性, 信頼区間, 記述統計, 層別).`;

const SCHEMA = contract.discussion_draft_schema;

export function hasDiscussionShape(value: unknown): boolean {
  return matchesSchema(value, SCHEMA);
}

export function checkDiscussionRequest(body: Record<string, unknown>): Record<string, unknown> | null {
  const extra = Object.keys(body).filter((key) => key !== "context" && key !== "prompt_version");
  if (extra.length || !matchesSchema(body.context, contract.discussion_context_schema)) return null;
  return body.context as Record<string, unknown>;
}

export function discussionPayload(settings: ModelSettings, context: unknown, repair?: string) {
  const content: Record<string, unknown>[] = [{ type: "input_text", text: JSON.stringify({ context }) }];
  if (repair) content.push({ type: "input_text", text: `The previous output was rejected: ${repair}. Return a corrected object.` });
  return {
    model: settings.model, store: false, service_tier: "default",
    reasoning: { effort: settings.reasoningEffort ?? "medium" },
    max_output_tokens: settings.maxOutputTokens,
    input: [
      { role: "system", content: [{ type: "input_text", text: DISCUSSION_SYSTEM_PROMPT }] },
      { role: "user", content },
    ],
    text: { format: { type: "json_schema", name: "cytellect_result_discussion", strict: true, schema: SCHEMA } },
  };
}

/** UTF-8 bytes bound the text tokens, including the schema and the largest repair message. */
export function discussionTokenCeiling(settings: ModelSettings, context: unknown): number {
  return new TextEncoder().encode(JSON.stringify(discussionPayload(settings, context, "x".repeat(256)))).byteLength + 1024;
}

export async function draftDiscussion(settings: ModelSettings, context: unknown): Promise<ModelResult & { calls: number }> {
  return structuredCall(settings, (repair) => discussionPayload(settings, context, repair),
    discussionTokenCeiling(settings, context), hasDiscussionShape);
}
