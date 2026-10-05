/** Public method scenarios, not private experiments or an image-performance benchmark.
 * Sources are the registered Senft/Waters/Kodiha/Lazic/Lord method notes in openai.ts.
 * No uploads, arbitrary prompts, filenames or remote image URLs are accepted by the harness.
 */
const channel = (token: string, stain: string | null, role: string | null) => ({ token, stain, role });
const nuclear = channel("ch1", "DAPI", "nuclear");
const gfp = channel("ch2", "GFP", "measure");
const ncl = channel("ch2", "NCL", "measure");
const base = { protocol: "1.1.0", goal: "", channels: [nuclear], field_count: 4, condition_count: 0,
  units_known: false, pairing_known: false, supplied_regions: false, measured_table: false, background_available: false };

export interface PublicCase {
  id: string;
  context: Record<string, unknown>;
  recipes: string[];
  metric: string | null;
  kind: string;
  forbiddenMetrics?: string[];
}
const make = (id: string, patch: Record<string, unknown>, recipes: string[], metric: string | null, kind = "descriptive", forbiddenMetrics?: string[]): PublicCase =>
  ({ id, context: { ...base, ...patch }, recipes, metric, kind, forbiddenMetrics });

export const PUBLIC_CASES: PublicCase[] = [
  make("nuclear-area", { goal: "DAPIで検出した核の面積分布を示す。群間検定は不要。" }, ["nuclear-intensity"], "area"),
  make("hoechst-area", { goal: "Hoechstで検出した核の面積分布を示す。", channels: [channel("ch1", "Hoechst", "nuclear")] }, ["nuclear-intensity"], "area"),
  make("gfp-raw", { goal: "核内GFPの補正前平均輝度を測定する。背景は未設定。", channels: [nuclear, gfp] }, ["nuclear-intensity"], "mean_raw", "descriptive", ["mean_corrected", "integral_corrected"]),
  make("gfp-corrected", { goal: "核内GFPの背景補正平均輝度を測定する。", channels: [nuclear, gfp], background_available: true }, ["nuclear-intensity"], "mean_corrected"),
  make("unknown-marker", { goal: "ch2の核内補正前平均輝度を測定する。染色名は不明。", channels: [nuclear, channel("ch2", null, "measure")] }, ["nuclear-intensity"], "mean_raw"),
  make("ncl-ratio", { goal: "NCLの背景補正平均輝度から核質対核小体のlog2比を測る。", channels: [nuclear, ncl], background_available: true }, ["nuclear-ncl"], "ncl_log2_nucleoplasm_over_nucleoli"),
  make("ncl-no-background", { goal: "NCLの核質対核小体のlog2比を測りたいが、背景がない。可能な補正前NCL輝度を先に示す。", channels: [nuclear, ncl] }, ["nuclear-ncl"], "mean_raw", "descriptive", ["ncl_log2_nucleoplasm_over_nucleoli", "mean_corrected"]),
  make("independence-unknown", { goal: "2群のGFP平均輝度を比較したい。独立実験単位は未確認なので記述的な図を作る。", channels: [nuclear, gfp], condition_count: 2 }, ["nuclear-intensity"], "mean_raw"),
  make("welch-two-groups", { goal: "独立した2群の核面積を実験単位で集計しWelch検定と図を作る。", condition_count: 2, units_known: true, units_per_condition: [3, 3] }, ["nuclear-intensity"], "area", "comparison"),
  make("paired-three-unsupported", { goal: "対応のある3条件の核面積を示す。2条件への限定はまだしていない。", condition_count: 3, units_known: true, pairing_known: true, units_per_condition: [3, 3, 3], complete_pair_count: 3 }, ["nuclear-intensity"], "area"),
  make("supplied-roi", { goal: "取り込んだ領域の面積分布を示す。核の自動検出は不要。", channels: [channel("ch1", null, "measure")], supplied_regions: true }, ["supplied-regions"], "area"),
  make("unsupported-frap", { goal: "時系列FRAP画像から回復時定数を求める。登録済み手法にない場合は実行可能としない。" }, ["none"], null),
];

/** Required positive behavior: reject-all and always-descriptive models cannot pass. */
export function expectedBehavior(item: PublicCase, draft: unknown): boolean {
  if (!draft || typeof draft !== "object") return false;
  const value = draft as { recipe?: string; metrics?: { metric: string }[]; statistics?: { kind: string } };
  return !!value.recipe && item.recipes.includes(value.recipe)
    && value.statistics?.kind === item.kind
    && (item.metric === null || !!value.metrics?.some((entry) => entry.metric === item.metric))
    && !value.metrics?.some((entry) => item.forbiddenMetrics?.includes(entry.metric));
}
