"use client";
import {useRef, type ReactNode} from "react";
import type {IntakeTarget} from "@/lib/workspace/api-adapter";
import {intakeReason} from "@/lib/workspace/intake-record";
import {breakdown, listedFields, matchingFields, type IntakeItem} from "@/lib/workspace/intake-list";
import styles from "./intake.module.css";

interface Props {
  items: IntakeItem[];
  /** Registered fields with their size, for the mask candidates' size match. */
  registered: ReadonlyArray<{name: string; shape: readonly number[]}>;
  /** Registration or an analysis holds the runtime: choosing and judging go on, adding waits. */
  busy: boolean;
  targetLabel: (target: IntakeTarget) => string;
  onAdd: (askAi: boolean) => void;
  onMore: () => void;
  onUndoLast: () => void;
  onRemove: (ids: string[]) => void;
  onReplace: (id: string, file: File) => void;
  onSeparate: (id: string) => void;
  onClose: () => void;
  /** The saved rows of images that did not become fields (W1), shown in the same list. */
  children?: ReactNode;
  /** Notes on registered fields (a stain one field has and another lacks): not images that failed, listed apart. */
  notes?: ReactNode;
}

const channelText = (channels: string[]) => channels.map(channel => channel.toUpperCase()).join(" · ");
/** A file's own name without its folders, for a button beside the full names. */
const shortName = (name: string) => name.replaceAll("\\", "/").split("/").at(-1) || name;

/**
 * The files chosen and not yet added (#284 W5): one line whose parts add up to what was received, then a row per field
 * to be made (thumbnail, name, channels, state) and a row per file that will not become a field, each with its own
 * action. 追加 registers the fields; nothing is registered before it.
 */
export function IntakeList({items, registered, busy, targetLabel, onAdd, onMore, onUndoLast, onRemove, onReplace, onSeparate, onClose, children, notes}: Props) {
  const input = useRef<HTMLInputElement>(null), replacing = useRef<string | null>(null);
  const fields = listedFields(items), others = items.filter(item => !["追加待ち", "読み込み中"].includes(item.state) || !item.file);
  const loading = items.some(item => item.state === "読み込み中"), addable = fields.some(field => !field.conflicts.length) || items.some(item => item.state === "読み取れない" && item.file);
  const choose = (id: string) => {replacing.current = id;input.current?.click();};
  return <section className={styles.list} aria-label="取り込みの一覧">
    <header className={styles.listHeader}>
      <p role="status">{breakdown(items) || "選択中のファイル：なし"}</p>
      <div className={styles.listActions}>
        {items.length > 0 && <>
          <button type="button" className={styles.primary} disabled={busy || loading || !addable} onClick={() => onAdd(false)}>追加</button>
          <button type="button" disabled={busy || loading || !fields.length} onClick={() => onAdd(true)}>追加して AI に質問</button>
        </>}
        <button type="button" onClick={onMore}>画像を追加</button>
        {items.length > 0 && <button type="button" disabled={!items.some(item => item.selection > 0)} onClick={onUndoLast}>直前の選択を取り消し</button>}
        <button type="button" onClick={onClose}>閉じる</button>
      </div>
    </header>
    {items.length > 0 && <table className={styles.table}>
      <thead><tr><th scope="col"><span className={styles.hidden}>縮小画像</span></th><th scope="col">名前</th><th scope="col">チャンネル</th><th scope="col">状態</th><th scope="col"><span className={styles.hidden}>操作</span></th></tr></thead>
      <tbody>
        {fields.map(field => <tr key={field.key}>
          <td>{field.thumbnail ? <img className={styles.thumb} src={field.thumbnail} alt=""/> : <span className={styles.thumb} aria-hidden="true"/>}</td>
          <th scope="row">{field.name}{field.items[0]?.target && <small>{targetLabel(field.items[0].target)}</small>}</th>
          <td>{channelText(field.channels)}</td>
          <td>{field.loading ? "読み込み中" : field.conflicts.length ? "要確認" : "追加待ち"}
            {field.conflicts.map(conflict => <small key={conflict.channel}>同じチャンネルに {conflict.items.length} 枚 · {conflict.channel.toUpperCase()}：{conflict.items.map(item => item.name).join("、")}</small>)}
            {field.repeated && !field.conflicts.length && <small>同じ名前 · 別の視野として追加</small>}</td>
          <td className={styles.rowActions}>
            {field.conflicts.flatMap(conflict => conflict.items.map(item => <button key={item.id} type="button" aria-label={`${item.name} を使用`} title={`${item.name} を使用`}
              onClick={() => onRemove(conflict.items.filter(other => other.id !== item.id).map(other => other.id))}>{shortName(item.name)} を使用</button>))}
            <button type="button" className={styles.remove} aria-label={`${field.name} を一覧から外す`} onClick={() => onRemove(field.items.map(item => item.id))}>×</button></td>
        </tr>)}
        {others.map(item => <tr key={item.id} data-state={item.state}>
          <td>{thumbnailOf(item, items) ? <img className={styles.thumb} src={thumbnailOf(item, items)!} alt=""/> : <span className={styles.thumb} aria-hidden="true"/>}</td>
          <th scope="row">{item.name}</th>
          <td>{item.channelNames.length ? channelText(item.channelNames) : "—"}</td>
          <td>{item.state}{detail(item, items, registered) && <small>{detail(item, items, registered)}</small>}</td>
          <td className={styles.rowActions}>
            {(item.state === "読み取れない" || item.state === "再選択") && <button type="button" onClick={() => choose(item.id)}>{item.state === "再選択" ? "選択" : "差し替え"}</button>}
            {item.state === "同一内容" && <button type="button" onClick={() => onSeparate(item.id)}>別の撮影として追加</button>}
            <button type="button" className={styles.remove} aria-label={`${item.name} を一覧から外す`} onClick={() => onRemove([item.id])}>×</button>
          </td>
        </tr>)}
      </tbody>
    </table>}
    {children && <h2 className={styles.savedHeading}>登録していない画像</h2>}
    {children}
    {notes && <h2 className={styles.savedHeading}>チャンネルの構成の違い</h2>}
    {notes}
    <input hidden type="file" accept=".tif,.tiff" ref={input} data-testid="intake-replace-input" onChange={event => {
      const id = replacing.current, file = event.target.files?.[0];replacing.current = null;event.target.value = "";
      if (id && file) onReplace(id, file);
    }}/>
  </section>;
}

/** A row's thumbnail; a copy shows the image it copies when that image is in the list (the same bytes). */
function thumbnailOf(item: IntakeItem, items: readonly IntakeItem[]): string | null {
  return item.thumbnail ?? (item.state === "同一内容" && item.sha256 ? items.find(other => other.sha256 === item.sha256 && other.thumbnail)?.thumbnail ?? null : null);
}

function detail(item: IntakeItem, items: readonly IntakeItem[], registered: Props["registered"]): string {
  if (item.state === "マスクの候補") {const fields = matchingFields(item, items, registered);return `寸法の一致：${fields.length ? fields.join("、") : "なし"}`;}
  if (item.state === "読み取れない") return intakeReason(item.code, false);
  if (item.state === "同一内容") return `対応先：${item.sameAs}`;
  if (item.state === "対象外") return "TIFF 以外";
  return "";
}
