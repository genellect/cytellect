import { describe, expect, it } from "vitest";
import { breakdown, formatNumber, formatP, summarize, type ComparisonEstimates } from "./result-summary";

// Saved-result shapes (comparison-estimates/1.0.0); the numbers are illustrative inputs to the text only.
const interval = (estimate: number | null, low: number | null, high: number | null, reason: string | null = null) =>
  ({estimate, ci_low: low, ci_high: high, confidence_level: 0.95, basis: estimate == null ? null : "basis", unavailable_reason: reason});
const base = (overrides: Partial<ComparisonEstimates> = {}): ComparisonEstimates => ({
  protocol: "comparison-estimates/1.0.0", direction: "treatment_minus_control", control: "DMSO", treatment: "Drug",
  design: "paired", test: "paired-t", metric: "area_um2", scale: "ratio", n_control: 3, n_treatment: 3, n_pairs: 3,
  difference: interval(-20, -35, -5), ratio: interval(0.8, 0.7, 0.92),
  groups: [{condition: "DMSO", n: 3, mean: 100, sd: 5, ci_low: 90, ci_high: 110, unavailable_reason: null},
    {condition: "Drug", n: 3, mean: 80, sd: 5, ci_low: 70, ci_high: 90, unavailable_reason: null}],
  runs: [{pair: "r1", control: 100, treatment: 80, difference: -20, ratio: 0.8}, {pair: "r2", control: 105, treatment: 82, difference: -23, ratio: 0.78},
    {pair: "r3", control: 95, treatment: 78, difference: -17, ratio: 0.82}],
  ...overrides,
});

describe("result summary", () => {
  it("states the direction, size, interval, change and n of a paired t test", () => {
    const summary = summarize(base(), {method: "paired t-test", p_value: 0.012}, "核の面積", "µm²");
    expect(summary.headline).toBe("核の面積は、DMSOに比べDrugで 20 µm² 小さい値でした。");
    expect(summary.interval).toBe("実験回ごとの差の平均（Drug − DMSO）の 95% 信頼区間：-35 〜 -5 µm²。対照に対する変化：−20%（95% 信頼区間 −30% 〜 −8%、実験回ごとの比の幾何平均）");
    expect(summary.test).toBe("実験回 n = 3（対）、対応のある t 検定 p = 0.012");
    expect(summary.runs).toBe("3 回中、Drugが小さい回 3、大きい回 0。実験回ごとの差（Drug − DMSO）：r1 −20、r2 −23、r3 −17 µm²");
    expect(summary.cautions[0]).toContain("n = 3");
  });

  it("describes a comparison without confirmed independence by its runs, never by a test", () => {
    const none = interval(null, null, null, "inference_not_requested");
    const summary = summarize(base({test: "none", difference: none, ratio: none,
      groups: base().groups.map(group => ({...group, ci_low: null, ci_high: null, unavailable_reason: "inference_not_requested"}))}), {}, "核の面積", "µm²");
    expect(summary.headline).toBe("核の面積をDMSOとDrugで比べました（実験単位の平均：DMSO 100、Drug 80 µm²）。");
    expect(summary.interval).toBe("実験回の独立性が確認されていないため、差の信頼区間と検定は計算していません");
    expect(summary.test).toBe("実験回 n = 3（対）、検定なし（記述のみ）");
    expect(summary.runs).toContain("r1 −20、r2 −23、r3 −17 µm²");
    expect(summary.cautions[0]).toContain("記述です");
    expect(JSON.stringify(summary)).not.toContain("p ");
  });

  it("uses percentage points for fractions and never a ratio", () => {
    // Saved fraction differences are in percentage points (comparison-estimates/1.0.0).
    const summary = summarize(base({metric: "positive_fraction", scale: "fraction", difference: interval(15, 5, 25),
      ratio: interval(null, null, null, "ratio_not_applicable")}), {method: "paired t-test", p_value: 0.0004}, "陽性の割合", "");
    expect(summary.headline).toBe("陽性の割合は、DMSOに比べDrugで 15 ポイント 高い値でした。");
    expect(summary.interval).toBe("実験回ごとの差の平均（Drug − DMSO）の 95% 信頼区間：5 〜 25 ポイント");
    expect(summary.test).toContain("p < 0.001");
  });

  it("flags intervals that include zero and does not call that no change", () => {
    const summary = summarize(base({difference: interval(-3, -10, 4), ratio: interval(0.97, 0.9, 1.04)}), {method: "paired t-test", p_value: 0.3}, "核の面積", "µm²");
    expect(summary.interval).toMatch(/信頼区間は 0 を含みます$/);
    expect(summary.cautions[0]).toContain("「変化がない」ことを示すものではありません");
  });

  it("reports rank tests with their effect size and no mean-difference interval", () => {
    const summary = summarize(base({test: "wilcoxon", difference: interval(null, null, null, "rank_test"), ratio: interval(null, null, null, "rank_test")}),
      {method: "Wilcoxon signed-rank", p_value: 0.25, effect: -1, effect_name: "matched rank-biserial correlation A minus B"}, "核の面積", "µm²");
    expect(summary.headline).toBe("核の面積をDMSOとDrugで比べました（実験単位の平均：DMSO 100、Drug 80 µm²）。");
    expect(summary.interval).toBe("順位に基づく検定では平均の差の信頼区間を出しません。効果量（順位双列相関）：-1");
    expect(summary.test).toBe("実験回 n = 3（対）、Wilcoxon 符号付き順位検定 p = 0.25");
  });

  it("describes independent designs by group sizes", () => {
    const summary = summarize(base({design: "independent", test: "welch-t", n_pairs: null, n_treatment: 4, runs: []}), {method: "Welch t-test", p_value: 0.04}, "核数", "");
    expect(summary.test).toBe("実験単位 n = 3（DMSO）、4（Drug）、Welch の t 検定 p = 0.04");
    expect(summary.runs).toBeNull();
    expect(summary.interval).toContain("群の平均の差");
  });

  it("formats numbers and p values", () => {
    expect([formatNumber(1234.5), formatNumber(0.012345), formatNumber(-0.5)]).toEqual(["1230", "0.0123", "-0.5"]);
    expect([formatP(0.0004), formatP(0.0456), formatP(null)]).toEqual(["p < 0.001", "p = 0.046", "p は計算できません"]);
  });
});

describe("result breakdown", () => {
  it("names runs, samples, fields and observations per group, and exclusions per run", () => {
    const counts = [{condition: "DMSO", observations: 120, input_fields: 3, selected_fields: 3, samples: 3, experimental_units: 3},
      {condition: "Drug", observations: 40, input_fields: 4, selected_fields: 3, samples: 3, experimental_units: 3}];
    const ledger = [{condition: "Drug", experimental_unit: "R1 · Drug", explicitly_excluded: true, excluded_observations: 0, missing_observations: 0},
      {condition: "Drug", experimental_unit: "R2 · Drug", excluded_observations: 2, missing_observations: 1},
      {condition: "DMSO", experimental_unit: "R1 · DMSO", excluded_observations: 0, missing_observations: 0}];
    const result = breakdown(counts, ledger, "核");
    expect(result.groups).toEqual(["DMSO：実験回 3、試料 3、視野 3、核 120", "Drug：実験回 3、試料 3、視野 3（入力 4）、核 40"]);
    expect(result.exclusions).toEqual(["R1 · Drug：除外した視野 1", "R2 · Drug：除外した核 2、測定値の欠測 1"]);
    expect(breakdown(counts, [], null).groups[0]).toBe("DMSO：実験回 3、試料 3、視野 3");
  });
});
