import type {ChannelGateFilter, ChannelGateResult} from "./channel-gate";
import {metricChoice} from "./metric-catalog";
import type {ReviewTarget} from "./review-preview";

/** How the image colours its regions (requirements MV-01). The colour mode is the entry to a measurement:
 * it decides what the image shows, what the table under it lists and where the next step goes. */
export type ColorBy = "outline" | "positivity" | "compartments";
export const COLOR_BY_LABELS: Record<ColorBy, string> = {outline: "輪郭", positivity: "陽性・陰性", compartments: "核小体と核質"};

/** What the shown fields have, which decides the colour modes that can be chosen. */
export interface ColorByInputs {
  /** Adopted nuclei in the shown field (or every shown pane). */
  nuclei: boolean;
  /** Stains the nuclei can be classified by. */
  gateChannels: number;
  /** Adopted nucleoli and nucleoplasm in the shown field. */
  nucleoli: boolean;
  nucleoplasm: boolean;
  /** A saved version of a figure or a detection candidate is on screen (read-only, not the adopted regions). */
  saved: boolean;
}
export interface ColorByChoice {id: ColorBy; label: string; reason: string | null}

/** Every colour mode, with why it cannot be chosen now (MV-01: shown but not selectable, naming what is missing). */
export function colorByChoices(inputs: ColorByInputs): ColorByChoice[] {
  const saved = inputs.saved ? "図の保存時の版や検出候補では選べません" : null;
  const nuclei = !inputs.nuclei ? "採用した核の結果が必要です" : null;
  return [
    {id: "outline", label: COLOR_BY_LABELS.outline, reason: null},
    {id: "positivity", label: COLOR_BY_LABELS.positivity, reason: saved ?? nuclei ?? (inputs.gateChannels ? null : "判定できる染色がありません")},
    {id: "compartments", label: COLOR_BY_LABELS.compartments, reason: saved ?? nuclei ?? (inputs.nucleoli && inputs.nucleoplasm ? null : "核小体と核質の結果が必要です")},
  ];
}
/** The colour mode in effect: the chosen one while it can be shown, otherwise the outlines. */
export function shownColorBy(chosen: ColorBy, choices: ColorByChoice[]): ColorBy {
  return choices.find(choice => choice.id === chosen)?.reason === null ? chosen : "outline";
}

/** A nucleus's state in a channel-gate decision (channel-gate/1.0.0); every state is drawn apart (MV-03). */
export type GateStatus = "positive" | "negative" | "unclassified" | "control" | "excluded";
export const GATE_STATUS_ORDER: GateStatus[] = ["positive", "negative", "unclassified", "excluded", "control"];
export const GATE_STATUS_LABELS: Record<GateStatus, string> = {positive: "陽性", negative: "陰性", unclassified: "未判定", excluded: "除外", control: "対照"};

type GateNucleus = ChannelGateResult["nuclei"][number];
/** The saved decision for each region of one field (region id → state). */
export function gateStates(nuclei: GateNucleus[] | undefined, fieldId: string): Record<number, GateStatus> {
  return Object.fromEntries((nuclei ?? []).filter(item => item.field_id === fieldId).map(item => [item.region_id, item.status as GateStatus]));
}
/** The legend of one image: each state present, with its number of nuclei, in a fixed order. */
export function gateLegend(states: Record<number, GateStatus>): Array<{status: GateStatus; label: string; count: number}> {
  const counts = new Map<GateStatus, number>();
  for (const status of Object.values(states)) counts.set(status, (counts.get(status) ?? 0) + 1);
  return GATE_STATUS_ORDER.filter(status => counts.has(status)).map(status => ({status, label: GATE_STATUS_LABELS[status], count: counts.get(status)!}));
}

const methodLabels: Record<ChannelGateFilter["method"], string> = {
  negative_control: "撮影日ごとの陰性対照", batch_otsu: "撮影日ごとの Otsu・探索的", manual: "指定したしきい値・探索的",
};
/** How a decision was made, as the image and table name it. A threshold not fixed by a negative control is exploratory (M22). */
export function gateMethodLabel(method: ChannelGateFilter["method"]): string {return methodLabels[method];}
export function gateExploratory(method: ChannelGateFilter["method"]): boolean {return method !== "negative_control";}

/** One acquisition date's distribution of the judged values, with its threshold, for judging the threshold (MV-04).
 * Display only: the values and thresholds are the saved ones; the bins only place them on the chart. */
export function gateHistogram(nuclei: GateNucleus[], date: string, bins = 24) {
  const shown = nuclei.filter(item => (item.acquisition_date ?? "") === date && typeof item.channel_mean === "number" && Number.isFinite(item.channel_mean));
  const thresholds = [...new Set(nuclei.filter(item => (item.acquisition_date ?? "") === date && typeof item.threshold === "number").map(item => item.threshold as number))];
  const values = shown.map(item => item.channel_mean as number);
  const threshold = thresholds.length === 1 ? thresholds[0] : null;
  const all = threshold === null ? values : [...values, threshold];
  if (!all.length) return {low: 0, high: 0, threshold, counts: [] as Array<Record<GateStatus, number>>, total: 0};
  const low = Math.min(...all), high = Math.max(...all), width = (high - low) / bins || 1;
  const counts = Array.from({length: bins}, () => ({positive: 0, negative: 0, unclassified: 0, control: 0, excluded: 0}) as Record<GateStatus, number>);
  for (const item of shown) counts[Math.min(bins - 1, Math.floor(((item.channel_mean as number) - low) / width))][item.status as GateStatus] += 1;
  return {low, high, threshold, counts, total: shown.length};
}

/** Nucleoplasm ÷ nucleoli: the partition table's K = target ÷ reference, in the direction of the statistics
 * metric log2_nucleoplasm_over_nucleolus, so the image and the comparison read the same way (owner decision 1). */
export const PARTITION_DIRECTION = {target: "nucleoplasm", reference: "nucleoli"} as const;
export function partitionDefaults(sources: Array<{name: ReviewTarget; revisionId: string}>): {target: string; reference: string} {
  const find = (name: ReviewTarget) => sources.find(source => source.name === name)?.revisionId ?? "";
  return {target: find(PARTITION_DIRECTION.target), reference: find(PARTITION_DIRECTION.reference)};
}

const regionNames: Record<ReviewTarget, string> = {nuclei: "核", nucleoli: "核小体", nucleoplasm: "核質", cell: "細胞ROI"};
/** What the table under the image lists, in the words of the image (MV-06): per what, which stain, which values. */
export function tableHeading(view:
  | {colorBy: "outline"; target: ReviewTarget; stain: string; corrected: boolean; nucleusTable: boolean}
  | {colorBy: "positivity"; stain: string; method: ChannelGateFilter["method"]; values: "raw" | "corrected"}
  | {colorBy: "compartments"; stain: string; target: string; reference: string}): string {
  if (view.colorBy === "positivity") return `核ごと · ${view.stain}で判定（${view.values === "corrected" ? "背景補正値" : "原値"}、${gateMethodLabel(view.method)}）`;
  if (view.colorBy === "compartments") return `核ごと · ${view.target} ÷ ${view.reference} · ${view.stain}`;
  if (view.nucleusTable) return "核ごと · すべての染色";
  return `${regionNames[view.target]}ごと · ${view.stain}${view.corrected ? "（原値・背景補正）" : "（原値）"}`;
}

/** The one next step beside the table (MV-09): the comparison of groups that the colour mode leads to. */
export interface NextComparison {label: string; metric: string; target: ReviewTarget; channel: string | null; reclassify: boolean; note?: string}
export function nextComparison(view: {colorBy: ColorBy; metric: string; target: ReviewTarget; channel: string; stain: string}): NextComparison {
  if (view.colorBy === "positivity") return {label: "陽性率を群で比べる", metric: "positive_fraction", target: "nuclei", channel: null, reclassify: true,
    note: "比べる視野を、同じ判定の規則で判定し直してから計算します。"};
  if (view.colorBy === "compartments") return {label: "核質／核小体の比を群で比べる", metric: "log2_nucleoplasm_over_nucleolus", target: "nucleoplasm", channel: view.channel, reclassify: false};
  const choice = metricChoice(view.metric);
  const channel = choice?.channel ? view.channel : null;
  const target = choice?.target ?? view.target;
  return {label: `${choice?.label ?? view.metric}${channel ? `（${view.stain}）` : ""}を群で比べる`, metric: view.metric, target, channel, reclassify: false};
}
