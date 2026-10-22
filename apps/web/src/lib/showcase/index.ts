/** Public-demo mode: activated only by the /demo page of a build without an analysis API. */
import runtimeConfig from "./runtime-config.json";
import {createWorkerEngine} from "./engine";
import type {RuntimeConfig, ShowcaseNoticeCode} from "./protocol";
import {SHOWCASE_NOTICE_CODES} from "./protocol";
import {createShowcaseTransport, type ShowcaseTransport} from "./transport";

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

let transport: ShowcaseTransport | null = null;
export function activateShowcase() {
  transport ??= createShowcaseTransport({
    fetchStatic: url => fetch(url, {credentials: "omit"}),
    createEngine: () => createWorkerEngine(runtimeConfig as RuntimeConfig, DEV_BACKEND),
    capable: () => liveCapable(),
    snapshotBase,
  });
  return transport;
}
export const showcaseTransport = () => transport;
export const showcaseActive = () => transport !== null;

export const showcaseNotices: Record<ShowcaseNoticeCode, string> = {
  showcase_detection_not_recorded: "公開デモでは、記録した検出条件だけを実行できます。一覧から条件を選んでください。",
  showcase_proposal_not_recorded: "公開デモのAIは、記録した指示の例だけに応答します。入力欄の上の例から選んでください。",
  showcase_upload_disabled: "公開デモでは画像を追加できません。Windows版・Docker版をご利用ください。",
  showcase_engine_unavailable: "この操作はPCのブラウザで試せます。この端末では保存済みの解析結果を表示しています。",
  showcase_unavailable: "公開デモのデータを読み込めませんでした。時間をおいて再読み込みしてください。",
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
export interface ShowcaseDataset {title: string; attribution: string; licence: string; licenceUrl: string; sourceUrl: string; caveats: string[]}
const httpsUrl = (value: unknown) => {try {return typeof value === "string" && new URL(value).protocol === "https:" ? value : "";} catch {return "";}};
export function validDataset(value: unknown): ShowcaseDataset | null {
  if (!value || typeof value !== "object") return null;
  const record = value as Record<string, unknown>;
  const text = (key: string) => typeof record[key] === "string" ? (record[key] as string).trim() : "";
  if (!text("title") || !text("attribution")) return null;
  return {title: text("title"), attribution: text("attribution"), licence: text("licence"), licenceUrl: httpsUrl(record.licenceUrl), sourceUrl: httpsUrl(record.sourceUrl),
    caveats: Array.isArray(record.caveats) ? record.caveats.filter((item): item is string => typeof item === "string" && !!item.trim()).slice(0, 8) : []};
}
export async function loadShowcaseExtras(): Promise<{options: RecordedOptions | null; examples: ProposalExample[]; dataset: ShowcaseDataset | null}> {
  const read = async (name: string) => {
    try {const response = await fetch(`${snapshotBase}${name}`, {credentials: "omit"}); if (!response.ok) {await response.text(); return null;} return await response.json() as unknown;}
    catch {return null;}
  };
  const [options, examples, dataset] = await Promise.all([read("recorded-options.json"), read("proposal-examples.json"), read("dataset.json")]);
  const validOptions = options && typeof options === "object" && !Array.isArray(options) ? options as RecordedOptions : null;
  const validExamples = Array.isArray(examples) ? examples.filter((value): value is ProposalExample =>
    !!value && typeof value.label === "string" && typeof value.instruction === "string" && !!value.instruction.trim()).slice(0, 8) : [];
  return {options: validOptions, examples: validExamples, dataset: validDataset(dataset)};
}
