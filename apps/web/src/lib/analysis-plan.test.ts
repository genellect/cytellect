import { describe, expect, it } from "vitest";
import { buildPlan, emptyPlan, planReceipt, type PlanAnswers } from "./analysis-plan";

const supported: PlanAnswers = { ...emptyPlan, region: "nucleus", signal: "gfp", input: "grayscale-2d", nuclearStain: "yes", background: "yes", acquisition: "matched", comparison: "independent", allocation: "biological" };

describe("scientific planning boundaries", () => {
  it("does not invent a recipe or independent units from unknown acquisition", () => {
    const p = buildPlan(emptyPlan);
    expect(p.recipe).toBeNull(); expect(p.statistics).toBe("undetermined");
    expect(p.questions.map(f => f.id)).toContain("independence");
  });
  it.each(["other", "unknown"] as const)("never relabels %s as GFP", signal => {
    expect(buildPlan({ ...supported, signal }).recipe).toBeNull();
  });
  it.each(["unknown", "rgb", "zt"] as const)("does not propose native measurement for %s pixels", input => {
    expect(buildPlan({ ...supported, input }).recipe).toBeNull();
  });
  it("retains acquisition and background questions even when a recipe exists", () => {
    const p = buildPlan({ ...supported, acquisition: "different", background: "no" });
    expect(p.recipe).toBe("gfp-nuclear-2d");
    expect(p.questions.map(f => f.id)).toEqual(expect.arrayContaining(["acquisition", "background"]));
  });
  it("does not use cell or field counts as independent units for either comparison", () => {
    for (const comparison of ["independent", "paired"] as const) {
      expect(buildPlan({ ...supported, comparison, allocation: "fields" }).statistics).toBe("undetermined");
    }
  });
  it("does not create nucleoli from GFP or a nuclear model", () => {
    expect(buildPlan({ ...supported, region: "nucleolus" }).recipe).toBeNull();
    const p = buildPlan({ ...supported, region: "nucleolus", signal: "ncl" });
    expect(p.recipe).toBe("ncl-native-2d"); expect(p.limits.map(f => f.id)).toContain("circularity");
  });
  it("exports an unadopted versioned plan with choices and primary references", () => {
    const p = planReceipt(supported);
    expect(p.status).toBe("planning-only-not-adopted");
    expect(p.answers).toEqual(supported);
    const ids = new Set(p.references.map(r => r.id));
    for (const f of [...p.guidance.questions, ...p.guidance.decisions, ...p.guidance.limits]) expect(ids.has(f.source)).toBe(true);
  });
});
