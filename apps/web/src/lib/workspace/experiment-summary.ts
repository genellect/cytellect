import {isStratified,readiness,type ExperimentDesign,type FieldAssignment} from "./experiment-design";

/** A field as the 「実験」 view counts it: its adopted nuclei (null: not measured), whether it has a current result
 * (by default, whether its nuclei are measured) and whether it is excluded. */
export interface SummaryField {id:string;nuclei?:number|null;measured?:boolean;excluded?:boolean}
export interface StatusChip {key:string;label:string;value:string;ok:boolean}
/** The experiment's own numbers, from the nuclei to the runs (n is the number of runs that can be analysed). */
export interface SummaryCounts {nuclei:number|null;fields:number;runs:number}
/** The runs of the design: those that count in n, and what each of the others lacks (項目：値). */
export interface AnalysedRuns {counted:string[];declared:number;lacking:Array<{runId:string;label:string;value:string}>}

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

const measuredField=(field:SummaryField)=>field.measured??typeof field.nuclei==="number";

/** n: a run counts only when every group has an included, measured field in it, and in a stratified design every
 * group within the same stratum (strata are never pooled). A run that is declared but not counted is listed with
 * what it lacks: a group with no included field (「なし」), a group whose fields are not measured (「未測定」), or
 * groups that are only in different strata (「同じ層の対なし」). */
export function analysedRuns(design:ExperimentDesign, fields:SummaryField[]):AnalysedRuns {
  const assignments:Record<string,FieldAssignment>=design.fields??{},stratified=isStratified(design);
  const included=fields.filter(field=>field.id in assignments&&!field.excluded);
  const counted:string[]=[],lacking:AnalysedRuns["lacking"]=[];
  for(const run of design.runs??[]){
    const inRun=included.filter(field=>assignments[field.id].run_id===run.id);
    const usable=inRun.filter(measuredField);
    // The strata (or the one plain set) in which every group has a usable field of this run.
    const keys=new Set(usable.map(field=>stratified?assignments[field.id].stratum_id??null:"all").filter((key):key is string=>key!==null));
    const complete=design.groups.length>0&&[...keys].some(key=>design.groups.every(group=>usable.some(field=>
      assignments[field.id].group_id===group.id&&(stratified?assignments[field.id].stratum_id===key:true))));
    if(complete){counted.push(run.id);continue;}
    const states=design.groups.map(group=>{
      const placed=inRun.filter(field=>assignments[field.id].group_id===group.id);
      return {label:group.label,state:!placed.length?"なし":!placed.some(measuredField)?"未測定":""};
    }).filter(item=>item.state);
    const value=!states.length?(design.layout==="pair"?"同じ層の対なし":"層なし")
      :states.length===design.groups.length&&states.every(item=>item.state==="なし")?"画像なし"
      :states.length===design.groups.length&&states.every(item=>item.state==="未測定")?"未測定"
      :states.map(item=>`${item.label} ${item.state}`).join("・");
    lacking.push({runId:run.id,label:run.label,value});
  }
  return {counted,declared:(design.runs??[]).length,lacking};
}

/** The state of the design as 項目：値, each complete (✓) or missing or limiting (▲). 実験回 is n, out of the declared
 * runs when some do not count, followed by one chip for each run that does not count. Independence is shown only for
 * two groups: one group is described, never tested. */
export function statusChips(design:ExperimentDesign, fields:SummaryField[]):StatusChip[] {
  const ids=fields.map(field=>field.id),codes=new Set(readiness(design,ids).map(issue=>issue.code));
  const assigned=ids.filter(id=>id in (design.fields??{})).length;
  const runs=analysedRuns(design,fields),n=runs.counted.length;
  const chips:StatusChip[]=[
    {key:"runs",label:"実験回",value:n===runs.declared?String(n):`${n} / ${runs.declared}`,ok:n>0&&n===runs.declared},
    ...runs.lacking.map(run=>({key:`run:${run.runId}`,label:run.label,value:run.value,ok:false})),
    {key:"groups",label:"群",value:String(design.groups.length),ok:!codes.has("experiment_design_control_required")},
    // Every field placed (and, in a stratified design, given its stratum), with no placement of an unknown field.
    {key:"fields",label:"視野",value:`${assigned} / ${ids.length}`,ok:ids.length>0&&assigned===ids.length
      &&!codes.has("experiment_design_unstratified_fields")&&!codes.has("experiment_design_unknown_fields")},
  ];
  if(design.layout==="pair")chips.push(design.independence_confirmed
    ?{key:"independence",label:"独立性",value:"確認済み",ok:true}
    :{key:"independence",label:"独立性",value:"未確認 → 検定なし",ok:false});
  return chips;
}

/** Nuclei → fields → runs for the fields placed in the design and not excluded. The nuclei are counted only when
 * every one of those fields is measured, so a partial count is never shown as the experiment's. n is the runs that
 * can be analysed (analysedRuns), the same n as the status chip and the table heading. */
export function summaryCounts(design:ExperimentDesign, fields:SummaryField[]):SummaryCounts {
  const assignments=design.fields??{};
  const placed=fields.filter(field=>field.id in assignments&&!field.excluded);
  const measured=placed.length>0&&placed.every(field=>typeof field.nuclei==="number");
  return {nuclei:measured?placed.reduce((sum,field)=>sum+(field.nuclei as number),0):null,fields:placed.length,runs:analysedRuns(design,fields).counted.length};
}
