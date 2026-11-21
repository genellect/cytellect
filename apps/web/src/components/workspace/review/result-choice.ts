import {measureLabel,metricLabel,metricUsesChannel,nucleusPositivity} from "../../../lib/workspace/metric-catalog";
import type {ResultOperation} from "./connected-results-model";

/** What a result answers, in the terms the side panel chooses (requirements SR-01, SR-02): the analysis,
 * the region set the values come from, the metric, the stain, a nucleus filter, the association's
 * horizontal axis and the stratum. Two results with the same condition answer the same question. */
export interface ResultCondition {
  operation: ResultOperation;
  regionSet: string;
  metric: string;
  /** The measured stain's channel; for positive counts and fractions, the classified channel. Null when the metric reads no stain. */
  channel: string | null;
  /** A nucleus filter applied before measuring (`cg:<channel>:<keep>` or `gfp:<channel>`), "" without one. */
  filter: string;
  x: {metric: string; channel: string | null} | null;
  stratum: string | null;
}

/** The saved request and payload parts this module reads; every field is optional in old results. */
export interface SavedSelectionLike {
  source?: string; region_set_id?: string; metric?: string; channel_id?: string | null;
  channel_gate?: {channel_id?: string; keep?: string} | null;
  gfp_gate?: {gfp_channel_id?: string} | null;
  positivity?: {channel_id?: string; gfp_channel_id?: string} | null;
}
export interface SavedChannelLike {channel_id: string; label?: string; stain?: string | null}
export interface SavedResultLike {
  metric?: string;
  channel?: SavedChannelLike | null;
  estimates?: {metric: string} | null;
  stratum?: {label: string} | null;
  selection?: {channel_gate?: {channel?: SavedChannelLike}} | null;
  spec?: {selection?: SavedSelectionLike; x_selection?: SavedSelectionLike; y_selection?: SavedSelectionLike} | null;
  x_source?: {metric?: string; channel?: SavedChannelLike | null; source_fields?: SavedResultLike["source_fields"]} | null;
  y_source?: {metric?: string; channel?: SavedChannelLike | null; source_fields?: SavedResultLike["source_fields"]} | null;
  /** Each field's adopted regions (their mask revision) and measurement, as the result recorded them. */
  source_fields?: Array<{field_id: string; region_set?: {region_set_id?: string; mask_revision_id?: string};
    measurement_protocol?: string; measurement?: {mode?: string} | null}>;
}

const positive = nucleusPositivity;
/** The stain channel a metric reads, as the side panel holds it. */
export function conditionChannel(metric: string, channel: string | null, gateChannel: string | null): string | null {
  return positive(metric) ? gateChannel : metricUsesChannel(metric) ? channel : null;
}
function filterKey(selection: SavedSelectionLike | undefined): string {
  if (!selection || positive(selection.metric ?? "")) return "";
  if (selection.channel_gate) return `cg:${selection.channel_gate.channel_id ?? ""}:${selection.channel_gate.keep ?? ""}`;
  if (selection.gfp_gate) return `gfp:${selection.gfp_gate.gfp_channel_id ?? ""}`;
  return "";
}
/** The nucleus filter of the side panel's choice, in the same form as a saved one. */
export function choiceFilter(metric: string, gfp: {channel?: string} | {gfp_channel_id?: string} | null, channelGate: {channel_id: string; keep: string} | null): string {
  if (positive(metric)) return "";
  if (gfp) return `gfp:${"gfp_channel_id" in gfp ? gfp.gfp_channel_id ?? "" : "channel" in gfp ? gfp.channel ?? "" : ""}`;
  if (channelGate) return `cg:${channelGate.channel_id}:${channelGate.keep}`;
  return "";
}

/** The condition a saved result answers, from the request it saved; null when the result does not record one. */
export function savedCondition(operation: ResultOperation, result: SavedResultLike): ResultCondition | null {
  const spec = result.spec ?? {};
  const y = operation === "association" ? spec.y_selection : spec.selection;
  const metric = y?.metric ?? result.estimates?.metric ?? result.metric ?? result.y_source?.metric;
  const regionSet = y?.region_set_id ?? result.source_fields?.[0]?.region_set?.region_set_id;
  if (!metric || !regionSet) return null;
  const gateChannel = y?.positivity?.channel_id ?? y?.positivity?.gfp_channel_id ?? result.selection?.channel_gate?.channel?.channel_id ?? null;
  const measured = y?.channel_id ?? (operation === "association" ? result.y_source?.channel?.channel_id : result.channel?.channel_id) ?? null;
  const x = operation === "association" ? spec.x_selection : undefined;
  const xMetric = x?.metric ?? result.x_source?.metric;
  return {operation, regionSet, metric, channel: conditionChannel(metric, measured, gateChannel), filter: filterKey(y),
    x: operation === "association" && xMetric ? {metric: xMetric, channel: conditionChannel(xMetric, x?.channel_id ?? result.x_source?.channel?.channel_id ?? null, null)} : null,
    stratum: result.stratum?.label ?? null};
}

export function conditionKey(condition: ResultCondition | null): string {
  return condition ? JSON.stringify([condition.operation, condition.regionSet, condition.metric, condition.channel, condition.filter,
    condition.x ? [condition.x.metric, condition.x.channel] : null, condition.stratum]) : "";
}

/** One chosen field's measurement as the result place compares it: its adopted regions and measurement. */
export interface CurrentSource {field: string; mask: string; protocol?: string; mode?: string}
/** Whether a saved result was calculated from exactly the fields now chosen, with the same adopted regions (mask
 * revision) and measurement protocol and mode. A result records no background value per field, so a changed
 * background within the same protocol and mode is not told apart here. */
export function sameSources(saved: SavedResultLike["source_fields"], current: CurrentSource[]): boolean {
  if (!saved?.length || saved.length !== current.length) return false;
  const chosen = new Map(current.map(source => [source.field, source]));
  return saved.every(field => {
    const source = chosen.get(field.field_id);
    return !!source && !!source.mask && field.region_set?.mask_revision_id === source.mask
      && (!field.measurement_protocol || !source.protocol || field.measurement_protocol === source.protocol)
      && (!field.measurement?.mode || !source.mode || field.measurement.mode === source.mode);
  });
}

/** The newest saved result for a condition (entries newest first): `current` when it was calculated from the
 * measurements now chosen, `older` when only an earlier measurement of the same condition was saved. */
export function savedFor<T extends {operation: ResultOperation; result: SavedResultLike}>(entries: T[], condition: ResultCondition | null,
  sources: CurrentSource[]): {current?: T; older?: T} {
  const key = conditionKey(condition);
  if (!key) return {};
  const same = entries.filter(entry => conditionKey(savedCondition(entry.operation, entry.result)) === key);
  // An association keeps its fields per axis (both axes are measured on the same fields).
  const fieldsOf = (result: SavedResultLike) => result.source_fields ?? result.y_source?.source_fields ?? result.x_source?.source_fields;
  return {current: same.find(entry => sameSources(fieldsOf(entry.result), sources)), older: same[0]};
}

export {measureLabel};
const stainOf = (channel: SavedChannelLike | null | undefined) => channel ? channel.stain || channel.label || channel.channel_id : null;

/** The measure a saved result shows (its vertical axis for an association), named by its recorded stain. */
export function savedMeasureLabel(operation: ResultOperation, result: SavedResultLike): string {
  const condition = savedCondition(operation, result);
  if (!condition) return metricLabel(result.estimates?.metric ?? result.metric ?? "");
  const channel = positive(condition.metric) ? result.selection?.channel_gate?.channel
    : operation === "association" ? result.y_source?.channel : result.channel;
  const stain = stainOf(channel) ?? condition.channel;
  return measureLabel(condition.metric, condition.regionSet, stain);
}

export const ANALYSIS_NAMES: Record<ResultOperation, string> = {comparison: "群間比較", association: "相関", distribution: "分布"};

/** An analysis the chosen measure cannot have is changed by the view; the researcher reads why (requirements SR-04). */
export function automaticOperation({operation, canAssociate, unconfirmed, saturated, saturatedAny, descriptive}: {
  operation: ResultOperation; canAssociate: boolean; unconfirmed: boolean; saturated: boolean; saturatedAny: boolean; descriptive: boolean;
}): {operation: ResultOperation; reason: string} | null {
  if (operation === "association" && unconfirmed) return {operation: "distribution", reason: "実験回の独立性が未確認のため、相関から分布に切り替えました。"};
  if (operation === "association" && !canAssociate) return {operation: "distribution", reason: saturatedAny
    ? "飽和した画素を含む群があるため、相関から分布に切り替えました。" : "この指標では相関を計算できないため、分布に切り替えました。"};
  if (operation === "comparison" && saturated) return {operation: "distribution", reason: "飽和した画素を含む群があり、群間比較ができないため、分布に切り替えました。"};
  if (operation === "distribution" && !descriptive && !saturated) return {operation: "comparison", reason: "この指標は分布を出せないため、群間比較に切り替えました。"};
  return null;
}

/** What the calculation still needs, named so that it can be done before 計算 is pressed (requirements SR-03). */
export function calculationNeeds(state: {
  stratumMissing: boolean; unstratified: number; sources: number; missing: number; reviewed: boolean;
  ledgerError: boolean; unresolvedUnconfirmed: boolean; designUnconfirmed: boolean; metadata: string | null;
  datesMissing: boolean; independenceMissing: boolean; positivityMissing: boolean; classificationMissing: boolean; unsupportedAxes: boolean;
  /** A design declared on 実験 (D-6): only the acquisition and the inclusion of fields are confirmed here. */
  declaredDesign?: boolean;
}): string[] {
  return [
    state.stratumMissing && "比べる層の選択",
    state.unstratified > 0 && `層が決まっていない視野（${state.unstratified} 件）の割り当て`,
    !state.sources && "測定した視野",
    state.missing > 0 && `${state.missing} 視野の測定`,
    state.positivityMissing && "核の分類（「画像」で色分けを「陽性・陰性」に）",
    state.classificationMissing && "分類記録の確認（「現在の実験情報で再分類」）",
    state.unsupportedAxes && "相関案の作り直し",
    state.metadata,
    state.datesMissing && "撮影日の入力",
    state.independenceMissing && "実験回の独立性の確認",
    state.ledgerError && "核小体を確定できない核の一覧の読み込み",
    state.unresolvedUnconfirmed && "核小体を確定できない核の一覧の確認",
    state.designUnconfirmed && (state.declaredDesign ? "撮影・画素条件と採否の確認" : "実験回の定義と解析条件の確認"),
    !state.reviewed && "測定領域と採用する視野の確認",
  ].filter((value): value is string => !!value);
}
