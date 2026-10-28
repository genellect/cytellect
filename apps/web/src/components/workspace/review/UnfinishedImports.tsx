import {useState} from "react";
import type {UnfinishedImport} from "@/lib/workspace/use-workspace-runtime";
import styles from "./connected-workspace.module.css";

const proposed = (reason: string | null) => reason ? `登録できない画像のため除外：${reason}`.slice(0, 300) : "";

/** Imports that never became a field stay in the record; the comparison needs a reason before leaving one out.
 * Several can be left out at once with one reason (for example, every label image of a batch). */
export function UnfinishedImports({items, disabled, onExclude}: {items: UnfinishedImport[]; disabled: boolean; onExclude: (entries: string[], reason: string) => void}) {
  const reasons = new Set(items.map(item => item.reason));
  return <>
    {items.length > 1 && <ExclusionForm key={items.map(item => item.entry).join()} label={`登録できなかった ${items.length} 件をまとめて除外`} initial={reasons.size === 1 ? proposed(items[0].reason) : ""}
      disabled={disabled} onSubmit={reason => onExclude(items.map(item => item.entry), reason)} button="まとめて除外"/>}
    {items.map(item => <li key={item.entry} className={styles.unfinishedImport}>
      <span><strong>{item.name ?? "名前の記録がない登録"}</strong>：{item.reason ?? "登録が完了していません。もう一度追加するか、理由を付けて除外してください。"}</span>
      <ExclusionForm initial={proposed(item.reason)} disabled={disabled} onSubmit={reason => onExclude([item.entry], reason)} button="除外"/>
    </li>)}
  </>;
}

function ExclusionForm({label, initial, disabled, onSubmit, button}: {label?: string; initial: string; disabled: boolean; onSubmit: (reason: string) => void; button: string}) {
  const [reason, setReason] = useState(initial);
  const form = <form onSubmit={event => {event.preventDefault(); onSubmit(reason);}}>
    <input aria-label={label ? `${label}の理由` : "除外の理由"} maxLength={300} value={reason} disabled={disabled} onChange={event => setReason(event.target.value)}/>
    <button type="submit" disabled={disabled || !reason.trim()}>{button}</button>
  </form>;
  return label ? <li className={styles.unfinishedImport}><span><strong>{label}</strong></span>{form}</li> : form;
}
