/** Stage-one review: read saved inputs/adoptions only; never run or adopt an analysis. */
import {effectiveChannelAssignments} from "./channel-assignments";
import {ApiError, fetchPrivateResponse, post, request} from "../api";
import {PREVIEW_DISPLAY_HEADER, readPreviewDisplay, type DisplayReceipt} from "../preview-display";
import type {Workspace} from "../types";
import {createApiAdapter, type ChannelAssignments, type Recipe, type SavedResult} from "./api-adapter";

export type ReviewTarget = "nuclei" | "nucleoli" | "nucleoplasm" | "cell";
export interface ReviewChannel {
  id: string;
  label: string;
  stain: string | null;
  role: "nuclear" | "measure" | "unused" | null;
}
export interface ReviewField {
  id: string;
  label: string;
  /** Defining channel of the loaded, adopted nucleus revision; never a stain inference. */
  nuclearChannelId?: string;
  metadata?: Record<string,string|number|null>;
  kind?:"analysis"|"reference";referenceFor?:string|null;
  width: number;
  height: number;
  channels: ReviewChannel[];
  previews: Record<string, string>;
  previewDisplay?: Record<string, DisplayReceipt>;
  results: Partial<Record<ReviewTarget, SavedResult>>;
  error?: string;
  exclusionReason?: string;
}
export interface ReviewData {
  workspaceId: string;
  title: string;
  fields: ReviewField[];
  channels: ReviewChannel[];
  warnings?: string[];
}

function biologicalTarget(recipe: Recipe): ReviewTarget | null {
  if (recipe.source === "stardist_nuclear") return "nuclei";
  if (recipe.source === "fiji_nuclear_compartment" && (recipe.compartment === "nucleoli" || recipe.compartment === "nucleoplasm")) return recipe.compartment;
  if (recipe.source === "manual" && recipe.region_set_id === "cell") return "cell";
  // Other named region sets or a
  // bright connected component must never be promoted to a cell/nucleolus.
  return null;
}

async function ensureSession() {
  try {
    const session = await request<{authenticated: boolean}>("/v1/session");
    if (!session.authenticated) throw new Error("session_required");
  } catch (error) {
    if (!(error instanceof ApiError && error.status === 401 && process.env.NEXT_PUBLIC_CYTELLECT_DESKTOP_OWNER === "true")) throw error;
    // The existing Desktop owner bootstrap is the sole permitted mutation.
    await post("/v1/desktop/session");
  }
}

export function releaseReviewPreview(data: ReviewData) {
  for (const url of new Set(data.fields.flatMap(field => Object.values(field.previews)))) URL.revokeObjectURL(url);
}

export async function loadReviewPreview(workspaceId?: string, fieldIds?: readonly string[]): Promise<ReviewData> {
  await ensureSession();
  if (!workspaceId) {
    // API returns a bare, unsorted list; created is in WorkspaceView's response.
    const saved = await request<Array<Workspace & {created: number; deleted: boolean}>>("/v1/workspaces");
    workspaceId = saved.filter(value => !value.deleted && value.expires > Date.now() / 1000)
      .sort((left, right) => right.created - left.created)[0]?.id;
    if (!workspaceId) throw new Error("no_saved_workspace");
  }
  const adapter = createApiAdapter();
  const saved = await adapter.restore(workspaceId);
  const data: ReviewData = {workspaceId, title: saved.record.title, fields: [], channels: [], warnings: []};
  let assignments: ChannelAssignments = {version: 0, assignments: []};
  try {assignments = await adapter.getChannelAssignments(workspaceId);}
  catch {data.warnings!.push("保存した染色設定を取得できません。登録時の名称を表示しています。");}
  let links:import("./api-adapter").FieldLinks={version:0,entries:[]};
  try{links=await adapter.getFieldLinks(workspaceId);}catch{data.warnings!.push("補助画像の対応を取得できません。");}
  try {
    for (const [index, input] of saved.fields.entries()) {
      if (fieldIds && !fieldIds.includes(input.id)) continue;
      const errors: string[] = [];
      const assigned=new Map(effectiveChannelAssignments(assignments,input.id).map(value=>[value.channel_id,value]));
      const link=links.entries.find(value=>value.field_id===input.id);
      const channels = input.image_info.channels.map(channel => {
        const assignment = assigned.get(channel.channel_id);
        return {id: channel.channel_id, label: assignment ? assignment.stain || channel.channel_id : channel.label,
          stain: assignment ? assignment.stain : channel.stain, role: assignment?.role ?? null};
      });
      const displayName = input.metadata.display_name;
      const field: ReviewField = {id: input.id, label: typeof displayName === "string" && displayName.trim() ? displayName : `視野 ${index + 1}`,
        metadata: input.metadata,kind:link?.kind??"analysis",referenceFor:link?.reference_for_field_id??null, width: input.image_info.shape[1], height: input.image_info.shape[0], channels, previews: {}, previewDisplay: {}, results: {}};
      data.fields.push(field);
      const entry = saved.selection.entries.find(value => value.field_id === input.id);
      if (entry?.exclusion_reason) field.exclusionReason = entry.exclusion_reason;
      if (!entry) errors.push("保存された解析対象への登録が完了していません。");
      const selectedIds = new Set(Object.values(entry?.target_revisions ?? {}));
      if (entry?.revision_id) selectedIds.add(entry.revision_id);
      const recipes: Partial<Record<ReviewTarget, Recipe>> = {};
      for (const id of selectedIds) {
        const revision = saved.revisions.find(value => value.id === id);
        if (!revision || !revision.config.field_ids.includes(input.id)) {errors.push("採用した解析版の出典を確認できません。"); continue;}
        const target = biologicalTarget(revision.config.recipe);
        if (!target) continue;
        const mapped = entry?.target_revisions?.[target];
        if (mapped && mapped !== id) continue;
        if (revision.state !== "succeeded") {errors.push("採用した解析版はまだ完了していません。"); continue;}
        try {
          field.results[target] = await adapter.readResult(id, input.id, revision.config.recipe);
          recipes[target] = revision.config.recipe;
        } catch {errors.push("採用した領域または測定値を読み込めません。");}
      }
      for (const target of ["nucleoli", "nucleoplasm"] as const) {
        const recipe = recipes[target];
        if (recipe && (recipe.nuclear_revision_id !== field.results.nuclei?.revision ||
          recipe.nuclear_channel_id !== recipes.nuclei?.defining_channel_id ||
          (target === "nucleoplasm" && recipe.nucleolar_revision_id && recipe.nucleolar_revision_id !== field.results.nucleoli?.revision))) {
          delete field.results[target];
          errors.push("保存した子領域と採用中の親領域の版が一致しません。");
        }
      }
      if (field.results.nuclei && recipes.nuclei?.defining_channel_id &&
        channels.some(channel => channel.id === recipes.nuclei!.defining_channel_id)) {
        field.nuclearChannelId = recipes.nuclei.defining_channel_id;
      }
      for (const channel of channels) {
        try {
          const response = await fetchPrivateResponse(`/v1/region-fields/${encodeURIComponent(input.id)}/preview?channel_id=${encodeURIComponent(channel.id)}&gain=1`);
          const receipt = readPreviewDisplay(response.headers.get(PREVIEW_DISPLAY_HEADER), {fieldId: input.id, channel: channel.id, gain: 1, composite: false});
          field.previews[channel.id] = URL.createObjectURL(await response.blob());
          field.previewDisplay![channel.id] = receipt;
        } catch {errors.push("画像プレビューを読み込めません。");}
        const existing = data.channels.find(value => value.id === channel.id);
        if (!existing) data.channels.push(channel);
        else if (existing.stain !== channel.stain) data.warnings!.push("同じチャンネルの登録名称が視野間で異なります。各画像の名称を確認してください。");
      }
      if (errors.length) field.error = [...new Set(errors)].join(" ");
    }
    data.warnings = [...new Set(data.warnings)];
    return data;
  } catch (error) {
    releaseReviewPreview(data);
    throw error;
  }
}
