import { describe, expect, it } from "vitest";
import { assignStratum, declareStrata, emptyDesign, type PlainExperimentDesign as ExperimentDesign } from "./experiment-design";
import { adoptedNuclei, analysedRuns, experimentHeading, statusChips, summaryCounts } from "./experiment-summary";

const design = (overrides: Partial<ExperimentDesign> = {}): ExperimentDesign => ({
  version: "1.0.0", layout: "pair",
  groups: [{ id: "drug", label: "Drug 1 uM" }, { id: "dmso", label: "DMSO" }],
  control_group_id: "dmso",
  runs: [{ id: "r1", label: "Rep1", performed_on: null, acquired_on: "2021-12-01" },
    { id: "r2", label: "Rep2", performed_on: null, acquired_on: "2021-12-01" }],
  independence_confirmed: false,
  fields: {
    f1: { group_id: "dmso", run_id: "r1", sample: null, acquired_on: null },
    f2: { group_id: "drug", run_id: "r1", sample: null, acquired_on: null },
    f3: { group_id: "dmso", run_id: "r2", sample: null, acquired_on: null },
    f4: { group_id: "drug", run_id: "r2", sample: null, acquired_on: null },
  },
  ...overrides,
});
const fields = (nuclei: Array<number | null>) => nuclei.map((value, index) => ({ id: `f${index + 1}`, nuclei: value }));

describe("experiment heading", () => {
  it("names the two groups, control first", () => {
    expect(experimentHeading(design())).toBe("2 群の比較：DMSO × Drug 1 uM");
  });
  it("names the one group of a single-group design", () => {
    const single = { ...emptyDesign("single"), groups: [{ id: "group-1", label: "U2OS" }] };
    expect(experimentHeading(single)).toBe("1 群：U2OS");
  });
});

describe("status chips", () => {
  it("marks a complete design and the unconfirmed independence that limits it to description", () => {
    expect(statusChips(design(), fields([1, 2, 3, 4])).map(chip => [chip.label, chip.value, chip.ok])).toEqual([
      ["実験回", "2", true], ["群", "2", true], ["視野", "4 / 4", true], ["撮影条件", "未確認", false], ["独立性", "未確認 → 検定なし", false]]);
    expect(statusChips(design({ independence_confirmed: true }), fields([1, 2, 3, 4])).at(-1)).toMatchObject({ value: "確認済み", ok: true });
  });
  it("marks the acquisition statement declared in 実験 (genellect/cytellect#257 decisions 11 and 13)", () => {
    const acquisition = (value: ExperimentDesign, recorded = false) => statusChips(value, fields([1, 2, 3, 4]), recorded).find(chip => chip.key === "acquisition");
    expect(acquisition(design({ acquisition_confirmed: true }))).toMatchObject({ label: "撮影条件", value: "確認済み", ok: true });
    expect(acquisition(design())).toMatchObject({ value: "未確認", ok: false });
    // A recorded public design states nothing about acquisition: no mark is made up for it.
    expect(acquisition(design(), true)).toBeUndefined();
    expect(acquisition(design({ acquisition_confirmed: true }), true)).toMatchObject({ value: "確認済み", ok: true });
  });
  it("marks unassigned fields, a run without both groups and a missing control", () => {
    const missing = design({ control_group_id: null, fields: { f1: { group_id: "dmso", run_id: "r1", sample: null, acquired_on: null } } });
    const chips = Object.fromEntries(statusChips(missing, fields([1, 2])).map(chip => [chip.key, chip]));
    expect(chips.fields).toMatchObject({ value: "1 / 2", ok: false });
    expect(chips.runs).toMatchObject({ value: "0 / 2", ok: false });
    // Each run outside n names what it lacks, as 項目：値.
    expect(chips["run:r1"]).toMatchObject({ label: "Rep1", value: "Drug 1 uM なし", ok: false });
    expect(chips["run:r2"]).toMatchObject({ label: "Rep2", value: "画像なし", ok: false });
    expect(chips.groups.ok).toBe(false);
  });
  it("marks fields without a stratum in a stratified design", () => {
    const declared = declareStrata(design(), "細胞株", ["U2OS"]);
    const stratified = assignStratum(declared, ["f2", "f3", "f4"], declared.strata[0].id);
    const chips = Object.fromEntries(statusChips(stratified, fields([1, 2, 3, 4])).map(chip => [chip.key, chip]));
    expect(statusChips(assignStratum(stratified, ["f1"], declared.strata[0].id), fields([1, 2, 3, 4])).find(chip => chip.key === "fields")?.ok).toBe(true);
    expect(chips.fields).toMatchObject({ value: "4 / 4", ok: false });
  });
  it("leaves independence out of a single-group design and marks a design without runs", () => {
    const chips = statusChips(emptyDesign("single"), []);
    expect(chips.map(chip => chip.key)).toEqual(["runs", "groups", "fields"]);
    expect(chips.find(chip => chip.key === "runs")).toMatchObject({ value: "0", ok: false });
    expect(chips.find(chip => chip.key === "fields")).toMatchObject({ value: "0 / 0", ok: false });
  });
});

describe("n: the runs that can be analysed", () => {
  // Rep1 is split by cell line: the control only in line A, the treatment only in line B.
  const split = () => {
    const declared = declareStrata(design(), "細胞株", ["A", "B"]);
    const [a, b] = declared.strata.map(stratum => stratum.id);
    return { declared, a, b, stratified: assignStratum(assignStratum(declared, ["f1", "f3", "f4"], a), ["f2"], b) };
  };
  it("does not count a run whose groups are only in different strata", () => {
    const { stratified, a } = split();
    expect(analysedRuns(stratified, fields([1, 2, 3, 4]))).toMatchObject({ counted: ["r2"], declared: 2, lacking: [{ runId: "r1", label: "Rep1", value: "同じ層の対なし" }] });
    const onlySplit = { ...stratified, runs: stratified.runs!.slice(0, 1), fields: { f1: stratified.fields!.f1, f2: stratified.fields!.f2 } };
    expect(summaryCounts(onlySplit, fields([1, 2])).runs).toBe(0);
    expect(statusChips(onlySplit, fields([1, 2]))[0]).toMatchObject({ label: "実験回", value: "0 / 1", ok: false });
    // Both groups within the same stratum: the run counts.
    expect(analysedRuns(assignStratum(stratified, ["f2"], a), fields([1, 2, 3, 4])).counted).toEqual(["r1", "r2"]);
  });
  it("does not count a run whose treated fields are not measured", () => {
    const runs = analysedRuns(design(), fields([1, null, 3, 4]));
    expect(runs.counted).toEqual(["r2"]);
    expect(runs.lacking).toEqual([{ runId: "r1", label: "Rep1", value: "Drug 1 uM 未測定" }]);
    expect(statusChips(design(), fields([1, null, 3, 4])).slice(0, 2).map(chip => [chip.label, chip.value, chip.ok])).toEqual([["実験回", "1 / 2", false], ["Rep1", "Drug 1 uM 未測定", false]]);
    expect(analysedRuns(design(), fields([null, null, 3, 4])).lacking[0].value).toBe("未測定");
  });
  it("counts a run with both groups measured, the same n in the chip, the figure and the table", () => {
    expect(analysedRuns(design(), fields([1, 2, 3, 4]))).toEqual({ counted: ["r1", "r2"], declared: 2, lacking: [] });
    expect(summaryCounts(design(), fields([1, 2, 3, 4])).runs).toBe(2);
    expect(statusChips(design(), fields([1, 2, 3, 4]))[0]).toMatchObject({ value: "2", ok: true });
    // A field measured for another region (no nucleus count) is measured: it counts in n, not in the nuclei.
    const cells = [{ id: "f1", measured: true }, { id: "f2", measured: true }, ...fields([0, 0, 3, 4]).slice(2)];
    expect(summaryCounts(design(), cells)).toEqual({ nuclei: null, fields: 4, runs: 2 });
  });
});

describe("summary counts", () => {
  it("adds the adopted nuclei of the placed, included fields", () => {
    expect(summaryCounts(design(), [...fields([10, 18, 9, 12]), { id: "f5", nuclei: 7 }])).toEqual({ nuclei: 49, fields: 4, runs: 2 });
    expect(summaryCounts(design(), [{ id: "f1", nuclei: 10 }, { id: "f2", nuclei: 18, excluded: true }, ...fields([0, 0, 9, 12]).slice(2)])).toEqual({ nuclei: 31, fields: 3, runs: 1 });
  });
  it("counts as n only the runs with values in every group", () => {
    const halfRun = { f1: { group_id: "dmso", run_id: "r1", sample: null, acquired_on: null }, f2: { group_id: "drug", run_id: "r1", sample: null, acquired_on: null },
      f3: { group_id: "dmso", run_id: "r2", sample: null, acquired_on: null } };
    expect(summaryCounts(design({ fields: halfRun }), fields([1, 2, 3]))).toEqual({ nuclei: 6, fields: 3, runs: 1 });
    // A run whose only treated field is excluded makes no pair either.
    expect(summaryCounts(design(), [...fields([1, 2, 3]), { id: "f4", nuclei: 4, excluded: true }]).runs).toBe(1);
    const single = { ...emptyDesign("single"), runs: [{ id: "r1", label: "Rep1", performed_on: null, acquired_on: null }, { id: "r2", label: "Rep2", performed_on: null, acquired_on: null }],
      fields: { f1: { group_id: "group-1", run_id: "r1", sample: null, acquired_on: null } } };
    expect(summaryCounts(single, fields([5])).runs).toBe(1);
  });
  it("never shows a partial nucleus count", () => {
    expect(summaryCounts(design(), fields([10, null, 9, 12]))).toEqual({ nuclei: null, fields: 4, runs: 1 });
    expect(summaryCounts(design({ fields: {} }), fields([10]))).toEqual({ nuclei: null, fields: 0, runs: 0 });
  });
  it("counts each region once and leaves out the regions a correction excluded", () => {
    const regions = [{ id: 1 }, { id: 2 }, { id: 2 }, { id: 3 }];
    expect(adoptedNuclei({ masks: { regions } })).toBe(3);
    expect(adoptedNuclei({ masks: { regions }, exclusions: [{ region_id: 3 }, { region_id: null }] })).toBe(2);
  });
});
