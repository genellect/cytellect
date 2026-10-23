"use client";
/** Additions of the public demo (/demo). Production renders none of these: the context defaults to disabled. */
import {createContext, useContext, useEffect, useRef, useState, useSyncExternalStore} from "react";
import {ApiError} from "../../../lib/api";
import {isShowcaseNotice, isShowcaseNoticeCode, showcaseTransport, type ProposalExample, type RecordedOptions, type ShowcaseDataset} from "../../../lib/showcase";
import type {ShowcaseState} from "../../../lib/showcase/transport";
import styles from "./showcase.module.css";

export type DemoStep = "image" | "statistics" | "figure";
export interface ShowcaseUi {
  enabled: boolean;
  options: RecordedOptions | null;
  examples: ProposalExample[];
  dataset: ShowcaseDataset | null;
  requestUpload: (kind: "image" | "csv") => void;
}
export const ShowcaseContext = createContext<ShowcaseUi>({enabled: false, options: null, examples: [], dataset: null, requestUpload: () => undefined});
export const useShowcaseUi = () => useContext(ShowcaseContext);
export const DOWNLOAD_HREF = "/#download";

/** Recorded values for one detector field; "locked" when the demo holds no alternative. */
export function recordedValues(options: RecordedOptions | null, kind: string, field: string): Array<number | null> | "locked" | undefined {
  if (!options) return undefined;
  const values = options[kind]?.[field];
  return Array.isArray(values) && values.length ? values.filter(value => value === null || Number.isFinite(value)) : "locked";
}
export const recordedKind = (options: RecordedOptions | null, ...kinds: string[]) => !options || kinds.some(kind => !!options[kind]);

/** An error that only reports a demo limitation is shown as information. */
export function isShowcaseNoticeError(error: unknown) {
  return error instanceof ApiError && isShowcaseNoticeCode(error.code) && !!showcaseTransport();
}
export function ErrorText({text, className}: {text: string; className?: string}) {
  if (isShowcaseNotice(text)) return <p className={styles.notice} role="status">{text}</p>;
  return <p className={className} role="alert">{text}</p>;
}

const idle: ShowcaseState = {engine: "idle", reason: null};
export function useShowcaseState(): ShowcaseState {
  return useSyncExternalStore(listener => showcaseTransport()?.subscribe(listener) ?? (() => undefined),
    () => showcaseTransport()?.state() ?? idle, () => idle);
}
/** Not shown: visitors see recorded results and never wait for a runtime. Tests read the state from the attribute. */
export function LiveStatus() {
  const state = useShowcaseState();
  return <span hidden data-showcase-engine={state.engine} data-showcase-reason={state.reason ?? undefined}/>;
}

export function UploadDialog({kind, onClose}: {kind: "image" | "csv" | null; onClose: () => void}) {
  const close = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!kind) return;
    close.current?.focus();
    const escape = (event: KeyboardEvent) => {if (event.key === "Escape") onClose();};
    window.addEventListener("keydown", escape);
    return () => window.removeEventListener("keydown", escape);
  }, [kind, onClose]);
  if (!kind) return null;
  return <div className={styles.backdrop} onClick={event => {if (event.target === event.currentTarget) onClose();}}>
    <div className={styles.dialog} role="dialog" aria-modal="true" aria-labelledby="showcase-upload-title">
      <h2 id="showcase-upload-title">{kind === "csv" ? "数値表の追加" : "画像の追加"}</h2>
      <p>公開デモでは、登録済みの公開画像だけを解析できます。手元の{kind === "csv" ? "数値表" : "画像"}は、PCで動くWindows版またはDocker版で追加・解析できます。画像はPCの外へ送信されません。</p>
      <div className={styles.actions}>
        <a className={styles.primary} href={DOWNLOAD_HREF} data-lp-event="demo_download">ダウンロードの案内</a>
        <button ref={close} type="button" onClick={onClose}>閉じる</button>
      </div>
    </div>
  </div>;
}

/** Source, licence and limits of the demo images (snapshot/dataset.json); nothing when absent. */
export function DatasetCredit({dataset}: {dataset: ShowcaseDataset}) {
  return <div className={styles.credit}>
    <p><strong>{dataset.title}</strong></p>
    <p>{dataset.attribution}{dataset.licence && <> · {dataset.licenceUrl ? <a href={dataset.licenceUrl} target="_blank" rel="noreferrer">{dataset.licence}</a> : dataset.licence}</>}{dataset.sourceUrl && <> · <a href={dataset.sourceUrl} target="_blank" rel="noreferrer">出典</a></>}</p>
    {dataset.caveats.length > 0 && <ul>{dataset.caveats.map(caveat => <li key={caveat}>{caveat}</li>)}</ul>}
  </div>;
}
/** Short, always visible image credit beside the field list; the badge holds the full attribution. */
export function SideCredit({dataset}: {dataset: ShowcaseDataset}) {
  return <p className={styles.sideCredit} title={dataset.attribution}>公開画像{dataset.licence && <> · {dataset.licenceUrl ? <a href={dataset.licenceUrl} target="_blank" rel="noreferrer">{dataset.licence}</a> : dataset.licence}</>}{dataset.sourceUrl && <> · <a href={dataset.sourceUrl} target="_blank" rel="noreferrer">画像の出典</a></>}</p>;
}
export function DemoBadge({dataset}: {dataset: ShowcaseDataset | null}) {
  if (!dataset) return <span className={styles.badge}>デモ</span>;
  return <details className={styles.badgeMenu}>
    <summary className={styles.badge} aria-label="デモ：画像の出典">デモ</summary>
    <div className={styles.popover}><DatasetCredit dataset={dataset}/></div>
  </details>;
}

const steps: Array<{mode: DemoStep; title: string; text: string; table?: boolean}> = [
  {mode: "image", title: "画像と輪郭", text: "核は検出済みです。輪郭を選ぶと値が分かり、ずれていればその場で直せます。「領域」で核小体・核質にも切り替えられます。"},
  {mode: "image", title: "測定値", text: "輪郭ごとの面積と輝度を表で確認できます。", table: true},
  {mode: "statistics", title: "統計", text: "視野や群をまとめて計算します。"},
  {mode: "figure", title: "グラフと書き出し", text: "論文用の図を編集し、ZIPで保存できます。"},
];

/** First-visit guide; each step opens the matching part of the real workspace. */
export function DemoGuide({open, onClose, onStep, dataset}: {open: boolean; onClose: () => void; onStep: (mode: DemoStep, table: boolean) => void; dataset: ShowcaseDataset | null}) {
  const [index, setIndex] = useState(0);
  if (!open) return null;
  const step = steps[index];
  const go = (next: number) => {setIndex(next); onStep(steps[next].mode, !!steps[next].table);};
  const finish = () => {setIndex(0); onClose();};
  return <aside className={styles.guide} aria-label="公開デモの使い方">
    <ol>{steps.map((value, position) => <li key={value.title} aria-current={position === index ? "step" : undefined}><button type="button" onClick={() => go(position)}>{position + 1} {value.title}</button></li>)}</ol>
    <p><strong>{step.title}</strong> {step.text}</p>
    {index === steps.length - 1 && dataset && <DatasetCredit dataset={dataset}/>}
    <div className={styles.actions}>
      {index < steps.length - 1 ? <button type="button" className={styles.primary} onClick={() => go(index + 1)}>次へ</button> : <button type="button" className={styles.primary} onClick={finish}>了解</button>}
      <button type="button" onClick={finish}>閉じる</button>
    </div>
  </aside>;
}

export function ProposalExamples({examples, disabled, onChoose}: {examples: ProposalExample[]; disabled: boolean; onChoose: (instruction: string) => void}) {
  if (!examples.length) return null;
  return <div className={styles.examples} role="group" aria-label="指示の例">{examples.map(example =>
    <button key={example.instruction} type="button" disabled={disabled} title={example.instruction} onClick={() => onChoose(example.instruction)}>{example.label}</button>)}</div>;
}
