import type {ReviewTarget} from "./review-preview";

/** Measurements grouped by the change a researcher asks about, named as nouns (UC-01); the statistics panel lists
 * them by subject and observation unit (SUBJECT_METRICS, requirements M-01).
 * Labels and definitions describe the saved common implementation; nothing is computed here. */
export interface MetricChoice {
  id: string; label: string;
  /** What is measured and on which region; what one observation is comes with SUBJECT_METRICS (subjectEntry). */
  definition: string;
  /** The region set the values come from, when the metric fixes it. */
  target?: ReviewTarget;
  /** The structure checked on the image, when it is not the region set the values come from:
   * a per-nucleus value of the nucleoli is read from the nucleoplasm set but checked on the nucleoli. */
  structure?: ReviewTarget;
  /** Whether a measured stain must be chosen. */
  channel: boolean;
  /** Needs a confirmed pixel size (µm², per mm²); without it the metric cannot be chosen (M-02). */
  calibrated?: boolean;
}
export interface MetricQuestion {question: string; metrics: MetricChoice[]}

export const METRIC_QUESTIONS: MetricQuestion[] = [
  {question: "大きさの変化", metrics: [
    {id: "area_px", label: "面積（px²）", channel: false,
      definition: "選んだ領域（核・核小体など）ごとの面積（画素数）。視野の中央値 → 試料 → 実験回の順にまとめます。核の面積の低下は形態の所見で、細胞死の確定ではありません。"},
    {id: "area_um2", label: "面積（µm²）", channel: false, calibrated: true,
      definition: "画素数 × 確認した画素の大きさ（µm²）。画素の大きさが登録された視野だけで使えます。"},
  ]},
  {question: "数の増減", metrics: [
    {id: "nucleus_count", label: "視野あたりの核数", target: "nuclei", channel: false,
      definition: "採用した核の数。画像の端にかかる核を含みます。画像に写った核の数であり、細胞数・生存率・増殖率そのものではありません。視野の選び方と播種の密度に左右されます。"},
    {id: "nucleus_density_per_mm2", label: "核の密度（mm² あたり）", target: "nuclei", channel: false, calibrated: true,
      definition: "視野あたりの核数 ÷ 撮影した視野の面積（mm²）。画素の大きさが確認された視野だけで計算します。"},
  ]},
  {question: "量（輝度）の変化", metrics: [
    {id: "mean", label: "平均輝度", channel: true, definition: "選んだ領域の中で、選んだ染色の画素値を平均した値（原値）。"},
    {id: "median", label: "中央値", channel: true, definition: "選んだ領域の中の、選んだ染色の画素値の中央値（原値）。"},
    {id: "integrated", label: "積算輝度", channel: true, definition: "選んだ領域の中の、選んだ染色の画素値の合計（原値）。領域の大きさにも左右されます。"},
    {id: "mean_corrected", label: "平均輝度（背景補正）", channel: true, definition: "背景を差し引いた平均輝度。背景の決め方は測定の設定に記録されます。"},
    {id: "integrated_corrected", label: "積算輝度（背景補正）", channel: true, definition: "背景を差し引いた積算輝度。領域の大きさにも左右されます。"},
  ]},
  {question:"陽性核の増減",metrics:[
    {id:"positive_count",label:"視野あたりの陽性核数",target:"nuclei",channel:false,
      definition:"記録したチャンネルの分類による、視野ごとの陽性核数。対照・除外核・未判定核は別に数えます。"},
    {id:"positive_fraction",label:"陽性率",target:"nuclei",channel:false,
      definition:"視野ごとの陽性核数 ÷ 選別前に判定できた陽性核と陰性核の数。未判定核・除外核・対照は分母に含めません。"},
  ]},
  {question: "核小体の変化", metrics: [
    {id: "nucleolar_area_px", label: "核小体の総面積（px²）", target: "nucleoplasm", structure: "nucleoli", channel: false,
      definition: "採用した核小体がある核ごとの、核小体の総面積（px²）。候補がない核は 0 ではなく欠測です。核小体を決めた染色と方法は解析の記録に残ります。"},
    {id: "nucleolar_area_um2", label: "核小体の総面積（µm²）", target: "nucleoplasm", structure: "nucleoli", channel: false, calibrated: true,
      definition: "核小体の総面積（px²）× 確認した画素の大きさ。画素の大きさが登録された視野だけで使えます。"},
    {id: "nucleolar_eccentricity", label: "核小体の離心率", target: "nucleoplasm", structure: "nucleoli", channel: false,
      definition: "核ごとの、核小体の離心率（0 = 円、1 に近いほど細長い）を面積で重みづけた平均。1 画素の核小体は測りません。比較では差で示します。"},
    {id: "nucleolar_count", label: "核小体数", target: "nucleoplasm", structure: "nucleoli", channel: false,
      definition: "採用した核小体がある核ごとの、核小体の数。候補がない核は 0 ではなく欠測として扱います。"},
    {id: "nucleolar_area_fraction", label: "核小体面積割合", target: "nucleoplasm", structure: "nucleoli", channel: false,
      definition: "採用した核小体がある核ごとの、核小体の総面積 ÷ 核の面積。比較では差をパーセントポイントで示します。"},
    {id: "largest_nucleolus_fraction", label: "最大の核小体の割合", target: "nucleoplasm", structure: "nucleoli", channel: false,
      definition: "採用した核小体がある核ごとの、最も大きい核小体の面積 ÷ 核小体の総面積。1 に近いほど 1 個に集まっています。比較では差をパーセントポイントで示します。"},
  ]},
  {question: "核の形", metrics: [
    {id: "solidity", label: "核のソリディティ", target: "nuclei", channel: false,
      definition: "核ごとの、面積 ÷ 凸包の面積（1 = 凹みなし）。96 px 未満の核と画像の端にかかる核は測りません。"},
    {id: "axis_ratio", label: "核の長短軸比", target: "nuclei", channel: false,
      definition: "核ごとの、同じ二次モーメントの楕円の長軸 ÷ 短軸（1 = 円）。96 px 未満の核と画像の端にかかる核は測りません。"},
    {id: "eccentricity", label: "核の離心率", target: "nuclei", channel: false,
      definition: "核ごとの離心率（0 = 円、1 に近いほど細長い）。96 px 未満の核と画像の端にかかる核は測りません。比較では差で示します。"},
  ]},
  {question: "核小体と核質への分配", metrics: [
    {id: "log2_nucleoplasm_over_nucleolus", label: "核質／核小体 log₂ 比", target: "nucleoplasm", channel: true,
      definition: "核ごとの log₂（核質の平均輝度 ÷ 核小体の平均輝度）。大きいほど核質へ移っています。同じ染色で核小体を決めて測る場合、信号の変化が境界も変えるという制約があります。"},
  ]},
];

const choices = new Map(METRIC_QUESTIONS.flatMap(group => group.metrics.map(metric => [metric.id, metric] as const)));
const extraLabels: Record<string, string> = {median_corrected: "中央値（背景補正）"};

export function metricChoice(id: string): MetricChoice | undefined {return choices.get(id);}
export function metricLabel(id: string): string {return choices.get(id)?.label ?? extraLabels[id] ?? id;}
/** The region set a metric's values come from: fixed by the metric, otherwise the chosen one. */
export function metricTarget(id: string, chosen: ReviewTarget): ReviewTarget {return choices.get(id)?.target ?? chosen;}
/** The structure a metric's values are checked on in the image (V-04, X-01). */
export function metricStructure(id: string, chosen: ReviewTarget): ReviewTarget {return choices.get(id)?.structure ?? metricTarget(id, chosen);}
export function metricUsesChannel(id: string): boolean {return !id.startsWith("area_") && (choices.get(id)?.channel ?? true);}

/** The part of the nucleus a metric describes, chosen before the metric (requirements M-01; Issue #257, owner decisions 1, 7 and 12).
 *  The subjects map onto the metrics above; no metric is added here, and the ids sent to the API stay the same. */
export type MetricSubject = ReviewTarget;
/** What one observation is. */
export type ObservationUnit = "nucleus" | "nucleolus" | "field" | "cell";
export const UNIT_LABELS: Record<ObservationUnit, string> = {nucleus: "核ごと", nucleolus: "核小体ごと", field: "視野ごと", cell: "細胞ごと"};
/** One entry of a subject's list: the base metric first, then its variants, offered as a switch under the list
 *  (px² / µm², 原値 / 背景補正) instead of as separate entries. */
export interface SubjectMetric {label: string; variants: Array<{id: string; label: string}>}
export interface SubjectGroup {unit: ObservationUnit; metrics: SubjectMetric[]}

const one = (label: string, id: string): SubjectMetric => ({label, variants: [{id, label: ""}]});
const area: SubjectMetric = {label: "面積", variants: [{id: "area_px", label: "px²"}, {id: "area_um2", label: "µm²"}]};
const intensities: SubjectMetric[] = [
  {label: "平均輝度", variants: [{id: "mean", label: "原値"}, {id: "mean_corrected", label: "背景補正"}]},
  one("中央値", "median"),
  {label: "積算輝度", variants: [{id: "integrated", label: "原値"}, {id: "integrated_corrected", label: "背景補正"}]},
];
export const SUBJECT_METRICS: Record<MetricSubject, SubjectGroup[]> = {
  nuclei: [
    {unit: "nucleus", metrics: [area, ...intensities, one("ソリディティ", "solidity"), one("長短軸比", "axis_ratio"), one("離心率", "eccentricity")]},
    {unit: "field", metrics: [one("数", "nucleus_count"), one("密度（mm² あたり）", "nucleus_density_per_mm2"), one("陽性核数", "positive_count"), one("陽性率", "positive_fraction")]},
  ],
  nucleoli: [
    {unit: "nucleolus", metrics: [area, ...intensities]},
    {unit: "nucleus", metrics: [one("数", "nucleolar_count"),
      {label: "総面積", variants: [{id: "nucleolar_area_px", label: "px²"}, {id: "nucleolar_area_um2", label: "µm²"}]},
      one("面積割合", "nucleolar_area_fraction"), one("離心率", "nucleolar_eccentricity"), one("最大の核小体の割合", "largest_nucleolus_fraction")]},
  ],
  nucleoplasm: [
    {unit: "nucleus", metrics: [area, ...intensities, one("核質／核小体 log₂ 比", "log2_nucleoplasm_over_nucleolus")]},
  ],
  cell: [
    {unit: "cell", metrics: [area, ...intensities]},
  ],
};
export const SUBJECTS: MetricSubject[] = ["nuclei", "nucleoli", "nucleoplasm", "cell"];

/** The subject a metric belongs to: the structure its values are checked on. */
export function metricSubject(id: string, chosen: ReviewTarget): MetricSubject {return metricStructure(id, chosen);}
/** The entry and observation unit of a metric in a subject's list. */
export function subjectEntry(subject: MetricSubject, id: string): {unit: ObservationUnit; metric: SubjectMetric} | undefined {
  for (const group of SUBJECT_METRICS[subject]) for (const metric of group.metrics) if (metric.variants.some(variant => variant.id === id)) return {unit: group.unit, metric};
  return undefined;
}
/** The metric kept when the subject changes: the same one if the subject offers it, else the mean intensity, else its first offered entry. */
export function metricForSubject(current: string, subject: MetricSubject, offered: (id: string) => boolean): string {
  if (subjectEntry(subject, current) && offered(current)) return current;
  if (subjectEntry(subject, "mean") && offered("mean")) return "mean";
  return SUBJECT_METRICS[subject].flatMap(group => group.metrics).find(metric => offered(metric.variants[0].id))?.variants[0].id ?? current;
}

/** The positive count and fraction of nuclei (field summary), judged by a recorded classification of a channel. */
export function nucleusPositivity(id: string): boolean {return id === "positive_count" || id === "positive_fraction";}

const REGION_NAMES: Record<ReviewTarget, string> = {nuclei: "核", nucleoli: "核小体", nucleoplasm: "核質", cell: "細胞ROI"};
/** Metrics that describe each region of the chosen set; the others name their own subject (核小体の離心率, 陽性率). */
const PER_REGION = new Set(["area_px", "area_um2", "mean", "median", "integrated", "mean_corrected", "median_corrected", "integrated_corrected"]);
/** One name for a measure wherever it is shown: 「核小体の平均輝度（5-EU）」. The region names a per-region metric; the
 * stain is the recorded stain name, a channel identifier only when nothing else was recorded. */
export function measureLabel(metric: string, regionSet: string | null | undefined, stain: string | null | undefined): string {
  const label = metricLabel(metric);
  const region = PER_REGION.has(metric) && regionSet ? REGION_NAMES[regionSet as ReviewTarget] : undefined;
  const named = !!stain && (nucleusPositivity(metric) || metricUsesChannel(metric));
  // A label that already ends in a parenthesis (「積算輝度（背景補正）」) takes the stain inside it.
  const text = named && label.endsWith("）") ? `${label.slice(0, -1)}、${stain}）` : named ? `${label}（${stain}）` : label;
  return `${region ? `${region}の` : ""}${text}`;
}
