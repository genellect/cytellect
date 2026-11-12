import { describe, expect, it } from "vitest";
import { breakdown, formatNumber, formatP, summarize, tidy, type ComparisonEstimates } from "./result-summary";

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
  const none = interval(null, null, null, "inference_not_requested");
  const descriptive = (overrides: Partial<ComparisonEstimates> = {}) => base({test: "none", difference: none, ratio: none, ...overrides});

  it("states a paired t test as a heading, points and one basis line (RS-01–RS-04)", () => {
    const summary = summarize(base(), {method: "paired t-test", p_value: 0.012}, "核の面積", "µm²");
    expect(summary.heading).toBe("Drug で、核の面積が約 20% 縮小");
    expect(summary.points).toEqual([
      "3 回の実験すべてで縮小",
      "平均：100 → 80 µm²",
      "差（実験回ごとの差の平均）：−20 µm²、95% 信頼区間 −35〜−5（変化率 −20%、−30%〜−8%）",
      "実験回ごとの変化：r1 −20%、r2 −22%、r3 −18%",
    ]);
    expect(summary.basis).toEqual({label: "対応のある t 検定 · n = 3 回 · p = 0.012", reason: null, action: null});
    expect(summary.cautions).toEqual(["実験回が少ない（n = 3）。p 値だけで判断せず、各回の値と信頼区間を確認"]);
  });

  it("describes a comparison without confirmed independence by its runs, and states that once, in the basis (NT-01, NT-02)", () => {
    const summary = summarize(descriptive({metric: "nucleus_count", ratio: none,
      runs: [{pair: "Run1", control: 456, treatment: 80, difference: -376, ratio: 0.175}, {pair: "Run2", control: 347, treatment: 73, difference: -274, ratio: 0.21},
        {pair: "Run3", control: 450, treatment: 70.3, difference: -380, ratio: 0.156}],
      groups: [{condition: "Non-targeting", n: 3, mean: 418, sd: 1, ci_low: null, ci_high: null, unavailable_reason: "inference_not_requested"},
        {condition: "PLK1 KO", n: 3, mean: 74.4, sd: 1, ci_low: null, ci_high: null, unavailable_reason: "inference_not_requested"}],
      control: "Non-targeting", treatment: "PLK1 KO"}), {}, "視野あたりの核数", "個／視野");
    expect(summary.heading).toBe("PLK1 KO で、視野あたりの核数が 79〜84% 減少");
    expect(summary.points).toEqual(["3 回の実験すべてで減少", "平均：418 → 74.4 個／視野", "実験回ごとの変化：Run1 −82.5%、Run2 −79%、Run3 −84.4%"]);
    expect(summary.basis.label).toBe("記述統計 · n = 3 回");
    expect(summary.basis.reason).toBe("実験回の独立性が未確認のため、検定と信頼区間は算出していません。");
    expect(summary.basis.action).toBe("experiment");
    // The premise is not repeated in the heading, the points or the cautions.
    for (const text of [summary.heading, ...summary.points, ...summary.cautions]) expect(text).not.toMatch(/独立|検定なし|記述のみ|記述統計/);
    expect(JSON.stringify(summary)).not.toContain("p ");
  });

  it("names an exploratory threshold in the basis and offers no experiment edit for it", () => {
    const summary = summarize(descriptive({metric: "positive_fraction", scale: "fraction",
      runs: base().runs.map((run, index) => ({...run, difference: 10 + index, ratio: null}))}), {}, "陽性率", "", {exploratory: true});
    expect(summary.basis.label).toBe("記述統計（探索的なしきい値） · n = 3 回");
    expect(summary.basis.reason).toContain("陰性対照");
    expect(summary.basis.action).toBeNull();
    expect(summary.heading).toBe("Drug で、陽性率が 10〜12 ポイント上昇");
  });

  it("puts the missing nuclei in the basis line (RS-07)", () => {
    const summary = summarize(base(), {method: "paired t-test", p_value: 0.012}, "核の面積", "µm²", {missing: "核小体を確定できない核 3 / 158 は欠測"});
    expect(summary.basis.label).toBe("対応のある t 検定 · n = 3 回 · p = 0.012 · 核小体を確定できない核 3 / 158 は欠測");
  });

  it("uses percentage points for fractions and never a ratio", () => {
    // Saved fraction differences are in percentage points (comparison-estimates/1.0.0).
    const summary = summarize(base({metric: "positive_fraction", scale: "fraction", difference: interval(15, 5, 25),
      ratio: interval(null, null, null, "ratio_not_applicable"), groups: [{condition: "DMSO", n: 3, mean: 0.2, sd: 0.01, ci_low: null, ci_high: null, unavailable_reason: null},
        {condition: "Drug", n: 3, mean: 0.35, sd: 0.01, ci_low: null, ci_high: null, unavailable_reason: null}],
      runs: base().runs.map(run => ({...run, difference: 15, ratio: null}))}), {method: "paired t-test", p_value: 0.0004}, "陽性率", "");
    expect(summary.heading).toBe("Drug で、陽性率が約 15 ポイント上昇");
    expect(summary.points).toContain("平均：20% → 35%");
    expect(summary.points).toContain("差（実験回ごとの差の平均）：+15 ポイント、95% 信頼区間 +5〜+25");
    expect(summary.basis.label).toContain("p < 0.001");
  });

  it("reads a large change as a fold change", () => {
    expect(summarize(base({metric: "nucleolar_count", difference: interval(3, 1, 5), ratio: interval(2.4, 1.5, 3.8),
      runs: base().runs.map(run => ({...run, difference: 3, ratio: 2.4}))}), {method: "paired t-test", p_value: 0.02}, "核小体の数", "").heading)
      .toBe("Drug で、核小体の数が約 2.4 倍に増加");
    const folds = descriptive({metric: "nucleolar_count", runs: base().runs.map((run, index) => ({...run, difference: 50, ratio: 2 + index / 10}))});
    expect(summarize(folds, {}, "核小体の数", "").heading).toBe("Drug で、核小体の数が 2〜2.2 倍に増加");
  });

  it("says when the runs disagree, without hiding it behind the mean", () => {
    const partly = descriptive({runs: [...base().runs.slice(0, 2), {pair: "r3", control: 95, treatment: 99, difference: 4, ratio: 1.04}]});
    const summary = summarize(partly, {}, "核の面積", "µm²");
    expect(summary.heading).toBe("Drug による核の面積の変化は、実験回で不一致");
    expect(summary.points[0]).toBe("3 回中 2 回で縮小、1 回で拡大");
    expect(summary.points).toContain("実験回ごとの変化：r1 −20%、r2 −22%、r3 +4%");
    const mixed = base({runs: [...base().runs.slice(0, 2), {pair: "r3", control: 95, treatment: 99, difference: 4, ratio: 1.04}]});
    expect(summarize(mixed, {method: "paired t-test", p_value: 0.04}, "核の面積", "µm²").points[0]).toBe("3 回中 2 回で縮小、1 回で拡大");
  });

  it("calls an interval that includes zero, or a rank test with p ≥ 0.05, not clear, never no change (S-07)", () => {
    const unclear = summarize(base({difference: interval(-3, -10, 4), ratio: interval(0.97, 0.9, 1.04)}), {method: "paired t-test", p_value: 0.3}, "核の面積", "µm²");
    expect(unclear.heading).toBe("Drug による核の面積の違いは不明確");
    expect(unclear.points[0]).toBe("違いがないことを示すものではない");
    const rank = (p: number) => summarize(base({test: "wilcoxon", difference: interval(null, null, null, "rank_test"), ratio: interval(null, null, null, "rank_test")}),
      {method: "Wilcoxon signed-rank", p_value: p, effect: 1, effect_name: "matched rank-biserial correlation A minus B", group_a: "DMSO", group_b: "Drug"}, "核の面積", "µm²");
    expect(rank(0.25).heading).toBe("Drug による核の面積の違いは不明確");
    expect(rank(0.03).heading).toBe("Drug で、核の面積が縮小");
    expect(rank(0.03).basis.label).toBe("Wilcoxon 符号付き順位検定 · n = 3 回 · p = 0.03");
    expect(rank(0.03).points).toContain("効果量（順位双列相関）：1");
    expect(rank(0.03).notes).toContain("順位に基づく検定では、平均の差の信頼区間を出しません。");
    for (const text of [unclear.heading, ...unclear.points, rank(0.25).heading]) expect(text).not.toMatch(/変化がない|変わらな|差がない/);
  });

  it("takes a rank test's direction from its saved effect, not from the means or the runs' majority", () => {
    // One extreme treatment unit raises the treatment mean, while the saved Mann–Whitney effect says treatment is lower.
    const independent = base({design: "independent", test: "mann-whitney-u", n_pairs: null, runs: [],
      difference: interval(null, null, null, "rank_test"), ratio: interval(null, null, null, "rank_test"),
      groups: [{condition: "DMSO", n: 8, mean: 13.5, sd: 2, ci_low: null, ci_high: null, unavailable_reason: "rank_test"},
        {condition: "Drug", n: 8, mean: 128, sd: 350, ci_low: null, ci_high: null, unavailable_reason: "rank_test"}]});
    const heading = (effect: number | null, groupA = "Drug", groupB = "DMSO") => summarize(independent,
      {method: "Mann–Whitney U", p_value: 0.0104, effect, effect_name: "probability of superiority A over B (ties half)", group_a: groupA, group_b: groupB}, "核の面積", "µm²").heading;
    expect(heading(0.125)).toBe("Drug で、核の面積が縮小");
    // The same effect saved with the groups the other way round reads the same.
    expect(heading(0.875, "DMSO", "Drug")).toBe("Drug で、核の面積が縮小");
    // Without an effect whose groups are known, no direction is claimed.
    expect(heading(null)).toBe("Drug と DMSO で、核の面積の分布が異なる");
    expect(heading(0.125, "A", "B")).toBe("Drug と DMSO で、核の面積の分布が異なる");
  });

  it("describes independent designs by group sizes", () => {
    const summary = summarize(base({design: "independent", test: "welch-t", metric: "nucleus_count", n_pairs: null, n_treatment: 4, runs: [],
      difference: interval(-4, -7, -1), ratio: interval(null, null, null, "nonpositive_values")}), {method: "Welch t-test", p_value: 0.03}, "核数", "");
    expect(summary.heading).toBe("Drug で、核数が約 4 減少");
    expect(summary.basis.label).toBe("Welch の t 検定 · n = 3・4（実験単位） · p = 0.03");
    expect(summary.points.some(point => point.startsWith("差（群の平均の差）"))).toBe(true);
    expect(summary.notes).toContain("0 以下の値を含むため、比は示しません。");
  });

  it("gives the same text for the same saved result, with at most four points (C-02, C-03)", () => {
    const one = summarize(base(), {method: "paired t-test", p_value: 0.012}, "核の面積", "µm²");
    expect(summarize(base(), {method: "paired t-test", p_value: 0.012}, "核の面積", "µm²")).toEqual(one);
    expect(one.points.length).toBeLessThanOrEqual(4);
    // More than five runs leave the per-run line to the table.
    const many = base({runs: Array.from({length: 6}, (_, index) => ({pair: `r${index + 1}`, control: 100, treatment: 80, difference: -20, ratio: 0.8})), n_pairs: 6});
    expect(summarize(many, {method: "paired t-test", p_value: 0.01}, "核の面積", "µm²").points.some(point => point.startsWith("実験回ごと"))).toBe(false);
  });

  it("spaces names in Latin script from the Japanese around them", () => {
    expect(tidy("PLK1 KOで、核数がNon-targetingより少ない")).toBe("PLK1 KO で、核数が Non-targeting より少ない");
    expect(tidy("（ DMSO ）、 Drug")).toBe("（DMSO）、Drug");
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

  it("counts nuclei whose nucleolus is unresolved as missing for every metric, without counting them twice (Q-05)", () => {
    const unresolved = {rows: [{condition: "Untreated", experimental_unit: "R2 · Untreated", missing: 2}, {condition: "ActD", experimental_unit: "R1 · ActD", missing: 0}], perNucleus: false};
    // Per nucleoli region the unresolved nuclei have no rows; the field ledger holds only other missing values.
    expect(breakdown([], [{condition: "Untreated", experimental_unit: "R2 · Untreated", missing_observations: 1}], "核小体", unresolved).exclusions)
      .toEqual(["R2 · Untreated：核小体を確定できない核 2（欠測）、ほかの測定値の欠測 1"]);
    // Per nucleus the unresolved nuclei are themselves the missing values, so the same result reads the same.
    const perNucleus = {...unresolved, perNucleus: true};
    const ledger = [{condition: "Untreated", experimental_unit: "R2 · Untreated", missing_observations: 1}, {condition: "Untreated", experimental_unit: "R2 · Untreated", missing_observations: 1}];
    expect(breakdown([], ledger, "核", perNucleus).exclusions).toEqual(["R2 · Untreated：核小体を確定できない核 2（欠測）"]);
    expect(breakdown([], [], "核小体", unresolved).exclusions).toEqual(["R2 · Untreated：核小体を確定できない核 2（欠測）"]);
    expect(breakdown([], [], "核小体", {rows: [], perNucleus: false}).exclusions).toEqual([]);
  });
});
