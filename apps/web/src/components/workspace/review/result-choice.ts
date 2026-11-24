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
  /** A nucleus filter applied before measuring (`cg:<channel>:<measured value>:<keep>`, see gateKey, or `gfp:<channel>`), "" without one. */
  filter: string;
  x: {metric: string; channel: string | null} | null;
  stratum: string | null;
}

/** The saved request and payload parts this module reads; every field is optional in old results. */
export interface SavedSelectionLike {
  source?: string; region_set_id?: string; metric?: string; channel_id?: string | null;
  channel_gate?: {channel_id?: string; values?: string; keep?: string} | null;
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
  spec?: {selection?: SavedSelectionLike; x_selection?: SavedSelectionLike; y_selection?: SavedSelectionLike;
    /** The comparison's test ("none" without inference), the association's method and the design, as requested. */
    test?: string | null; method?: string | null; design?: {kind?: string | null} | null} | null;
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
/** A classification by a stain: its stain, the measured value it classified by (raw or background-corrected) and
 * the nuclei kept, `eu5:raw:positive`. The same stain classified by another value keeps other nuclei. */
export function gateKey(gate: {channel_id?: string; values?: string; keep?: string}): string {
  return [gate.channel_id ?? "", ...(gate.values ? [gate.values] : []), gate.keep ?? ""].join(":");
}
function filterKey(selection: SavedSelectionLike | undefined): string {
  if (!selection || positive(selection.metric ?? "")) return "";
  if (selection.channel_gate) return `cg:${gateKey(selection.channel_gate)}`;
  if (selection.gfp_gate) return `gfp:${selection.gfp_gate.gfp_channel_id ?? ""}`;
  return "";
}
/** The nucleus filter of the side panel's choice, in the same form as a saved one. */
export function choiceFilter(metric: string, gfp: {channel?: string} | {gfp_channel_id?: string} | null, channelGate: {channel_id: string; values?: string; keep: string} | null): string {
  if (positive(metric)) return "";
  if (gfp) return `gfp:${"gfp_channel_id" in gfp ? gfp.gfp_channel_id ?? "" : "channel" in gfp ? gfp.channel ?? "" : ""}`;
  if (channelGate) return `cg:${gateKey(channelGate)}`;
  return "";
}
/**
 * Whether a recorded statistic of the public demo (`recorded-statistics.json`, its `gate`) holds the nucleus filter of a
 * choice (`choiceFilter`). An index written before the measured value was part of the key (`eu5:positive`) names any
 * value: it is read as it was then, so a demo published with it offers what it offered.
 */
export function recordedGateMatches(recorded: string | null | undefined, filter: string): boolean {
  if (!recorded) return filter === "";
  if (`cg:${recorded}` === filter) return true;
  const parts = recorded.split(":");
  if (parts.length !== 2) return false;
  const chosen = filter.split(":");
  return chosen.length === 4 && chosen[0] === "cg" && chosen[1] === parts[0] && chosen[3] === parts[1];
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

/** An analysis the chosen measure or design cannot have is changed by the view, and the researcher reads why
 * (genellect/cytellect#257 SR-04). With two or more groups the result is the group comparison (owner decision 15,
 * 2026-11-21): the distribution is an analysis only of a design without a comparison, or the fallback when every
 * pair holds saturated pixels. */
export function automaticOperation({operation, comparable, canAssociate, unconfirmed, saturated, saturatedAny, descriptive}: {
  operation: ResultOperation; comparable: boolean; canAssociate: boolean; unconfirmed: boolean; saturated: boolean; saturatedAny: boolean; descriptive: boolean;
}): {operation: ResultOperation; reason: string} | null {
  if (operation === "association" && unconfirmed) return {operation: comparable && !saturated ? "comparison" : "distribution", reason: "実験回の独立性が未確認のため、相関は計算しません。"};
  if (operation === "association" && !canAssociate) return {operation: comparable && !saturated ? "comparison" : "distribution", reason: saturatedAny
    ? "飽和した画素を含む群があるため、相関は計算しません。" : "この指標では相関を計算できません。"};
  if (operation === "comparison" && saturated) return {operation: "distribution", reason: "すべての比較に飽和した画素を含む群があるため、群間比較はできません。"};
  if (operation === "distribution" && comparable && !saturated) return {operation: "comparison", reason: ""};
  if (operation === "distribution" && !descriptive && !saturated) return {operation: "comparison", reason: "この指標は分布を出せません。"};
  return null;
}

/** The analysis settings that change a result beyond its condition: the test, the pairing and the rank method. */
export interface ChosenMethod {paired: boolean; rank: boolean; inference: boolean}
/** Whether a saved result was calculated with the method now chosen (genellect/cytellect#257 review, 2026-11-21): a
 * p value of a paired t test is not shown under a choice of a rank test, nor a test under a choice of a description.
 * A result that records no method (an older format) is taken as it was. */
export function sameMethod(operation: ResultOperation, spec: SavedResultLike["spec"], chosen: ChosenMethod): boolean {
  if (operation === "distribution" || !spec) return true;
  if (operation === "association") return !spec.method || spec.method === (chosen.rank ? "spearman" : "pearson");
  const kind = spec.design?.kind;
  if (kind && kind !== (chosen.paired ? "paired" : "independent")) return false;
  if (!spec.test) return true;
  // A description answers a choice that could be tested as well: chosen without 計算, a comparison is described, and
  // 計算 tests it (D-5, genellect/cytellect#257 decision 11). A test never answers a choice that cannot be tested.
  if (spec.test === "none") return true;
  const expected = !chosen.inference ? "none" : chosen.paired ? (chosen.rank ? "wilcoxon" : "paired-t") : (chosen.rank ? "mann-whitney-u" : "welch-t");
  return spec.test === expected;
}
/** The method a saved result was calculated with, for the side panel to follow it when the result is chosen. */
export function savedMethod(operation: ResultOperation, spec: SavedResultLike["spec"]): {paired?: boolean; rank?: boolean} {
  if (!spec || operation === "distribution") return {};
  if (operation === "association") return spec.method ? {rank: spec.method === "spearman"} : {};
  return {...(spec.design?.kind ? {paired: spec.design.kind === "paired"} : {}),
    ...(spec.test && spec.test !== "none" ? {rank: spec.test === "wilcoxon" || spec.test === "mann-whitney-u"} : {})};
}
