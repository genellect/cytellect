import { describe, expect, it } from "vitest";
import { comparisonDefaults, emptyDesign, fieldMetadata, labelProblem, newId, readiness, type ExperimentDesign } from "./experiment-design";

// The same cases as tests/test_experiment_design.py, so both derivations agree.
const design = (overrides: Partial<ExperimentDesign> = {}): ExperimentDesign => ({
  version: "1.0.0", layout: "pair",
  groups: [{ id: "dmso", label: "DMSO" }, { id: "drug", label: "Drug 1 uM" }],
  control_group_id: "dmso",
  runs: [{ id: "r1", label: "2026-10-01", performed_on: "2026-10-01", acquired_on: "2026-10-02" },
    { id: "r2", label: "2026-10-08", performed_on: "2026-10-08", acquired_on: null }],
  independence_confirmed: true,
  fields: {
    f1: { group_id: "dmso", run_id: "r1", sample: null, acquired_on: null },
    f2: { group_id: "drug", run_id: "r1", sample: null, acquired_on: "2026-10-03" },
    f3: { group_id: "dmso", run_id: "r2", sample: "CS1", acquired_on: null },
    f4: { group_id: "dmso", run_id: "r2", sample: "CS2", acquired_on: null },
    f5: { group_id: "drug", run_id: "r2", sample: "CS1", acquired_on: null },
  },
  ...overrides,
});

describe("experiment design 1.0.0", () => {
  it("derives the metadata of the existing comparison ledgers", () => {
    const derived = fieldMetadata(design());
    expect(derived.f1).toEqual({ condition: "DMSO", experimental_unit: "2026-10-01 · DMSO", sample: "2026-10-01 · DMSO",
      acquisition_date: "2026-10-02", pair: "2026-10-01", repeat_length: null });
    expect(derived.f2.acquisition_date).toBe("2026-10-03");
    expect([derived.f3.sample, derived.f4.sample]).toEqual(["2026-10-08 · CS1", "2026-10-08 · CS2"]);
    expect(derived.f3.experimental_unit).toBe(derived.f4.experimental_unit);
    expect([derived.f5.sample, derived.f5.experimental_unit]).toEqual(["2026-10-08 · CS1", "2026-10-08 · Drug 1 uM"]);
    expect(derived.f3.acquisition_date).toBeNull();
    expect(Object.keys(derived)).toEqual(["f1", "f2", "f3", "f4", "f5"]);
  });

  it("has no pairs for one group and puts the treatment first for two", () => {
    const single = design({ layout: "single", groups: [{ id: "wt", label: "WT" }], control_group_id: null,
      fields: { f1: { group_id: "wt", run_id: "r1", sample: null, acquired_on: null } } });
    expect(fieldMetadata(single).f1.pair).toBeNull();
    expect(() => comparisonDefaults(single)).toThrow("experiment_design_control_required");
    expect(comparisonDefaults(design()).contrasts).toEqual([["Drug 1 uM", "DMSO"]]);
    expect(comparisonDefaults(design({ control_group_id: "drug" })).contrasts).toEqual([["DMSO", "Drug 1 uM"]]);
  });

  it("reports what blocks inference in the API order", () => {
    const incomplete = design({ independence_confirmed: false, fields: {
      f1: { group_id: "dmso", run_id: "r1", sample: null, acquired_on: null },
      f2: { group_id: "drug", run_id: "r1", sample: null, acquired_on: null },
      f3: { group_id: "dmso", run_id: "r2", sample: null, acquired_on: null } } });
    expect(readiness(incomplete, ["f1", "f2", "f3", "f9"])).toEqual([
      { code: "experiment_design_unassigned_fields", field_ids: ["f9"] },
      { code: "experiment_design_missing_combination", run_id: "r2", group_ids: ["drug"] },
      { code: "experiment_design_acquisition_dates_missing", field_ids: ["f3"] },
      { code: "experiment_design_independence_unconfirmed" },
    ]);
    expect(readiness(design(), ["f1", "f2", "f3", "f4", "f5"])).toEqual([
      { code: "experiment_design_acquisition_dates_missing", field_ids: ["f3", "f4", "f5"] }]);
    expect(readiness(emptyDesign("pair"), [])).toEqual([{ code: "experiment_design_no_runs" },
      { code: "experiment_design_independence_unconfirmed" }]);
  });

  it("checks labels and creates stable identifiers", () => {
    expect(labelProblem("ActD 1 µM")).toBeNull();
    expect(labelProblem(" WT")).not.toBeNull();
    expect(labelProblem("A · B")).not.toBeNull();
    expect(labelProblem("x".repeat(25))).not.toBeNull();
    expect(newId("2026-10-01", [])).toBe("2026-10-01");
    expect(newId("ActD 1 µM", [])).toBe("ActD-1-M");
    expect(newId("ActD 1", ["ActD-1"])).toBe("ActD-1-2");
    expect(newId("対照", [])).toBe("item");
  });
});

describe("editing an experiment design", () => {
  it("adds runs, assigns fields with samples and widens one group to two", async () => {
    const { addRun, assignFields, expandToPair, fieldsIn, removeRun, unassignField, updateRun } = await import("./experiment-design");
    let value = emptyDesign("single");
    value = addRun(value, { label: "2026-10-01", performed_on: "2026-10-01" });
    value = addRun(value, { label: "2026-10-01b" });
    expect(value.runs!.map(run => run.id)).toEqual(["2026-10-01", "2026-10-01b"]);
    value = assignFields(value, ["f1", "f2"], { group_id: "group-1", run_id: "2026-10-01", sample: "CS1" });
    value = updateRun(value, "2026-10-01", { acquired_on: "2026-10-02" });
    expect(fieldMetadata(value).f1).toMatchObject({ sample: "2026-10-01 · CS1", acquisition_date: "2026-10-02", pair: null });
    expect(() => removeRun(value, "2026-10-01")).toThrow("experiment_design_run_in_use");
    expect(removeRun(value, "2026-10-01b").runs).toHaveLength(1);
    const pair = expandToPair(value);
    expect(pair.layout).toBe("pair");
    expect(pair.control_group_id).toBe("group-1");
    expect(pair.groups.map(group => group.label)).toEqual(["群 1", "処理"]);
    expect(pair.fields).toEqual(value.fields);
    expect(fieldMetadata(pair).f1.pair).toBe("2026-10-01");
    expect(fieldsIn(pair, "group-1", "2026-10-01").map(([id]) => id)).toEqual(["f1", "f2"]);
    expect(Object.keys(unassignField(pair, "f1").fields!)).toEqual(["f2"]);
  });
});
