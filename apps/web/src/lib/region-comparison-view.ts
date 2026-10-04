import type {components} from "./generated";
import type {Job} from "./types";
import {regionMetricLabels,type RegionMetric} from "./region-types";

export type RegionComparisonResult=components["schemas"]["RegionComparisonView"]|components["schemas"]["CommonComparisonView"];
// Keep the saved-result contract generated from OpenAPI; the trace adapter validates
// its deliberately untyped nested ledger rows before exposing a UI hierarchy.
export type RegionComparisonTraceInput=Pick<RegionComparisonResult,
 "revision_id"|"source_fingerprint"|"spec"|"metric"|"region"|"channel"|
 "source_fields"|"source_field_ledger"|"observation_ledger"|"field_summary"|
 "sample_summary"|"unit_summary"|"unit_ledger"|"pair_ledger"|"missingness"|"excluded_failed_fields">;
export function regionComparisonJobs(jobs:Job[]){return jobs.filter(job=>job.kind==="statistics"&&job.analysis_mode==="region-experimental-unit").toSorted((a,b)=>b.created-a.created);}
export function selectedRegionComparisonJob(jobs:Job[],selectedId:string,revisionId?:string){const available=regionComparisonJobs(jobs);return selectedId?available.find(job=>job.id===selectedId):available.find(job=>job.revision_id===revisionId);}
export function comparisonLabel(result:RegionComparisonResult){return [result.region.label,result.channel?.label,regionMetricLabels[result.metric as RegionMetric]||result.metric].filter(Boolean).join(" · ");}
export function probabilityLabel(value:unknown){if(typeof value!=="number"||!Number.isFinite(value))return "—";return value!==0&&Math.abs(value)<.001?value.toExponential(2):value.toPrecision(3);}
export const comparisonWarnings:Record<string,string>={
 few_independent_units_model_assumptions_and_power_require_review:"独立実験単位が少ないため、分布の仮定と検出力を確認してください。",
 missing_outcomes_excluded_not_assumed_missing_at_random:"欠測値は比較から除いています。欠測が無作為とは仮定していません。",
 explicitly_excluded_failed_fields_have_unknown_observation_counts:"失敗を確認して除外した視野の領域数は不明です。",
 acquisition_comparability_user_confirmed_not_machine_verified:"撮影条件の比較可能性は利用者の確認に基づき、画像から自動検証していません。",
 pointwise_confidence_intervals_are_not_holm_adjusted:"95%信頼区間は個別の区間です。Holm補正はp値に適用します。",
 acquisition_batches_partially_unbalanced_no_batch_adjustment:"群間で撮影バッチが一部異なります。バッチ補正は行っていません。",
};
