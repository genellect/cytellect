"use client";
/** The discussion of one saved comparison (requirements AC-01–AC-08): apart from the computed result, marked as
 * AI-made (or, in the public demo, as an example), never a source of values. Made only when the researcher asks. */
import {useEffect, useState} from "react";
import {ApiError, errorMessage} from "@/lib/api";
import type {ApiAdapter, DiscussionView} from "@/lib/workspace/api-adapter";
import styles from "./discussion.module.css";

const HEADINGS = [["implications", "解釈"], ["alternatives", "限界・代替説明"], ["next_steps", "追加検証"]] as const;
const SENT = "送信内容：保存済みの集計値（群の値、差と信頼区間、実験回ごとの値、n、検定、p 値）と実験の目的。画像・ファイル名・パスは送信しません。";

function day(seconds: number) {
  const date = new Date(seconds * 1000);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

export function DiscussionPanel({adapter, job, demo}: {adapter: Pick<ApiAdapter, "discussion" | "draftDiscussion">; job: string; demo: boolean}) {
  const [view, setView] = useState<DiscussionView | null | undefined>(undefined);
  const [asking, setAsking] = useState(false);
  const [purpose, setPurpose] = useState("");
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<{text: string; retry: boolean} | null>(null);
  useEffect(() => {
    let live = true;
    setView(undefined); setFailure(null); setAsking(false);
    adapter.discussion(job).then(value => {if (live) setView(value);}).catch(() => {if (live) setView(null);});
    return () => {live = false;};
  }, [adapter, job]);
  if (view === undefined) return null;
  // The public demo never calls a model: it shows an example only where the build recorded one (AC-08).
  if (!view && demo) return null;
  const make = async (retry: boolean) => {
    setBusy(true); setFailure(null);
    try {
      setView(await adapter.draftDiscussion(job, purpose.trim() ? {purpose: purpose.trim(), stains: []} : {stains: []}, retry));
      setAsking(false);
    } catch (error) {
      const rejected = error instanceof ApiError && error.status === 502 && error.code === "request_failed";
      const again = error instanceof ApiError && error.code === "proposal_explicit_retry_required";
      setFailure({text: rejected ? "不採用：結果にない数値または記述を含む出力でした。" :
        again ? "前回の依頼が未完了です。再生成すると再度課金される場合があります。" : errorMessage(error), retry: rejected || again});
    } finally {setBusy(false);}
  };
  if (!view) return <section className={styles.panel} aria-label="考察">
    <h4>考察</h4>
    {!asking ? <button type="button" onClick={() => setAsking(true)}>考察を生成</button> : <div className={styles.ask}>
      <p>{SENT}</p>
      <label>実験の目的（任意）<textarea maxLength={500} rows={2} value={purpose} onChange={event => setPurpose(event.target.value)}/></label>
      <div className={styles.actions}>
        <button type="button" disabled={busy} onClick={() => void make(false)}>送信して生成</button>
        <button type="button" disabled={busy} onClick={() => setAsking(false)}>キャンセル</button>
      </div>
    </div>}
    {failure && <p role="status" className={styles.failure}>{failure.text}{failure.retry && <button type="button" disabled={busy} onClick={() => void make(true)}>再生成</button>}</p>}
  </section>;
  return <SavedDiscussion view={view}/>;
}

/** A stored discussion: its frame says who wrote it and that it holds no computed value (AC-01, AC-06, AC-08). */
export function SavedDiscussion({view}: {view: DiscussionView}) {
  const draft = view.discussion.draft;
  const example = view.discussion.origin === "example";
  return <section className={styles.panel} aria-label="考察">
    <h4>考察 <small>{example ? "デモ用サンプル（参考）" : `AI 生成（参考）· ${view.discussion.model} · ${day(view.created)}`}</small></h4>
    {HEADINGS.map(([key, label]) => (draft[key] ?? []).length > 0 && <div key={key}><h5>{label}</h5><ul>{(draft[key] ?? []).map(item => <li key={item}>{item}</li>)}</ul></div>)}
  </section>;
}
