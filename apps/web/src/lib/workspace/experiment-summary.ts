import {readiness,type ExperimentDesign} from "./experiment-design";

/** A field as the 「実験」 view counts it: its adopted nuclei (null: not measured) and whether it is excluded. */
export interface SummaryField {id:string;nuclei?:number|null;excluded?:boolean}
export interface StatusChip {key:"runs"|"groups"|"fields"|"acquisition"|"independence";label:string;value:string;ok:boolean}
/** The experiment's own numbers, from the nuclei to the runs (n is the number of runs). */
export interface SummaryCounts {nuclei:number|null;fields:number;runs:number}

/** Adopted nuclei of one saved result: its regions, without the regions excluded by a correction. */
export function adoptedNuclei(result:{masks:{regions:Array<{id:number}>};exclusions?:Array<{region_id:number|null}>}):number {
  const excluded=new Set((result.exclusions??[]).flatMap(item=>item.region_id==null?[]:[item.region_id]));
  return new Set(result.masks.regions.map(region=>region.id).filter(id=>!excluded.has(id))).size;
}

/** The purpose in a few words, control first: 「2 群の比較：対照 × 処理」 or 「1 群：群」. */
export function experimentHeading(design:ExperimentDesign):string {
  if(design.layout!=="pair")return `1 群：${design.groups[0]?.label??""}`;
  const ordered=[...design.groups].sort((a,b)=>Number(b.id===design.control_group_id)-Number(a.id===design.control_group_id));
  return `2 群の比較：${ordered.map(group=>group.label).join(" × ")}`;
}

/** The state of the design as 項目：値, each complete (a check mark) or missing or limiting (a warning triangle). The acquisition statement and
 * independence are shown only for two groups: one group is described, never compared. A recorded design (the public
 * demo, `recorded`) shows the acquisition statement only when it states it: nothing is declared for public data. */
export function statusChips(design:ExperimentDesign, fields:SummaryField[], recorded=false):StatusChip[] {
  const ids=fields.map(field=>field.id),codes=new Set(readiness(design,ids).map(issue=>issue.code));
  const runs=design.runs??[],assigned=ids.filter(id=>id in (design.fields??{})).length;
  const chips:StatusChip[]=[
    {key:"runs",label:"実験回",value:String(runs.length),ok:runs.length>0&&!codes.has("experiment_design_missing_combination")},
    {key:"groups",label:"群",value:String(design.groups.length),ok:!codes.has("experiment_design_control_required")},
    // Every field placed (and, in a stratified design, given its stratum), with no placement of an unknown field.
    {key:"fields",label:"視野",value:`${assigned} / ${ids.length}`,ok:ids.length>0&&assigned===ids.length
      &&!codes.has("experiment_design_unstratified_fields")&&!codes.has("experiment_design_unknown_fields")},
  ];
  // Acquisition and pixel settings (S10, genellect/cytellect#257 decisions 11 and 13).
  if(design.layout==="pair"&&(!recorded||design.acquisition_confirmed))chips.push(design.acquisition_confirmed
    ?{key:"acquisition",label:"撮影条件",value:"確認済み",ok:true}
    :{key:"acquisition",label:"撮影条件",value:"未確認",ok:false});
  if(design.layout==="pair")chips.push(design.independence_confirmed
    ?{key:"independence",label:"独立性",value:"確認済み",ok:true}
    :{key:"independence",label:"独立性",value:"未確認 → 検定なし",ok:false});
  return chips;
}

/** Nuclei → fields → runs for the fields placed in the design and not excluded. The nuclei are counted only when
 * every one of those fields is measured, so a partial count is never shown as the experiment's. n counts only the
 * runs with values in every group (in a pair, the runs that make a pair), never the runs declared without them. */
export function summaryCounts(design:ExperimentDesign, fields:SummaryField[]):SummaryCounts {
  const assignments=design.fields??{};
  const placed=fields.filter(field=>field.id in assignments&&!field.excluded);
  const measured=placed.length>0&&placed.every(field=>typeof field.nuclei==="number");
  const present=new Set(placed.map(field=>`${assignments[field.id].run_id}\u0000${assignments[field.id].group_id}`));
  const runs=(design.runs??[]).filter(run=>design.groups.length>0&&design.groups.every(group=>present.has(`${run.id}\u0000${group.id}`))).length;
  return {nuclei:measured?placed.reduce((sum,field)=>sum+(field.nuclei as number),0):null,fields:placed.length,runs};
}
