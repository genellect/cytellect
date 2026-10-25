/** Public-demo mode: activated only by the /demo page of a build without an analysis API. */
import runtimeConfig from "./runtime-config.json";
import {createWorkerEngine} from "./engine";
import type {RuntimeConfig, ShowcaseNoticeCode} from "./protocol";
import {SHOWCASE_NOTICE_CODES} from "./protocol";
import {createShowcaseTransport, type RecordedExchange, type ShowcaseTransport} from "./transport";

/** Loopback-only development forwarder (scripts/dev_showcase_backend.py); unset in every published build. */
export const DEV_BACKEND = (() => {
  const value = process.env.NEXT_PUBLIC_SHOWCASE_DEV_BACKEND || "";
  try {const url = new URL(value); return url.protocol === "http:" && ["localhost", "127.0.0.1"].includes(url.hostname) ? url.origin : null;}
  catch {return null;}
})();
export const SHOWCASE_BASE = "/showcase/";
const snapshotBase = DEV_BACKEND ? `${DEV_BACKEND}/snapshot/` : `${SHOWCASE_BASE}snapshot/`;

/** Desktop browsers with enough memory run the API; phones keep the recorded view. */
export function liveCapable(environment: {navigator: Navigator; matchMedia?: (query: string) => MediaQueryList; innerWidth: number} | undefined = typeof window === "undefined" ? undefined : window): boolean {
  if (!environment || typeof Worker === "undefined" || typeof WebAssembly === "undefined") return false;
  const memory = (environment.navigator as Navigator & {deviceMemory?: number}).deviceMemory;
  if (typeof memory === "number" && memory < 4) return false;
  const touch = environment.matchMedia?.("(pointer: coarse)").matches ?? false;
  return !(touch && environment.innerWidth < 1024);
}

/** Present only in the build-time tour recorder, which defines it before the page loads. */
function recorder(): ((exchange: RecordedExchange) => void) | undefined {
  const hook = typeof window === "undefined" ? undefined : (window as Window & {__cytellectShowcaseRecord?: (exchange: unknown) => void}).__cytellectShowcaseRecord;
  if (typeof hook !== "function") return undefined;
  return exchange => {
    let binary = "";
    new Uint8Array(exchange.bytes).forEach(byte => {binary += String.fromCharCode(byte);});
    hook({...exchange, bytes: btoa(binary)});
  };
}

let transport: ShowcaseTransport | null = null;
export function activateShowcase() {
  transport ??= createShowcaseTransport({
    fetchStatic: url => fetch(url, {credentials: "same-origin"}),
    createEngine: () => createWorkerEngine(runtimeConfig as RuntimeConfig, DEV_BACKEND),
    capable: () => liveCapable(),
    snapshotBase,
    record: recorder(),
  });
  return transport;
}
export const showcaseTransport = () => transport;
export const showcaseActive = () => transport !== null;

export const showcaseNotices: Record<ShowcaseNoticeCode, string> = {
  showcase_detection_not_recorded: "公開デモでは、記録した検出条件だけを実行できます。一覧から条件を選んでください。",
  showcase_proposal_not_recorded: "公開デモのAIは、記録した指示の例だけに応答します。入力欄の上の例から選んでください。",
  showcase_upload_disabled: "公開デモでは画像を追加できません。Windows版・Docker版をご利用ください。",
  showcase_engine_unavailable: "この操作の結果は公開デモで表示できません。保存済みの解析結果はそのまま試せます。",
  showcase_unavailable: "公開デモのデータを読み込めませんでした。時間をおいて再読み込みしてください。",
  showcase_action_not_recorded: "この操作の結果は公開デモに記録していません。「使い方」の手順、統計・図・測定・AIの例は、そのまま試せます。お手元の画像の解析は Windows 版で行えます。",
};
export const isShowcaseNoticeCode = (code: string): code is ShowcaseNoticeCode => (SHOWCASE_NOTICE_CODES as readonly string[]).includes(code);
/** A displayed message that only reports a demo limitation (shown as information, not as an error). */
export function isShowcaseNotice(text: string | null | undefined) {
  return !!text && showcaseActive() && Object.values(showcaseNotices).some(notice => text.includes(notice));
}

export type RecordedOptions = Record<string, Record<string, Array<number | null>>>;
export interface ProposalExample {label: string; instruction: string}
/** Optional files from the demo build; absence leaves the controls as they are. */
/** `snapshot/dataset.json`: source and limits of the demo's public images. */
export interface ShowcaseDataset {title: string; attribution: string; licence: string; licenceUrl: string; sourceUrl: string; caveats: string[];
  /** Region sets the demo recorded; null keeps every region (older recordings). */
  regions: Array<"nuclei" | "nucleoli" | "nucleoplasm"> | null;
  /** The change the source reports, shown apart from the demo's own measurement (X-03). */
  reported: {source: string; comparison: string; direction: string; quantity: string; scope: string; independence?: string} | null}
const httpsUrl = (value: unknown) => {try {return typeof value === "string" && new URL(value).protocol === "https:" ? value : "";} catch {return "";}};
export function validDataset(value: unknown): ShowcaseDataset | null {
  if (!value || typeof value !== "object") return null;
  const record = value as Record<string, unknown>;
  const text = (key: string) => typeof record[key] === "string" ? (record[key] as string).trim() : "";
  if (!text("title") || !text("attribution")) return null;
  return {title: text("title"), attribution: text("attribution"), licence: text("licence"), licenceUrl: httpsUrl(record.licenceUrl), sourceUrl: httpsUrl(record.sourceUrl),
    caveats: Array.isArray(record.caveats) ? record.caveats.filter((item): item is string => typeof item === "string" && !!item.trim()).slice(0, 8) : [],
    regions: Array.isArray(record.regions) ? record.regions.filter((item): item is "nuclei" | "nucleoli" | "nucleoplasm" => item === "nuclei" || item === "nucleoli" || item === "nucleoplasm") : null,
    reported: reportedChange(record.reportedChange)};
}
function reportedChange(value: unknown): ShowcaseDataset["reported"] {
  if (!value || typeof value !== "object") return null;
  const record = value as Record<string, unknown>;
  const keys = ["source", "comparison", "direction", "quantity", "scope"] as const;
  if (!keys.every(key => typeof record[key] === "string" && (record[key] as string).trim())) return null;
  const independence = typeof record.independence === "string" && record.independence.trim() ? {independence: record.independence.trim()} : {};
  return {...Object.fromEntries(keys.map(key => [key, (record[key] as string).trim()])), ...independence} as NonNullable<ShowcaseDataset["reported"]>;
}
/** One demo scene (snapshot/scenes.json): a workspace with its own public images and examples. */
export interface ShowcaseScene {id: string; label: string; workspaceId: string; dataset: ShowcaseDataset; examples: ProposalExample[];
  /** Snapshot file with another method's published objects matched to the adopted nuclei (display only). */
  reference?: string;
  /** What visitors can ask of this scene's images, for a request the recordings do not cover. */
  assistantScope?: string}
const validExamplesOf = (value: unknown): ProposalExample[] => Array.isArray(value) ? value.filter((item): item is ProposalExample =>
  !!item && typeof item.label === "string" && typeof item.instruction === "string" && !!item.instruction.trim()).slice(0, 8) : [];
export function validScenes(value: unknown): ShowcaseScene[] {
  const list = value && typeof value === "object" && Array.isArray((value as {scenes?: unknown}).scenes) ? (value as {scenes: unknown[]}).scenes : [];
  return list.flatMap(item => {
    if (!item || typeof item !== "object") return [];
    const record = item as Record<string, unknown>;
    const dataset = validDataset(record);
    const id = typeof record.id === "string" ? record.id : "", label = typeof record.label === "string" ? record.label.trim() : "";
    const workspaceId = typeof record.workspaceId === "string" ? record.workspaceId : "";
    const reference = typeof record.reference === "string" && /^reference-[\w.-]+\.json$/.test(record.reference) ? record.reference : undefined;
    const assistantScope = typeof record.assistantScope === "string" && record.assistantScope.trim() ? record.assistantScope.trim().slice(0, 400) : undefined;
    return dataset && id && label && workspaceId ? [{id, label, workspaceId, dataset, examples: validExamplesOf(record.examples), ...(reference ? {reference} : {}), ...(assistantScope ? {assistantScope} : {})}] : [];
  });
}
export async function loadShowcaseExtras(): Promise<{options: RecordedOptions | null; examples: ProposalExample[]; dataset: ShowcaseDataset | null; scenes: ShowcaseScene[]}> {
  const read = async (name: string) => {
    try {const response = await fetch(`${snapshotBase}${name}`, {credentials: "same-origin"}); if (!response.ok) {await response.text(); return null;} return await response.json() as unknown;}
    catch {return null;}
  };
  const [options, examples, dataset, scenes] = await Promise.all([read("recorded-options.json"), read("proposal-examples.json"), read("dataset.json"), read("scenes.json")]);
  const validOptions = options && typeof options === "object" && !Array.isArray(options) ? options as RecordedOptions : null;
  return {options: validOptions, examples: validExamplesOf(examples), dataset: validDataset(dataset), scenes: validScenes(scenes)};
}

export type ReferenceTone = "both" | "split" | "reference_only" | "labels_only";
/** One field's comparison with the published reference objects (counts of each match status). */
export interface ReferenceField {
  both: number; split: number; referenceOnly: number; labelsOnly: number; labels: number;
  /** Adopted nuclei not touching the image border (the reference count's rule). */
  labelsInterior: number | null;
  /** The reference method's own per-image count (nuclei touching the border excluded). */
  countNuclei: number | null;
  medianAreaPx: {both: number | null; split: number | null; referenceOnly: number | null};
  markers: Array<{x: number; y: number; r: number; tone: ReferenceTone}>;
}
/** One group's means per field, computed by the demo build (services/showcase cellprofiler.py). */
export interface ReferenceGroup {id: string; label: string; fields: number; cytellect: number; cellprofiler: number;
  referenceOnly: number; split: number; labelsOnly: number; matchedFraction: number | null;
  referenceOnlyMedianAreaPx: number | null; matchedMedianAreaPx: number | null}
export interface ReferenceRatio {cytellect: number; cellprofiler: number}
export interface ShowcaseReference {label: string; note: string; fields: Record<string, ReferenceField>;
  groups: ReferenceGroup[]; ratio: ReferenceRatio | null; runs: Array<{id: string; label: string; ratio: ReferenceRatio | null}>}
const TONES = new Set<string>(["both", "split", "reference_only", "labels_only"]);
const count = (value: unknown) => typeof value === "number" && Number.isFinite(value) && value >= 0 ? value : null;
export function validReference(value: unknown): ShowcaseReference | null {
  if (!value || typeof value !== "object") return null;
  const record = value as Record<string, unknown>;
  if (record.version !== 1 || typeof record.label !== "string" || !record.fields || typeof record.fields !== "object") return null;
  const fields: Record<string, ReferenceField> = {};
  for (const [id, raw] of Object.entries(record.fields as Record<string, unknown>)) {
    if (!raw || typeof raw !== "object") continue;
    const item = raw as Record<string, unknown>, areas = (item.median_area_px && typeof item.median_area_px === "object" ? item.median_area_px : {}) as Record<string, unknown>;
    const both = count(item.both), split = count(item.split), referenceOnly = count(item.reference_only), labelsOnly = count(item.labels_only), labels = count(item.labels);
    if (both === null || split === null || referenceOnly === null || labelsOnly === null || labels === null) continue;
    const markers = Array.isArray(item.markers) ? item.markers.flatMap(marker => Array.isArray(marker) && marker.length === 4 && marker.slice(0, 3).every(v => typeof v === "number" && Number.isFinite(v)) && TONES.has(marker[3])
      ? [{x: marker[0] as number, y: marker[1] as number, r: Math.max(2, marker[2] as number), tone: marker[3] as ReferenceTone}] : []) : [];
    fields[id] = {both, split, referenceOnly, labelsOnly, labels, labelsInterior: count(item.labels_away_from_border), countNuclei: count(item.count_nuclei),
      medianAreaPx: {both: count(areas.both), split: count(areas.split), referenceOnly: count(areas.reference_only)}, markers};
  }
  const ratioOf = (value: unknown): ReferenceRatio | null => {
    const item = value && typeof value === "object" ? value as Record<string, unknown> : {};
    const cytellect = count(item.cytellect), cellprofiler = count(item.cellprofiler);
    return cytellect === null || cellprofiler === null ? null : {cytellect, cellprofiler};
  };
  const groups = Array.isArray(record.groups) ? record.groups.flatMap((raw): ReferenceGroup[] => {
    const item = raw && typeof raw === "object" ? raw as Record<string, unknown> : {};
    const values = [item.fields, item.cytellect_per_field, item.cellprofiler_per_field, item.reference_only_per_field, item.split_per_field, item.labels_only_per_field].map(count);
    if (typeof item.id !== "string" || typeof item.label !== "string" || values.some(value => value === null)) return [];
    const [fieldCount, cytellect, cellprofiler, referenceOnly, split, labelsOnly] = values as number[];
    return [{id: item.id, label: item.label, fields: fieldCount, cytellect, cellprofiler, referenceOnly, split, labelsOnly,
      matchedFraction: count(item.matched_fraction), referenceOnlyMedianAreaPx: count(item.reference_only_median_area_px), matchedMedianAreaPx: count(item.matched_median_area_px)}];
  }) : [];
  const runs = Array.isArray(record.runs) ? record.runs.flatMap(raw => {
    const item = raw && typeof raw === "object" ? raw as Record<string, unknown> : {};
    return typeof item.id === "string" && typeof item.label === "string" ? [{id: item.id, label: item.label, ratio: ratioOf(item.ratio)}] : [];
  }) : [];
  return Object.keys(fields).length ? {label: record.label.trim(), note: typeof record.note === "string" ? record.note : "", fields, groups, ratio: ratioOf(record.ratio), runs} : null;
}
export async function loadShowcaseReference(file: string): Promise<ShowcaseReference | null> {
  if (!/^reference-[\w.-]+\.json$/.test(file)) return null;
  try {const response = await fetch(`${snapshotBase}${file}`, {credentials: "same-origin"}); if (!response.ok) {await response.text(); return null;} return validReference(await response.json());}
  catch {return null;}
}

/** Topics a visitor's request can name, and the words that signal them (Japanese and English). */
const TOPICS: Record<string, RegExp> = {
  area: /面積|大きさ|サイズ|広さ|形|area|size|shape/i,
  distribution: /分布|ばらつき|ヒストグラム|視野ごと|分散|distribution|histogram|spread/i,
  intensity: /輝度|量|発現|強さ|明るさ|シグナル|蛍光|NPM1|intensity|expression|signal|level/i,
  comparison: /比較|比べ|違い|差|変化|有意|検定|ActD|PLK1|ノックアウト|対照|処理|未処理|条件間|compare|difference|versus|vs|treat|knock/i,
  association: /関係|相関|関連|依存|散布|association|correlat|relationship|scatter/i,
};
const topicsOf = (text: string) => new Set(Object.entries(TOPICS).filter(([, pattern]) => pattern.test(text)).map(([topic]) => topic));
/** The demo AI maps a free-form request onto the closest recorded example (no paid model is called).
 *  Returns null when the request names none of the analyses this public dataset supports. */
export function closestExample(text: string, examples: ProposalExample[]): ProposalExample | null {
  const asked = topicsOf(text);
  if (!asked.size) return null;
  let best: ProposalExample | null = null, score = 0;
  for (const example of examples) {
    const offered = topicsOf(example.instruction);
    const shared = [...asked].filter(topic => offered.has(topic)).length - [...offered].filter(topic => !asked.has(topic)).length * 0.25;
    if (shared > score) {score = shared; best = example;}
  }
  return best;
}
