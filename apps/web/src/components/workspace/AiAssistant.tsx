"use client";
import {useEffect, useRef, useState} from "react";
import styles from "./ai-assistant.module.css";

/** One setting the AI changed on the method card, shown with its reason. */
export interface AiChange {step: string; label: string; before: string; after: string; reason?: string}
export interface AiTurn {
  id: string; instruction: string; state: "pending" | "done" | "failed";
  rationale?: string; changes?: AiChange[]; questions?: string[]; confirm?: string[]; error?: string; undone?: boolean;
}
export type AiStatus = {enabled: boolean; reason: string | null} | null;

const disabledText: Record<string, string> = {
  not_configured: "この解析サーバーには AI 中継サービスが設定されていません。",
  invalid_configuration: "AI 中継サービスの設定が無効です（HTTPS の URL が必要です）。",
};

/**
 * The researcher's AI operation surface: always visible in the header.
 * The AI chooses method settings only; measurements and statistics stay with the API.
 */
export function AiAssistant({status, busy, disabled, disabledHint, turns, onSend, onUndo, onShowStep, onRetry}: {
  status: AiStatus; busy: boolean; disabled: boolean; disabledHint?: string; turns: AiTurn[];
  onSend: (instruction: string) => void; onUndo: (turn: string) => void; onShowStep: (step: string) => void; onRetry?: () => void;
}) {
  const [text, setText] = useState("");
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const log = useRef<HTMLOListElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  const unavailable = status !== null && !status.enabled;
  const blocked = busy || disabled || unavailable;
  const last = turns[turns.length - 1];
  useEffect(() => {if (busy || last?.state === "done" || last?.state === "failed") setOpen(true);}, [busy, last?.id, last?.state]);
  useEffect(() => {log.current?.scrollTo({top: log.current.scrollHeight});}, [turns, open]);
  useEffect(() => {
    if (!open) return;
    const close = (event: KeyboardEvent) => {if (event.key === "Escape") setOpen(false);};
    const outside = (event: PointerEvent) => {if (root.current && !root.current.contains(event.target as Node)) setOpen(false);};
    window.addEventListener("keydown", close); window.addEventListener("pointerdown", outside);
    return () => {window.removeEventListener("keydown", close); window.removeEventListener("pointerdown", outside);};
  }, [open]);
  const send = () => {const value = text.trim(); if (!value || blocked) return; onSend(value); setText("");};
  const answer = (question: string) => {setText(`「${question}」への回答：`); setOpen(true); input.current?.focus();};
  const state = status === null ? "確認中" : status.enabled ? "利用可能" : "未設定";
  return <div ref={root} className={styles.assistant} data-open={open || undefined}>
    <form className={styles.bar} onSubmit={event => {event.preventDefault(); send();}}>
      <button type="button" className={styles.state} data-state={status === null ? "checking" : status.enabled ? "on" : "off"}
        aria-expanded={open} aria-controls="ai-assistant-panel" title="AI の状態と履歴" onClick={() => setOpen(value => !value)}>
        AI <span>{state}</span>
      </button>
      <label htmlFor="ai-instruction" className={styles.hidden}>AI への指示</label>
      <textarea ref={input} id="ai-instruction" rows={1} value={text} maxLength={1000} disabled={unavailable}
        placeholder={unavailable ? "AI は未設定です（左の「AI 未設定」で手順を確認）" : "AI に指示：例）GFP 陽性の核だけで、処理群と対照群の核の大きさを比べたい"}
        onFocus={() => {if (turns.length || unavailable) setOpen(true);}}
        onChange={event => setText(event.target.value)}
        onKeyDown={event => {if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {event.preventDefault(); send();}}}/>
      <button type="submit" className={styles.send} disabled={blocked || !text.trim()} title={disabled && disabledHint ? disabledHint : "指示を送り、方法の設定を AI に選ばせます"}>
        {busy ? "考え中…" : "送信"}
      </button>
    </form>
    {open && <div id="ai-assistant-panel" className={styles.panel} role="region" aria-label="AI の応答">
      {unavailable && <section className={styles.notice}>
        <strong>AI は使えません</strong>
        <p>{disabledText[status?.reason ?? ""] ?? "AI 中継サービスを利用できません。"}</p>
        <p>手動の解析はそのまま使えます。AI を使うには、管理者が中継サービスの URL と端末用トークンのファイルを指定して起動します（Docker 版：<code>scripts\docker-desktop.ps1 Start -ProposalConfig &lt;設定ファイル&gt;</code>、手順は docs/local.md）。</p>
      </section>}
      {!turns.length && !unavailable && <p className={styles.empty}>調べたいことを書くと、AI が核の検出・測る対象・しきい値・背景・GFP の絞り込み・比較と図を選び、右の「方法」に設定します。設定はすべて変更できます。</p>}
      <ol ref={log} className={styles.log}>
        {turns.map(turn => <li key={turn.id} className={styles.turn}>
          <p className={styles.instruction}>{turn.instruction}</p>
          {turn.state === "pending" && <p className={styles.pending} role="status">方法を選んでいます…</p>}
          {turn.state === "failed" && <p className={styles.error} role="alert">{turn.error}{onRetry && turn === last && <button type="button" onClick={onRetry}>再送信</button>}</p>}
          {turn.state === "done" && <div className={styles.reply}>
            {turn.rationale && <p>{turn.rationale}</p>}
            {!!turn.changes?.length && <table className={styles.changes}>
              <caption>{turn.undone ? "設定を元に戻しました" : `${turn.changes.length} 項目を設定しました`}</caption>
              <tbody>{turn.changes.map((change, index) => <tr key={index} data-undone={turn.undone || undefined}>
                <th scope="row"><button type="button" title="方法のこのステップを表示" onClick={() => onShowStep(change.step)}>{change.label}</button></th>
                <td><span className={styles.before}>{change.before}</span> → <b>{change.after}</b>{change.reason && <small>{change.reason}</small>}</td>
              </tr>)}</tbody>
            </table>}
            {turn.changes && !turn.changes.length && <p className={styles.muted}>現在の設定から変更はありません。</p>}
            {!!turn.confirm?.length && <ul className={styles.questions}>{turn.confirm.map((value, index) => <li key={index}>確認が必要：{value}</li>)}</ul>}
            {!!turn.questions?.length && <ul className={styles.questions}>{turn.questions.map((question, index) => <li key={index}>{question} <button type="button" onClick={() => answer(question)}>回答する</button></li>)}</ul>}
            {!!turn.changes?.length && !turn.undone && turn === last && <button type="button" className={styles.undo} disabled={busy} onClick={() => onUndo(turn.id)}>この変更を元に戻す</button>}
          </div>}
        </li>)}
      </ol>
      <p className={styles.footnote}>送信するのは指示文と画像の構成（チャンネル数・記録された染色名・視野数・群の数）だけです。画像・ファイル名・測定値は送りません。AI は測定値や統計を計算しません。</p>
    </div>}
  </div>;
}
