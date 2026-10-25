import type {ReviewTarget} from "./review-preview";

/** Measurements offered by the research question they answer (requirements M-01).
 * Labels and definitions describe the saved common implementation; nothing is computed here. */
export interface MetricChoice {
  id: string; label: string;
  /** What is measured, on which region, and what one observation is. */
  definition: string;
  /** The region set the values come from, when the metric fixes it. */
  target?: ReviewTarget;
  /** Whether a measured stain must be chosen. */
  channel: boolean;
  /** Needs a confirmed pixel size (µm², per mm²); without it the metric cannot be chosen (M-02). */
  calibrated?: boolean;
}
export interface MetricQuestion {question: string; metrics: MetricChoice[]}

export const METRIC_QUESTIONS: MetricQuestion[] = [
  {question: "大きさが変わったか", metrics: [
    {id: "area_px", label: "面積（px²）", channel: false,
      definition: "選んだ領域（核・核小体など）ごとの面積（画素数）。観測は領域ごとで、視野の中央値 → 試料 → 実験回の順にまとめます。核の面積の低下は形態の所見で、細胞死の確定ではありません。"},
    {id: "area_um2", label: "面積（µm²）", channel: false, calibrated: true,
      definition: "画素数 × 確認した画素の大きさ（µm²）。画素の大きさが登録された視野だけで使えます。"},
  ]},
  {question: "数が増えた・減ったか", metrics: [
    {id: "nucleus_count", label: "視野あたりの核数", target: "nuclei", channel: false,
      definition: "採用した核の数（画像の端にかかる核を含む）。観測は視野ごとです。画像に写った核の数であり、細胞数・生存率・増殖率そのものではありません。視野の選び方と播種の密度に左右されます。"},
    {id: "nucleus_density_per_mm2", label: "核の密度（mm² あたり）", target: "nuclei", channel: false, calibrated: true,
      definition: "視野あたりの核数 ÷ 撮影した視野の面積（mm²）。画素の大きさが確認された視野だけで計算します。観測は視野ごとです。"},
  ]},
  {question: "量（明るさ）が変わったか", metrics: [
    {id: "mean", label: "平均輝度", channel: true, definition: "選んだ領域の中で、選んだ染色の画素値を平均した値（原値）。観測は領域ごとです。"},
    {id: "median", label: "中央値", channel: true, definition: "選んだ領域の中の、選んだ染色の画素値の中央値（原値）。観測は領域ごとです。"},
    {id: "integrated", label: "積算輝度", channel: true, definition: "選んだ領域の中の、選んだ染色の画素値の合計（原値）。領域の大きさにも左右されます。"},
    {id: "mean_corrected", label: "平均輝度（背景補正）", channel: true, definition: "背景を差し引いた平均輝度。背景の決め方は測定の設定に記録されます。"},
    {id: "integrated_corrected", label: "積算輝度（背景補正）", channel: true, definition: "背景を差し引いた積算輝度。領域の大きさにも左右されます。"},
  ]},
  {question: "核小体が変わったか", metrics: [
    {id: "nucleolar_area_px", label: "核小体の総面積（px²）", target: "nucleoplasm", channel: false,
      definition: "採用した核小体がある核ごとの、核小体の総面積（px²）。候補がない核は 0 ではなく欠測です。核小体を決めた染色と方法は解析の記録に残ります。"},
    {id: "nucleolar_area_um2", label: "核小体の総面積（µm²）", target: "nucleoplasm", channel: false, calibrated: true,
      definition: "核小体の総面積（px²）× 確認した画素の大きさ。画素の大きさが登録された視野だけで使えます。"},
    {id: "nucleolar_eccentricity", label: "核小体の離心率", target: "nucleoplasm", channel: false,
      definition: "核ごとの、核小体の離心率（0 = 円、1 に近いほど細長い）を面積で重みづけた平均。1 画素の核小体は測りません。比較では差で示します。"},
    {id: "nucleolar_count", label: "核小体数", target: "nucleoplasm", channel: false,
      definition: "採用した核小体がある核ごとの、核小体の数。候補がない核は 0 ではなく欠測として扱います。"},
    {id: "nucleolar_area_fraction", label: "核小体面積割合", target: "nucleoplasm", channel: false,
      definition: "採用した核小体がある核ごとの、核小体の総面積 ÷ 核の面積。比較では差をパーセントポイントで示します。"},
  ]},
  {question: "核小体から核質へ移ったか", metrics: [
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
export function metricUsesChannel(id: string): boolean {return !id.startsWith("area_") && (choices.get(id)?.channel ?? true);}
