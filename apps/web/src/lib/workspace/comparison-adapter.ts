/** Comparison transport uses immutable server cohorts and explicit research decisions. */
import {API, errorCodeMessage, fetchBlob, post, request} from "../api";
import {defaultFigureEdits} from "../figure-controls";
import {comparisonMethod, type CommonComparisonRequest, type CommonPlotKind} from "../common-statistics";
import type {components} from "../generated";
import type {Job} from "../types";
import {assertWorkspaceConnection, type SavedResult, type Transport} from "./api-adapter";

export type ComparisonResult = components["schemas"]["CommonComparisonView"];
export type Metadata = components["schemas"]["RegionFieldMetadata"];
export interface ComparisonSource {field: string; revision: string; label: string; result: SavedResult; metadata: Metadata}
export interface ComparisonChoices {
  metric: CommonComparisonRequest["selection"]["metric"]; channel: string | null; regionSet: string; design: "independent" | "paired";
  method: "parametric" | "rank"; unitDefinition: string; pairingBasis: string;
  contrasts: string[][]; independence: boolean; acquisition: boolean; sampling: boolean; missingness: boolean;
  kind: CommonPlotKind; width: number; height: number; yLabel: string;
}
export function comparisonRequest(choices: ComparisonChoices): CommonComparisonRequest {
  const conditions = [...new Set(choices.contrasts.flat())];
  if (!choices.independence || !choices.acquisition || !choices.missingness || !choices.unitDefinition.trim()) throw new Error("独立性・撮影条件・採否を確認してください。");
  if (conditions.length < 2 || choices.contrasts.some(pair => pair.length !== 2 || pair[0] === pair[1])) throw new Error("比較する群の組を指定してください。");
  if ((choices.metric === "area_px" || choices.metric.includes("integrated")) && !choices.sampling) throw new Error("画素の大きさと空間サンプリングを確認してください。");
  if (choices.design === "paired" && !choices.pairingBasis.trim()) throw new Error("対応の根拠を指定してください。");
  const settings = comparisonMethod(choices.method, choices.design, conditions.length)!;
  return {mode: "region-experimental-unit", ...settings,
    selection: {source: "region", region_set_id: choices.regionSet, metric: choices.metric, channel_id: choices.channel},
    design: {kind: choices.design, confirmed: true, unit_definition: choices.unitDefinition.trim(), pairing_basis: choices.design === "paired" ? choices.pairingBasis.trim() : null},
    conditions, comparison_family: {family_id: "workspace-planned", kind: "planned", control: null, contrasts: choices.contrasts},
    acquisition_review: {confirmed: true, basis: choices.metric === "area_um2" ? "calibrated-area" : "same-settings", field_batches: {}, spatial_sampling_confirmed: choices.sampling},
    missingness_confirmed: true, aggregation: "field-median_sample-mean_unit-mean-v1", missingness_policy: "available-observations_require-unexcluded-units-v1",
    plot: {...defaultFigureEdits(), kind: choices.kind, preset: "custom", language: "en", histogram_bins: 10,
      width_inches: choices.width / 25.4, height_inches: choices.height / 25.4, y_label: choices.yLabel},
  };
}
export function createComparisonAdapter(overrides: Partial<Transport> = {}) {
  const client = {request, post, blob: fetchBlob, wait: () => new Promise<void>(resolve => setTimeout(resolve, 1200)), ...overrides};
  const pending = new Map<string, {job_id: string; revision_id?: string} | "uncertain">();
  const check = () => {if (typeof window !== "undefined") assertWorkspaceConnection(window.location.hostname, API);};
  async function accepted(workspace: string, path: string, body: unknown, identity: unknown = body) {
    check(); const key = JSON.stringify([path, identity]); let record = pending.get(key);
    if (record === "uncertain") throw new Error("受付状態が不明です。再読み込みで保存済みの処理を確認してください。");
    if (!record) {pending.set(key, "uncertain"); record = await client.post<{job_id: string; revision_id?: string}>(path, body); pending.set(key, record);}
    for (;;) {
      const jobs = await client.request<Job[]>(`/v1/workspaces/${workspace}/jobs`);
      const job = jobs.find(value => value.id === record.job_id);
      if (!job) throw new Error("保存された処理が見つかりません。");
      if (job.state === "succeeded") return record;
      if (job.state === "failed" || job.state === "cancelled") {pending.delete(key); throw new Error(job.error ? errorCodeMessage(job.error) : "処理を中止しました。");}
      await client.wait();
    }
  }
  return {
    async metadata(workspace: string, sources: ComparisonSource[]) {
      check();
      const revisions = await client.request<Array<{id: string; state: string; created: number; config: {cohort_sources?: Record<string, {revision_id: string}>; field_snapshot?: Record<string, {metadata: Metadata}>}}>>(`/v1/workspaces/${workspace}/revisions`);
      const match = revisions.filter(revision => revision.state === "succeeded" && revision.config.cohort_sources && Object.keys(revision.config.cohort_sources).length === sources.length && sources.every(source => revision.config.cohort_sources?.[source.field]?.revision_id === source.revision)).toSorted((a,b) => b.created - a.created)[0];
      if (!match || !sources.every(source => match.config.field_snapshot?.[source.field])) return null;
      return {revision: match.id, fields: Object.fromEntries(sources.map(source => [source.field, match.config.field_snapshot![source.field].metadata]))};
    },
    async history(workspace: string) {
      check(); const jobs = await client.request<Job[]>(`/v1/workspaces/${workspace}/jobs`);
      return jobs.filter(job => job.kind === "statistics" && job.analysis_mode === "region-experimental-unit" && job.analysis_version === "2.0.0" && job.state === "succeeded").toSorted((a,b) => b.created - a.created);
    },
    async saved(job: Job) {
      check(); const result = await client.request<ComparisonResult>(`/v1/jobs/${job.id}/common-statistics`);
      if (result.revision_id !== job.revision_id || result.region_comparison_version !== "2.0.0") throw new Error("保存された比較の出典が一致しません。");
      return {job: job.id, result};
    },
    async cohort(workspace: string, sources: ComparisonSource[], metadata: Record<string, Metadata>) {
      if (sources.length < 2 || new Set(sources.map(source => source.field)).size !== sources.length) throw new Error("異なる視野を2件以上選択してください。");
      check(); const current = await client.request<{active_revision: string | null}>(`/v1/workspaces/${workspace}`);
      const result = await accepted(workspace, `/v1/workspaces/${workspace}/region-cohorts`, {expected_active_revision_id: current.active_revision, sources: sources.map(source => ({field_id: source.field, revision_id: source.revision})), metadata}, {sources: sources.map(source => [source.field, source.revision]), metadata});
      if (!result.revision_id) throw new Error("集合の解析版がありません。");
      return result.revision_id;
    },
    async review(revision: string, confirmed: boolean) {
      if (!confirmed) throw new Error("画像・領域と採否の確認が必要です。");
      check(); await client.post(`/v1/revisions/${revision}/review`, {accept_invalidated_fields: []});
    },
    async compare(workspace: string, revision: string, spec: CommonComparisonRequest) {
      const job = await accepted(workspace, `/v1/revisions/${revision}/common-statistics`, spec);
      const result = await client.request<ComparisonResult>(`/v1/jobs/${job.job_id}/common-statistics`);
      if (result.revision_id !== revision || result.analysis_kind !== "region-comparison" || result.region_comparison_version !== "2.0.0") throw new Error("比較結果の出典が一致しません。");
      return {job: job.job_id, result};
    },
  };
}
