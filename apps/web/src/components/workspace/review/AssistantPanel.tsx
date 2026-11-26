"use client";
import {useEffect, useRef} from "react";
import type {AssistantMessage} from "@/lib/workspace/api-adapter";
import {reasonView, type ReasonPlace} from "@/lib/workspace/assistant-reasons";
import type {ReviewField} from "@/lib/workspace/review-preview";
import type {AnswerView, ChannelConfirmation, RunTargets} from "@/lib/workspace/use-workspace-runtime";
import styles from "./connected-workspace.module.css";

const SOURCES: Record<string, string> = {filename: "ファイル名", ome_metadata: "OME メタデータ", user_entered: "入力", unresolved: "未確定", assignment: "染色対応"};
const ROLES: Record<string, string> = {nuclear: "核染色", measure: "測定", unused: "未使用"};
const PLACES: Record<ReasonPlace, string> = {images: "画像", channels: "染色対応", experiment: "実験デザイン", settings: "解析設定"};

/** The state of a message as one value (section 5.7 of the #284 plan): 送信中, 回答, 失敗, 設定を適用済み, 実行済み. */
export function messageState(message: AssistantMessage): string {
  if (message.effect === "run") return "実行済み";
  if (message.effect === "settings") return "設定を適用済み";
  return message.state === "pending" ? "送信中" : message.state === "failed" ? "失敗" : "回答";
}

/**
 * Whether a message offers 「再送」: a failed one; one left 送信中 by a session that ended before its answer (never the
 * request in flight); an answer with settings, choices or run and group suggestions this session no longer holds (a
 * reload); and an answer whose settings were refused for a reason on the service's side. A question's plain answer has
 * nothing to send again.
 */
export function resendable(message: AssistantMessage, serviceReason: boolean, held: boolean, busy: boolean, demo: boolean, last = true): boolean {
  if (demo) return false;
  if (message.state === "failed") return true;
  if (message.state === "pending") return !busy;
  if (message.applicable === false) return serviceReason;
  // `restorable`: the recorded answer holds choices or run and group suggestions, which a resend returns from the record.
  // A question's answer is fetched again as the latest message (its choices are offered there alone), or from any
  // message when it holds run and group suggestions (the experiment table shows them).
  return (message.applicable === true || (message.restorable === true && last) || message.suggests_assignments === true) && message.effect === "none" && !held;
}

interface Props {
  field?: ReviewField;
  messages: AssistantMessage[];
  busy: boolean;
  /** The public demo answers only its recorded examples; it shows neither resend nor the image facts' actions. */
  demo: boolean;
  canApply: (id: string) => boolean;
  canTry: (id: string) => boolean;
  /** The message whose applied settings 「AI による設定変更を戻す」 restores (the latest applied one). */
  undoable: string | null;
  onApply: (id: string, trial: boolean) => void;
  onResend: (message: AssistantMessage) => void;
  onUndo: () => void;
  onShowSettings: () => void;
  onPlace: (place: ReasonPlace) => void;
  /** Sends the images alone (an empty instruction) for a proposal; offered when there are images. */
  onPropose?: () => void;
  /** What an answer received in this session offers (#284 W7); null for one restored after a reload. A restored
   * answer with settings (`applicable: true`) offers 「再送」 to apply it; a question's answer has nothing to apply. */
  answerOf?: (id: string) => AnswerView | null;
  runTargets?: (id: string) => RunTargets | null;
  canRun?: (id: string) => boolean;
  /** 「適用して実行」: the run request's settings, then detection candidates on its target fields. */
  onRun?: (id: string) => void;
  /** A choice of an item to confirm, sent as the next message. */
  onChoose?: (text: string) => void;
  /** The nuclear channels the answer proposes that the workspace has not recorded yet: applying waits for them. */
  confirmationOf?: (id: string) => ChannelConfirmation[];
  /** 「核染色に … を指定」: the researcher's own record of the nuclear stain (as in 染色対応); applies nothing. */
  onConfirm?: (id: string, channel: string) => void;
}

/** The fields a run request covers, as one state: 「対象：選択した視野 · A01」 or 「対象：全視野 · 2 視野 · 対象外 1」. */
export function targetText(targets: RunTargets): string {
  if (targets.scope === "selected") return `対象：選択した視野 · ${targets.fields[0]?.label ?? "未選択"}`;
  return `対象：全視野 · ${targets.fields.length} 視野${targets.excluded ? ` · 対象外 ${targets.excluded}` : ""}`;
}

/**
 * The AI conversation of this workspace (#284 W2, W7). The facts of the selected field come from the workspace, not the
 * model. Every message keeps its own state, answer, reasons and actions. The answer's kind of request only chooses the
 * actions (plan 5.6): a question shows its answer and the items to confirm, a settings request 「設定を適用」, a run
 * request its target fields and 「適用して実行」. Nothing changes settings or runs an analysis until the researcher
 * chooses one (decision 4).
 */
export function AssistantPanel({field, messages, busy, demo, canApply, canTry, undoable, onApply, onResend, onUndo, onShowSettings, onPlace, onPropose,
  answerOf = () => null, runTargets = () => null, canRun = () => false, onRun, onChoose, confirmationOf = () => [], onConfirm}: Props) {
  const nuclear = field?.channels.find(channel => channel.id === field.nuclearChannelId) ?? field?.channels.find(channel => channel.role === "nuclear");
  // The message whose state just changed (a new answer, or the answer or failure of a resend) starts at the top of the
  // panel, and the newest one when the panel opens: an answer of a few paragraphs otherwise leaves every later request
  // below the visible part, and a resend (confirmed above the conversation) would be answered out of sight. A message
  // is found by the change of its state, so applying settings, and fetching a recorded answer again, move nothing.
  // Only the panel's own scrolling box moves, never the page.
  const list = useRef<HTMLOListElement>(null), states = useRef<Map<string, string> | null>(null);
  useEffect(() => {
    const before = states.current;
    states.current = new Map(messages.map(message => [message.id, message.state]));
    const moved = before ? messages.filter(message => before.get(message.id) !== message.state).at(-1) : messages.at(-1);
    const item = moved && [...list.current?.children ?? []].find(node => (node as HTMLElement).dataset.message === moved.id);
    if (!item) return;
    for (let box = item.parentElement; box; box = box.parentElement) {
      if (!/auto|scroll/.test(getComputedStyle(box).overflowY) || box.scrollHeight <= box.clientHeight) continue;
      box.scrollTop += item.getBoundingClientRect().top - box.getBoundingClientRect().top - 8;
      return;
    }
  }, [messages]);
  return <div className={styles.assistant}>
    {field && <section aria-label="選択した視野の情報" className={styles.assistantFacts}>
      <p><strong>視野：</strong>{field.label} · {field.width} × {field.height} px</p>
      <ul>{field.channels.map(channel => <li key={channel.id}>
        {channel.stain || channel.label}（{channel.id}）：由来 {SOURCES[channel.stainSource ?? "unresolved"] ?? "未確定"} · 役割 {channel.role ? ROLES[channel.role] ?? "未指定" : "未指定"}
      </li>)}</ul>
      <p><strong>核染色のチャンネル：</strong>{nuclear ? nuclear.stain || nuclear.label : "未指定"}</p>
    </section>}
    {onPropose && !demo && <button type="button" disabled={busy} onClick={onPropose}>解析案を作る</button>}
    <ol ref={list} className={styles.messages} aria-label="AI との会話" aria-live="polite">
      {messages.map(message => {
        const reasons = message.reasons.map(reasonView);
        const view = answerOf(message.id), intent = view?.intent ?? null, targets = intent === "run" ? runTargets(message.id) : null;
        const confirmation = demo ? [] : confirmationOf(message.id);
        return <li key={message.id} data-message={message.id} className={styles.message} data-state={message.state}>
          <p className={styles.userMessage}>{message.text || "画像からの解析案"}</p>
          <p className={styles.messageState}>状態：{messageState(message)}</p>
          {message.reply && message.reply.split("\n").map((line, index) => <p key={index}>{line}</p>)}
          {reasons.length > 0 && <ul className={styles.messageReasons} aria-label={message.applicable === false ? "適用できない理由" : "失敗の理由"}>
            {reasons.map((reason, index) => <li key={index}>
              {reason.text}
              {reason.kind === "researcher" && reason.place && <> <button type="button" disabled={busy} onClick={() => onPlace(reason.place!)}>{PLACES[reason.place]}</button></>}
              {reason.kind === "service" && <> <code>{message.reasons[index]}</code></>}
            </li>)}
          </ul>}
          {view && view.choices.length > 0 && !demo && message.id === messages.at(-1)?.id && <div className={styles.messageChoices}>
            {view.choices.map((choice, index) => <div key={index} role="group" aria-label={choice.question}>
              <p>{choice.question}</p>
              {choice.options.map(option => <button key={option} type="button" disabled={busy || !onChoose} onClick={() => onChoose?.(option)}>{option}</button>)}
            </div>)}
          </div>}
          {view && view.assignments > 0 && <p className={styles.messageState}>割付の案：{view.assignments} 視野 <button type="button" disabled={busy} onClick={() => onPlace("experiment")}>実験</button></p>}
          {targets && <p className={styles.messageState}>{targetText(targets)}</p>}
          {targets && !targets.fields.length && message.effect === "none" && <p className={styles.messageState}>実行には、対象の視野が必要です。</p>}
          {confirmation.length > 0 && <div className={styles.messageChoices} role="group" aria-label="核染色の指定">
            <p>{view?.applies === false ? "核染色：未指定" : "設定の適用には、核染色の指定が必要です。"}</p>
            {confirmation.map(item => <button key={item.channel} type="button" disabled={busy || !onConfirm} onClick={() => onConfirm?.(message.id, item.channel)}>核染色に {item.label} を指定</button>)}
          </div>}
          <div className={styles.messageActions}>
            {message.effect === "none" && intent === null && canApply(message.id) && <>
              <button type="button" disabled={busy} onClick={() => onApply(message.id, false)}>設定を適用</button>
              {canTry(message.id) && <button type="button" disabled={busy} onClick={() => onApply(message.id, true)}>適用して試行</button>}
            </>}
            {message.effect === "none" && intent === "settings" && canApply(message.id) &&
              <button type="button" disabled={busy} onClick={() => onApply(message.id, false)}>設定を適用</button>}
            {message.effect === "none" && intent === "run" && canRun(message.id) && onRun &&
              <button type="button" disabled={busy} onClick={() => onRun(message.id)}>適用して実行</button>}
            {message.effect !== "none" && <button type="button" disabled={busy} onClick={onShowSettings}>解析設定を表示</button>}
            {message.effect !== "none" && undoable === message.id && <button type="button" disabled={busy} onClick={onUndo}>AIによる設定変更を戻す</button>}
            {resendable(message, reasons.some(reason => reason.kind === "service"), !!view, busy, demo, message.id === messages.at(-1)?.id) &&
              <button type="button" disabled={busy} onClick={() => onResend(message)}>再送</button>}
          </div>
        </li>;
      })}
    </ol>
  </div>;
}
