"use client";
import {useState} from "react";
import {applySuggestions, suggestAssignments, type FieldPaths} from "@/lib/workspace/assignment-suggestions";
import {assignFields, type ExperimentDesign} from "@/lib/workspace/experiment-design";
import styles from "./experiment-setup.module.css";

interface Props {
  design: ExperimentDesign;
  fields: Array<FieldPaths & {preview?: string; channels: string[]}>;
  locked: boolean;
  onSave: (design: ExperimentDesign) => Promise<unknown>;
  onOpenField: (id: string) => void;
}

/**
 * 「群・実験回が未割り当ての視野」 as a table (#284 W6): one row per field (thumbnail, name, channels), its suggested run
 * and group, and a choice for the rows the researcher selects. Suggestions come from fixed rules (folders, or the only
 * run and group of a one-screen design) and are saved only by 「案を適用」; nothing places several fields in one
 * group without the researcher choosing it.
 */
export function UnassignedFields({design, fields, locked, onSave, onOpenField}: Props) {
  const [chosen, setChosen] = useState<Set<string>>(new Set()), [target, setTarget] = useState("");
  const suggestions = suggestAssignments(design, fields), byField = new Map(suggestions.map(value => [value.fieldId, value]));
  const runs = design.runs ?? [];
  const toggle = (id: string) => setChosen(previous => {const next = new Set(previous);if (next.has(id)) next.delete(id);else next.add(id);return next;});
  const assign = () => {const [runId, groupId] = target.split("\u0000");if (!runId || !groupId || !chosen.size) return;
    void onSave(assignFields(design, [...chosen], {run_id: runId, group_id: groupId})).then(() => {setChosen(new Set());setTarget("");});};
  return <section className={styles.unassigned} aria-label="群・実験回が未割り当ての視野">
    <h2>群・実験回が未割り当ての視野</h2>
    <div className={styles.unassignedActions}>
      {suggestions.length > 0 && <button type="button" disabled={locked} onClick={() => void onSave(applySuggestions(design, suggestions).design)}>案を適用</button>}
      <label className={styles.inline}>割付先<select aria-label="選択した視野の割付先" disabled={locked || !runs.length} value={target} onChange={event => setTarget(event.target.value)}>
        <option value="">未選択</option>
        {runs.flatMap(run => design.groups.map(group => <option key={`${run.id}:${group.id}`} value={`${run.id}\u0000${group.id}`}>{run.label} · {group.label}</option>))}
      </select></label>
      <button type="button" disabled={locked || !chosen.size || !target} onClick={assign}>選択した視野を割付（{chosen.size}）</button>
    </div>
    <table className={styles.unassignedTable}>
      <thead><tr><th scope="col"><span className={styles.hidden}>選択</span></th><th scope="col"><span className={styles.hidden}>縮小画像</span></th><th scope="col">視野</th><th scope="col">チャンネル</th><th scope="col">案（実験回 · 群）</th></tr></thead>
      <tbody>{fields.map(field => {const suggestion = byField.get(field.id);return <tr key={field.id}>
        <td><input type="checkbox" aria-label={`${field.label} を選択`} checked={chosen.has(field.id)} disabled={locked} onChange={() => toggle(field.id)}/></td>
        <td>{field.preview ? <img src={field.preview} alt=""/> : <span aria-hidden="true"/>}</td>
        <th scope="row"><button type="button" className={styles.link} onClick={() => onOpenField(field.id)}>{field.label}</button></th>
        <td>{field.channels.join(" · ") || "—"}</td>
        <td>{suggestion ? `${suggestion.runLabel} · ${suggestion.groupLabel}` : "案なし"}</td>
      </tr>;})}</tbody>
    </table>
  </section>;
}
