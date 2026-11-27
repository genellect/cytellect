/** Per-field progress of an analysis run (#284 W8, Issue 「測定中の表示」). A run's steps are field × target; the
 * researcher reads fields, so progress is counted in fields and each field has one state, shown the same way in the
 * field list and beside the image. Every value comes from the run's own steps; nothing is estimated. */
import type {WorkspaceRun} from "./api-adapter";

/** 準備中: requested, the run not yet accepted by the API. 待機: accepted, its steps not started. 検出中: a step started.
 * 候補を確認: every step done, the candidates wait for the researcher. 採用中: being adopted. 保存済み: adopted.
 * 失敗: a step failed or could not start because one it depends on failed. */
export type FieldProgress = "準備中" | "待機" | "検出中" | "候補を確認" | "採用中" | "保存済み" | "失敗";

const DONE = new Set(["succeeded", "reused"]);

/** The state of each field in the run (fields outside the run are absent). */
export function fieldProgress(run: Pick<WorkspaceRun, "state" | "steps">): Record<string, FieldProgress> {
  const byField = new Map<string, WorkspaceRun["steps"]>();
  for (const step of run.steps) byField.set(step.field_id, [...(byField.get(step.field_id) ?? []), step]);
  const result: Record<string, FieldProgress> = {};
  for (const [field, steps] of byField) {
    if (steps.some(step => step.state === "failed" || step.state === "blocked")) result[field] = "失敗";
    else if (steps.every(step => DONE.has(step.state))) result[field] = run.state === "adopted" ? "保存済み" : "候補を確認";
    else if (steps.every(step => step.state === "pending")) result[field] = "待機";
    else result[field] = "検出中";
  }
  return result;
}

/** The header line: fields done of the run's fields, then what is running and where (「視野 1/2 · BBBC007-a9：核を検出中」). */
export function progressLine(run: Pick<WorkspaceRun, "state" | "steps">, label: (field: string) => string, targetLabel: (target: string) => string): string {
  const states = fieldProgress(run), fields = Object.keys(states);
  const done = fields.filter(field => states[field] !== "待機" && states[field] !== "検出中").length;
  const failed = fields.filter(field => states[field] === "失敗").length;
  const running = run.steps.find(step => step.state === "queued");
  const parts = [`視野 ${done}/${fields.length}`];
  if (running) parts.push(`${label(running.field_id)}：${targetLabel(running.target)}を検出中`);
  if (failed) parts.push(`失敗：${failed} 視野`);
  return parts.join(" · ");
}

/** The fields whose steps all succeeded or were reused (they can be adopted although another field failed). */
export function completedFields(run: Pick<WorkspaceRun, "steps">): string[] {
  const states = fieldProgress({state: "failed", steps: run.steps});
  return Object.keys(states).filter(field => states[field] === "候補を確認");
}
