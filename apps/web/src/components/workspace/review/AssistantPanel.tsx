"use client";
import type {AssistantMessage} from "@/lib/workspace/api-adapter";
import {reasonView, type ReasonPlace} from "@/lib/workspace/assistant-reasons";
import type {ReviewField} from "@/lib/workspace/review-preview";
import type {AnswerView, RunTargets} from "@/lib/workspace/use-workspace-runtime";
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
  /** What an answer received in this session offers (#284 W7); null for one restored after a reload. */
  answerOf?: (id: string) => AnswerView | null;
  runTargets?: (id: string) => RunTargets | null;
  canRun?: (id: string) => boolean;
  /** 「適用して実行」: the run request's settings, then detection candidates on its target fields. */
  onRun?: (id: string) => void;
  /** A choice of an item to confirm, sent as the next message. */
  onChoose?: (text: string) => void;
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
  answerOf = () => null, runTargets = () => null, canRun = () => false, onRun, onChoose}: Props) {
  const nuclear = field?.channels.find(channel => channel.id === field.nuclearChannelId) ?? field?.channels.find(channel => channel.role === "nuclear");
  return <div className={styles.assistant}>
    {field && <section aria-label="選択した視野の情報" className={styles.assistantFacts}>
      <p><strong>視野：</strong>{field.label} · {field.width} × {field.height} px</p>
      <ul>{field.channels.map(channel => <li key={channel.id}>
        {channel.stain || channel.label}（{channel.id}）：由来 {SOURCES[channel.stainSource ?? "unresolved"] ?? "未確定"} · 役割 {channel.role ? ROLES[channel.role] ?? "未指定" : "未指定"}
      </li>)}</ul>
      <p><strong>核染色のチャンネル：</strong>{nuclear ? nuclear.stain || nuclear.label : "未指定"}</p>
    </section>}
    {onPropose && !demo && <button type="button" disabled={busy} onClick={onPropose}>解析案を作る</button>}
    <ol className={styles.messages} aria-label="AI との会話">
      {messages.map(message => {
        const reasons = message.reasons.map(reasonView);
        const view = answerOf(message.id), intent = view?.intent ?? null, targets = intent === "run" ? runTargets(message.id) : null;
        return <li key={message.id} className={styles.message} data-state={message.state}>
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
          {view && view.choices.length > 0 && !demo && <div className={styles.messageChoices}>
            {view.choices.map((choice, index) => <div key={index} role="group" aria-label={choice.question}>
              <p>{choice.question}</p>
              {choice.options.map(option => <button key={option} type="button" disabled={busy || !onChoose} onClick={() => onChoose?.(option)}>{option}</button>)}
            </div>)}
          </div>}
          {view && view.assignments > 0 && <p className={styles.messageState}>割付の案：{view.assignments} 視野 <button type="button" disabled={busy} onClick={() => onPlace("experiment")}>実験</button></p>}
          {targets && <p className={styles.messageState}>{targetText(targets)}</p>}
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
            {!demo && message.state !== "pending" && (message.state === "failed" || (message.applicable !== false && message.effect === "none" && !view)) &&
              <button type="button" disabled={busy} onClick={() => onResend(message)}>再送</button>}
          </div>
        </li>;
      })}
    </ol>
  </div>;
}
