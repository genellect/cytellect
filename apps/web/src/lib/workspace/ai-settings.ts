/** The researcher's AI settings on this PC (docs/drafts/llm-assistant/plan.md, 4.5 and §8): whether proposals
 * also send display-scaled previews, whether the discussion's transmission scope has been acknowledged once,
 * and the goal last written to the AI per workspace, which a discussion starts from as its purpose.
 * Stored per browser profile; a blocked storage falls back to the defaults (previews on, scope not yet seen,
 * no goal). */
const PREVIEWS_SETTING = "cytellect.ai.include-previews";
// v3: the scope grew (the summary, n breakdown and method, 2026-11-17); it is shown in full once again.
const DISCUSSION_SCOPE_SETTING = "cytellect.ai.discussion-scope-seen.v3";
const GOAL_SETTING = "cytellect.ai.goal.";

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
/** The goal the researcher last wrote to the AI in this workspace (the analysis proposal's goal). */
export function rememberedGoal(workspace: string): string {return workspace ? read(GOAL_SETTING + workspace) ?? "" : "";}
export function rememberGoal(workspace: string, goal: string) {if (workspace && goal.trim()) write(GOAL_SETTING + workspace, goal.trim());}
