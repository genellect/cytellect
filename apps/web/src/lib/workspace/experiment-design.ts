import type {components} from "../generated";

/** Experiment design 1.0.0 and 1.1.0 (docs/methods.md, "Experiment design 1.0.0" and "1.1.0"). Mirrors
 * cytellect_analysis.experiment_design; tests/test_experiment_design.py and tests/test_experiment_strata.py
 * hold the same cases. 1.1.0 adds declared strata: a factor's levels, each stratum one level, and the
 * stratum each field was assigned to (never inferred). */
export type PlainExperimentDesign = components["schemas"]["ExperimentDesign"];
export type StratifiedExperimentDesign = components["schemas"]["StratifiedExperimentDesign"];
export type ExperimentDesign = PlainExperimentDesign | StratifiedExperimentDesign;
export type ExperimentGroup = components["schemas"]["ExperimentGroup"];
export type ExperimentRun = components["schemas"]["ExperimentRun"];
export type FieldAssignment = components["schemas"]["FieldAssignment"] & {stratum_id?:string|null};
export interface DerivedMetadata {condition:string;experimental_unit:string;sample:string;acquisition_date:string|null;pair:string|null;repeat_length:null}
export type ReadinessIssue =
  | {code:"experiment_design_unassigned_fields"|"experiment_design_unknown_fields"|"experiment_design_acquisition_dates_missing";field_ids:string[]}
  | {code:"experiment_design_no_runs"|"experiment_design_control_required"|"experiment_design_independence_unconfirmed"|"experiment_design_no_strata"}
  | {code:"experiment_design_missing_combination";run_id:string;group_ids:string[];stratum_id?:string}
  | {code:"experiment_design_unstratified_fields";field_ids:string[]}
  | {code:"experiment_design_empty_stratum";stratum_id:string};

export const SEPARATOR = " · ";
export const LABEL_LIMIT = 24;

/** The reason a label is refused, or null; the API applies the same rule. */
export function labelProblem(value:string):string|null {
  if (!value.trim()) return "名前を入力してください。";
  if (value !== value.trim()) return "前後の空白を除いてください。";
  // A lone surrogate (half of an emoji) cannot be saved as text.
  if (/[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]/.test(value)) return "使えない文字が含まれています。";
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
  if (isStratified(design)) {
    const unstratified = Object.entries(design.fields ?? {}).filter(([id, value]) => registered.has(id) && !value.stratum_id).map(([id]) => id).sort();
    if (!design.strata.length) issues.push({code:"experiment_design_no_strata"});
    if (unstratified.length) issues.push({code:"experiment_design_unstratified_fields", field_ids:unstratified});
    // Within each stratum, every run that appears there needs both groups (strata are never pooled).
    for (const stratum of design.strata) {
      const within = new Set(Object.entries(design.fields ?? {}).filter(([id, value]) => registered.has(id) && value.stratum_id === stratum.id).map(([, value]) => `${value.run_id}\u0000${value.group_id}`));
      if (!within.size) issues.push({code:"experiment_design_empty_stratum", stratum_id:stratum.id});
      for (const run of runs) {
        if (![...within].some(key => key.startsWith(`${run.id}\u0000`))) continue;
        const missing = design.groups.filter(group => !within.has(`${run.id}\u0000${group.id}`)).map(group => group.id);
        if (missing.length) issues.push({code:"experiment_design_missing_combination", run_id:run.id, group_ids:missing, stratum_id:stratum.id});
      }
    }
  } else {
    const present = new Set(Object.entries(assigned).filter(([id]) => registered.has(id)).map(([, value]) => `${value.run_id}\u0000${value.group_id}`));
    for (const run of runs) {
      const missing = design.groups.filter(group => !present.has(`${run.id}\u0000${group.id}`)).map(group => group.id);
      if (missing.length) issues.push({code:"experiment_design_missing_combination", run_id:run.id, group_ids:missing});
    }
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
  const fields:Record<string,FieldAssignment> = {...(design.fields ?? {})};
  for (const id of fieldIds) fields[id] = {group_id:target.group_id, run_id:target.run_id, sample:target.sample || null, acquired_on:fields[id]?.acquired_on ?? null,
    ...(isStratified(design) ? {stratum_id:fields[id]?.stratum_id ?? null} : {})};
  return {...design, fields} as ExperimentDesign;
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
    case "experiment_design_missing_combination": {
      const within = issue.stratum_id ? `層「${stratumLabel(design, issue.stratum_id)}」の ` : "";
      return design.layout === "pair"
        ? `${within}${run(issue.run_id)} に ${issue.group_ids.map(group).join("、")} の画像がありません。この回は対にできません。`
        : `${within}${run(issue.run_id)} に画像がありません。`;
    }
    case "experiment_design_unstratified_fields": return `層が決まっていない視野があります（${issue.field_ids.map(fieldLabel).join("、")}）。層を選ぶまで、どの層の比較にも入りません。`;
    case "experiment_design_no_strata": return "層がまだ宣言されていません。各因子の水準を 1 つずつ選んで層を宣言してください。";
    case "experiment_design_empty_stratum": return `層「${stratumLabel(design, issue.stratum_id)}」に視野がありません。`;
    case "experiment_design_acquisition_dates_missing": return `撮影日が入っていない視野があります（${issue.field_ids.map(fieldLabel).join("、")}）。輝度を比べるには撮影日が必要です（面積や数には不要）。`;
    case "experiment_design_independence_unconfirmed": return "実験回が独立に行われたこと（別々に播種・処理・染色したこと）を確認すると、群間比較の検定と信頼区間に進めます。確認がなくても、実験回ごとの値と差は示します。";
  }
}

/** The fields a two-group design shows first: the first run's first field of each group, control first
 * (the order PairStage opens on). Empty for other designs. */
export function openingPair(design:ExperimentDesign|null):string[]{
  if(!design||design.layout!=="pair")return [];
  const groups=[...design.groups].sort((a,b)=>Number(b.id===design.control_group_id)-Number(a.id===design.control_group_id));
  const run=(design.runs??[]).find(value=>groups.some(group=>fieldsIn(design,group.id,value.id).length));
  return run?groups.flatMap(group=>fieldsIn(design,group.id,run.id).slice(0,1).map(([id])=>id)):[];
}

/** True for a design with declared strata (1.1.0). */
export function isStratified(design:ExperimentDesign|null|undefined):design is StratifiedExperimentDesign {
  return design?.version === "1.1.0";
}

export function stratumLabel(design:ExperimentDesign, stratumId:string):string {
  return isStratified(design) ? design.strata.find(value => value.id === stratumId)?.label ?? stratumId : stratumId;
}

/** Each declared stratum with the fields the researcher assigned to it, in declaration order. */
export function strataOf(design:ExperimentDesign|null|undefined):Array<{id:string;label:string;fieldIds:string[]}> {
  if (!isStratified(design)) return [];
  return design.strata.map(stratum => ({id:stratum.id, label:stratum.label,
    fieldIds:Object.entries(design.fields ?? {}).filter(([, value]) => value.stratum_id === stratum.id).map(([id]) => id).sort()}));
}

/** Declares one factor (for example 細胞株) whose levels are each one stratum. Fields keep their group and
 * run and wait for the researcher to choose their stratum (none is guessed). */
export function declareStrata(design:ExperimentDesign, factorLabel:string, levelLabels:string[]):StratifiedExperimentDesign {
  if (isStratified(design)) throw new Error("experiment_design_already_stratified");
  const factorId = newId(factorLabel, []), levels:Array<{id:string;label:string}> = [];
  for (const label of levelLabels) levels.push({id:newId(label, levels.map(value => value.id)), label});
  if (!levels.length) throw new Error("experiment_design_stratum_levels");
  const fields = Object.fromEntries(Object.entries(design.fields ?? {}).map(([id, value]) => [id, {...value, stratum_id:null}]));
  return {...design, version:"1.1.0", factors:[{id:factorId, label:factorLabel, levels}],
    strata:levels.map(level => ({id:`stratum-${level.id}`, label:level.label, levels:{[factorId]:level.id}})), fields};
}

/** Adds one level of the (single) declared factor as a new stratum. */
export function addStratum(design:StratifiedExperimentDesign, label:string):StratifiedExperimentDesign {
  const factor = design.factors[0];
  const level = {id:newId(label, factor.levels.map(value => value.id)), label};
  return {...design, factors:[{...factor, levels:[...factor.levels, level]}, ...design.factors.slice(1)],
    strata:[...design.strata, {id:newId(`stratum-${level.id}`, design.strata.map(value => value.id)), label, levels:{[factor.id]:level.id}}]};
}

/** The researcher's choice of stratum for fields (null: not yet assigned). */
export function assignStratum(design:StratifiedExperimentDesign, fieldIds:string[], stratumId:string|null):StratifiedExperimentDesign {
  if (stratumId !== null && !design.strata.some(value => value.id === stratumId)) throw new Error("experiment_design_unknown_stratum");
  const fields = {...(design.fields ?? {})};
  for (const id of fieldIds) if (fields[id]) fields[id] = {...fields[id], stratum_id:stratumId};
  return {...design, fields};
}

/** Back to one undivided design (1.0.0): strata and the fields' strata are removed; groups and runs stay. */
export function removeStrata(design:StratifiedExperimentDesign):PlainExperimentDesign {
  const fields = Object.fromEntries(Object.entries(design.fields ?? {}).map(([id, value]) =>
    [id, {group_id:value.group_id, run_id:value.run_id, sample:value.sample ?? null, acquired_on:value.acquired_on ?? null}]));
  return {version:"1.0.0", layout:design.layout, groups:design.groups, control_group_id:design.control_group_id ?? null,
    runs:design.runs ?? [], independence_confirmed:design.independence_confirmed, fields};
}

/** The one declared stratum a cohort holds, bound to the saved design by the hash the API returned. */
export interface StratumRequest {design_version:"1.1.0";design_sha256:string;stratum_id:string}

/** The stratum request for a chosen stratum of the saved design; null when there is none to send. */
export function stratumRequestFor(design:ExperimentDesign|null|undefined, designSha256:string|null|undefined, stratumId:string):StratumRequest|null {
  if (!isStratified(design) || !designSha256 || !design.strata.some(value => value.id === stratumId)) return null;
  return {design_version:"1.1.0", design_sha256:designSha256, stratum_id:stratumId};
}

/** Binds an input identity (sources, metadata, selection or a channel gate) to the saved design and
 * stratum, so a classification, cohort or result from another design or stratum is never reused. */
export function scopedIdentity(base:string, stratum:StratumRequest|null):string {
  return stratum ? `${base}\u0000stratum\u0000${stratum.design_sha256}\u0000${stratum.stratum_id}` : base;
}

/** The key a pair pane remembers its chosen field under: the group, and for a stratified design also
 * the run and stratum, so a field chosen in one stratum never reappears beside another stratum's. */
export function paneKey(design:ExperimentDesign, runId:string, groupId:string, stratumId:string|null):string {
  return isStratified(design) ? `${runId}\u0000${stratumId ?? ""}\u0000${groupId}` : groupId;
}

export interface PairPane {groupId:string;ids:string[];fieldId:string|undefined;key:string}
/** The two panes of a two-group design for one run: control first. A stratified design shows only the
 * selected field's declared stratum (the first stratum with fields in the run when nothing there is
 * selected); a field without a stratum is shown alone and never beside another stratum's field. */
export function pairPanes(design:ExperimentDesign, runId:string|undefined, selectedField:string|undefined,
  chosen:Record<string,string>):{stratumId:string|null;unassigned:boolean;panes:PairPane[]} {
  const groups = [...design.groups].sort((a,b) => (a.id === design.control_group_id ? -1 : 0) - (b.id === design.control_group_id ? -1 : 0));
  const pick = (ids:string[], key:string) => ids.includes(selectedField ?? "") ? selectedField! : ids.includes(chosen[key]) ? chosen[key] : ids[0];
  if (!runId) return {stratumId:null, unassigned:false, panes:groups.map(group => ({groupId:group.id, ids:[], fieldId:undefined, key:group.id}))};
  if (!isStratified(design)) return {stratumId:null, unassigned:false, panes:groups.map(group => {
    const ids = fieldsIn(design, group.id, runId).map(([id]) => id), key = paneKey(design, runId, group.id, null);
    return {groupId:group.id, ids, fieldId:pick(ids, key), key};
  })};
  const selected = selectedField ? design.fields?.[selectedField] : undefined;
  const here = selected && selected.run_id === runId ? selected : undefined;
  if (here && !here.stratum_id) return {stratumId:null, unassigned:true, panes:groups.map(group => {
    const own = group.id === here.group_id;
    return {groupId:group.id, ids:own ? [selectedField!] : [], fieldId:own ? selectedField : undefined, key:paneKey(design, runId, group.id, null)};
  })};
  const stratumId = here?.stratum_id ?? design.strata.find(stratum => Object.values(design.fields ?? {}).some(value => value.run_id === runId && value.stratum_id === stratum.id))?.id ?? null;
  return {stratumId, unassigned:false, panes:groups.map(group => {
    const ids = fieldsIn(design, group.id, runId).filter(([, value]) => !!stratumId && value.stratum_id === stratumId).map(([id]) => id);
    const key = paneKey(design, runId, group.id, stratumId);
    return {groupId:group.id, ids, fieldId:pick(ids, key), key};
  })};
}

/** Fields that lose their stratum when the given strata are removed (shown before the researcher confirms). */
export function fieldsInStrata(design:StratifiedExperimentDesign, stratumIds:string[]):string[] {
  const removed = new Set(stratumIds);
  return Object.entries(design.fields ?? {}).filter(([, value]) => !!value.stratum_id && removed.has(value.stratum_id)).map(([id]) => id).sort();
}

/** Removes strata; their fields keep group and run and become unassigned (never moved to another stratum). */
export function removeStrataById(design:StratifiedExperimentDesign, stratumIds:string[]):StratifiedExperimentDesign {
  const removed = new Set(stratumIds);
  const fields = Object.fromEntries(Object.entries(design.fields ?? {}).map(([id, value]) =>
    [id, value.stratum_id && removed.has(value.stratum_id) ? {...value, stratum_id:null} : value]));
  return {...design, strata:design.strata.filter(value => !removed.has(value.id)), fields};
}

/** Adds a factor (at most three). Existing strata named one level of the earlier factors only, so they
 * are removed and their fields become unassigned; the researcher declares the new combinations. */
export function addFactor(design:StratifiedExperimentDesign, label:string, levelLabels:string[]):StratifiedExperimentDesign {
  if (design.factors.length >= 3) throw new Error("experiment_design_factor_limit");
  const levels:Array<{id:string;label:string}> = [];
  for (const level of levelLabels) levels.push({id:newId(level, levels.map(value => value.id)), label:level});
  if (!levels.length) throw new Error("experiment_design_stratum_levels");
  const cleared = removeStrataById(design, design.strata.map(value => value.id));
  return {...cleared, factors:[...design.factors, {id:newId(label, design.factors.map(value => value.id)), label, levels}]};
}

/** Removes a factor; every stratum is removed (each named a level of it). The last factor ends the strata. */
export function removeFactor(design:StratifiedExperimentDesign, factorId:string):ExperimentDesign {
  if (design.factors.length <= 1) return removeStrata(design);
  const cleared = removeStrataById(design, design.strata.map(value => value.id));
  return {...cleared, factors:design.factors.filter(value => value.id !== factorId)};
}

export function addLevel(design:StratifiedExperimentDesign, factorId:string, label:string):StratifiedExperimentDesign {
  return {...design, factors:design.factors.map(factor => factor.id !== factorId ? factor
    : {...factor, levels:[...factor.levels, {id:newId(label, factor.levels.map(value => value.id)), label}]})};
}

/** Removes a level and the strata that named it; their fields become unassigned. */
export function removeLevel(design:StratifiedExperimentDesign, factorId:string, levelId:string):StratifiedExperimentDesign {
  const factor = design.factors.find(value => value.id === factorId);
  if (!factor || factor.levels.length <= 1) throw new Error("experiment_design_stratum_levels");
  const cleared = removeStrataById(design, design.strata.filter(value => value.levels[factorId] === levelId).map(value => value.id));
  return {...cleared, factors:design.factors.map(value => value.id !== factorId ? value : {...value, levels:value.levels.filter(level => level.id !== levelId)})};
}

/** The strata a level or factor removal would remove (to warn first). */
export function strataNaming(design:StratifiedExperimentDesign, factorId:string, levelId?:string):string[] {
  return design.strata.filter(value => levelId === undefined || value.levels[factorId] === levelId).map(value => value.id);
}

/** Declares one stratum: exactly one level of every factor, a combination not declared yet. */
export function addStratumCombination(design:StratifiedExperimentDesign, levels:Record<string,string>, label:string):StratifiedExperimentDesign {
  if (design.factors.some(factor => !factor.levels.some(level => level.id === levels[factor.id])) || Object.keys(levels).length !== design.factors.length)
    throw new Error("experiment_design_stratum_levels");
  const key = (value:Record<string,string>) => design.factors.map(factor => value[factor.id]).join("\u0000");
  if (design.strata.some(value => key(value.levels) === key(levels))) throw new Error("experiment_design_duplicate");
  return {...design, strata:[...design.strata, {id:newId(`stratum-${Object.values(levels).join("-")}`, design.strata.map(value => value.id)), label,
    levels:Object.fromEntries(design.factors.map(factor => [factor.id, levels[factor.id]]))}]};
}

/** A default stratum label from its levels ("水準A / 水準X"), within the label limit (counted in characters, never splitting one). */
export function combinationLabel(design:StratifiedExperimentDesign, levels:Record<string,string>):string {
  return [...design.factors.map(factor => factor.levels.find(level => level.id === levels[factor.id])?.label ?? "").filter(Boolean).join(" / ")].slice(0, LABEL_LIMIT).join("").trim();
}

/** The limits the API enforces on declared strata (experiment_design.StratifiedExperimentDesign). */
export const FACTOR_LIMIT = 3, LEVEL_LIMIT = 12, STRATUM_LIMIT = 24;
// Close to Python's str.casefold (the API's rule): upper- then lower-casing folds ß to ss and final sigma.
const fold = (value:string) => value.trim().toUpperCase().toLowerCase();
const repeated = (values:string[]) => new Set(values.map(fold)).size !== values.length;

/** Why a factor with these levels cannot be declared or added, checked before saving (the API refuses the same). */
export function factorProblem(design:ExperimentDesign, label:string, levelLabels:string[]):string|null {
  const problem = labelProblem(label) ?? levelLabels.map(labelProblem).find(Boolean);
  if (problem) return problem;
  if (!levelLabels.length) return "水準を 1 つ以上入力してください。";
  if (levelLabels.length > LEVEL_LIMIT) return `水準は 1 つの因子につき ${LEVEL_LIMIT} 個までです。`;
  if (repeated(levelLabels)) return "同じ名前の水準が重なっています。";
  if (!isStratified(design)) return null;
  if (design.factors.length >= FACTOR_LIMIT) return `因子は ${FACTOR_LIMIT} つまでです。`;
  if (design.factors.some(factor => fold(factor.label) === fold(label))) return "同じ名前の因子がすでにあります。";
  return null;
}

/** Why a level cannot be added to a factor. With one factor the level is also a new stratum of the same name. */
export function levelProblem(design:StratifiedExperimentDesign, factorId:string, label:string):string|null {
  const problem = labelProblem(label);
  if (problem) return problem;
  const factor = design.factors.find(value => value.id === factorId);
  if (!factor) return "因子が見つかりません。";
  if (factor.levels.length >= LEVEL_LIMIT) return `水準は 1 つの因子につき ${LEVEL_LIMIT} 個までです。`;
  if (factor.levels.some(level => fold(level.label) === fold(label))) return "同じ名前の水準がすでにあります。";
  if (design.factors.length === 1 && design.strata.length >= STRATUM_LIMIT) return `層は ${STRATUM_LIMIT} 個までです。`;
  if (design.factors.length === 1 && design.strata.some(stratum => fold(stratum.label) === fold(label))) return "同じ名前の層がすでにあります。";
  return null;
}

/** Why a stratum (one level of every factor) cannot be declared. */
export function stratumProblem(design:StratifiedExperimentDesign, levels:Record<string,string>, label:string):string|null {
  const problem = labelProblem(label);
  if (problem) return problem;
  if (design.factors.some(factor => !factor.levels.some(level => level.id === levels[factor.id]))) return "それぞれの因子から水準を 1 つずつ選んでください。";
  if (design.strata.length >= STRATUM_LIMIT) return `層は ${STRATUM_LIMIT} 個までです。`;
  if (design.strata.some(stratum => fold(stratum.label) === fold(label))) return "同じ名前の層がすでにあります。";
  if (design.strata.some(stratum => design.factors.every(factor => stratum.levels[factor.id] === levels[factor.id]))) return "同じ水準の組み合わせの層がすでにあります。";
  return null;
}

/** What the plan editor shows after a save: the new plan once stored, otherwise the last stored plan and why.
 * A refused edit never stays on screen as if it were saved (fields would otherwise appear assigned differently). */
export async function savePlan(stored:ExperimentDesign|null, next:ExperimentDesign, persist:(design:ExperimentDesign)=>Promise<void>):
  Promise<{ok:boolean;stored:ExperimentDesign|null;shown:ExperimentDesign|null;error:string}> {
  try {
    await persist(next);
    return {ok:true, stored:next, shown:next, error:""};
  } catch (cause) {
    const reason = cause instanceof Error && cause.message ? cause.message : "保存できませんでした。";
    return {ok:false, stored, shown:stored, error:`${reason} 変更は保存されていないため、最後に保存した計画に戻しました。`};
  }
}
