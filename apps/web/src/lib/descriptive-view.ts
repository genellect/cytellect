import { metricLabels, type Job } from "./types";
import { regionMetricLabels } from "./region-types";

export type DescriptiveSelection =
  | { source: "legacy-cell"; metric: string }
  | { source: "region"; region_set_id: string; channel_id: string | null; metric: string };

export type DescriptiveResult = {
  analysis_kind: "descriptive";
  revision_id: string;
  spec: { selection: DescriptiveSelection; plot: { language: string; preset: string; group_order?:string[] } };
  metric: string;
  unit: string;
  counts: { observations: number; input_fields: number; selected_fields: number; excluded_failed_fields: number; experimental_units: null };
  selection: { input_rows: number; excluded: number; gate_unselected: number; missing_metric_selected: number };
  field_summary: Array<{ field_id: string; selected_rows: number; median: number | null; q1: number | null; q3: number | null; status: string }>;
  source_fields: Array<{ field_id: string; region_set?: { label: string }; channel_provenance?: Array<{ channel: { channel_id: string; label: string; stain: string | null } }> }>;
  excluded_failed_fields: Array<{ field_id: string; reason: string }>;
  figure: { source_files: string[] };
  warnings: string[];
};

export function descriptiveJobs(jobs: Job[]) {
  return jobs.filter(job => job.kind === "statistics" && job.analysis_mode === "descriptive").toSorted((a, b) => b.created - a.created);
}

// An explicit selection remains selected while queued, failed, cancelled or not yet polled.
// In particular, a failed new figure must never silently resolve to a previous success.
export function selectedDescriptiveJob(jobs: Job[], selectedId: string, revisionId?: string) {
  const available = descriptiveJobs(jobs);
  if (selectedId) return available.find(job => job.id === selectedId);
  return available.find(job => job.revision_id === revisionId) ?? available[0];
}

export function sameDescriptiveSettings(result: DescriptiveResult, selection: DescriptiveSelection | undefined, language: string, preset: string) {
  const saved = result.spec.selection;
  if (!selection || saved.source !== selection.source || saved.metric !== selection.metric) return false;
  if (saved.source === "region" && selection.source === "region" && (saved.region_set_id !== selection.region_set_id || saved.channel_id !== selection.channel_id)) return false;
  return result.spec.plot.language === language && result.spec.plot.preset === preset;
}

export function savedDescriptiveLabel(result: DescriptiveResult) {
  const selection = result.spec.selection;
  if (selection.source === "legacy-cell") return metricLabels[selection.metric] ?? selection.metric;
  const field = result.source_fields[0];
  const region = field?.region_set?.label ?? selection.region_set_id;
  const metric = regionMetricLabels[selection.metric as keyof typeof regionMetricLabels] ?? selection.metric;
  if (selection.channel_id === null) return `${region} · ${metric}`;
  const channel = field?.channel_provenance?.find(item => item.channel.channel_id === selection.channel_id)?.channel;
  const label = channel ? `${channel.label}（標識: ${channel.stain ?? "未記録"}）` : "標識名未記録";
  return `${region} · ${label} · ${metric}`;
}

const statuses: Record<string, string> = { selected: "採用値あり", no_regions: "領域なし", no_selected_values: "採用可能な値なし" };
export function descriptiveFieldNumber(result:DescriptiveResult,fieldId:string){
  const order=result.spec.plot.group_order?.length?result.spec.plot.group_order:result.field_summary.map(row=>row.field_id);
  const index=order.indexOf(fieldId);
  return index<0?null:index+1;
}
export const descriptiveFieldStatus = (status: string) => statuses[status] ?? status;
const warnings: Record<string, string> = {
  descriptive_independence_not_assessed: "独立反復は評価していません。観測数・視野数を独立した実験反復数として扱わないでください。",
  acquisition_comparability_not_established: "撮影条件の比較可能性は未確認です。視野間の差を処置の効果と判断する前に、取得条件を確認してください。",
  missing_outcomes_excluded_inspect_fieldwise_missingness: "指標が欠測した観測は図に含まれません。視野ごとの欠測と理由を確認してください。",
  ncl_defined_regions_can_change_with_the_measured_ncl_distribution: "NCLから定義した領域は、測定対象であるNCLの分布とともに変化することがあります。",
  data_derived_or_manual_gfp_selection_requires_predeclared_or_independent_validation: "GFPの手動・データ由来の選別を含みます。事前に定めた条件または別データでの検証を確認してください。",
};
export const descriptiveWarning = (code: string) => warnings[code] ?? code;
