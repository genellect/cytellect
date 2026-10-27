import {useState} from "react";
import type {UnfinishedImport} from "@/lib/workspace/use-workspace-runtime";
import styles from "./connected-workspace.module.css";

/** Imports that never became a field stay in the record; the comparison needs a reason before leaving one out. */
export function UnfinishedImports({items, disabled, onExclude}: {items: UnfinishedImport[]; disabled: boolean; onExclude: (entry: string, reason: string) => void}) {
  return <>{items.map(item => <UnfinishedImportItem key={item.entry} item={item} disabled={disabled} onExclude={onExclude}/>)}</>;
}

function UnfinishedImportItem({item, disabled, onExclude}: {item: UnfinishedImport; disabled: boolean; onExclude: (entry: string, reason: string) => void}) {
  const [reason, setReason] = useState(item.reason ? `登録できない画像のため除外：${item.reason}`.slice(0, 300) : "");
  return <li className={styles.unfinishedImport}>
    <span><strong>{item.name ?? "名前の記録がない登録"}</strong>：{item.reason ?? "登録が完了していません。もう一度追加するか、理由を付けて除外してください。"}</span>
    <form onSubmit={event => {event.preventDefault(); onExclude(item.entry, reason);}}>
      <input aria-label="除外の理由" maxLength={300} value={reason} disabled={disabled} onChange={event => setReason(event.target.value)}/>
      <button type="submit" disabled={disabled || !reason.trim()}>除外</button>
    </form>
  </li>;
}
