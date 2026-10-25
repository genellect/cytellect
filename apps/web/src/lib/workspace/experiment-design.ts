import type {components} from "../generated";

/** Experiment design 1.0.0 (docs/methods.md, "Experiment design 1.0.0"). Mirrors
 * cytellect_analysis.experiment_design; tests/test_experiment_design.py holds the same cases. */
export type ExperimentDesign = components["schemas"]["ExperimentDesign"];
export type ExperimentGroup = components["schemas"]["ExperimentGroup"];
export type ExperimentRun = components["schemas"]["ExperimentRun"];
export type FieldAssignment = components["schemas"]["FieldAssignment"];
export interface DerivedMetadata {condition:string;experimental_unit:string;sample:string;acquisition_date:string|null;pair:string|null;repeat_length:null}
export type ReadinessIssue =
  | {code:"experiment_design_unassigned_fields"|"experiment_design_unknown_fields"|"experiment_design_acquisition_dates_missing";field_ids:string[]}
  | {code:"experiment_design_no_runs"|"experiment_design_control_required"|"experiment_design_independence_unconfirmed"}
  | {code:"experiment_design_missing_combination";run_id:string;group_ids:string[]};

export const SEPARATOR = " · ";
export const LABEL_LIMIT = 24;

/** The reason a label is refused, or null; the API applies the same rule. */
export function labelProblem(value:string):string|null {
  if (!value.trim()) return "名前を入力してください。";
  if (value !== value.trim()) return "前後の空白を除いてください。";
  if ([...value].length > LABEL_LIMIT) return `${LABEL_LIMIT} 文字以内にしてください。`;
  if ([...value].some(char => char.charCodeAt(0) < 32) || value.includes(SEPARATOR.trim())) return "「·」と制御文字は使えません。";
  return null;
}

export function fieldMetadata(design:ExperimentDesign):Record<string,DerivedMetadata> {
  const groups = new Map(design.groups.map(group => [group.id, group]));
  const runs = new Map((design.runs ?? []).map(run => [run.id, run]));
  const derived:Record<string,DerivedMetadata> = {};
  for (const [fieldId, assignment] of Object.entries(design.fields ?? {}).sort(([a],[b]) => a < b ? -1 : a > b ? 1 : 0)) {
    const group = groups.get(assignment.group_id), run = runs.get(assignment.run_id);
    if (!group || !run) continue;
    const unit = `${run.label}${SEPARATOR}${group.label}`;
    derived[fieldId] = {condition:group.label, experimental_unit:unit,
      sample:assignment.sample ? `${run.label}${SEPARATOR}${assignment.sample}` : unit,
      acquisition_date:assignment.acquired_on ?? run.acquired_on ?? null,
      pair:design.layout === "pair" ? run.label : null, repeat_length:null};
  }
  return derived;
}

export function readiness(design:ExperimentDesign, registeredFieldIds:string[]):ReadinessIssue[] {
  const registered = new Set(registeredFieldIds), assigned = design.fields ?? {}, runs = design.runs ?? [];
  const issues:ReadinessIssue[] = [];
  const unassigned = [...registered].filter(id => !(id in assigned)).sort();
  if (unassigned.length) issues.push({code:"experiment_design_unassigned_fields", field_ids:unassigned});
  const unknown = Object.keys(assigned).filter(id => !registered.has(id)).sort();
  if (unknown.length) issues.push({code:"experiment_design_unknown_fields", field_ids:unknown});
  if (!runs.length) issues.push({code:"experiment_design_no_runs"});
  if (design.layout === "pair" && !design.control_group_id) issues.push({code:"experiment_design_control_required"});
  const present = new Set(Object.entries(assigned).filter(([id]) => registered.has(id)).map(([, value]) => `${value.run_id}\u0000${value.group_id}`));
  for (const run of runs) {
    const missing = design.groups.filter(group => !present.has(`${run.id}\u0000${group.id}`)).map(group => group.id);
    if (missing.length) issues.push({code:"experiment_design_missing_combination", run_id:run.id, group_ids:missing});
  }
  const runsById = new Map(runs.map(run => [run.id, run]));
  const undated = Object.entries(assigned).filter(([id, value]) => registered.has(id) && !(value.acquired_on || runsById.get(value.run_id)?.acquired_on)).map(([id]) => id).sort();
  // Intensities need actual acquisition dates (S10); areas and counts do not.
  if (undated.length) issues.push({code:"experiment_design_acquisition_dates_missing", field_ids:undated});
  if (!design.independence_confirmed) issues.push({code:"experiment_design_independence_unconfirmed"});
  return issues;
}

/** Paired by run with contrast [treatment, control]: the reported effect is treatment − control. */
export function comparisonDefaults(design:ExperimentDesign) {
  if (design.layout !== "pair" || !design.control_group_id) throw new Error("experiment_design_control_required");
  const control = design.groups.find(group => group.id === design.control_group_id)!;
  const treatment = design.groups.find(group => group.id !== design.control_group_id)!;
  return {conditions:[control.label, treatment.label], control:control.label, treatment:treatment.label,
    contrasts:[[treatment.label, control.label]], design:"paired" as const,
    pairing_basis:"control and treatment from the same independent experimental run"};
}

/** A stable identifier for a new group or run; it never encodes meaning beyond the label. */
export function newId(label:string, taken:Iterable<string>):string {
  const used = new Set(taken), base = label.replace(/[^A-Za-z0-9_-]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 60) || "item";
  let candidate = base, index = 2;
  while (used.has(candidate)) candidate = `${base}-${index++}`;
  return candidate;
}

export function emptyDesign(layout:"single"|"pair"):ExperimentDesign {
  return {version:"1.0.0", layout, groups:layout === "single" ? [{id:"group-1", label:"群 1"}] : [{id:"group-1", label:"対照"}, {id:"group-2", label:"処理"}],
    control_group_id:layout === "pair" ? "group-1" : null, runs:[], independence_confirmed:false, fields:{}};
}

/** Adds an independent run; its label defaults to the date it was performed. */
export function addRun(design:ExperimentDesign, run:{label:string;performed_on?:string|null;acquired_on?:string|null}):ExperimentDesign {
  const runs = design.runs ?? [];
  return {...design, runs:[...runs, {id:newId(run.label, runs.map(value => value.id)), label:run.label,
    performed_on:run.performed_on ?? null, acquired_on:run.acquired_on ?? null}]};
}

export function updateRun(design:ExperimentDesign, runId:string, patch:Partial<Omit<ExperimentRun,"id">>):ExperimentDesign {
  return {...design, runs:(design.runs ?? []).map(run => run.id === runId ? {...run, ...patch} : run)};
}

/** Removes a run only when no field is assigned to it. */
export function removeRun(design:ExperimentDesign, runId:string):ExperimentDesign {
  if (Object.values(design.fields ?? {}).some(value => value.run_id === runId)) throw new Error("experiment_design_run_in_use");
  return {...design, runs:(design.runs ?? []).filter(run => run.id !== runId)};
}

export function renameGroup(design:ExperimentDesign, groupId:string, label:string):ExperimentDesign {
  return {...design, groups:design.groups.map(group => group.id === groupId ? {...group, label} : group)};
}

export function assignFields(design:ExperimentDesign, fieldIds:string[], target:{group_id:string;run_id:string;sample?:string|null}):ExperimentDesign {
  const fields = {...(design.fields ?? {})};
  for (const id of fieldIds) fields[id] = {group_id:target.group_id, run_id:target.run_id, sample:target.sample || null, acquired_on:fields[id]?.acquired_on ?? null};
  return {...design, fields};
}

export function unassignField(design:ExperimentDesign, fieldId:string):ExperimentDesign {
  const fields = {...(design.fields ?? {})};
  delete fields[fieldId];
  return {...design, fields};
}

/** One group becomes the control of a two-group comparison; inputs and assignments are kept (E-07). */
export function expandToPair(design:ExperimentDesign, label = "処理"):ExperimentDesign {
  if (design.layout === "pair") return design;
  const control = design.groups[0];
  return {...design, layout:"pair", control_group_id:control.id,
    groups:[control, {id:newId(label, [control.id]), label}]};
}

export function fieldsIn(design:ExperimentDesign, groupId:string, runId:string):Array<[string, FieldAssignment]> {
  return Object.entries(design.fields ?? {}).filter(([, value]) => value.group_id === groupId && value.run_id === runId);
}

/** Plain-language text for a readiness issue (labels, not internal IDs). */
export function issueText(design:ExperimentDesign, issue:ReadinessIssue, fieldLabel:(id:string)=>string):string {
  const group = (id:string) => design.groups.find(value => value.id === id)?.label ?? id;
  const run = (id:string) => (design.runs ?? []).find(value => value.id === id)?.label ?? id;
  switch (issue.code) {
    case "experiment_design_unassigned_fields": return `群と実験回が決まっていない視野があります（${issue.field_ids.map(fieldLabel).join("、")}）。`;
    case "experiment_design_unknown_fields": return "登録されていない視野が割り当てに残っています。";
    case "experiment_design_no_runs": return "実験回（実験日）を追加してください。";
    case "experiment_design_control_required": return "どちらの群を対照にするか選んでください。";
    case "experiment_design_missing_combination": return `${run(issue.run_id)} に ${issue.group_ids.map(group).join("、")} の画像がありません。この回は対にできません。`;
    case "experiment_design_acquisition_dates_missing": return `撮影日が入っていない視野があります（${issue.field_ids.map(fieldLabel).join("、")}）。輝度を比べるには撮影日が必要です（面積や数には不要）。`;
    case "experiment_design_independence_unconfirmed": return "実験回が独立に行われたこと（別々に播種・処理・染色したこと）を確認すると、群間比較の検定に進めます。";
  }
}
