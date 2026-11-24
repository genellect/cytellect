import {measureLabel,metricLabel,metricUsesChannel,nucleusPositivity} from "../../../lib/workspace/metric-catalog";
import type {MeasuredChannelProvenance} from "../../../lib/workspace/api-adapter";
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
  selection?: {channel_gate?: {channel?: SavedChannelLike}; records?: SavedObservationLike[]} | null;
  /** Every observation the result read, with whether it was excluded (a comparison; an association per axis). */
  observation_ledger?: SavedObservationLike[];
  spec?: {selection?: SavedSelectionLike; x_selection?: SavedSelectionLike; y_selection?: SavedSelectionLike;
    /** The comparison's test ("none" without inference), the association's method and the design, as requested. */
    test?: string | null; method?: string | null; design?: {kind?: string | null} | null;
    /** The compared pairs of groups, as requested. */
    comparison_family?: {contrasts?: string[][]} | null} | null;
  x_source?: {metric?: string; channel?: SavedChannelLike | null; source_fields?: SavedResultLike["source_fields"]; observation_ledger?: SavedObservationLike[]} | null;
  y_source?: {metric?: string; channel?: SavedChannelLike | null; source_fields?: SavedResultLike["source_fields"]; observation_ledger?: SavedObservationLike[]} | null;
  /** Each field's adopted regions (their mask revision), measurement and channels (with the background each was
   * corrected by), its assignment and, for a per-field summary, its excluded regions, as the result recorded them. */
  source_fields?: Array<{field_id: string; region_set?: {region_set_id?: string; mask_revision_id?: string};
    measurement_protocol?: string; measurement?: {mode?: string} | null; channel_provenance?: ChannelProvenanceLike[] | null;
    metadata?: SavedAssignmentLike | null; field_summary?: {excluded_region_count?: number} | null}>;
}
/** One observation a saved result read (`[field, region set, region]` identifiers). */
export interface SavedObservationLike {observation_id?: string; field_id?: string; region_id?: number | null; excluded?: boolean}
export type ChannelProvenanceLike = MeasuredChannelProvenance;

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

/** One chosen field's measurement as the result place compares it: its adopted regions, measurement and the
 * backgrounds its channels were corrected by (`backgroundFingerprint`, "" when the table records none), the regions
 * excluded in its table (`excludedRegions`) and its assignment in 実験 (`fieldAssignment`). */
export interface CurrentSource {field: string; mask: string; protocol?: string; mode?: string; background?: string; excluded?: number[]; assignment?: string}
const canonical = (value: unknown): string => Array.isArray(value) ? `[${value.map(canonical).join(",")}]`
  : value && typeof value === "object" ? `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${canonical((value as Record<string, unknown>)[key])}`).join(",")}}`
  : JSON.stringify(value) ?? "null";
/** The backgrounds a field's channels were corrected by, in a form that compares equal exactly when they are the same
 * (genellect/cytellect#257 NS-04): a redrawn background ROI keeps the regions' mask revision, the protocol and the
 * mode, and only this changes. The revision that measured it (`background_revision_id`, the analysis revision) is
 * left out, so measuring again with the same background, or measuring another region set, keeps the fingerprint.
 * "" when nothing is recorded (an older result or table). */
export function backgroundFingerprint(provenance: ChannelProvenanceLike[] | null | undefined): string {
  if (!provenance?.length) return "";
  return canonical(provenance.map(item => [item.channel?.channel_id ?? "", "background" in item ? item.background ?? null
    : {mask: item.background_mask_sha256 ?? null, pixels: item.background_pixel_count ?? null, median: item.background_median ?? null}])
    .sort((a, b) => String(a[0]).localeCompare(String(b[0]))));
}
/** Whether a saved result was calculated from exactly the fields now chosen, with the same adopted regions (mask
 * revision), measurement protocol and mode, and background. A result or table that records no background is taken as
 * it was. */
export function sameSources(saved: SavedResultLike["source_fields"], current: CurrentSource[]): boolean {
  if (!saved?.length || saved.length !== current.length) return false;
  const chosen = new Map(current.map(source => [source.field, source]));
  return saved.every(field => {
    const source = chosen.get(field.field_id);
    const background = backgroundFingerprint(field.channel_provenance);
    return !!source && !!source.mask && field.region_set?.mask_revision_id === source.mask
      && (!field.measurement_protocol || !source.protocol || field.measurement_protocol === source.protocol)
      && (!field.measurement?.mode || !source.mode || field.measurement.mode === source.mode)
      && (!background || !source.background || background === source.background);
  });
}

/** Whether a field a saved result was calculated from has been measured again differently since: its adopted regions
 * (mask revision), protocol, mode or background differ where both the result and the current table record them. A
 * field not chosen now, or a measurement not loaded yet, is no evidence of a change. */
export function changedSources(saved: SavedResultLike["source_fields"], current: CurrentSource[]): boolean {
  const chosen = new Map(current.map(source => [source.field, source]));
  return (saved ?? []).some(field => {
    const source = chosen.get(field.field_id);
    if (!source) return false;
    const mask = field.region_set?.mask_revision_id, background = backgroundFingerprint(field.channel_provenance);
    return (!!mask && !!source.mask && mask !== source.mask)
      || (!!field.measurement_protocol && !!source.protocol && field.measurement_protocol !== source.protocol)
      || (!!field.measurement?.mode && !!source.mode && field.measurement.mode !== source.mode)
      || (!!background && !!source.background && background !== source.background);
  });
}

/** The fields a saved result was calculated from; an association keeps them per axis (both axes are measured on the
 * same fields). */
export const resultSourceFields = (result: SavedResultLike) => result.source_fields ?? result.y_source?.source_fields ?? result.x_source?.source_fields;

/** The newest saved result for a condition (entries newest first): `current` when it was calculated from the
 * measurements, exclusions, assignment and compared pairs now chosen (`changedInputs`), `older` when only an earlier
 * one of the same condition was saved. */
export function savedFor<T extends {operation: ResultOperation; result: SavedResultLike}>(entries: T[], condition: ResultCondition | null,
  sources: CurrentSource[], contrasts: string[][] = []): {current?: T; older?: T} {
  const key = conditionKey(condition);
  if (!key) return {};
  const same = entries.filter(entry => conditionKey(savedCondition(entry.operation, entry.result)) === key);
  return {current: same.find(entry => sameSources(resultSourceFields(entry.result), sources) && !changedInputs(entry.operation, entry.result, sources, contrasts)), older: same[0]};
}

/** A field's assignment in 実験 as a cohort records it (group, run, sample, acquisition date and pair, spacing removed),
 * "" when nothing is assigned yet. */
export function fieldAssignment(metadata: SavedAssignmentLike | null | undefined): string {
  const values = ASSIGNMENT.map(key => metadata?.[key]?.trim() || null);
  return values.some(value => value !== null) ? JSON.stringify(values) : "";
}
const ASSIGNMENT = ["condition", "experimental_unit", "sample", "acquisition_date", "pair"] as const;
export type SavedAssignmentLike = Partial<Record<(typeof ASSIGNMENT)[number], string | null>>;
/** The regions of a field excluded in its measured table, in ascending order. Undefined when the table is not loaded or
 * the whole field is excluded (that is no evidence about its regions). */
export function excludedRegions(exclusions: Array<{field_id: string; region_id: number | null; reason?: string}> | null | undefined, field: string): number[] | undefined {
  if (!exclusions) return undefined;
  const own = exclusions.filter(item => item.field_id === field);
  if (own.some(item => item.region_id === null)) return undefined;
  return [...new Set(own.map(item => item.region_id as number))].sort((a, b) => a - b);
}
/** The region an observation record describes: the last part of its identifier (`[field, region set, region]`), or its
 * region ID; null for a record of a whole field. */
function recordRegion(record: SavedObservationLike): number | null {
  try {
    const id = record.observation_id ? (JSON.parse(record.observation_id) as unknown[]).at(-1) : undefined;
    if (typeof id === "number") return id;
  } catch { /* an identifier of another form */ }
  return typeof record.region_id === "number" ? record.region_id : null;
}
/** What a saved result recorded of each field's excluded regions: their IDs from its observation records (a
 * comparison's ledger, an association's vertical axis, a distribution's selection), or their number for a per-field
 * summary. A field without such a record is absent. */
function savedExclusions(result: SavedResultLike): Map<string, number[] | number> {
  const records = result.observation_ledger ?? result.y_source?.observation_ledger ?? result.selection?.records ?? [];
  const recorded = new Map<string, number[] | number>();
  for (const record of records) {
    const region = recordRegion(record);
    if (region === null || !record.field_id) continue;
    const ids = recorded.get(record.field_id);
    const list = Array.isArray(ids) ? ids : [];
    if (record.excluded === true) list.push(region);
    recorded.set(record.field_id, list);
  }
  for (const field of resultSourceFields(result) ?? []) {
    const count = field.field_summary?.excluded_region_count;
    if (!recorded.has(field.field_id) && typeof count === "number") recorded.set(field.field_id, count);
  }
  return recorded;
}
const pairKey = (pairs: string[][]) => JSON.stringify(pairs.map(pair => JSON.stringify(pair)).sort());
/**
 * Whether what a saved result was calculated from has changed since in what its measurement does not show
 * (genellect/cytellect#257 NS-04): a nucleus excluded or included again in 画像 (the regions' mask revision is kept), a
 * field assigned to another group, run or pair in 実験, or other pairs of groups compared. Only what both the result
 * and the current choice record is compared: an older result without the record, a table or design not loaded yet, or
 * pairs not chosen yet are no evidence of a change. A distribution does not read the assignment.
 */
export function changedInputs(operation: ResultOperation, result: SavedResultLike, current: CurrentSource[], contrasts: string[][]): boolean {
  const chosen = new Map(current.map(source => [source.field, source]));
  const excluded = savedExclusions(result);
  for (const [field, saved] of excluded) {
    const now = chosen.get(field)?.excluded;
    if (!now) continue;
    if (typeof saved === "number" ? saved !== now.length : JSON.stringify([...saved].sort((a, b) => a - b)) !== JSON.stringify(now)) return true;
  }
  if (operation !== "distribution") for (const field of resultSourceFields(result) ?? []) {
    const saved = fieldAssignment(field.metadata), now = chosen.get(field.field_id)?.assignment;
    if (saved && now && saved !== now) return true;
  }
  const pairs = result.spec?.comparison_family?.contrasts;
  return operation === "comparison" && !!pairs?.length && contrasts.length > 0 && pairKey(pairs) !== pairKey(contrasts);
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
