"use client";
/** The discussion of one saved comparison (requirements AC-01–AC-08): apart from the computed result, marked as
 * AI-made (or, in the public demo, as an example), never a source of values. Made only when the researcher asks. */
import {useEffect, useRef, useState, useSyncExternalStore} from "react";
import {ApiError, errorMessage} from "@/lib/api";
import type {ApiAdapter, DiscussionView} from "@/lib/workspace/api-adapter";
import {DISCUSSION_SCOPE, discussionScopeSeen, markDiscussionScopeSeen, rememberedGoal, subscribeAiSettings} from "@/lib/workspace/ai-settings";
import {AiAvailabilityHint,useAi} from "../AiSettings";
import {GeneratedContentReportLink} from "./GeneratedContentReportLink";
import styles from "./discussion.module.css";

const HEADINGS = [["implications", "解釈"], ["alternatives", "限界・代替説明"], ["next_steps", "追加検証"]] as const;

function day(seconds: number) {
  const date = new Date(seconds * 1000);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

/** `summary`: the heading and points the card above shows, sent so that the discussion reads the result the same way.
 * The purpose starts from the goal last written to the AI in this workspace. */
export function DiscussionPanel({adapter, job, demo, workspace = "", summary}: {adapter: Pick<ApiAdapter, "discussion" | "draftDiscussion" | "discussionHistory">; job: string; demo: boolean;
  workspace?: string; summary?: {heading: string; points: string[]}}) {
  const [view, setView] = useState<DiscussionView | null | undefined>(undefined);
  const [previous, setPrevious] = useState<DiscussionView|null>(null);
  const generation = useRef(0),access=useAi();
  const scopeSeen=useSyncExternalStore(subscribeAiSettings,discussionScopeSeen,()=>false);
  const [purpose, setPurpose] = useState(() => rememberedGoal(workspace));
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<{text: string; retry: boolean} | null>(null);
  useEffect(() => {
    let live = true;
    ++generation.current;
    setView(undefined); setPrevious(null); setFailure(null); setBusy(false);
    const reading=demo?adapter.discussion(job).then(current=>({current,previous:null})):adapter.discussionHistory(job);
    reading.then(value => {if (live){setView(value.current??null);setPrevious(value.previous??null);}}).catch(error => {
      if (live){setView(null);setFailure({text:errorMessage(error),retry:false});}});
    // The live flag protects reads; invalidate a generation only when the next result is selected.
    return () => {live = false;};
  }, [adapter, job,demo]);
  if (view === undefined) return null;
  // The public demo never calls a model: it shows an example only where the build recorded one (AC-08).
  if (!view && demo) return <section className={styles.panel} aria-label="考察"><h4>考察</h4>
    <p>Windows 版・Docker 版では、この結果から考察を生成できます。</p></section>;
  const make = async (retry: boolean) => {
    if(!access.available||busy)return;
    const ticket=generation.current;
    setBusy(true); setFailure(null);
    try {
      const result=await adapter.draftDiscussion(job, purpose.trim() ? {purpose: purpose.trim(), stains: []} : {stains: []}, retry,
        summary ? {heading: summary.heading, points: summary.points} : undefined);
      markDiscussionScopeSeen();
      if(ticket===generation.current)setView(result);
    } catch (error) {
      if(ticket!==generation.current)return;
      const rejected = error instanceof ApiError && error.status === 502 && error.code === "request_failed";
      const again = error instanceof ApiError && error.code === "proposal_explicit_retry_required";
      setFailure({text: rejected ? "AI の出力を読み取れませんでした。再生成すると再度課金される場合があります。" :
        again ? "前回の依頼が未完了です。再生成すると再度課金される場合があります。" : errorMessage(error), retry: rejected || again});
    } finally {if(ticket===generation.current)setBusy(false);}
  };
  if (!view) return <>
    {previous&&<SavedDiscussion view={previous} previous/>}
    <section className={styles.panel} aria-label="考察">
    <h4>考察</h4>
    <AiAvailabilityHint/>
    <div className={styles.ask}>
      {/* The scope is shown in full until the researcher has sent once; afterwards it stays one click away. */}
      {scopeSeen ? <details><summary>送信内容</summary><p>{DISCUSSION_SCOPE}</p></details> : <p>{DISCUSSION_SCOPE}</p>}
      <label>実験の目的（任意）<textarea disabled={busy||!access.available} maxLength={2000} rows={2} value={purpose} onChange={event => setPurpose(event.target.value)}/></label>
      <div className={styles.actions}>
        <button type="button" disabled={busy||!access.available} onClick={() => void make(false)}>{busy?"生成中…":"考察を生成"}</button>
      </div>
    </div>
    {failure && <p role="status" className={styles.failure}>{failure.text}{failure.retry && <button type="button" disabled={busy||!access.available} onClick={() => void make(true)}>再生成</button>}</p>}
  </section></>;
  return <SavedDiscussion view={view}/>;
}

/** A stored discussion: its frame says who wrote it and that it holds no computed value (AC-01, AC-06, AC-08). */
export function SavedDiscussion({view,previous=false}: {view: DiscussionView;previous?:boolean}) {
  const draft = view.discussion.draft;
  const example = view.discussion.origin === "example";
  const title=previous?"前の結果の考察":"考察";
  return <section className={styles.panel} aria-label={title}>
    <h4>{title} <small>{example ? "デモ用サンプル（参考）" : `AI 生成（参考）· ${view.discussion.model} · ${day(view.created)}`}</small></h4>
    {HEADINGS.map(([key, label]) => (draft[key] ?? []).length > 0 && <div key={key}><h5>{label}</h5><ul>{(draft[key] ?? []).map(item => <li key={item}>{item}</li>)}</ul></div>)}
    {!example && <GeneratedContentReportLink/>}
  </section>;
}
