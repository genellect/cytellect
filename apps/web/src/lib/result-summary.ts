import type { components } from "./generated";

/** The summary of a saved two-group comparison (requirements RS-01–RS-08, NT-01–NT-07; S-01–S-07).
 * Every number comes from the saved result; nothing is recalculated here, and no model writes it. */
export type ComparisonEstimates = components["schemas"]["ComparisonEstimates"];
export interface SavedComparison {method?: string; p_value?: number | null; effect?: number | null; effect_name?: string | null; group_a?: string; group_b?: string}
/** What the result's statements rest on (RS-04, NT-01): one line, with why a test was not made and where to fix it. */
export interface ResultBasis {label: string; reason: string | null; action: "experiment" | null}
/** `heading`: what moved, which way and about how much (RS-02). `points`: up to four lines of values (RS-03).
 * `basis`: the method, n and p in one line, the only place that states the premises (RS-04, NT-01).
 * `cautions`: what changes how this result is read, shown always; `notes`: the rest, folded (NT-05). */
export interface ResultSummary {heading: string; points: string[]; basis: ResultBasis; cautions: string[]; notes: string[]}
export interface SummaryOptions {
  /** The positivity was judged by a threshold no negative control fixed (M22). */
  exploratory?: boolean;
  /** "核小体を確定できない核 3 / 158 は欠測" (RS-07). */
  missing?: string | null;
}

const methodNames: Record<string, string> = {
  "paired t-test": "対応のある t 検定", "Welch t-test": "Welch の t 検定",
  "Mann–Whitney U": "Mann–Whitney U 検定", "Wilcoxon signed-rank": "Wilcoxon 符号付き順位検定",
};
const reasons: Record<string, string> = {
  rank_test: "順位に基づく検定では、平均の差の信頼区間を出しません。",
  too_few_pairs: "対が 2 つ未満のため、差の信頼区間を計算できません。", too_few_units: "実験単位が 2 つ未満の群があるため、差の信頼区間を計算できません。",
  zero_variance: "値のばらつきが 0 のため、差の信頼区間を計算できません。", nonpositive_values: "0 以下の値を含むため、比は示しません。",
  ratio_not_applicable: "この指標では比を示しません。",
};
/** Why a comparison is descriptive (NT-01): the one sentence behind 「記述統計」. */
const DESCRIPTIVE_REASON = "実験回が独立に行われたことが確認されていないため、検定と信頼区間は計算せず、実験回ごとの値と差を示しています。";
const EXPLORATORY_REASON = "陰性対照で決めたしきい値ではない（手動・Otsu）ため、陽性率と陽性の核数は、検定と信頼区間を計算せず、実験回ごとの値と差を示しています。";

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

/** The change a metric shows, as a noun (decrease, increase) for the heading and the points. */
function nouns(metric: string): [string, string] {
  if (metric.startsWith("area") || metric.includes("_area")) return ["縮小", "拡大"];
  if (metric.includes("count") || metric.includes("density")) return ["減少", "増加"];
  if (metric.includes("eccentricity")) return ["低下", "上昇"];
  if (metric.includes("fraction") || metric.includes("ratio") || metric.startsWith("log2")) return ["低下", "上昇"];
  return ["低下", "上昇"];
}

/** Two significant digits: the heading states a size in plain words, the points give the saved values. */
const rough = (value: number) => String(Number(Math.abs(value).toPrecision(2)));
const signed = (value: number, text: (value: number) => string = formatNumber) => `${value > 0 ? "+" : value < 0 ? "−" : ""}${text(Math.abs(value))}`;
const signedPercent = (ratio: number) => `${signed((ratio - 1) * 100)}%`;
const span = (values: number[], text: (value: number) => string) => {
  const [low, high] = [Math.min(...values), Math.max(...values)];
  return low === high ? text(low) : `${text(low)}〜${text(high)}`;
};

/** Japanese with names in Latin script: a space between a name and the Japanese around it, none before
 * punctuation (「PLK1 KO で」, 「Non-targeting より」). */
export function tidy(text: string): string {
  return text
    .replace(/([A-Za-z0-9µ%)）])(?=[\p{sc=Hiragana}\p{sc=Katakana}\p{sc=Han}])/gu, "$1 ")
    .replace(/([\p{sc=Hiragana}\p{sc=Katakana}\p{sc=Han}])(?=[A-Za-z0-9µ(])/gu, "$1 ")
    .replace(/ +/g, " ").replace(/ ([、。：）〜])/g, "$1").replace(/([（：〜、]) /g, "$1").trim();
}

export function summarize(estimates: ComparisonEstimates, comparison: SavedComparison, metricLabel: string, unit: string, options: SummaryOptions = {}): ResultSummary {
  const {control, treatment, scale, difference, ratio, runs} = estimates;
  const [lower, higher] = nouns(estimates.metric);
  const paired = estimates.design === "paired";
  const fraction = scale === "fraction";
  const descriptive = estimates.test === "none";
  // Saved differences of a fraction are already in percentage points; unit values are fractions.
  const unitText = fraction ? "ポイント" : scale === "log2" ? "log₂ 単位" : unit;
  const withUnit = (text: string) => unitText ? `${text} ${unitText}` : text;
  const sign = (value: number) => value < 0 ? -1 : value > 0 ? 1 : 0;
  const noun = (direction: number) => direction < 0 ? lower : higher;

  // The direction the runs show by majority, or else the group means (no runs in an independent design).
  const means = Object.fromEntries(estimates.groups.map(group => [group.condition, group.mean]));
  const shown = runs.length ? sign(runs.reduce((total, run) => total + sign(run.difference), 0))
    : means[control] != null && means[treatment] != null ? sign(means[treatment]! - means[control]!) : 0;
  const count = (direction: number) => runs.filter(run => sign(run.difference) === direction).length;

  // Heading (RS-02).
  const ratios = runs.length && runs.every(run => run.ratio != null && run.ratio > 0) ? runs.map(run => run.ratio!) : null;
  const suffix = fraction ? " ポイント" : scale === "log2" ? "（log₂）" : unit ? ` ${unit}` : "";
  const moved = (direction: number, size: string) => `${treatment}で、${metricLabel}が${size}${noun(direction)}`;
  const unclear = `${treatment}による${metricLabel}の違いは不明確`;
  let heading: string, isUnclear = false;
  if (descriptive) {
    if (!shown || (runs.length && count(shown) < runs.length)) heading = runs.length ? `${treatment}による${metricLabel}の変化は、実験回で不一致` : unclear;
    else if (!runs.length) heading = moved(shown, "");
    else if (ratios?.every(value => value >= 2)) heading = `${treatment}で、${metricLabel}が ${span(ratios, rough)} 倍に${noun(shown)}`;
    else if (ratios) heading = moved(shown, `${span(ratios.map(value => Math.abs(value - 1) * 100), rough)}%`);
    else heading = moved(shown, `${span(runs.map(run => Math.abs(run.difference)), rough)}${suffix}`);
  } else if (difference.estimate != null && difference.ci_low != null && difference.ci_high != null) {
    const direction = sign(difference.estimate);
    if (!direction || difference.ci_low <= 0 && difference.ci_high >= 0) {heading = unclear; isUnclear = true;}
    else {
      const change = ratio.estimate != null && ratio.estimate > 0 && sign(ratio.estimate - 1) === direction ? ratio.estimate : null;
      heading = change != null && change >= 2 ? `${treatment}で、${metricLabel}が約 ${rough(change)} 倍に${noun(direction)}`
        : moved(direction, change != null ? `約 ${rough((change - 1) * 100)}%`
          : fraction ? `約 ${rough(difference.estimate)} ポイント`
          : scale === "log2" ? `log₂ で約 ${rough(difference.estimate)}`
          : `約 ${rough(difference.estimate)}${unit ? ` ${unit}` : ""}`);
    }
  } else {
    // Rank tests give no mean difference: the direction is the saved effect's (group A against B, turned to
    // treatment against control), stated only when p < 0.05; the runs' majority or the means never set it.
    const p = comparison.p_value;
    const centre = comparison.effect_name?.includes("superiority") ? 0.5 : comparison.effect_name?.includes("rank-biserial") ? 0 : null;
    const facing = comparison.group_a === treatment && comparison.group_b === control ? 1 : comparison.group_a === control && comparison.group_b === treatment ? -1 : 0;
    const ranked = comparison.effect != null && Number.isFinite(comparison.effect) && centre != null ? sign(comparison.effect - centre) * facing : 0;
    if (p == null || !Number.isFinite(p) || p >= 0.05) {heading = unclear; isUnclear = true;}
    else heading = ranked ? moved(ranked, "") : `${treatment}と${control}で、${metricLabel}の分布が異なる`;
  }

  // Points (RS-03), at most four.
  const points: string[] = [];
  if (isUnclear) points.push("違いがないことを示すものではない");
  if (runs.length) {
    const down = count(-1), up = count(1), same = runs.length - down - up;
    points.push(down === runs.length || up === runs.length ? `${runs.length} 回の実験すべてで${noun(up ? 1 : -1)}`
      : [`${runs.length} 回中 ${down} 回で${lower}`, up ? `${up} 回で${higher}` : "", same ? `${same} 回で変化なし` : ""].filter(Boolean).join("、"));
  }
  if (means[control] != null && means[treatment] != null) {
    const value = (mean: number) => fraction ? `${formatNumber(mean * 100)}%` : formatNumber(mean);
    points.push(`平均：${value(means[control]!)} → ${value(means[treatment]!)}${!fraction && unit ? ` ${unit}` : ""}`);
  }
  if (difference.estimate != null && difference.ci_low != null && difference.ci_high != null) {
    let line = `差（${paired ? "実験回ごとの差の平均" : "群の平均の差"}）：${withUnit(signed(difference.estimate))}、95% 信頼区間 ${signed(difference.ci_low)}〜${signed(difference.ci_high)}`;
    if (ratio.estimate != null && ratio.ci_low != null && ratio.ci_high != null)
      line += `（変化率 ${signedPercent(ratio.estimate)}、${signedPercent(ratio.ci_low)}〜${signedPercent(ratio.ci_high)}）`;
    points.push(line);
  } else if (comparison.effect != null && comparison.effect_name)
    points.push(`効果量（${comparison.effect_name.includes("superiority") ? "優越確率" : "順位双列相関"}）：${formatNumber(comparison.effect)}`);
  if (runs.length && runs.length <= 5)
    points.push(`実験回ごとの${ratios ? "変化" : "差"}：${runs.map(run => `${run.pair} ${ratios ? signedPercent(run.ratio!) : signed(run.difference)}`).join("、")}${ratios ? "" : suffix}`);

  // Basis (RS-04, NT-01): the only place that states the premises.
  const n = paired ? `n = ${estimates.n_pairs ?? 0} 回` : `n = ${estimates.n_control}・${estimates.n_treatment}（実験単位）`;
  const method = descriptive ? (options.exploratory ? "記述統計（探索的なしきい値）" : "記述統計") : methodNames[comparison.method ?? ""] ?? comparison.method ?? "検定";
  const parts = [method, n, descriptive ? "" : formatP(comparison.p_value), options.missing ?? ""].filter(Boolean);
  const basis: ResultBasis = {label: parts.join(" · "), reason: descriptive ? (options.exploratory ? EXPLORATORY_REASON : DESCRIPTIVE_REASON) : null,
    action: descriptive && !options.exploratory ? "experiment" : null};

  // Cautions that change how this result is read; the rest is folded (NT-05).
  const cautions: string[] = [], notes: string[] = [];
  const units = paired ? estimates.n_pairs ?? 0 : Math.min(estimates.n_control, estimates.n_treatment);
  if (!descriptive && units < 5) cautions.push(`実験回が少ない（n = ${units}）。p 値だけで判断せず、各回の値と信頼区間を確認`);
  for (const why of new Set([difference.unavailable_reason, ratio.unavailable_reason].map(reason => reasons[reason ?? ""]).filter(Boolean))) notes.push(why);
  notes.push(descriptive ? "n は記録した実験回の数です。核や視野の数は n ではありません。" : "n は独立した実験回の数です。核や視野の数は n ではありません。");
  return {heading: tidy(heading), points: points.slice(0, 4).map(tidy), basis: {...basis, label: tidy(basis.label)}, cautions, notes};
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
