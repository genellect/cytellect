import {useRef} from "react";
import type {IntakeOutcome, IntakeRow} from "@/lib/workspace/use-workspace-runtime";
import {intakeReason, namesText} from "@/lib/workspace/intake-record";
import styles from "./connected-workspace.module.css";

interface Props {
  /** Saved rows of images that did not become a field: they stay named after a restart. */
  rows: IntakeRow[];
  /** The last addition: conflicts, copies and files that are not images (no saved row; gone after a reload). */
  outcome: IntakeOutcome | null;
  disabled: boolean;
  onReplace: (entry: string, files: File[]) => void;
  onCancel: (entry: string) => void;
  onSeparate: (id: string) => void;
  onChoose: () => void;
}

/**
 * The 取込 list (#284 W1): each image that was not registered, why, and what can be done about it. The app records
 * why; the researcher is never asked for a reason, and a row never blocks the comparison (decision 2). A row is
 * replaced by choosing all of its files again (the refusal does not name the file), or removed with 記録から削除.
 */
export function UnfinishedImports({rows, outcome, disabled, onReplace, onCancel, onSeparate, onChoose}: Props) {
  const input = useRef<HTMLInputElement>(null), replacing = useRef<string | null>(null);
  const replace = (entry: string) => {replacing.current = entry; input.current?.click();};
  const unrecorded = outcome?.rejected.filter(item => !item.entry) ?? [];
  return <>
    {rows.map(row => <li key={row.entry} className={styles.unfinishedImport}>
      <span>{row.state === "legacy" ? <>名前の記録なし：{intakeReason(null)}</> : <><strong>{namesText(row.names)}</strong>：{intakeReason(row.state === "pending" ? null : row.code, row.mask)}</>}</span>
      <span className={styles.intakeActions}>
        {row.state !== "legacy" && !row.mask && <button type="button" disabled={disabled} onClick={() => replace(row.entry)}>差し替え</button>}
        <button type="button" disabled={disabled} onClick={() => onCancel(row.entry)}>記録から削除</button>
      </span>
    </li>)}
    {outcome?.held.map(item => <li key={item.names.join()} className={styles.unfinishedImport}>
      <span><strong>{namesText(item.names)}</strong>：要確認 · 同じ視野・チャンネルに 2 枚</span>
      <span className={styles.intakeActions}><button type="button" disabled={disabled} onClick={onChoose}>画像を再選択</button></span>
    </li>)}
    {outcome?.duplicates.map(item => <li key={item.id} className={styles.unfinishedImport}>
      <span><strong>{item.name}</strong>：同一内容 · {item.sameAs}</span>
      <span className={styles.intakeActions}><button type="button" disabled={disabled} onClick={() => onSeparate(item.id)}>別の撮影として追加</button></span>
    </li>)}
    {unrecorded.map(item => <li key={item.names.join()}><strong>{namesText(item.names)}</strong>：{intakeReason(item.code)}</li>)}
    {outcome?.skipped.map(item => <li key={item.name}><strong>{item.name}</strong>：対象外 · TIFF 以外</li>)}
    <input hidden type="file" multiple accept=".tif,.tiff" ref={input} data-testid="replace-input" onChange={event => {
      const entry = replacing.current, files = Array.from(event.target.files ?? []);replacing.current = null;event.target.value = "";
      if (entry && files.length) onReplace(entry, files);
    }}/>
  </>;
}
