import {measureLabel,metricLabel,metricUsesChannel,nucleusPositivity} from "../../../lib/workspace/metric-catalog";
import type {ResultOperation} from "./connected-results-model";

/** What a result answers, in the terms the side panel chooses (genellect/cytellect#257 D-1, D-2): the analysis,
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
