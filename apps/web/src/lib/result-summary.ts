import type { components } from "./generated";

/** Plain-language summary of a saved two-group comparison (requirements S-01–S-07).
 * Every number comes from the saved result; nothing is recalculated here. */
export type ComparisonEstimates = components["schemas"]["ComparisonEstimates"];
export interface SavedComparison {method?: string; p_value?: number | null; effect?: number | null; effect_name?: string | null}
/** `conclusion` is the one line a researcher reads first (S-01); `headline` states the measured difference. */
export interface ResultSummary {conclusion: string; headline: string; interval: string | null; test: string; runs: string | null; cautions: string[]}

const methodNames: Record<string, string> = {
  "paired t-test": "対応のある t 検定", "Welch t-test": "Welch の t 検定",
  "Mann–Whitney U": "Mann–Whitney U 検定", "Wilcoxon signed-rank": "Wilcoxon 符号付き順位検定",
};
const reasons: Record<string, string> = {
  rank_test: "順位に基づく検定では平均の差の信頼区間を出しません",
  too_few_pairs: "対が 2 つ未満のため計算できません", too_few_units: "実験単位が 2 つ未満の群があるため計算できません",
  zero_variance: "値のばらつきが 0 のため計算できません", nonpositive_values: "0 以下の値を含むため比は示しません",
  ratio_not_applicable: "この指標では比を示しません",
  inference_not_requested: "実験回の独立性が確認されていないため、差の信頼区間と検定は計算していません",
};

/** Three significant digits without trailing zeros or exponent notation for ordinary values. */
export function formatNumber(value: number): string {
  if (!Number.isFinite(value)) return "—";
  if (value === 0) return "0";
  const magnitude = Math.abs(value);
  if (magnitude >= 1e6 || magnitude < 1e-3) return value.toExponential(2);
  return String(Number(value.toPrecision(3)));
}

export function formatP(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "p は計算できません";
  return value < 0.001 ? "p < 0.001" : `p = ${Number(value.toPrecision(2))}`;
}

function words(metric: string): [string, string] {
  if (metric.startsWith("area") || metric.includes("_area")) return ["小さい", "大きい"];
  if (metric.includes("count") || metric.includes("density")) return ["少ない", "多い"];
  return ["低い", "高い"];
}

/** "小さい" → "小さく", for "小さくなりました". */
const adverb = (word: string) => word.replace(/い$/, "く");
/** Two significant digits: the conclusion states a size in plain words, the lines below give the saved values. */
const rough = (value: number) => String(Number(Math.abs(value).toPrecision(2)));
const signedPercent = (ratio: number) => `${ratio >= 1 ? "+" : "−"}${formatNumber(Math.abs(ratio - 1) * 100)}%`;

export function summarize(estimates: ComparisonEstimates, comparison: SavedComparison, metricLabel: string, unit: string): ResultSummary {
  const {control, treatment, scale, difference, ratio} = estimates;
  const [lower, higher] = words(estimates.metric);
  const paired = estimates.design === "paired";
  const percentagePoints = scale === "fraction";
  // Saved differences of a fraction are already in percentage points; unit values are fractions.
  const show = (value: number) => formatNumber(value);
  const showValue = (value: number) => percentagePoints ? formatNumber(value * 100) : formatNumber(value);
  const unitText = percentagePoints ? "ポイント" : scale === "log2" ? "log₂ 単位" : unit;
  let headline: string, interval: string | null = null;
  if (difference.estimate != null && difference.ci_low != null && difference.ci_high != null) {
    const direction = difference.estimate < 0 ? lower : difference.estimate > 0 ? higher : "同じ";
    headline = difference.estimate === 0
      ? `${metricLabel}は、${control}と${treatment}で平均の差がありませんでした。`
      : `${metricLabel}は、${control}に比べ${treatment}で ${show(Math.abs(difference.estimate))} ${unitText ? `${unitText} ` : ""}${direction}値でした。`;
    interval = `${paired ? "実験回ごとの差の平均" : "群の平均の差"}（${treatment} − ${control}）の 95% 信頼区間：${show(difference.ci_low)} 〜 ${show(difference.ci_high)} ${unitText}`;
    if (ratio.estimate != null && ratio.ci_low != null && ratio.ci_high != null)
      interval += `。対照に対する変化：${signedPercent(ratio.estimate)}（95% 信頼区間 ${signedPercent(ratio.ci_low)} 〜 ${signedPercent(ratio.ci_high)}、${paired ? "実験回ごとの比の幾何平均" : "幾何平均の比"}）`;
    if (difference.ci_low < 0 && difference.ci_high > 0) interval += "。信頼区間は 0 を含みます";
  } else {
    const groups = Object.fromEntries(estimates.groups.map(group => [group.condition, group]));
    const means = groups[control]?.mean != null && groups[treatment]?.mean != null
      ? `（実験単位の平均：${control} ${showValue(groups[control].mean!)}、${treatment} ${showValue(groups[treatment].mean!)}${percentagePoints ? "%" : ` ${unitText}`}）` : "";
    headline = `${metricLabel}を${control}と${treatment}で比べました${means}。`;
    interval = reasons[difference.unavailable_reason ?? ""] ?? null;
    if (comparison.effect != null && comparison.effect_name)
      interval = `${interval ? `${interval}。` : ""}効果量（${comparison.effect_name.includes("superiority") ? "優越確率" : "順位双列相関"}）：${formatNumber(comparison.effect)}`;
  }
  const n = paired ? `実験回 n = ${estimates.n_pairs ?? 0}（対）` : `実験単位 n = ${estimates.n_control}（${control}）、${estimates.n_treatment}（${treatment}）`;
  const descriptive = estimates.test === "none";
  const test = descriptive ? `${n}、検定なし（記述のみ）` : `${n}、${methodNames[comparison.method ?? ""] ?? comparison.method ?? "検定"} ${formatP(comparison.p_value)}`;
  let runs: string | null = null;
  if (paired && estimates.runs.length) {
    const down = estimates.runs.filter(run => run.difference < 0).length, up = estimates.runs.filter(run => run.difference > 0).length;
    runs = `${estimates.runs.length} 回中、${treatment}が${lower}回 ${down}、${higher}回 ${up}` + (estimates.runs.length - down - up ? `、同じ回 ${estimates.runs.length - down - up}` : "")
      + `。実験回ごとの差（${treatment} − ${control}）：` + estimates.runs.map(run => `${run.pair} ${run.difference > 0 ? "+" : run.difference < 0 ? "−" : ""}${show(Math.abs(run.difference))}`).join("、") + (unitText ? ` ${unitText}` : "");
  }
  const conclusion = conclude(estimates, comparison, metricLabel, unit, [lower, higher]);
  const cautions: string[] = [];
  const units = paired ? estimates.n_pairs ?? 0 : Math.min(estimates.n_control, estimates.n_treatment);
  if (descriptive) cautions.push("実験回が独立に行われたことが確認されていないため、この比較は記述です。差の大きさと向きは各回の値で確かめ、検定の結果としては扱わないでください。");
  else if (units < 5) cautions.push(`実験回が少ないため（n = ${units}）、p 値だけで結論せず、各回の値と信頼区間を合わせて確かめてください。p が 0.05 以上でも「変化がない」ことを示すものではありません。`);
  cautions.push(descriptive ? "n は記録した実験回の数です（独立性は未確認）。核や視野の数は n ではありません。" : "n は独立した実験回の数です。核や視野の数は n ではありません。");
  return {conclusion, headline, interval, test, runs, cautions};
}

/** The conclusion in one line (S-01, S-07): which way the treatment moved the metric, about how much, and whether
 * the runs agree. It is built only from the saved estimates. A result whose interval includes 0, or a rank test with
 * p ≥ 0.05, is "not clear", never "no change". Biological interpretation is not made here (roadmap: 結果の考察). */
function conclude(estimates: ComparisonEstimates, comparison: SavedComparison, metricLabel: string, unit: string, [lower, higher]: [string, string]): string {
  const {control, treatment, scale, difference, ratio, runs} = estimates;
  const sign = (value: number) => value < 0 ? -1 : value > 0 ? 1 : 0;
  const word = (direction: number) => direction < 0 ? lower : higher;
  // The direction the runs show by majority, or else the group means (no runs in an independent design).
  const means = Object.fromEntries(estimates.groups.map(group => [group.condition, group.mean]));
  const shown = runs.length ? sign(runs.reduce((total, run) => total + sign(run.difference), 0))
    : means[control] != null && means[treatment] != null ? sign(means[treatment]! - means[control]!) : 0;
  const agreeing = (direction: number) => runs.filter(run => sign(run.difference) === direction).length;
  const agreement = (direction: number) => !runs.length ? ""
    : agreeing(direction) === runs.length ? `。${runs.length} 回の実験すべてで同じ向きでした` : `。同じ向きだったのは ${runs.length} 回中 ${agreeing(direction)} 回です`;
  // About how much: a percent change where a ratio in the same direction is saved, otherwise the difference in its unit.
  const moved = (direction: number) => {
    const change = ratio.estimate != null && ratio.estimate > 0 && sign(ratio.estimate - 1) === direction ? ratio.estimate : null;
    if (change != null && change >= 2) return `約 ${rough(change)} 倍になりました`;
    const amount = change != null ? `約 ${rough((change - 1) * 100)}% `
      : difference.estimate == null ? ""
      : scale === "fraction" ? `約 ${rough(difference.estimate)} ポイント `
      : scale === "log2" ? `log₂ で約 ${rough(difference.estimate)} `
      : `約 ${rough(difference.estimate)}${unit ? ` ${unit}` : ""} `;
    return `${amount}${adverb(word(direction))}なりました`;
  };
  const unclear = (why: string) => `この実験では、${treatment}による${metricLabel}の違いははっきりしませんでした（${why}）。違いがないことを示すものではありません。`;
  if (estimates.test === "none") {
    // Descriptive: what the recorded runs show, never a test result.
    if (!shown) return `記録した実験回では、${treatment}と${control}で${metricLabel}の向きは揃いませんでした（記述のみ・検定なし）。`;
    if (!runs.length) return `実験単位の平均で、${treatment}の${metricLabel}は${control}より${word(shown)}値でした（記述のみ・検定なし）。`;
    // About how much, as the range of the saved per-run changes (no estimate is saved without a test).
    const span = (values: number[], text: (value: number) => string) => {
      const [low, high] = [Math.min(...values), Math.max(...values)];
      return low === high ? text(low) : `${text(low)}〜${text(high)}`;
    };
    const ratios = runs.every(run => run.ratio != null && run.ratio > 0) ? runs.map(run => run.ratio!) : null;
    const suffix = scale === "fraction" ? " ポイント" : scale === "log2" ? "（log₂）" : unit ? ` ${unit}` : "";
    if (agreeing(shown) === runs.length) {
      // All runs agree: the size alone, in the direction just stated.
      const size = ratios?.every(value => value >= 2) ? `の ${span(ratios, rough)} 倍の`
        : ratios ? `より ${span(ratios.map(value => Math.abs(value - 1) * 100), rough)}% ${word(shown)}`
        : `より ${span(runs.map(run => Math.abs(run.difference)), rough)}${suffix} ${word(shown)}`;
      return `記録した ${runs.length} 回の実験すべてで、${treatment}の${metricLabel}は${control}${size}値でした（記述のみ・検定なし）。`;
    }
    const signed = (value: number) => `${value > 0 ? "+" : value < 0 ? "−" : ""}${rough(value)}`;
    const change = ratios ? span(ratios.map(value => (value - 1) * 100), value => `${signed(value)}%`) : `${span(runs.map(run => run.difference), signed)}${suffix}`;
    return `記録した ${runs.length} 回の実験のうち ${agreeing(shown)} 回で、${treatment}の${metricLabel}は${control}より${word(shown)}値でした（実験回ごとの変化 ${change}、記述のみ・検定なし）。`;
  }
  if (difference.estimate != null && difference.ci_low != null && difference.ci_high != null) {
    const direction = sign(difference.estimate);
    if (!direction || difference.ci_low <= 0 && difference.ci_high >= 0) return unclear("差の 95% 信頼区間が 0 を含みます");
    return `${treatment}で、${metricLabel}が${control}に比べ${moved(direction)}${agreement(direction)}。`;
  }
  // Rank tests give no mean difference: the direction is stated only when p < 0.05.
  const p = comparison.p_value;
  if (p == null || !Number.isFinite(p) || p >= 0.05 || !shown) return unclear(formatP(p));
  return `${treatment}で、${metricLabel}が${control}に比べ${adverb(word(shown))}なりました（順位に基づく検定、${formatP(p)}）${agreement(shown)}。`;
}

export interface CountRow {condition: string; observations?: number; input_fields?: number; selected_fields?: number; samples?: number; experimental_units?: number}
export interface FieldLedgerRow {condition: string; experimental_unit: string; explicitly_excluded?: boolean; excluded_observations?: number; missing_observations?: number}
export interface Breakdown {groups: string[]; exclusions: string[]}
/** The saved ledger of nuclei whose nucleolus could not be established (Q-05). `perNucleus` when the values are
 * per nucleus (a compartment summary), so those nuclei are also among the field ledger's missing values. */
export interface UnresolvedNuclei {rows: Array<{condition: string | null; experimental_unit: string | null; missing: number}>; perNucleus: boolean}

/** What n is and what was left out, per group and per run (S-03, Q-02, Q-05); counts are the saved ones.
 * `noun` names one observation (核, 領域); null when the observations are fields themselves. */
export function breakdown(counts: CountRow[], ledger: FieldLedgerRow[], noun: string | null, unresolved: UnresolvedNuclei | null = null): Breakdown {
  const groups = counts.map(row => {
    const fields = row.input_fields != null && row.selected_fields !== row.input_fields ? `${row.selected_fields}（入力 ${row.input_fields}）` : `${row.selected_fields ?? 0}`;
    return `${row.condition}：実験回 ${row.experimental_units ?? 0}、試料 ${row.samples ?? 0}、視野 ${fields}` + (noun ? `、${noun} ${row.observations ?? 0}` : "");
  });
  const units = new Map<string, {condition: string; excluded: number; missing: number; fields: number; unresolved: number}>();
  const unit = (condition: string, experimental: string) => {
    const key = `${condition}\u0000${experimental}`;
    const entry = units.get(key) ?? {condition, excluded: 0, missing: 0, fields: 0, unresolved: 0};
    units.set(key, entry); return entry;
  };
  for (const row of ledger) {
    const entry = unit(row.condition, row.experimental_unit);
    entry.excluded += row.excluded_observations ?? 0; entry.missing += row.missing_observations ?? 0; entry.fields += row.explicitly_excluded ? 1 : 0;
  }
  for (const row of unresolved?.rows ?? []) if (row.missing) unit(row.condition ?? "", row.experimental_unit ?? "").unresolved += row.missing;
  const exclusions = [...units.entries()].map(([key, value]) => {
    // A per-nucleus value is missing for every unresolved nucleus; only the rest are other missing values.
    const other = unresolved?.perNucleus ? Math.max(0, value.missing - value.unresolved) : value.missing;
    const parts = [value.fields ? `除外した視野 ${value.fields}` : "", noun && value.excluded ? `除外した${noun} ${value.excluded}` : "",
      value.unresolved ? `核小体を確定できない核 ${value.unresolved}（欠測）` : "", other ? `${value.unresolved ? "ほかの" : ""}測定値の欠測 ${other}` : ""].filter(Boolean);
    return parts.length ? `${key.split("\u0000")[1]}：${parts.join("、")}` : "";
  }).filter(Boolean);
  return {groups, exclusions};
}
