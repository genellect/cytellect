/** Real workspace transport. Pixels, masks, summaries and figures remain server-owned. */
import { API, errorCodeMessage, fetchBlob, post, request } from "../api";
import { descriptiveFigureView, type DescriptiveResult } from "../descriptive-view";
import type { Job, Point, Workspace } from "../types";
import type { ChannelDefinition, GroupedField, Grouping } from "./grouping";
import type {DistributionPoint, FieldSummary} from "./adapter";
import type { ProposalProcessing, NuclearProcessingDetector, SignalProcessingDetector } from "./proposal-processing";
import {localProposal, type ProposalChannelLink} from "./proposal-mapping";

export interface SelectionEntry {id: string; field_id: string | null; revision_id: string | null; exclusion_reason: string | null; target_revisions?: Partial<Record<"nuclei" | "gfp" | "ncl" | "nucleoli" | "nucleoplasm" | "cell", string>>}
export interface WorkspaceSelection {version: number; entries: SelectionEntry[]}
export interface ChannelAssignment {channel_id: string; stain: string | null; role: "nuclear" | "measure" | "unused"}
export interface ChannelAssignmentGroup {id:string;field_ids:string[];channel_ids:string[];assignments:ChannelAssignment[]}
export interface ChannelAssignments {version: number; assignments: ChannelAssignment[];groups?:ChannelAssignmentGroup[];global_field_ids?:string[]}
export interface FieldLinks {version:number;entries:Array<{field_id:string;kind:"analysis"|"reference";reference_for_field_id:string|null;previous_exclusion?:string|null}>}
export interface ImportedField {
  id: string; workspace_id: string;
  metadata: Record<string, string | number | null>;
  image_info: {input_mode?: "native" | "display-rgb"; shape: [number, number]; channels: Array<{channel_id: string; label: string; stain: string | null}>};
}
export interface MeasurementRow {
  region_id: number; channel_id: string; area_px: number; area_um2: number | null;
  mean: number | null; median: number | null; integrated: number | null;
  mean_corrected?: number | null; median_corrected?: number | null; integrated_corrected?: number | null;
  area_missing_reason?: string | null; intensity_missing_reason?: string | null; correction_missing_reason?: string | null;
}
export interface SavedResult {
  regionSet?: string; revision: string; field: string; rows: MeasurementRow[];
  masks: {regions: Array<{id: number; points: Point[]}>; metadata: {mask_revision_id: string}};
  exclusions: Array<{field_id: string; region_id: number | null; reason: string}>;
  /** Measurement protocol of the saved table; "4.0.0" carries automatic-background corrections. */
  protocol?: string;
  measurement?: MeasurementPolicy | {version:"1.0.0";mode:"area_only"} | null;
  backgrounds?: Record<string,Record<string,{polygon:Point[];confirmed:true}>>;
  confirmedChannelIds?:string[];
}
/** Raw values (3.0.0) or raw values plus an automatic, unconfirmed background candidate (4.0.0). */
/** Mask corrections the workspace offers; delete goes through the exclusion/delete path. */
export type MaskOperation = "add" | "replace" | "split" | "merge";
export type MeasurementPolicy = {version: "1.1.0"; mode: "raw_intensity"} | {version: "1.2.0"; mode: "automatic_background"};
export const rawMeasurement: MeasurementPolicy = {version: "1.1.0", mode: "raw_intensity"};
export const automaticBackground: MeasurementPolicy = {version: "1.2.0", mode: "automatic_background"};
const measurementOf = (result: SavedResult) => result.measurement !== undefined ? result.measurement : result.protocol === "1.0.0" ? null : result.protocol === "2.0.0" ? {version:"1.0.0",mode:"area_only"} : result.protocol === "4.0.0" ? automaticBackground : rawMeasurement;
interface Report {
  revision_id: string; protocol_version?: string; field_tables: Record<string, {rows: MeasurementRow[]}>;
  field_failures: Array<{field_id: string; reason: string}>;
  exclusions: SavedResult["exclusions"];
}
export interface FigureChoice {metric: string; channel: string | null; width: number; height: number; label: string; xLabel?: string; fontSize?: number; language?: "ja" | "en"; yMin?: number | null; yMax?: number | null; yTickStep?: number | null; pointSize?: number | null}
export interface SavedFigure {job: string; revision: string; choice: FigureChoice; result: DescriptiveResult}
export interface Recipe {
  id: "region-2d"; version: "1.0.0" | "1.2.0" | "1.3.0" | "1.4.0" | "1.5.0" | "1.7.0"; region_set_id: string; label: string;
  source: "manual" | "stardist_nuclear" | "fiji_positive_regions" | "fiji_nuclear_compartment"; defining_channel_id: string;
  compartment?: "nucleoli" | "nucleoplasm"; nuclear_revision_id?: string; nuclear_channel_id?: string;
  detector?: NuclearProcessingDetector | SignalProcessingDetector | {engine?: "fiji-nucleolar-compartments"; protocol_version?: "1.0.0" | "1.1.0"; threshold_method?: "otsu" | "manual"; threshold?: number | null; smoothing_sigma_px: number; minimum_area_px: number; maximum_area_px?: number | null; split_touching: boolean}
    | {engine: "cytellect-nucleolar-v2"; protocol_version: "2.0.0" | "2.1.0"; source: "dapi_poor" | "marker"; smoothing_sigma_px: number; rim_exclusion_px: number; relative_threshold: number; marker_fraction: number; background_radius_px: number; minimum_area_px: number; maximum_area_px: number | null; minimum_solidity: number};
  nucleolar_revision_id?: string;
  nuclear_role_source?: "recorded_stain" | "user_selected_role";
  detection_max_side_px?: number; detection_scale?: "nuclear-size/1.0.0";
}
export interface ProposalMetric {metric:string;channel:string|null;region?:string|null}
export interface ProposalStatistics {kind:"descriptive"|"comparison"|"association";test:string|null;omnibus:string|null;association:string|null;x?:ProposalMetric|null;y?:ProposalMetric|null}
export interface ProposalDraft {
  recipe: "nuclear-intensity" | "nuclear-ncl" | "supplied-regions" | "measured-table" | "none";
  channels: Array<{token: string; stain: string | null; role: "nuclear" | "measure" | "unused"; reason: string}>;
  metrics: Array<{metric: string; channel: string | null; region?: string | null}>;
  statistics: ProposalStatistics;
  additional_analyses?: ProposalStatistics[];
  figures: Array<{kind: string; metric: string; channel: string | null;region?:string|null;analysis_index?:number}>;
  missing_information: string[]; reference_ids: string[]; rationale: string;
  processing?: ProposalProcessing | null;
  background?:{mode:"raw"|"automatic"|"confirmed_roi"}|null;
  gfp_selection?:{channel:string;unit:"nucleus"|"cell_roi";method:"manual"|"batch_otsu"|"negative_control";threshold:number|null;values:"raw"|"corrected";keep:"positive"|"negative";percentile:number}|null;
}
export interface ValidatedProposal {draft: ProposalDraft; needs_confirmation: string[]}
export interface GfpGateResult {unit?: "nucleus" | "cell_roi"; objects?: Array<{field_id:string;region_id:number;gfp_mean:number|null;gfp_positive:boolean|null;gfp_gate_reason:string}>; protocol?: string; method?: "negative_control" | "manual" | "batch_otsu"; nuclei?: Array<{field_id:string;region_id:number;gfp_mean:number|null;gfp_positive:boolean|null;gfp_gate_reason:string}>; percentile: number; dates: Record<string, {threshold: number | null; control_nuclei: number; missing_reason: string | null}>; field_counts: Record<string, {positive: number; negative: number; control: number; unselected: number}>}
export interface CompartmentSummaryRow {nucleus_id: number; nucleolar_count: number; nucleolar_area_fraction: number | null; nucleolar_mean: number | null; nucleoplasm_mean: number | null; log2_nucleoplasm_over_nucleolus: number | null; missing_reason: string | null; values: "raw" | "background_corrected"}
export interface CompartmentSummaryFile {
  channels: Record<string, {protocol: string; rows: CompartmentSummaryRow[]}>;
  /** Present for automatic-background measurements; a channel without a background has no rows and a reason. */
  corrected_channels?: Record<string, {protocol: string; rows: CompartmentSummaryRow[]; missing_reason?: string | null}>;
}
export type RunTarget = "nuclei" | "nucleoli" | "nucleoplasm" | "cell";
export interface WorkspaceRun {id:string; workspace_id:string;spec_version:number;target:RunTarget;state:"queued"|"running"|"succeeded"|"failed"|"cancelled"|"adopted";created:number;updated:number;steps:Array<{field_id:string;target:RunTarget;state:"pending"|"queued"|"succeeded"|"reused"|"failed"|"blocked";revision_id:string|null;job_id:string|null;recipe:Recipe|null;error:string|null;background_pending?:boolean}>}
export interface RevisionRecord {id: string; state: string; created: number; config: {recipe: Recipe; field_ids: string[]; exclusions?: SavedResult["exclusions"];measurement?:SavedResult["measurement"];backgrounds?:SavedResult["backgrounds"];confirmed_channel_ids?:string[]}}
export interface Transport {
  request: typeof request; post: typeof post; blob: typeof fetchBlob; wait: () => Promise<void>;
}
const defaults: Transport = {request, post, blob: fetchBlob, wait: () => new Promise(resolve => setTimeout(resolve, 1200))};
class TerminalJobError extends Error {}
export function assertWorkspaceConnection(host: string, origin: string) {
  const loopback = (name: string) => ["localhost", "127.0.0.1", "[::1]", "::1"].includes(name);
  if (origin && loopback(new URL(origin, `https://${host}`).hostname) && !loopback(host)) throw new Error("公開サイトからローカルの解析サーバーには接続できません。ランチャーから開いてください。");
}

export function channelSpecification(channel: ChannelDefinition) {
  return {channel_id: channel.token, label: channel.stain || channel.token, stain: channel.stain,
    identity_source: channel.evidence === "ome" ? "ome_metadata" : channel.evidence === "user" ? "user_entered" : channel.evidence === "filename" || channel.evidence === "folder" ? "filename" : "unresolved",
    acquisition_saturation_value: null, acquisition_saturation_confirmed: false};
}

export function nuclearRecipe(channel: ChannelDefinition, detectionMaxSide?: number | null): Recipe {
  if (channel.role !== "nuclear") throw new Error("核検出に使うチャンネルを選択してください");
  if (detectionMaxSide != null && (!Number.isInteger(detectionMaxSide) || detectionMaxSide < 64 || detectionMaxSide > 2048)) throw new Error("検出用画像の長辺は64〜2048pxで指定してください");
  // Without an explicit size the detection copy follows the estimated nucleus size (nuclear-size/1.0.0),
  // so high-resolution images are not split into nuclear texture.
  return {id: "region-2d", version: detectionMaxSide == null ? "1.7.0" : "1.5.0", region_set_id: "nuclei", label: "核", source: "stardist_nuclear",
    ...(detectionMaxSide == null ? {detection_scale: "nuclear-size/1.0.0" as const} : {detection_max_side_px: detectionMaxSide}),
    defining_channel_id: channel.token, nuclear_role_source: channel.evidence === "user" ? "user_selected_role" : "recorded_stain"};
}

/** Figure identity includes both the saved revision and every editable setting. */
export function figureIdentity(revision: string, choice: FigureChoice) { return JSON.stringify([revision, choice.metric, choice.channel, choice.width, choice.height, choice.label, choice.xLabel ?? "", choice.fontSize ?? 7, choice.language ?? "ja", choice.yMin ?? null, choice.yMax ?? null, choice.yTickStep ?? null, choice.pointSize ?? null]); }

/** Map saved values for interactive selection; never calculate summaries in the browser. */
export function savedDistribution(figure: SavedFigure): {points: DistributionPoint[]; summaries: FieldSummary[]} {
  const points = (figure.result.plot_data ?? []).map(row => {
    if (typeof row.field_id !== "string" || !Number.isInteger(row.region_id) || typeof row.value !== "number" || !Number.isFinite(row.value)) throw new Error("図の出典を確認できません");
    return {field: row.field_id, region: row.region_id as number, value: row.value, state: "included" as const};
  });
  return {points, summaries: figure.result.field_summary.map(row => ({field: row.field_id, n: row.selected_rows,
    excluded: figure.result.selection.excluded, median: row.median, q1: row.q1, q3: row.q3}))};
}

export function createApiAdapter(overrides: Partial<Transport> = {}) {
  const transport = {...defaults, ...overrides};
  const check = () => {if (typeof window !== "undefined") assertWorkspaceConnection(window.location.hostname, API);};
  const client: Transport = {...transport,
    request: (path, options) => {check(); return transport.request(path, options);},
    post: (path, body) => {check(); return transport.post(path, body);},
    blob: (path, signal) => {check(); return transport.blob(path, signal);},
  };
  const uploadKeys = new Map<string, string>();
  let selection: WorkspaceSelection | null = null;
  async function loadSelection(workspace: string) {selection = await client.request<WorkspaceSelection>(`/v1/workspaces/${workspace}/selection`); return selection;}
  async function saveSelection(workspace: string, entries: SelectionEntry[]) {
    if (!selection) throw new Error("保存状態を再読み込みしてください。");
    selection = await client.post<WorkspaceSelection>(`/v1/workspaces/${workspace}/selection`, {version: selection.version, entries});
    return selection;
  }
  async function assertSelection(workspace: string) {
    if (!selection) await loadSelection(workspace);
    const current = await client.request<WorkspaceSelection>(`/v1/workspaces/${workspace}/selection`);
    if (JSON.stringify(current) !== JSON.stringify(selection)) throw new Error("別のタブで採用状態が更新されました。再読み込みしてください。");
  }
  async function adopt(workspace: string, result: SavedResult) {
    // Re-adopting the already adopted revision is not a change and writes nothing.
    if (selection!.entries.every(entry => entry.field_id !== result.field || entry.revision_id === result.revision)) return result;
    await saveSelection(workspace, selection!.entries.map(entry => entry.field_id === result.field ? {...entry, revision_id: result.revision} : entry));
    return result;
  }
  const revisionRecipes = new Map<string, Recipe>();
  const revisionConfigs = new Map<string,RevisionRecord["config"]>();
  const runs = new Map<string, {job_id: string; revision_id: string; recipe: string} | "uncertain">();
  async function waitJob(workspace: string, id: string, onState?: (state: string) => void): Promise<Job> {
    // Polling reads do not extend retention. A lost connection never resubmits a job.
    for (;;) {
      const jobs = await client.request<Job[]>(`/v1/workspaces/${workspace}/jobs`);
      const job = jobs.find(item => item.id === id);
      if (job) onState?.(job.state);
      if (!job) throw new Error("処理が見つかりません。作業の保存期限を確認してください");
      if (job.state === "succeeded") return job;
      if (job.state === "failed" || job.state === "cancelled") throw new TerminalJobError(job.error ? errorCodeMessage(job.error) : "処理を中止しました");
      await client.wait();
    }
  }
  async function readResult(revision: string, field: string, recipe?: Recipe): Promise<SavedResult> {
    if (recipe) revisionRecipes.set(revision, recipe);
    const report = await client.request<Report>(`/v1/revisions/${revision}/region-measurements`);
    if (report.revision_id !== revision) throw new Error("保存された測定値の解析版が一致しません");
    const failure = report.field_failures.find(item => item.field_id === field);
    if (failure) throw new Error(`この視野の解析に失敗しました (${failure.reason})`);
    const table = report.field_tables[field];
    if (!table) throw new Error("この視野の測定値がありません");
    const masks = await client.request<SavedResult["masks"]>(`/v1/revisions/${revision}/region-masks?field_id=${encodeURIComponent(field)}`);
    const record=revisionConfigs.has(revision)?{config:revisionConfigs.get(revision)}:await client.request<{config?:RevisionRecord["config"]}>(`/v1/revisions/${revision}`);
    return {regionSet: revisionRecipes.get(revision)?.region_set_id || "nuclei", revision, field, rows: table.rows, masks, exclusions: report.exclusions, protocol: report.protocol_version,
      ...(record.config?{measurement:record.config.measurement??null,backgrounds:record.config.backgrounds??{},confirmedChannelIds:record.config.confirmed_channel_ids??[]}: {})};
  }
  return {
    async create() {const record = await client.post<Workspace>("/v1/workspaces", {title: "画像解析"}); await loadSelection(record.id); return record;},
    selection: () => selection,
    getFieldLinks(workspace:string){return client.request<FieldLinks>(`/v1/workspaces/${workspace}/field-links`);},
    async saveFieldLink(workspace:string,field:string,value:{version:number;selection_version:number;kind:"analysis"|"reference";reference_for_field_id:string|null}){const result=await client.request<FieldLinks>(`/v1/workspaces/${workspace}/field-links/${field}`,{method:"PUT",body:JSON.stringify(value)});await loadSelection(workspace);return result;},
    getChannelAssignments(workspace: string) {
      return client.request<ChannelAssignments>(`/v1/workspaces/${workspace}/channel-assignments`);
    },
    saveChannelAssignments(workspace: string, assignments: {version:number;assignments:ChannelAssignment[];field_ids?:string[]}) {
      return client.request<ChannelAssignments>(`/v1/workspaces/${workspace}/channel-assignments`, {method: "PUT", body: JSON.stringify(assignments)});
    },
    async isSelectionCurrent(workspace: string) {
      const expected = JSON.stringify(selection);
      const current = await client.request<WorkspaceSelection>(`/v1/workspaces/${workspace}/selection`);
      return JSON.stringify(current) === expected;
    },
    async registerImport(workspace: string, id: string) {
      if (!selection) await loadSelection(workspace);
      if (!selection!.entries.some(entry => entry.id === id)) await saveSelection(workspace, [...selection!.entries, {id, field_id: null, revision_id: null, exclusion_reason: null}]);
    },
    async excludeField(workspace: string, id: string, reason: string | null) {
      return saveSelection(workspace, selection!.entries.map(entry => entry.id === id ? {...entry, exclusion_reason: reason} : entry));
    },
    async recoverField(workspace: string, field: string) {
      await assertSelection(workspace);
      const existing = selection!.entries.find(entry => entry.field_id === field);
      if (existing) return existing;
      const entry: SelectionEntry = {id: crypto.randomUUID(), field_id: field, revision_id: null, exclusion_reason: null};
      await saveSelection(workspace, [...selection!.entries, entry]);
      return entry;
    },
    async upload(workspace: string, field: GroupedField, channels: Grouping["channels"], files: Map<string, File>, entryId?: string) {
      if (channels.length > 4) throw new Error("1視野につき4チャンネルまで取り込めます");
      const data = new FormData();
      const presentChannels = channels.filter(channel => field.files[channel.token]);
      const modes = new Set(presentChannels.map(channel => field.files[channel.token].inputMode || "native"));
      if (modes.size > 1) throw new Error("同じ視野にグレースケール画像とRGB表示画像が混在しています。画像ごとに取り込むか、同じ形式で書き出してください。");
      presentChannels.forEach((channel, index) => {
        const added = field.files[channel.token];
        const file = added && files.get(added.path);
        if (!file) throw new Error(`チャンネル ${channel.stain || channel.token} の画像がありません`);
        data.set(`ch${index}`, file);
      });
      const key = `${workspace}:${field.key}`;
      if (!uploadKeys.has(key)) uploadKeys.set(key, crypto.randomUUID());
      data.set("specification", JSON.stringify({version: "1.1.0", client_upload_id: entryId || uploadKeys.get(key),
        channels: presentChannels.map(channelSpecification), input_mode: modes.has("display-rgb") ? "display-rgb" : "native", metadata: {}, calibration: null}));
      const uploaded = await client.request<ImportedField>(`/v1/workspaces/${workspace}/region-fields`, {method: "POST", body: data});
      if (entryId) {
        const existing = selection!.entries.find(entry => entry.field_id === uploaded.id && entry.id !== entryId);
        await saveSelection(workspace, existing
          ? selection!.entries.filter(entry => entry.id !== entryId)
          : selection!.entries.map(entry => entry.id === entryId ? {...entry, field_id: uploaded.id} : entry));
      }
      return uploaded;
    },
    async uploadOme(workspace:string,file:File,entryId:string){
      const data=new FormData();data.set("ome",file);data.set("client_upload_id",entryId);
      const uploaded=await client.request<ImportedField>(`/v1/workspaces/${workspace}/region-fields/ome`,{method:"POST",body:data});
      const existing=selection!.entries.find(entry=>entry.field_id===uploaded.id&&entry.id!==entryId);
      await saveSelection(workspace,existing?selection!.entries.filter(entry=>entry.id!==entryId):selection!.entries.map(entry=>entry.id===entryId?{...entry,field_id:uploaded.id}:entry));
      return uploaded;
    },
    async preview(field: string, channel: string) { return client.blob(`/v1/region-fields/${field}/preview?channel_id=${encodeURIComponent(channel)}&gain=1`); },
    async run(workspace: string, field: string, recipe: Recipe, onState?: (state: string) => void, measurement: MeasurementPolicy = rawMeasurement, options: {adopt?: boolean} = {}) {
      await assertSelection(workspace);
      const key = `${workspace}:${field}:${JSON.stringify(recipe)}:${measurement.mode}:${options.adopt !== false}`;
      let created = runs.get(key);
      if (created === "uncertain") throw new Error("受付状態を確認できません。再読み込みで保存済みの処理状態を確認してください。");
      if (created && created.recipe !== JSON.stringify(recipe)) throw new Error("受付済みの解析条件が異なります。再読み込みして処理状態を確認してください。");
      if (!created) {
        runs.set(key, "uncertain");
        const accepted = await client.post<{job_id: string; revision_id: string}>(`/v1/workspaces/${workspace}/region-analyses`, {
          field_ids: [field], recipe, measurement, backgrounds: {}, exclusions: [],
        });
        created = {...accepted, recipe: JSON.stringify(recipe)}; runs.set(key, created);
      }
      try {await waitJob(workspace, created.job_id, onState); onState?.("reading_results"); const saved = await readResult(created.revision_id, field, recipe); return options.adopt === false ? saved : await adopt(workspace, saved);}
      catch (error) {if (error instanceof TerminalJobError) runs.delete(key); throw error;}
    },
    startWorkspaceRun(workspace:string,body:{request_id:string;spec_version:number;target:RunTarget;field_ids:string[];purpose?:"preview"|"measurement"}){return client.post<WorkspaceRun>(`/v1/workspaces/${workspace}/runs`,body);},
    listWorkspaceRuns(workspace:string){return client.request<WorkspaceRun[]>(`/v1/workspaces/${workspace}/runs`);},
    async waitWorkspaceRun(workspace:string,id:string,onState?:(run:WorkspaceRun)=>void){for(;;){const run=await client.request<WorkspaceRun>(`/v1/workspaces/${workspace}/runs/${id}`);onState?.(run);if(run.state!=="queued"&&run.state!=="running")return run;await client.wait();}},
    async acceptWorkspaceRun(workspace:string,id:string){const run=await client.post<WorkspaceRun>(`/v1/workspaces/${workspace}/runs/${id}/accept`,{});await loadSelection(workspace);return run;},
    cancelWorkspaceRun(workspace:string,id:string){return client.post<WorkspaceRun>(`/v1/workspaces/${workspace}/runs/${id}/cancel`,{});},
    readResult,
    async restore(workspace: string) {
      const [record, fields, revisions, jobs] = await Promise.all([
        client.request<Workspace>(`/v1/workspaces/${workspace}`),
        client.request<ImportedField[]>(`/v1/workspaces/${workspace}/region-fields`),
        client.request<RevisionRecord[]>(`/v1/workspaces/${workspace}/revisions`),
        client.request<Job[]>(`/v1/workspaces/${workspace}/jobs`),
      ]);
      for (const revision of revisions) {revisionRecipes.set(revision.id, revision.config.recipe);revisionConfigs.set(revision.id,revision.config);}
      const adopted = await loadSelection(workspace);
      return {record, fields, revisions, jobs, selection: adopted};
    },
    async resume(workspace: string, job: Job, field: string) {await waitJob(workspace, job.id); return adopt(workspace, await readResult(job.revision_id, field));},
    async correct(workspace: string, result: SavedResult, kind: "exclude" | "delete", region: number, recipe: Recipe) {
      await assertSelection(workspace);
      await client.post(`/v1/workspaces/${workspace}/current`, {revision_id: result.revision});
      const created = kind === "delete"
        ? await client.post<{job_id: string; revision_id: string}>(`/v1/revisions/${result.revision}/region-edits`, {
          field_id: result.field, region_set_id: recipe.region_set_id, operation: "delete", ids: [region], polygon: [], expected_mask_revision_id: result.masks.metadata.mask_revision_id,
        })
        : await client.post<{job_id: string; revision_id: string}>(`/v1/revisions/${result.revision}/region-reconfigure`, {
          field_ids: [result.field], recipe, measurement: measurementOf(result), backgrounds: result.backgrounds??{},
          ...(result.confirmedChannelIds?.length?{confirmed_channel_ids:result.confirmedChannelIds}:{}),
          exclusions: [...result.exclusions, {field_id: result.field, region_id: region, reason: "ワークスペースで対象から除外（利用者の操作）"}],
        });
      await waitJob(workspace, created.job_id);
      return adopt(workspace, await readResult(created.revision_id, result.field, recipe));
    },
    async selectRevision(workspace: string, revision: string, field: string) {
      await assertSelection(workspace);
      return adopt(workspace, await readResult(revision, field));
    },
    async editMask(workspace: string, result: SavedResult, recipe: Recipe, operation: MaskOperation, polygon: Point[], region?: number, merged: number[] = []) {
      if (operation === "merge" ? merged.length < 2 : polygon.length < 3 || (operation !== "add" && !region)) throw new Error("修正する領域と輪郭を指定してください");
      await assertSelection(workspace);
      await client.post(`/v1/workspaces/${workspace}/current`, {revision_id: result.revision});
      const created = await client.post<{job_id: string; revision_id: string}>(`/v1/revisions/${result.revision}/region-edits`, {
        field_id: result.field, region_set_id: recipe.region_set_id, operation,
        ids: operation === "add" ? [] : operation === "merge" ? merged : [region], polygon: operation === "merge" ? [] : polygon,
        expected_mask_revision_id: result.masks.metadata.mask_revision_id,
      });
      await waitJob(workspace, created.job_id);
      return adopt(workspace, await readResult(created.revision_id, result.field, recipe));
    },
    async gfpGate(workspace: string, body: {gfp_channel_id: string; percentile: number; unit?: "nucleus" | "cell_roi"; method?: "negative_control" | "manual" | "batch_otsu"; threshold?: number; values?: "raw" | "corrected"; fields: Array<{field_id: string; revision_id: string; control: boolean}>}) {
      return client.post<GfpGateResult>(`/v1/workspaces/${workspace}/gfp-gate`, body);
    },
    async compartmentSummary(revision: string, field: string) {
      return client.request<CompartmentSummaryFile>(`/v1/revisions/${revision}/compartment-summary?field_id=${encodeURIComponent(field)}`);
    },
    async figure(workspace: string, result: SavedResult, choice: FigureChoice): Promise<SavedFigure> {
      const created = await client.post<{job_id: string}>(`/v1/revisions/${result.revision}/descriptive-preview`, {
        mode: "descriptive", selection: {source: "region", region_set_id: result.regionSet || "nuclei", metric: choice.metric, channel_id: choice.channel},
        group_by: "field", plot: {kind: "distribution", preset: "custom", width_inches: choice.width / 25.4, height_inches: choice.height / 25.4, language: choice.language ?? "en", y_label: choice.label, x_label: choice.xLabel ?? "", font_size: choice.fontSize ?? 7, y_min: choice.yMin ?? null, y_max: choice.yMax ?? null, y_tick_step: choice.yTickStep ?? null, point_size: choice.pointSize ?? null},
      });
      await waitJob(workspace, created.job_id);
      const saved = await client.request<DescriptiveResult>(`/v1/jobs/${created.job_id}/result`);
      if (saved.revision_id !== result.revision) throw new Error("図と測定値の解析版が一致しません");
      return {job: created.job_id, revision: result.revision, choice, result: saved};
    },
    figureFiles(figure: SavedFigure) {
      const view = descriptiveFigureView(figure.result);
      return {view, files: figure.result.figure.source_files};
    },
    async draft(workspace: string, goal: string, retryFailed = false, continuation?: {current_processing: ProposalProcessing | null; previous_goal: string; previous_proposal: ProposalDraft | null;field_id?:string}) {
      // Called only after the one-time scope notice has been accepted in this workspace.
      const response = await client.post<{proposal: ValidatedProposal; channels: ProposalChannelLink[]}>(`/v1/workspaces/${workspace}/proposal-drafts`, {goal, transmission_confirmed: true, ...(retryFailed ? {retry_failed: true} : {}), ...continuation});
      return {proposal: localProposal(response.proposal,response.channels)};
    },
  };
}
export type ApiAdapter = ReturnType<typeof createApiAdapter>;
