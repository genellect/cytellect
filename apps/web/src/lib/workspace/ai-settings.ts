/** The researcher's AI settings on this PC (docs/drafts/llm-assistant/plan.md, 4.5 and 8): whether proposals
 * also send display-scaled previews, whether the discussion's transmission scope has been acknowledged once,
 * and the goal last written to the AI per workspace, which a discussion starts from as its purpose.
 * Stored per browser profile; a blocked storage falls back to the defaults (previews on, scope not yet seen,
 * no goal). */
const PREVIEWS_SETTING = "cytellect.ai.include-previews";
export const AI_SCOPE = "AI への相談では、書いた目的、チャンネル名、視野の名前と記録、追加した画像のフォルダー内の名前、実験回と群の名前、代表的な視野の縮小画像（設定で止められます）を送ります。";
export const DISCUSSION_SCOPE = "送信内容：保存済みの結果（上のまとめの見出しと要点、指標とその定義、領域・チャネル・群・実験回の名前、群の値、差と信頼区間、実験回ごとの値、n とその内訳、集計と検定の方法、警告）と実験の目的。";
// v3: the scope grew (the summary, n breakdown and method, 2026-11-17); it is shown in full once again.
const DISCUSSION_SCOPE_SETTING = "cytellect.ai.discussion-scope-seen.v3";
const GOAL_SETTING = "cytellect.ai.goal.";
// The proposal scope grew on 2026-11-17 (labels, field records, previews) and again with #284 W7 (the folder-relative
// names fields were added with, the design's run and group names); installations that agreed to an earlier scope
// confirm it once more before their next proposal (requirement L03).
const PROPOSAL_SCOPE_SETTING = "cytellect.ai.proposal-scope-seen.v3";

// A choice this page could not store (storage blocked or full). It holds until the page closes, so an opt-out of
// previews is never lost to a failed write; a choice that was stored is read back from storage, so a change made in
// another tab of the same browser takes effect here too.
const unsaved = new Map<string, string>();
const SETTINGS_EVENT = "cytellect-ai-settings";
export function subscribeAiSettings(listener:()=>void):()=>void {
  if(typeof window==="undefined")return ()=>{};
  window.addEventListener("storage",listener);window.addEventListener(SETTINGS_EVENT,listener);
  return ()=>{window.removeEventListener("storage",listener);window.removeEventListener(SETTINGS_EVENT,listener);};
}

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
  if(typeof window!=="undefined")window.dispatchEvent(new Event(SETTINGS_EVENT));
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
