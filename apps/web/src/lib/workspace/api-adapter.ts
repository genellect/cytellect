/** Real workspace transport. Pixels, masks, summaries and figures remain server-owned. */
import { API, errorCodeMessage, fetchBlob, post, request } from "../api";
import { descriptiveFigureView, type DescriptiveResult } from "../descriptive-view";
import type { Job, Point, Workspace } from "../types";
import type { ChannelDefinition, GroupedField, Grouping } from "./grouping";
import type {DistributionPoint, FieldSummary} from "./adapter";

export interface SelectionEntry {id: string; field_id: string | null; revision_id: string | null; exclusion_reason: string | null}
export interface WorkspaceSelection {version: number; entries: SelectionEntry[]}
export interface ImportedField {
  id: string; workspace_id: string;
  metadata: Record<string, string | number | null>;
  image_info: {input_mode?: "native" | "display-rgb"; shape: [number, number]; channels: Array<{channel_id: string; label: string; stain: string | null}>};
}
export interface MeasurementRow {
  region_id: number; channel_id: string; area_px: number; area_um2: number | null;
  mean: number | null; median: number | null; integrated: number | null;
}
export interface SavedResult {
  regionSet?: string; revision: string; field: string; rows: MeasurementRow[];
  masks: {regions: Array<{id: number; points: Point[]}>; metadata: {mask_revision_id: string}};
  exclusions: Array<{field_id: string; region_id: number | null; reason: string}>;
}
interface Report {
  revision_id: string; field_tables: Record<string, {rows: MeasurementRow[]}>;
  field_failures: Array<{field_id: string; reason: string}>;
  exclusions: SavedResult["exclusions"];
}
export interface FigureChoice {metric: string; channel: string | null; width: number; height: number; label: string}
export interface SavedFigure {job: string; revision: string; choice: FigureChoice; result: DescriptiveResult}
export interface Recipe {
  id: "region-2d"; version: "1.2.0" | "1.3.0" | "1.4.0"; region_set_id: string; label: string;
  source: "stardist_nuclear" | "fiji_positive_regions" | "fiji_nuclear_compartment"; defining_channel_id: string;
  compartment?: "nucleoli" | "nucleoplasm"; nuclear_revision_id?: string; nuclear_channel_id?: string;
  detector?: {threshold_method?: "otsu" | "manual"; threshold?: number | null; smoothing_sigma_px: number; minimum_area_px: number; split_touching: boolean};
  nuclear_role_source?: "recorded_stain" | "user_selected_role";
}
export interface RevisionRecord {id: string; state: string; created: number; config: {recipe: Recipe; field_ids: string[]; exclusions?: SavedResult["exclusions"]}}
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

export function nuclearRecipe(channel: ChannelDefinition): Recipe {
  if (channel.role !== "nuclear") throw new Error("核検出に使うチャンネルを選択してください");
  return {id: "region-2d", version: "1.2.0", region_set_id: "nuclei", label: "核", source: "stardist_nuclear",
    defining_channel_id: channel.token, nuclear_role_source: channel.evidence === "user" ? "user_selected_role" : "recorded_stain"};
}

/** Figure identity includes both the saved revision and every editable setting. */
export function figureIdentity(revision: string, choice: FigureChoice) { return JSON.stringify([revision, choice.metric, choice.channel, choice.width, choice.height, choice.label]); }

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
    await saveSelection(workspace, selection!.entries.map(entry => entry.field_id === result.field ? {...entry, revision_id: result.revision} : entry));
    return result;
  }
  const revisionRecipes = new Map<string, Recipe>();
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
    return {regionSet: revisionRecipes.get(revision)?.region_set_id || "nuclei", revision, field, rows: table.rows, masks, exclusions: report.exclusions};
  }
  return {
    async create() {const record = await client.post<Workspace>("/v1/workspaces", {title: "画像解析"}); await loadSelection(record.id); return record;},
    selection: () => selection,
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
    async preview(field: string, channel: string) { return client.blob(`/v1/region-fields/${field}/preview?channel_id=${encodeURIComponent(channel)}&gain=1`); },
    async run(workspace: string, field: string, recipe: Recipe, onState?: (state: string) => void) {
      await assertSelection(workspace);
      const key = `${workspace}:${field}:${JSON.stringify(recipe)}`;
      let created = runs.get(key);
      if (created === "uncertain") throw new Error("受付状態を確認できません。再読み込みで保存済みの処理状態を確認してください。");
      if (created && created.recipe !== JSON.stringify(recipe)) throw new Error("受付済みの解析条件が異なります。再読み込みして処理状態を確認してください。");
      if (!created) {
        runs.set(key, "uncertain");
        const accepted = await client.post<{job_id: string; revision_id: string}>(`/v1/workspaces/${workspace}/region-analyses`, {
          field_ids: [field], recipe, measurement: {version: "1.1.0", mode: "raw_intensity"}, backgrounds: {}, exclusions: [],
        });
        created = {...accepted, recipe: JSON.stringify(recipe)}; runs.set(key, created);
      }
      try {await waitJob(workspace, created.job_id, onState); onState?.("reading_results"); return await adopt(workspace, await readResult(created.revision_id, field, recipe));}
      catch (error) {if (error instanceof TerminalJobError) runs.delete(key); throw error;}
    },
    readResult,
    async restore(workspace: string) {
      const [record, fields, revisions, jobs] = await Promise.all([
        client.request<Workspace>(`/v1/workspaces/${workspace}`),
        client.request<ImportedField[]>(`/v1/workspaces/${workspace}/region-fields`),
        client.request<RevisionRecord[]>(`/v1/workspaces/${workspace}/revisions`),
        client.request<Job[]>(`/v1/workspaces/${workspace}/jobs`),
      ]);
      for (const revision of revisions) revisionRecipes.set(revision.id, revision.config.recipe);
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
          field_ids: [result.field], recipe, measurement: {version: "1.1.0", mode: "raw_intensity"}, backgrounds: {},
          exclusions: [...result.exclusions, {field_id: result.field, region_id: region, reason: "ワークスペースで対象から除外（利用者の操作）"}],
        });
      await waitJob(workspace, created.job_id);
      return adopt(workspace, await readResult(created.revision_id, result.field, recipe));
    },
    async selectRevision(workspace: string, revision: string, field: string) {
      await assertSelection(workspace);
      return adopt(workspace, await readResult(revision, field));
    },
    async figure(workspace: string, result: SavedResult, choice: FigureChoice): Promise<SavedFigure> {
      const created = await client.post<{job_id: string}>(`/v1/revisions/${result.revision}/descriptive-preview`, {
        mode: "descriptive", selection: {source: "region", region_set_id: result.regionSet || "nuclei", metric: choice.metric, channel_id: choice.channel},
        group_by: "field", plot: {kind: "distribution", preset: "custom", width_inches: choice.width / 25.4, height_inches: choice.height / 25.4, language: "ja", y_label: choice.label},
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
    async draft(workspace: string, goal: string, retryFailed = false) {
      // Called only after the one-time scope notice has been accepted in this workspace.
      return client.post<{proposal: {draft: {rationale: string; missing_information: string[]}; needs_confirmation: string[]}}>(`/v1/workspaces/${workspace}/proposal-drafts`, {goal, transmission_confirmed: true, ...(retryFailed ? {retry_failed: true} : {})});
    },
  };
}
export type ApiAdapter = ReturnType<typeof createApiAdapter>;
