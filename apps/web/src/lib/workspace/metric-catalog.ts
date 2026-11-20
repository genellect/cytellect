import type {ReviewTarget} from "./review-preview";

/** Measurements grouped by the change a researcher asks about, named as nouns (requirements M-01, UC-01).
 * Labels and definitions describe the saved common implementation; nothing is computed here. */
export interface MetricChoice {
  id: string; label: string;
  /** What is measured, on which region, and what one observation is. */
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
  /** The subjects (核・核小体・核質・細胞ROI) whose metrics list it (B-1); unset for a per-region metric, offered for every subject. */
  subjects?: ReviewTarget[];
  /** One observation, when the metric fixes it (B-4); unset for a per-region metric, whose observation is one region of the subject. */
  unit?: string;
}
export interface MetricQuestion {question: string; metrics: MetricChoice[]}

export const METRIC_QUESTIONS: MetricQuestion[] = [
  {question: "大きさの変化", metrics: [
    {id: "area_px", label: "面積（px²）", channel: false,
      definition: "選んだ領域（核・核小体など）ごとの面積（画素数）。観測は領域ごとで、視野の中央値 → 試料 → 実験回の順にまとめます。核の面積の低下は形態の所見で、細胞死の確定ではありません。"},
    {id: "area_um2", label: "面積（µm²）", channel: false, calibrated: true,
      definition: "画素数 × 確認した画素の大きさ（µm²）。画素の大きさが登録された視野だけで使えます。"},
  ]},
  {question: "数の増減", metrics: [
    {id: "nucleus_count", subjects: ["nuclei"], unit: "視野ごと", label: "視野あたりの核数", target: "nuclei", channel: false,
      definition: "採用した核の数。画像の端にかかる核を含みます。観測は視野ごとです。画像に写った核の数であり、細胞数・生存率・増殖率そのものではありません。視野の選び方と播種の密度に左右されます。"},
    {id: "nucleus_density_per_mm2", subjects: ["nuclei"], unit: "視野ごと", label: "核の密度（mm² あたり）", target: "nuclei", channel: false, calibrated: true,
      definition: "視野あたりの核数 ÷ 撮影した視野の面積（mm²）。画素の大きさが確認された視野だけで計算します。観測は視野ごとです。"},
  ]},
  {question: "量（輝度）の変化", metrics: [
    {id: "mean", label: "平均輝度", channel: true, definition: "選んだ領域の中で、選んだ染色の画素値を平均した値（原値）。観測は領域ごとです。"},
    {id: "median", label: "輝度の中央値", channel: true, definition: "選んだ領域の中の、選んだ染色の画素値の中央値（原値）。観測は領域ごとです。"},
    {id: "integrated", label: "積算輝度", channel: true, definition: "選んだ領域の中の、選んだ染色の画素値の合計（原値）。領域の大きさにも左右されます。"},
    {id: "mean_corrected", label: "平均輝度（背景補正）", channel: true, definition: "背景を差し引いた平均輝度。背景の決め方は測定の設定に記録されます。"},
    {id: "integrated_corrected", label: "積算輝度（背景補正）", channel: true, definition: "背景を差し引いた積算輝度。領域の大きさにも左右されます。"},
  ]},
  {question: "形の変化", metrics: [
    {id: "solidity", label: "ソリディティ", channel: false,
      definition: "選んだ領域の面積 ÷ 領域を囲む最小の多角形の面積（solidity）。1 に近いほどくぼみや切れ込みが少ない。96 px 未満の領域と画像の端にかかる領域は形を測らず欠測にします（個数と面積には含めます）。2D の値で、体積や球形度ではありません。"},
    {id: "axis_ratio", label: "長短軸比", channel: false,
      definition: "選んだ領域の二次モーメントから計算した長軸 ÷ 短軸。1 は等方、大きいほど細長い。96 px 未満の領域と画像の端にかかる領域は欠測です。"},
    {id: "eccentricity", label: "離心率", channel: false,
      definition: "選んだ領域の離心率（0 = 円、1 に近いほど細長い）。長短軸比と同じ二次モーメントから計算します。96 px 未満の領域と画像の端にかかる領域は欠測です。"},
  ]},
  {question: "信号の偏りと広がり", metrics: [
    {id: "cv", label: "画素の変動係数（CV）", channel: true,
      definition: "選んだ領域の中の、選んだ染色の画素値の標準偏差 ÷ 平均（原値）。小さいほど領域の中の信号が均一。染色・露光・ピントに左右されるため、同じ撮影条件の中で比べます。"},
    {id: "cv_corrected", label: "画素の変動係数（CV、背景補正）", channel: true,
      definition: "自動推定した背景を差し引いた画素値で計算した変動係数。背景が決まらない視野と、補正後の平均が 0 以下の領域は欠測です。"},
    {id: "positive_area_fraction", label: "陽性面積率", channel: true,
      definition: "選んだ領域の画素のうち、視野ごとに決めた閾値以上の画素の割合。閾値はその視野の採用した領域すべての画素から Otsu 法で決め、値を結果に記録します。露光や全体の明るさにも左右されます。"},
  ]},
  {question:"陽性核の増減",metrics:[
    {id:"positive_count", subjects: ["nuclei"], unit: "視野ごと",label:"視野あたりの陽性核数",target:"nuclei",channel:false,
      definition:"記録したチャンネルの分類による、視野ごとの陽性核数。対照・除外核・未判定核は別に数えます。"},
    {id:"positive_fraction", subjects: ["nuclei"], unit: "視野ごと",label:"陽性率",target:"nuclei",channel:false,
      definition:"視野ごとの陽性核数 ÷ 選別前に判定できた陽性核と陰性核の数。未判定核・除外核・対照は分母に含めません。"},
  ]},
  {question: "核小体の変化", metrics: [
    {id: "nucleolar_area_px", subjects: ["nucleoli"], unit: "核ごと（その核の核小体をまとめた値）", label: "核小体の総面積（px²）", target: "nucleoplasm", structure: "nucleoli", channel: false,
      definition: "採用した核小体がある核ごとの、核小体の総面積（px²）。候補がない核は 0 ではなく欠測です。核小体を決めた染色と方法は解析の記録に残ります。"},
    {id: "nucleolar_area_um2", subjects: ["nucleoli"], unit: "核ごと（その核の核小体をまとめた値）", label: "核小体の総面積（µm²）", target: "nucleoplasm", structure: "nucleoli", channel: false, calibrated: true,
      definition: "核小体の総面積（px²）× 確認した画素の大きさ。画素の大きさが登録された視野だけで使えます。"},
    {id: "nucleolar_eccentricity", subjects: ["nucleoli"], unit: "核ごと（その核の核小体をまとめた値）", label: "核小体の離心率", target: "nucleoplasm", structure: "nucleoli", channel: false,
      definition: "核ごとの、核小体の離心率（0 = 円、1 に近いほど細長い）を面積で重みづけた平均。1 画素の核小体は測りません。比較では差で示します。"},
    {id: "largest_nucleolus_fraction", subjects: ["nucleoli"], unit: "核ごと（その核の核小体をまとめた値）", label: "最大の核小体の割合", target: "nucleoplasm", structure: "nucleoli", channel: false,
      definition: "核ごとの、最大の核小体の面積 ÷ その核の核小体の総面積（0〜1）。1 に近いほど 1 個の大きな核小体にまとまり、小さいほど同じくらいの核小体に分かれています。候補がない核は欠測です。"},
    {id: "nucleolar_count", subjects: ["nucleoli"], unit: "核ごと（その核の核小体をまとめた値）", label: "核小体数", target: "nucleoplasm", structure: "nucleoli", channel: false,
      definition: "採用した核小体がある核ごとの、核小体の数。候補がない核は 0 ではなく欠測として扱います。"},
    {id: "nucleolar_area_fraction", subjects: ["nucleoli"], unit: "核ごと（その核の核小体をまとめた値）", label: "核小体面積割合", target: "nucleoplasm", structure: "nucleoli", channel: false,
      definition: "採用した核小体がある核ごとの、核小体の総面積 ÷ 核の面積。比較では差をパーセントポイントで示します。"},
  ]},
  {question: "核小体と核質への分配", metrics: [
    {id: "log2_nucleoplasm_over_nucleolus", subjects: ["nucleoli", "nucleoplasm"], unit: "核ごと（核質と核小体の比）", label: "核質／核小体 log₂ 比", target: "nucleoplasm", channel: true,
      definition: "核ごとの log₂（核質の平均輝度 ÷ 核小体の平均輝度）。大きいほど核質へ移っています。同じ染色で核小体を決めて測る場合、信号の変化が境界も変えるという制約があります。"},
  ]},
];

const choices = new Map(METRIC_QUESTIONS.flatMap(group => group.metrics.map(metric => [metric.id, metric] as const)));
const extraLabels: Record<string, string> = {median_corrected: "輝度の中央値（背景補正）"};

export function metricChoice(id: string): MetricChoice | undefined {return choices.get(id);}
export function metricLabel(id: string): string {return choices.get(id)?.label ?? extraLabels[id] ?? id;}
/** The region set a metric's values come from: fixed by the metric, otherwise the chosen one. */
export function metricTarget(id: string, chosen: ReviewTarget): ReviewTarget {return choices.get(id)?.target ?? chosen;}
/** The structure a metric's values are checked on in the image (V-04, X-01). */
export function metricStructure(id: string, chosen: ReviewTarget): ReviewTarget {return choices.get(id)?.structure ?? metricTarget(id, chosen);}
/** The positive count and fraction of nuclei (field summary), judged by a recorded classification of a channel. Not the
 * positive-area fraction, which is a pixel measure of a region (region-features/1.0.0). */
export function nucleusPositivity(id: string): boolean {return id === "positive_count" || id === "positive_fraction";}
export function metricUsesChannel(id: string): boolean {return !id.startsWith("area_") && (choices.get(id)?.channel ?? true);}

const SUBJECTS: ReviewTarget[] = ["nuclei", "nucleoli", "nucleoplasm", "cell"];
const SUBJECT_NAMES: Record<ReviewTarget, string> = {nuclei: "核", nucleoli: "核小体", nucleoplasm: "核質", cell: "細胞ROI"};
/** The observation of a per-region metric: one region of the chosen subject. */
const REGION_UNITS: Record<ReviewTarget, string> = {nuclei: "核ごと", nucleoli: "核小体ごと", nucleoplasm: "核ごと（核質の領域）", cell: "細胞ROIごと"};
export function subjectName(subject: ReviewTarget): string {return SUBJECT_NAMES[subject];}
/** The subjects a metric is listed under (B-1). */
export function metricSubjects(id: string): ReviewTarget[] {return choices.get(id)?.subjects ?? SUBJECTS;}
/** What one observation is when the metric describes this subject (B-4). */
export function metricUnit(id: string, subject: ReviewTarget): string {return choices.get(id)?.unit ?? REGION_UNITS[subject];}
/** The metrics of one subject, grouped by what one observation is, in catalog order (B-1, requirements M-01 revised 2026-11-20). */
export function metricsForSubject(subject: ReviewTarget): Array<{unit: string; metrics: MetricChoice[]}> {
  const groups: Array<{unit: string; metrics: MetricChoice[]}> = [];
  for (const metric of METRIC_QUESTIONS.flatMap(group => group.metrics)) {
    if (!metricSubjects(metric.id).includes(subject)) continue;
    const unit = metricUnit(metric.id, subject);
    const group = groups.find(value => value.unit === unit);
    if (group) group.metrics.push(metric); else groups.push({unit, metrics: [metric]});
  }
  return groups;
}
/** Metrics that describe each region of the chosen set; the others name their own subject (核小体の離心率, 陽性率). */
const PER_REGION = new Set(["area_px", "area_um2", "mean", "median", "integrated", "mean_corrected", "median_corrected", "integrated_corrected",
  "solidity", "axis_ratio", "eccentricity", "cv", "cv_corrected", "positive_area_fraction"]);
export function perRegionMetric(id: string): boolean {return PER_REGION.has(id);}
/** One name for a measure everywhere it is shown (requirements S-12, SL-02): 「核小体の平均輝度（5-EU）」.
 * The region names a per-region metric; the stain is the recorded stain name, never a channel identifier
 * unless nothing else was recorded. */
export function measureLabel(metric: string, regionSet: string | null | undefined, stain: string | null | undefined): string {
  const label = metricLabel(metric);
  const region = PER_REGION.has(metric) && regionSet ? SUBJECT_NAMES[regionSet as ReviewTarget] : undefined;
  const named = !!stain && (nucleusPositivity(metric) || metricUsesChannel(metric));
  // A label that already ends in a parenthesis (「積算輝度（背景補正）」) takes the stain inside it.
  const text = named && label.endsWith("）") ? `${label.slice(0, -1)}、${stain}）` : named ? `${label}（${stain}）` : label;
  return `${region ? `${region}の` : ""}${text}`;
}
/** One sentence of what is measured, on which subject, and what one observation is (B-2, SL-01). */
export function metricSentence(id: string, subject: ReviewTarget): string {
  return `対象：${SUBJECT_NAMES[subject]}。観測の単位：${metricUnit(id, subject)}。`;
}
