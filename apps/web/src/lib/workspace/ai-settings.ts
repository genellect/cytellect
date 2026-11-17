/** The researcher's AI settings on this PC (docs/drafts/llm-assistant/plan.md, 4.5 and 8): whether proposals
 * also send display-scaled previews, whether the discussion's transmission scope has been acknowledged once,
 * and the goal last written to the AI per workspace, which a discussion starts from as its purpose.
 * Stored per browser profile; a blocked storage falls back to the defaults (previews on, scope not yet seen,
 * no goal). */
const PREVIEWS_SETTING = "cytellect.ai.include-previews";
// v3: the scope grew (the summary, n breakdown and method, 2026-11-17); it is shown in full once again.
const DISCUSSION_SCOPE_SETTING = "cytellect.ai.discussion-scope-seen.v3";
const GOAL_SETTING = "cytellect.ai.goal.";
// The proposal scope grew on 2026-11-17 (labels, field records, previews); installations that agreed to the earlier
// scope at sign-in confirm it once more before their next proposal (requirement L03).
const PROPOSAL_SCOPE_SETTING = "cytellect.ai.proposal-scope-seen.v2";

// A choice this page could not store (storage blocked or full). It holds until the page closes, so an opt-out of
// previews is never lost to a failed write; a choice that was stored is read back from storage, so a change made in
// another tab of the same browser takes effect here too.
const unsaved = new Map<string, string>();

function read(key: string): string | null {
  if (unsaved.has(key)) return unsaved.get(key)!;
  try {return globalThis.localStorage?.getItem(key) ?? null;} catch {return null;}
}
function write(key: string, value: string) {
  try {
    const storage = globalThis.localStorage;
    if (!storage) throw new Error("storage_unavailable");
    storage.setItem(key, value);
    unsaved.delete(key);
  } catch {unsaved.set(key, value);}
}

export function includePreviews(): boolean {return read(PREVIEWS_SETTING) !== "0";}
export function setIncludePreviews(value: boolean) {write(PREVIEWS_SETTING, value ? "1" : "0");}
export function discussionScopeSeen(): boolean {return read(DISCUSSION_SCOPE_SETTING) === "1";}
export function markDiscussionScopeSeen() {write(DISCUSSION_SCOPE_SETTING, "1");}
export function proposalScopeSeen(): boolean {return read(PROPOSAL_SCOPE_SETTING) === "1";}
export function markProposalScopeSeen() {write(PROPOSAL_SCOPE_SETTING, "1");}
/** The goal the researcher last wrote to the AI in this workspace (the analysis proposal's goal). */
export function rememberedGoal(workspace: string): string {return workspace ? read(GOAL_SETTING + workspace) ?? "" : "";}
export function rememberGoal(workspace: string, goal: string) {if (workspace && goal.trim()) write(GOAL_SETTING + workspace, goal.trim());}
