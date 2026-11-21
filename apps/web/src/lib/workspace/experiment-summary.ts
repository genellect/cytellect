import {readiness,type ExperimentDesign} from "./experiment-design";

/** A field as the 「実験」 view counts it: its adopted nuclei (null: not measured) and whether it is excluded. */
export interface SummaryField {id:string;nuclei?:number|null;excluded?:boolean}
export interface StatusChip {key:"runs"|"groups"|"fields"|"independence";label:string;value:string;ok:boolean}
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

/** The state of the design as 項目：値, each complete (✓) or missing or limiting (▲). Independence is shown
 * only for two groups: one group is described, never tested. */
export function statusChips(design:ExperimentDesign, fields:SummaryField[]):StatusChip[] {
  const ids=fields.map(field=>field.id),codes=new Set(readiness(design,ids).map(issue=>issue.code));
  const runs=design.runs??[],assigned=ids.filter(id=>id in (design.fields??{})).length;
  const chips:StatusChip[]=[
    {key:"runs",label:"実験回",value:String(runs.length),ok:runs.length>0&&!codes.has("experiment_design_missing_combination")},
    {key:"groups",label:"群",value:String(design.groups.length),ok:!codes.has("experiment_design_control_required")},
    {key:"fields",label:"視野",value:`${assigned} / ${ids.length}`,ok:ids.length>0&&assigned===ids.length},
  ];
  if(design.layout==="pair")chips.push(design.independence_confirmed
    ?{key:"independence",label:"独立性",value:"確認済み",ok:true}
    :{key:"independence",label:"独立性",value:"未確認 → 検定なし",ok:false});
  return chips;
}

/** Nuclei → fields → runs for the fields placed in the design and not excluded. The nuclei are counted only when
 * every one of those fields is measured, so a partial count is never shown as the experiment's. */
export function summaryCounts(design:ExperimentDesign, fields:SummaryField[]):SummaryCounts {
  const placed=fields.filter(field=>field.id in (design.fields??{})&&!field.excluded);
  const measured=placed.length>0&&placed.every(field=>typeof field.nuclei==="number");
  return {nuclei:measured?placed.reduce((sum,field)=>sum+(field.nuclei as number),0):null,fields:placed.length,runs:(design.runs??[]).length};
}
