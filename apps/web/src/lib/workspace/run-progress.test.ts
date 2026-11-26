import {describe, expect, it} from "vitest";
import type {WorkspaceRun} from "./api-adapter";
import {completedFields, fieldProgress, progressLine} from "./run-progress";

type Step = WorkspaceRun["steps"][number];
const step = (field_id: string, target: Step["target"], state: Step["state"], extra: Partial<Step> = {}): Step =>
  ({field_id, target, state, revision_id: null, job_id: null, recipe: null, error: null, ...extra});
const labels = (id: string) => ({a9: "BBBC007-a9", f9620: "BBBC007-f9620"})[id] ?? id;
const targets = (target: string) => ({nuclei: "核", nucleoli: "核小体"})[target] ?? target;

describe("per-field progress of a run (#284 W8)", () => {
  it("counts fields, not steps: two fields with nuclei and nucleoli are 2, not 4", () => {
    const run = {state: "running" as const, steps: [step("a9", "nuclei", "succeeded"), step("a9", "nucleoli", "queued"), step("f9620", "nuclei", "pending"), step("f9620", "nucleoli", "pending")]};
    expect(fieldProgress(run)).toEqual({a9: "検出中", f9620: "待機"});
    expect(progressLine(run, labels, targets)).toBe("視野 0/2 · BBBC007-a9：核小体を検出中");
  });
  it("shows candidates to review, saved fields, reused steps and failures with their dependants", () => {
    const run = {state: "failed" as const, steps: [step("a9", "nuclei", "reused"), step("a9", "nucleoli", "succeeded"),
      step("f9620", "nuclei", "failed", {error: "x"}), step("f9620", "nucleoli", "blocked")]};
    expect(fieldProgress(run)).toEqual({a9: "候補を確認", f9620: "失敗"});
    expect(progressLine(run, labels, targets)).toBe("視野 2/2 · 失敗：1 視野");
    expect(completedFields(run)).toEqual(["a9"]);
    expect(fieldProgress({...run, state: "adopted", steps: run.steps.slice(0, 2)})).toEqual({a9: "保存済み"});
    // A step waiting for its background is done computing; adoption checks the background separately.
    expect(fieldProgress({state: "succeeded", steps: [step("a9", "nuclei", "succeeded", {background_pending: true})]})).toEqual({a9: "候補を確認"});
  });
});
