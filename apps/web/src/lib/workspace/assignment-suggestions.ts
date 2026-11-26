/** Run and group suggestions for unassigned fields (#284 W6). A suggestion is shown, never saved, until the researcher
 * applies it; it never decides a stain or a biological role. Rules, in order:
 *  1. A folder-relative path (a folder choice or a drop) with two folders above the file: run = outer, group = inner
 *     (Rep1/未処理/… → run Rep1, group 未処理). With one folder: group = that folder, run = the design's only run.
 *  2. A design with one run and one group (1 画面): that run and group.
 *  Otherwise no suggestion: the row asks for its own choice. */
import {addRun, assignFields, labelProblem, renameGroup, updateRun, type ExperimentDesign} from "./experiment-design";

export interface FieldPaths {id: string; label: string; paths: string[]}
export interface Suggestion {fieldId: string; runLabel: string; groupLabel: string}

const folders = (path: string) => path.replaceAll("\\", "/").split("/").filter(Boolean).slice(0, -1);
const same = (a: string, b: string) => a.trim().toLowerCase() === b.trim().toLowerCase();

export function suggestAssignments(design: ExperimentDesign | null, fields: readonly FieldPaths[]): Suggestion[] {
  const runs = design?.runs ?? [], groups = design?.groups ?? [];
  const result: Suggestion[] = [];
  // A folder name the design cannot hold as a label (too long, a separator) gives no suggestion: it is never shortened.
  const push = (value: Suggestion) => {if (!labelProblem(value.runLabel) && !labelProblem(value.groupLabel)) result.push(value);};
  for (const field of fields) {
    const parts = field.paths.map(folders).find(value => value.length > 0);
    if (parts && parts.length >= 2) push({fieldId: field.id, runLabel: parts.at(-2)!, groupLabel: parts.at(-1)!});
    else if (parts && parts.length === 1 && runs.length === 1) push({fieldId: field.id, runLabel: runs[0].label, groupLabel: parts[0]});
    else if (runs.length === 1 && groups.length === 1) push({fieldId: field.id, runLabel: runs[0].label, groupLabel: groups[0].label});
  }
  return result;
}

/** The number of groups the suggestions name, for proposing 1 画面 or 2 画面 before a design exists. */
export function suggestedGroups(suggestions: readonly Suggestion[]): string[] {
  return [...new Set(suggestions.map(value => value.groupLabel))];
}

/**
 * Applies suggestions: the design's only, still empty run takes the name of the one run the suggestions name; other
 * runs named by a suggestion and missing from the design are added; groups are matched by name,
 * and when the suggestions name exactly as many groups as the design has and none of them matches, the design's
 * groups take the suggested names in order (the researcher still chooses the control). Fields whose group cannot be
 * placed are left unassigned. Returns the design and the fields left.
 */
export function applySuggestions(design: ExperimentDesign, suggestions: readonly Suggestion[]): {design: ExperimentDesign; left: string[]} {
  let next = design;
  const labels = suggestedGroups(suggestions);
  if (labels.length === next.groups.length && !labels.some(label => next.groups.some(group => same(group.label, label))))
    next.groups.forEach((group, index) => {next = renameGroup(next, group.id, labels[index]);});
  // The design's only run, still empty (the dated run 1 画面/2 画面 creates), takes the one run the folders name.
  const runLabels = [...new Set(suggestions.map(value => value.runLabel))], onlyRun = next.runs?.length === 1 ? next.runs[0] : null;
  if (runLabels.length === 1 && onlyRun && !same(onlyRun.label, runLabels[0]) && !Object.values(next.fields ?? {}).some(value => value.run_id === onlyRun.id))
    next = updateRun(next, onlyRun.id, {label: runLabels[0]});
  const left: string[] = [];
  for (const suggestion of suggestions) {
    let run = (next.runs ?? []).find(value => same(value.label, suggestion.runLabel));
    if (!run) {next = addRun(next, {label: suggestion.runLabel});run = (next.runs ?? []).find(value => same(value.label, suggestion.runLabel));}
    const group = next.groups.find(value => same(value.label, suggestion.groupLabel));
    if (!run || !group) {left.push(suggestion.fieldId);continue;}
    next = assignFields(next, [suggestion.fieldId], {run_id: run.id, group_id: group.id});
  }
  return {design: next, left};
}
