"use client";
/** Additions of the public demo (/demo). Production renders none of these: the context defaults to disabled. */
import {createContext, useContext, useEffect, useRef, useState, useSyncExternalStore} from "react";
import {ApiError} from "../../../lib/api";
import {isShowcaseNotice, isShowcaseNoticeCode, showcaseTransport, type ProposalExample, type ShowcaseDataset, type ShowcaseScene} from "../../../lib/showcase";
import {TERMS} from "../../../lib/showcase/terms";
import type {ShowcaseState} from "../../../lib/showcase/transport";
import styles from "./showcase.module.css";

export type DemoStep = "image" | "statistics" | "figure";
export interface ShowcaseUi {
  enabled: boolean;
  examples: ProposalExample[];
  dataset: ShowcaseDataset | null;
  /** Demo scenes (one workspace each) and the one shown; empty for a single-scene demo. */
  scenes: ShowcaseScene[];
  scene: ShowcaseScene | null;
  requestUpload: (kind: "image" | "csv") => void;
}
export const ShowcaseContext = createContext<ShowcaseUi>({enabled: false, examples: [], dataset: null, scenes: [], scene: null, requestUpload: () => undefined});
/** Switches the demo to another scene (its own workspace); a fresh page keeps the scenes apart. */
export function SceneSwitcher({scenes, scene}: {scenes: ShowcaseScene[]; scene: ShowcaseScene | null}) {
  if (scenes.length < 2) return null;
  // A full page load (not client navigation) so the workspace runtime starts from the new scene.
  return <label className={styles.scene}><span className={styles.sceneLabel}>場面</span><select aria-label="場面" title={scene?.label} value={scene?.id ?? ""} onChange={event => {
    const next = scenes.find(item => item.id === event.target.value);
    if (next) window.location.href = new URL(`/demo?id=${encodeURIComponent(next.workspaceId)}`, window.location.origin).href;
  }}>{scenes.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>;
}
export const useShowcaseUi = () => useContext(ShowcaseContext);
export const DOWNLOAD_HREF = "/#download";

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
      <p>公開デモで解析できるのは、登録済みの公開画像だけです。手元の{kind === "csv" ? "数値表" : "画像"}は、PC で動く Windows 版・Docker 版で解析できます。画像は PC の外へ送信されません。</p>
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
  // Each part keeps its words together; the parts wrap as units in a narrow sidebar.
  return <p className={styles.sideCredit} title={dataset.attribution}><span>公開画像</span>{dataset.licence && <span>{dataset.licenceUrl ? <a href={dataset.licenceUrl} target="_blank" rel="noreferrer">{dataset.licence}</a> : dataset.licence}</span>}{dataset.sourceUrl && <a href={dataset.sourceUrl} target="_blank" rel="noreferrer">画像の出典</a>}</p>;
}
/** The demo's menu: the image source, and on phones the guide and download the header has no room for (N-08). */
export function DemoBadge({dataset, onGuide}: {dataset: ShowcaseDataset | null; onGuide: () => void}) {
  const menu = useRef<HTMLDetailsElement>(null);
  if (!dataset) return <span className={styles.badge}>デモ</span>;
  return <details className={styles.badgeMenu} ref={menu}>
    <summary className={styles.badge} aria-label="デモ：使い方・ダウンロード・画像の出典">デモ</summary>
    <div className={styles.popover}>
      <div className={styles.badgeActions}><button type="button" data-lp-event="demo_guide" onClick={() => {if (menu.current) menu.current.open = false; onGuide();}}>使い方</button><a href={DOWNLOAD_HREF} data-lp-event="demo_download">ダウンロード</a></div>
      <DatasetCredit dataset={dataset}/>
    </div>
  </details>;
}

/** The steps; the first names only the regions this scene has, and where outlines are corrected. */
function guideSteps(dataset: ShowcaseDataset | null): Array<{mode: DemoStep; title: string; text: string; table?: boolean; nucleus?: boolean}> {
  const nucleolar = !!dataset?.regions?.includes("nucleoli");
  return [
  {mode: "image", title: "画像と輪郭", text: `2 群の画像に、検出した輪郭を重ねています。輪郭を選び、表で値を確認します。輪郭の修正は各画像の左下から行います。公開デモでは修正を記録しません。${nucleolar ? "「領域」で核・核小体・核質を切り替えます。" : ""}`},
  {mode: "image", title: "測定値", text: "輪郭ごとの面積と輝度を、各画像の下の表に示します。", table: true},
  {mode: "image", title: "核ごとの表", text: `1 視野の核を 1 行ずつ示します。核の面積、各染色の輝度${nucleolar ? "、核小体の数・面積・形" : ""}を核ごとに並べます。行を選ぶと、画像の該当する核に移動します。表は ZIP（CSV と列の定義）で保存します。${nucleolar ? "画像の上の「色分け」の「核小体と核質」で、核ごとの核質と核小体の信号の比を表に示します。" : ""}`, table: true, nucleus: true},
  {mode: "statistics", title: "統計", text: `視野と群を集計して計算します。${dataset?.gateChannels?.length ? "陽性率の比較には、「画像」の「色分け」の「陽性・陰性」での核の分類が必要です。" : ""}`},
  {mode: "figure", title: "グラフと書き出し", text: "論文用の図を編集し、ZIP で保存します。"},
  ];
}

/** First-visit guide; each step opens the matching part of the real workspace. */
export function DemoGuide({open, onClose, onStep, dataset}: {open: boolean; onClose: () => void; onStep: (mode: DemoStep, table: boolean, nucleus: boolean) => void; dataset: ShowcaseDataset | null}) {
  const [index, setIndex] = useState(0);
  if (!open) return null;
  const steps = guideSteps(dataset), step = steps[index];
  const go = (next: number) => {setIndex(next); onStep(steps[next].mode, !!steps[next].table, !!steps[next].nucleus);};
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

const introKey = (scene: string) => `cytellect.demo.intro.closed.${scene}`;
function introClosed(scene: string) {try {return window.localStorage.getItem(introKey(scene)) === "1";} catch {return false;}}
/** The scene in brief for visitors who are not biologists (DM-11, UC-01–UC-07): conditions, display, result. It
 * stays closed once closed for this scene (per browser); 「場面の概要」 opens it again. */
export function SceneIntro({scene, dataset}: {scene: string; dataset: ShowcaseDataset | null}) {
  const [open, setOpen] = useState(false);
  useEffect(() => {setOpen(!introClosed(scene));}, [scene]);
  const explainer = dataset?.explainer;
  if (!explainer) return null;
  const close = () => {setOpen(false); try {window.localStorage.setItem(introKey(scene), "1");} catch {/* Closing still works for this page. */}};
  const reopen = () => {setOpen(true); try {window.localStorage.removeItem(introKey(scene));} catch {/* Opening still works for this page. */}};
  if (!open) return <button type="button" className={styles.introButton} onClick={reopen}>場面の概要</button>;
  const terms = explainer.terms.filter(term => TERMS[term]);
  return <section className={styles.intro} aria-label="場面の概要">
    <dl>
      <div><dt>条件</dt><dd>{explainer.what}</dd></div>
      <div><dt>表示</dt><dd>{explainer.colors}</dd></div>
      <div><dt>結果</dt><dd>{explainer.finding}</dd></div>
    </dl>
    {terms.length > 0 && <details><summary>用語</summary><dl className={styles.terms}>{terms.map(term => <div key={term}><dt>{term}</dt><dd>{TERMS[term]}</dd></div>)}</dl></details>}
    <button type="button" className={styles.introClose} aria-label="場面の概要を閉じる" onClick={close}>閉じる</button>
  </section>;
}

export function ProposalExamples({examples, disabled, onChoose}: {examples: ProposalExample[]; disabled: boolean; onChoose: (instruction: string) => void}) {
  if (!examples.length) return null;
  return <div className={styles.examples} role="group" aria-label="指示の例">{examples.map(example =>
    <button key={example.instruction} type="button" disabled={disabled} title={example.instruction} onClick={() => onChoose(example.instruction)}>{example.label}</button>)}</div>;
}
