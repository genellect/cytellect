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
export interface ShowcaseScene {id: string; label: string; workspaceId: string; dataset: ShowcaseDataset; examples: ProposalExample[]}
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
    return dataset && id && label && workspaceId ? [{id, label, workspaceId, dataset, examples: validExamplesOf(record.examples)}] : [];
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
