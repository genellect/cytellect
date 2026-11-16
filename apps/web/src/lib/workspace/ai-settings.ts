/** The researcher's AI settings on this PC (docs/drafts/llm-assistant/plan.md, 4.5): whether proposals also
 * send display-scaled previews, and whether the discussion's transmission scope has been acknowledged once.
 * Stored per browser profile; a blocked storage falls back to the defaults (previews on, scope not yet seen). */
const PREVIEWS_SETTING = "cytellect.ai.include-previews";
const DISCUSSION_SCOPE_SETTING = "cytellect.ai.discussion-scope-seen.v2";

function read(key: string): string | null {
  try {return globalThis.localStorage?.getItem(key) ?? null;} catch {return null;}
}
function write(key: string, value: string) {
  try {globalThis.localStorage?.setItem(key, value);} catch {/* The setting applies to this page only. */}
}

export function includePreviews(): boolean {return read(PREVIEWS_SETTING) !== "0";}
export function setIncludePreviews(value: boolean) {write(PREVIEWS_SETTING, value ? "1" : "0");}
export function discussionScopeSeen(): boolean {return read(DISCUSSION_SCOPE_SETTING) === "1";}
export function markDiscussionScopeSeen() {write(DISCUSSION_SCOPE_SETTING, "1");}
