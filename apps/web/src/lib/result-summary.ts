import type { components } from "./generated";

/** Plain-language summary of a saved two-group comparison (requirements S-01–S-07).
 * Every number comes from the saved result; nothing is recalculated here. */
export type ComparisonEstimates = components["schemas"]["ComparisonEstimates"];
export interface SavedComparison {method?: string; p_value?: number | null; effect?: number | null; effect_name?: string | null}
export interface ResultSummary {headline: string; interval: string | null; test: string; runs: string | null; cautions: string[]}

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
  const cautions: string[] = [];
  const units = paired ? estimates.n_pairs ?? 0 : Math.min(estimates.n_control, estimates.n_treatment);
  if (descriptive) cautions.push("実験回が独立に行われたことが確認されていないため、この比較は記述です。差の大きさと向きは各回の値で確かめ、検定の結果としては扱わないでください。");
  else if (units < 5) cautions.push(`実験回が少ないため（n = ${units}）、p 値だけで結論せず、各回の値と信頼区間を合わせて確かめてください。p が 0.05 以上でも「変化がない」ことを示すものではありません。`);
  cautions.push("n は独立した実験回の数です。核や視野の数は n ではありません。");
  return {headline, interval, test, runs, cautions};
}

export interface CountRow {condition: string; observations?: number; input_fields?: number; selected_fields?: number; samples?: number; experimental_units?: number}
export interface FieldLedgerRow {condition: string; experimental_unit: string; explicitly_excluded?: boolean; excluded_observations?: number; missing_observations?: number}
export interface Breakdown {groups: string[]; exclusions: string[]}

/** What n is and what was left out, per group and per run (S-03, Q-02); counts are the saved ones.
 * `noun` names one observation (核, 領域); null when the observations are fields themselves. */
export function breakdown(counts: CountRow[], ledger: FieldLedgerRow[], noun: string | null): Breakdown {
  const groups = counts.map(row => {
    const fields = row.input_fields != null && row.selected_fields !== row.input_fields ? `${row.selected_fields}（入力 ${row.input_fields}）` : `${row.selected_fields ?? 0}`;
    return `${row.condition}：実験回 ${row.experimental_units ?? 0}、試料 ${row.samples ?? 0}、視野 ${fields}` + (noun ? `、${noun} ${row.observations ?? 0}` : "");
  });
  const units = new Map<string, {condition: string; excluded: number; missing: number; fields: number}>();
  for (const row of ledger) {
    const key = `${row.condition}\u0000${row.experimental_unit}`;
    const entry = units.get(key) ?? {condition: row.condition, excluded: 0, missing: 0, fields: 0};
    entry.excluded += row.excluded_observations ?? 0; entry.missing += row.missing_observations ?? 0; entry.fields += row.explicitly_excluded ? 1 : 0;
    units.set(key, entry);
  }
  const exclusions = [...units.entries()].filter(([, value]) => value.excluded || value.missing || value.fields).map(([key, value]) => {
    const parts = [value.fields ? `除外した視野 ${value.fields}` : "", noun && value.excluded ? `除外した${noun} ${value.excluded}` : "", value.missing ? `測定値の欠測 ${value.missing}` : ""].filter(Boolean);
    return `${key.split("\u0000")[1]}：${parts.join("、")}`;
  });
  return {groups, exclusions};
}
