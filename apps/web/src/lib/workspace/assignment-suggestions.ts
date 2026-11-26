/** Run and group suggestions for unassigned fields (#284 W6). A suggestion is shown, never saved, until the researcher
 * applies it; it never decides a stain or a biological role. Rules, in order:
 *  1. A folder-relative path (a folder choice or a drop) with two folders above the file: run = outer, group = inner
 *     (Rep1/未処理/… → run Rep1, group 未処理). With one folder: group = that folder, run = the design's only run.
 *  2. A design with one run and one group (1 画面): that run and group.
 *  Otherwise no suggestion: the row asks for its own choice. */
import {addRun, assignFields, labelProblem, renameGroup, updateRun, type ExperimentDesign} from "./experiment-design";

export interface FieldPaths {id: string; label: string; paths: string[]}
/** `source`: fixed rules (folders, a one-screen design) or an AI answer (#284 W7). Absent means the rules. */
export interface Suggestion {fieldId: string; runLabel: string; groupLabel: string; source?: "rules" | "ai"}

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

/** The rule suggestions with the AI's for the listed fields: the AI's replaces the rule's for the same field, since the
 * researcher asked for it. AI suggestions for other fields (already assigned, or not listed) are left out, so applying
 * never moves a field the table does not show. */
export function mergeSuggestions(rules: readonly Suggestion[], ai: readonly Suggestion[], fieldIds: readonly string[]): Suggestion[] {
  const listed = new Set(fieldIds), chosen = new Map<string, Suggestion>();
  for (const value of rules) if (listed.has(value.fieldId)) chosen.set(value.fieldId, {...value, source: "rules"});
  for (const value of ai) if (listed.has(value.fieldId) && !labelProblem(value.runLabel) && !labelProblem(value.groupLabel)) chosen.set(value.fieldId, {...value, source: "ai"});
  return fieldIds.flatMap(id => chosen.has(id) ? [chosen.get(id)!] : []);
}

/** The number of groups the suggestions name, for proposing 1 画面 or 2 画面 before a design exists. */
export function suggestedGroups(suggestions: readonly Suggestion[]): string[] {
  return [...new Set(suggestions.map(value => value.groupLabel))];
}

/** What applying the suggestions would change in the design besides placing fields. */
export interface SuggestionPlan {
  /** Groups that take a suggested name: only a group without fields that no suggestion names. */
  renames: Array<{groupId: string; from: string; to: string}>;
  /** A two-group design whose groups are both empty and unnamed by the suggestions: the researcher says which
   * suggested group is the control before anything is applied. The names, in the order suggested. */
  controlChoice: string[] | null;
  /** Suggested group names the design has no group for; their fields stay unassigned. */
  unplaced: string[];
}

/**
 * Plans the group names of an application. A group that has fields is never renamed, and neither is one a suggestion
 * names. The control is never decided by the order of folder names or of an answer: when both groups of a two-group
 * design would be named, `control` (one of the suggested names) says which becomes the control group.
 */
export function planSuggestions(design: ExperimentDesign, suggestions: readonly Suggestion[], control = ""): SuggestionPlan {
  const labels = suggestedGroups(suggestions), used = new Set(Object.values(design.fields ?? {}).map(value => value.group_id));
  const unmatched = labels.filter(label => !design.groups.some(group => same(group.label, label)));
  const free = design.groups.filter(group => !used.has(group.id) && !labels.some(label => same(group.label, label)));
  if (!unmatched.length) return {renames: [], controlChoice: null, unplaced: []};
  if (design.layout === "pair" && unmatched.length === 2 && free.length === 2) {
    const chosen = unmatched.find(label => label === control), other = unmatched.find(label => label !== control);
    if (!chosen || !other) return {renames: [], controlChoice: unmatched, unplaced: unmatched};
    const controlGroup = free.find(group => group.id === design.control_group_id) ?? free[0], treated = free.find(group => group.id !== controlGroup.id)!;
    return {renames: [{groupId: controlGroup.id, from: controlGroup.label, to: chosen}, {groupId: treated.id, from: treated.label, to: other}], controlChoice: unmatched, unplaced: []};
  }
  if (unmatched.length === 1 && free.length === 1) return {renames: [{groupId: free[0].id, from: free[0].label, to: unmatched[0]}], controlChoice: null, unplaced: []};
  return {renames: [], controlChoice: null, unplaced: unmatched};
}

/**
 * Applies suggestions as planned (`planSuggestions`): empty groups take the suggested names, the design's only, still
 * empty run takes the first run the suggestions name, other runs they name are added, and each field goes to its run
 * and group. Fields whose group the design cannot hold are left unassigned. Returns the design and the fields left.
 */
export function applySuggestions(design: ExperimentDesign, suggestions: readonly Suggestion[], control = ""): {design: ExperimentDesign; left: string[]} {
  let next = design;
  for (const rename of planSuggestions(design, suggestions, control).renames) next = renameGroup(next, rename.groupId, rename.to);
  // Only suggestions whose group exists place a field; a run is named or added only for those.
  const placeable = suggestions.filter(value => next.groups.some(group => same(group.label, value.groupLabel)));
  // The design's only run, still empty (the dated run 1 画面/2 画面 creates), takes the first run the suggestions name.
  const runLabels = [...new Set(placeable.map(value => value.runLabel))], onlyRun = next.runs?.length === 1 ? next.runs[0] : null;
  if (runLabels.length && onlyRun && !runLabels.some(label => same(onlyRun.label, label)) && !Object.values(next.fields ?? {}).some(value => value.run_id === onlyRun.id))
    next = updateRun(next, onlyRun.id, {label: runLabels[0]});
  const left: string[] = [];
  for (const suggestion of suggestions) {
    const group = next.groups.find(value => same(value.label, suggestion.groupLabel));
    if (!group) {left.push(suggestion.fieldId);continue;}
    let run = (next.runs ?? []).find(value => same(value.label, suggestion.runLabel));
    if (!run) {next = addRun(next, {label: suggestion.runLabel});run = (next.runs ?? []).find(value => same(value.label, suggestion.runLabel));}
    if (!run) {left.push(suggestion.fieldId);continue;}
    next = assignFields(next, [suggestion.fieldId], {run_id: run.id, group_id: group.id});
  }
  return {design: next, left};
}
