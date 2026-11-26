"use client";
import {useState} from "react";
import {applySuggestions, mergeSuggestions, planSuggestions, suggestAssignments, type FieldPaths, type Suggestion} from "@/lib/workspace/assignment-suggestions";
import {assignFields, type ExperimentDesign} from "@/lib/workspace/experiment-design";
import styles from "./experiment-setup.module.css";

interface Props {
  design: ExperimentDesign;
  fields: Array<FieldPaths & {preview?: string; channels: string[]}>;
  locked: boolean;
  onSave: (design: ExperimentDesign) => Promise<unknown>;
  onOpenField: (id: string) => void;
  /** Suggestions from an AI answer (#284 W7); for a listed field they replace the rule's and are marked 「AI」. */
  aiSuggestions?: readonly Suggestion[];
}

/**
 * 「群・実験回が未割り当ての視野」 as a table (#284 W6): one row per field (thumbnail, name, channels), its suggested run
 * and group, and a choice for the rows the researcher selects. Suggestions come from fixed rules (folders, or the only
 * run and group of a one-screen design) and are saved only by 「案を適用」; nothing places several fields in one
 * group without the researcher choosing it.
 */
export function UnassignedFields({design, fields, locked, onSave, onOpenField, aiSuggestions = []}: Props) {
  const [chosen, setChosen] = useState<Set<string>>(new Set()), [target, setTarget] = useState(""), [control, setControl] = useState("");
  const suggestions = mergeSuggestions(suggestAssignments(design, fields), aiSuggestions, fields.map(field => field.id));
  const byField = new Map(suggestions.map(value => [value.fieldId, value]));
  const runs = design.runs ?? [];
  // What applying would change besides placing fields: stated before it is applied, and the control is never guessed.
  const plan = planSuggestions(design, suggestions, control), named = new Set([...design.groups.map(group => group.label.trim().toLowerCase()), ...plan.renames.map(value => value.to.trim().toLowerCase())]);
  const placeable = (value: Suggestion) => named.has(value.groupLabel.trim().toLowerCase());
  const awaitingControl = !!plan.controlChoice && !plan.renames.length;
  const toggle = (id: string) => setChosen(previous => {const next = new Set(previous);if (next.has(id)) next.delete(id);else next.add(id);return next;});
  const assign = () => {const [runId, groupId] = target.split("\u0000");if (!runId || !groupId || !chosen.size) return;
    void onSave(assignFields(design, [...chosen], {run_id: runId, group_id: groupId})).then(() => {setChosen(new Set());setTarget("");});};
  return <section className={styles.unassigned} aria-label="群・実験回が未割り当ての視野">
    <h2>群・実験回が未割り当ての視野</h2>
    <div className={styles.unassignedActions}>
      {plan.controlChoice && <label className={styles.inline}>案の対照の群<select aria-label="案の対照の群" disabled={locked} value={control} onChange={event => setControl(event.target.value)}>
        <option value="">未選択</option>
        {plan.controlChoice.map(label => <option key={label} value={label}>{label}</option>)}
      </select></label>}
      {suggestions.length > 0 && <button type="button" disabled={locked || awaitingControl || !suggestions.some(placeable)} onClick={() => void onSave(applySuggestions(design, suggestions, control).design).then(() => setControl(""))}>案を適用</button>}
      <label className={styles.inline}>割付先<select aria-label="選択した視野の割付先" disabled={locked || !runs.length} value={target} onChange={event => setTarget(event.target.value)}>
        <option value="">未選択</option>
        {runs.flatMap(run => design.groups.map(group => <option key={`${run.id}:${group.id}`} value={`${run.id}\u0000${group.id}`}>{run.label} · {group.label}</option>))}
      </select></label>
      <button type="button" disabled={locked || !chosen.size || !target} onClick={assign}>選択した視野を割付（{chosen.size}）</button>
    </div>
    {(plan.renames.length > 0 || plan.unplaced.length > 0 || awaitingControl) && <p role="status" className={styles.unassignedPlan}>
      {[awaitingControl ? "案の適用には、対照の群の指定が必要です。" : "",
        plan.renames.length ? `群の名前の変更：${plan.renames.map(value => `${value.from} → ${value.to}`).join("、")}` : "",
        !awaitingControl && plan.unplaced.length ? `実験デザインにない群：${plan.unplaced.join("、")}` : ""].filter(Boolean).join(" ")}
    </p>}
    <table className={styles.unassignedTable}>
      <thead><tr><th scope="col"><span className={styles.hidden}>選択</span></th><th scope="col"><span className={styles.hidden}>縮小画像</span></th><th scope="col">視野</th><th scope="col">チャンネル</th><th scope="col">案（実験回 · 群）</th></tr></thead>
      <tbody>{fields.map(field => {const suggestion = byField.get(field.id);return <tr key={field.id}>
        <td><input type="checkbox" aria-label={`${field.label} を選択`} checked={chosen.has(field.id)} disabled={locked} onChange={() => toggle(field.id)}/></td>
        <td>{field.preview ? <img src={field.preview} alt=""/> : <span aria-hidden="true"/>}</td>
        <th scope="row"><button type="button" className={styles.link} onClick={() => onOpenField(field.id)}>{field.label}</button></th>
        <td>{field.channels.join(" · ") || "—"}</td>
        <td>{suggestion ? <>{suggestion.source === "ai" && <small className={styles.suggestionSource}>AI</small>}{suggestion.runLabel} · {suggestion.groupLabel}</> : "案なし"}</td>
      </tr>;})}</tbody>
    </table>
  </section>;
}
