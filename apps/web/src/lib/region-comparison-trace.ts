import type {RegionComparisonTraceInput} from "./region-comparison-view";
import type {RegionFieldTraceTarget} from "./region-trace";

type FieldStatus="selected"|"excluded"|"out_of_scope"|"no_regions"|"no_selected_values";
type ObservationStatus="selected"|"excluded"|"missing"|"out_of_scope";
export type ComparisonFieldNode={
 key:string;fieldId:string;fieldNumber:number;condition:string;experimentalUnit:string|null;sample:string|null;pair:string|null;
 status:FieldStatus;value:number|null;inputObservations:number|null;selectedObservations:number|null;
 excludedObservations:number|null;missingObservations:number|null;exclusionReason:string|null;failureReason:string|null;
 observationNotes:{observationId:string;status:ObservationStatus;reason:string|null}[];target:RegionFieldTraceTarget|null;
};
export type ComparisonSampleNode={key:string;condition:string;experimentalUnit:string;sample:string;value:number|null;fields:ComparisonFieldNode[]};
export type ComparisonUnitNode={
 key:string;condition:string;experimentalUnit:string;pair:string|null;status:"selected"|"excluded";
 value:number|null;selectedObservations:number;samples:ComparisonSampleNode[];
};
export type ComparisonPairNode={key:string;pair:string;status:"selected"|"excluded";units:ComparisonUnitNode[]};
export type RegionComparisonHierarchy=
 |{ok:true;revisionId:string;sourceFingerprint:string;design:"independent"|"paired";units:ComparisonUnitNode[];pairs:ComparisonPairNode[];outOfScopeFields:ComparisonFieldNode[]}
 |{ok:false;reason:"saved_comparison_hierarchy_inconsistent"};

type Row=Record<string,unknown>;
class InvalidTrace extends Error {}
function requireValue(condition:unknown):asserts condition {if(!condition)throw new InvalidTrace();}
function record(value:unknown):Row {requireValue(value!==null&&typeof value==="object"&&!Array.isArray(value));return value as Row;}
function rows(value:unknown):Row[] {requireValue(Array.isArray(value));return value.map(record);}
function text(value:unknown):string {requireValue(typeof value==="string"&&value.trim().length>0);return value;}
function nullableText(value:unknown):string|null {return value===null?null:text(value);}
function finite(value:unknown):number {requireValue(typeof value==="number"&&Number.isFinite(value));return value;}
function count(value:unknown):number {requireValue(Number.isSafeInteger(value)&&Number(value)>=0);return value as number;}
const key=(...parts:unknown[])=>JSON.stringify(parts);
function identifiers(value:unknown):string[]{requireValue(Array.isArray(value));const result=value.map(text);requireValue(new Set(result).size===result.length);return result;}
function sameMembers(a:string[],b:string[]){return a.length===b.length&&a.every(item=>b.includes(item));}
function unique(map:Map<string,Row>,id:string,row:Row){requireValue(!map.has(id));map.set(id,row);}
const fieldIdentity=(row:Row)=>key(text(row.condition),text(row.experimental_unit),text(row.sample),text(row.field_id));
const sampleIdentity=(row:Row)=>key(text(row.condition),text(row.experimental_unit),text(row.sample));
const unitIdentity=(row:Row)=>key(text(row.condition),text(row.experimental_unit));

// This is identity validation and presentation only. No means, medians, counts,
// confidence intervals or statistical inclusion decisions are computed here.
export function regionComparisonHierarchy(result:RegionComparisonTraceInput):RegionComparisonHierarchy {
 try{return buildHierarchy(result);}catch(error){if(!(error instanceof InvalidTrace))throw error;return {ok:false,reason:"saved_comparison_hierarchy_inconsistent"};}
}

function sourceTarget(result:RegionComparisonTraceInput,field:Row,source:Row|undefined,observations:Row[]):RegionFieldTraceTarget|null {
 try{
  if(!source)return null;
  const selection=result.spec.selection;
  const channelId=selection.channel_id;
  requireValue(channelId===null||(typeof channelId==="string"&&channelId.trim().length>0));
  const region=record(source.region_set),info=record(source.image_info),metadata=record(source.metadata);
  const shape=info.shape;
  requireValue(Array.isArray(shape)&&shape.length===2&&shape.every(size=>Number.isSafeInteger(size)&&size>0));
  requireValue(source.analysis_revision_id===result.revision_id&&source.field_id===field.field_id&&
   region.region_set_id===selection.region_set_id&&region.label===result.region.label&&
   result.region.region_set_id===selection.region_set_id&&source.hash_format==="cytellect-array-v1");
  requireValue(["condition","sample","experimental_unit","pair","acquisition_date"].every(name=>metadata[name]===field[name]));
  const maskRevisionId=text(region.mask_revision_id),maskSha256=text(source.mask_sha256),maskSource=text(region.source);
  requireValue(/^[a-f0-9]{64}$/.test(maskSha256)&&["manual","imported","stardist_nuclear"].includes(maskSource));
  requireValue(observations.every(row=>row.mask_revision_id===maskRevisionId));
  const channels=rows(source.channel_provenance).map(item=>record(item.channel));
  requireValue(new Set(channels.map(channel=>text(channel.channel_id))).size===channels.length);
  let channelLabel:string|null=null,channelStain:string|null=null;
  if(channelId!==null){
   const channel=channels.find(item=>item.channel_id===channelId);
   requireValue(channel&&channel.identity_confirmed===true);
   channelLabel=text(channel.label);channelStain=nullableText(channel.stain);
   requireValue(result.channel!==null);
   requireValue(result.channel.channel_id===channelId&&result.channel.label===channelLabel&&result.channel.stain===channelStain);
   const imageChannels=rows(info.channels).filter(item=>item.channel_id===channelId);
   requireValue(imageChannels.length===1&&imageChannels[0].identity_confirmed===true&&imageChannels[0].label===channelLabel&&imageChannels[0].stain===channelStain);
  }else requireValue(result.channel===null);
  return {revisionId:result.revision_id,fieldId:text(field.field_id),regionSetId:selection.region_set_id,
   maskRevisionId,maskSha256,maskSource,shape:[...shape] as number[],channelId,
   channelLabel,channelStain,regionLabel:text(region.label)};
 }catch(error){if(!(error instanceof InvalidTrace))throw error;return null;}
}

function buildHierarchy(result:RegionComparisonTraceInput):Extract<RegionComparisonHierarchy,{ok:true}> {
 const revisionId=text(result.revision_id),sourceFingerprint=text(result.source_fingerprint);
 requireValue(/^[a-f0-9]{64}$/.test(sourceFingerprint));
 const spec=record(result.spec),selection=record(spec.selection),design=record(spec.design).kind;
 requireValue(design==="independent"||design==="paired");
 requireValue(selection.source==="region"&&selection.metric===result.metric);
 text(selection.region_set_id);
 requireValue(typeof result.metric==="string"&&(result.metric.startsWith("area_")?selection.channel_id===null:typeof selection.channel_id==="string"));
 if(selection.channel_id!==null)text(selection.channel_id);
 const conditions=identifiers(spec.conditions);requireValue(conditions.length>=2);
 const fields=new Map<string,ComparisonFieldNode>(),fieldRows=new Map<string,Row>(),samples=new Map<string,ComparisonSampleNode>();
 const fieldSummaries=new Map<string,Row>(),sampleSummaries=new Map<string,Row>(),unitSummaries=new Map<string,Row>();
 const sources=new Map<string,Row>(),failures=new Map<string,Row>(),observations=new Map<string,Row[]>();
 for(const row of rows(result.source_fields))unique(sources,text(row.field_id),row);
 for(const row of rows(result.excluded_failed_fields)){text(row.reason);text(row.error);unique(failures,text(row.field_id),row);}
 for(const row of rows(result.field_summary)){finite(row.value);unique(fieldSummaries,fieldIdentity(row),row);}
 for(const row of rows(result.sample_summary)){finite(row.value);unique(sampleSummaries,sampleIdentity(row),row);}
 for(const row of rows(result.unit_summary)){finite(row.value);unique(unitSummaries,unitIdentity(row),row);}
 const sampleUnits=new Map<string,string>();
 rows(result.source_field_ledger).forEach((row,index)=>{
  const fieldId=text(row.field_id),condition=text(row.condition),sample=nullableText(row.sample),experimentalUnit=nullableText(row.experimental_unit),pair=nullableText(row.pair);
  unique(fieldRows,fieldId,row);
  requireValue(typeof row.in_scope==="boolean"&&row.in_scope===conditions.includes(condition)&&typeof row.explicitly_excluded==="boolean");
  const status=row.status as FieldStatus;
  requireValue(["selected","excluded","out_of_scope","no_regions","no_selected_values"].includes(status));
  requireValue(row.in_scope?status!=="out_of_scope":status==="out_of_scope");
  requireValue(!row.in_scope||(row.explicitly_excluded?status==="excluded":status!=="excluded"));
  const exclusionReason=nullableText(row.exclusion_reason);
  requireValue(row.explicitly_excluded?exclusionReason!==null:exclusionReason===null);
  const counts={inputObservations:count(row.input_observations),selectedObservations:count(row.selected_observations),
   excludedObservations:count(row.excluded_observations),missingObservations:count(row.missing_observations)};
  requireValue(status==="selected"?counts.selectedObservations>0:counts.selectedObservations===0);
  if(status==="no_regions")requireValue(counts.inputObservations===0);
  const failed=failures.get(fieldId);
  if(failed)requireValue(row.explicitly_excluded&&failed.reason===exclusionReason);
  const identity=key(condition,experimentalUnit,sample,fieldId),summary=fieldSummaries.get(identity);
  requireValue((status==="selected")===!!summary);
  const node:ComparisonFieldNode={key:identity,fieldId,fieldNumber:index+1,condition,experimentalUnit,sample,pair,status,
   value:summary?finite(summary.value):null,...(failed?{inputObservations:null,selectedObservations:null,excludedObservations:null,missingObservations:null}:counts),
   exclusionReason,failureReason:failed?text(failed.error):null,observationNotes:[],target:null};
  fields.set(fieldId,node);if(summary)fieldSummaries.delete(identity);
  if(row.in_scope){
   requireValue(sample!==null&&experimentalUnit!==null&&(design!=="paired"||pair!==null));
   const sampleKey=key(condition,experimentalUnit,sample),conditionSample=key(condition,sample);
   requireValue(!sampleUnits.has(conditionSample)||sampleUnits.get(conditionSample)===experimentalUnit);sampleUnits.set(conditionSample,experimentalUnit);
   const sampleNode=samples.get(sampleKey)||{key:sampleKey,condition,experimentalUnit,sample,value:null,fields:[]};
   sampleNode.fields.push(node);samples.set(sampleKey,sampleNode);
  }
 });
 requireValue(fields.size>0&&fieldSummaries.size===0);
 requireValue([...sources.keys(),...failures.keys()].every(id=>fields.has(id)));
 for(const id of failures.keys())requireValue(!sources.has(id));
 const allObservations=new Map<string,Row>();
 for(const row of rows(result.observation_ledger)){
  const fieldId=text(row.field_id),field=fieldRows.get(fieldId),id=text(row.observation_id);
  requireValue(field&&!failures.has(fieldId));unique(allObservations,id,row);
  requireValue(Number.isSafeInteger(row.region_id)&&Number(row.region_id)>0&&id===key(fieldId,selection.region_set_id,row.region_id));
  requireValue(row.analysis_revision_id===revisionId&&row.region_set_id===selection.region_set_id&&row.channel_id===selection.channel_id);
  text(row.mask_revision_id);
  requireValue(["condition","sample","experimental_unit","pair","acquisition_date"].every(name=>row[name]===field[name]));
  requireValue(["selected","excluded","missing","out_of_scope"].includes(text(row.selection_status)));
  requireValue(row.value===null||(typeof row.value==="number"&&Number.isFinite(row.value)));
  requireValue(typeof row.excluded==="boolean");
  requireValue(row.excluded?nullableText(row.exclusion_reason)!==null:row.exclusion_reason===null);
  requireValue(!field.explicitly_excluded||row.excluded);
  if(row.selection_status==="out_of_scope")requireValue(!field.in_scope);
  else {requireValue(field.in_scope);if(row.selection_status==="excluded")requireValue(row.excluded);else requireValue(!row.excluded);}
  if(row.selection_status==="selected")requireValue(row.value!==null);
  if(row.selection_status==="missing")requireValue(row.value===null);
  const entries=observations.get(fieldId)||[];entries.push(row);observations.set(fieldId,entries);
 }
 const missing=new Map<string,Row>();
 for(const row of rows(result.missingness)){
  const id=text(row.observation_id),observation=allObservations.get(id);
  requireValue(observation?.selection_status==="missing"&&row.field_id===observation.field_id);text(row.reason);unique(missing,id,row);
 }
 for(const [id,row] of allObservations){
  if(row.selection_status==="missing")requireValue(missing.has(id));
  if(row.selection_status!=="selected")fields.get(text(row.field_id))!.observationNotes.push({
   observationId:id,status:row.selection_status as ObservationStatus,
   reason:row.selection_status==="missing"?text(missing.get(id)!.reason):nullableText(row.exclusion_reason??row.missing_reason??null),
  });
 }
 for(const [id,node] of fields){
  const entries=observations.get(id)||[];
  requireValue(node.status!=="selected"||entries.some(row=>row.selection_status==="selected"));
  node.target=failures.has(id)?null:sourceTarget(result,fieldRows.get(id)!,sources.get(id),entries);
 }
 for(const [id,node] of samples){
  const summary=sampleSummaries.get(id),hasValues=node.fields.some(field=>field.value!==null);
  requireValue(hasValues===!!summary);if(summary){node.value=finite(summary.value);sampleSummaries.delete(id);}
 }
 requireValue(sampleSummaries.size===0);
 const units:ComparisonUnitNode[]=[],unitMap=new Map<string,ComparisonUnitNode>(),sharedUnits=new Map<string,string>();
 for(const row of rows(result.unit_ledger)){
  const condition=text(row.condition),experimentalUnit=text(row.experimental_unit),identity=unitIdentity(row),pair=nullableText(row.pair);
  requireValue(conditions.includes(condition)&&!unitMap.has(identity)&&(row.status==="selected"||row.status==="excluded"));
  requireValue(design==="paired"?pair!==null:pair===null);
  const sharedIdentity=design==="paired"?pair!:condition;
  requireValue(!sharedUnits.has(experimentalUnit)||sharedUnits.get(experimentalUnit)===sharedIdentity);sharedUnits.set(experimentalUnit,sharedIdentity);
  const memberSamples=[...samples.values()].filter(sample=>sample.condition===condition&&sample.experimentalUnit===experimentalUnit);
  requireValue(memberSamples.length>0);
  const memberFields=memberSamples.flatMap(sample=>sample.fields);
  requireValue(sameMembers(identifiers(row.field_ids),memberFields.map(field=>field.fieldId)));
  requireValue(sameMembers(identifiers(row.excluded_fields),memberFields.filter(field=>field.exclusionReason!==null).map(field=>field.fieldId)));
  if(design==="paired")requireValue(memberFields.every(field=>field.pair===pair));
  const summary=unitSummaries.get(identity),selectedObservations=count(row.selected_observations);
  requireValue((row.status==="selected")===!!summary&&(row.status==="selected"?selectedObservations>0:selectedObservations===0));
  requireValue((row.status==="selected")===memberSamples.some(sample=>sample.value!==null));
  if(row.status==="excluded")requireValue(memberFields.every(field=>field.exclusionReason!==null));
  if(summary)requireValue(design==="paired"?summary.pair===pair:summary.pair===undefined||summary.pair===null);
  const node:ComparisonUnitNode={key:identity,condition,experimentalUnit,pair,status:row.status,value:summary?finite(summary.value):null,selectedObservations,samples:memberSamples};
  units.push(node);unitMap.set(identity,node);if(summary)unitSummaries.delete(identity);
 }
 requireValue(unitSummaries.size===0&&units.length>0&&conditions.every(condition=>units.some(unit=>unit.condition===condition)));
 requireValue([...samples.values()].every(sample=>unitMap.has(key(sample.condition,sample.experimentalUnit))));
 const pairs:ComparisonPairNode[]=[],pairIds=new Set<string>(),pairedUnits=new Set<string>();
 for(const row of rows(result.pair_ledger)){
  requireValue(design==="paired");const pair=text(row.pair),mapping=record(row.units);
  requireValue(!pairIds.has(pair)&&sameMembers(Object.keys(mapping),conditions));pairIds.add(pair);
  requireValue(row.status==="selected"||row.status==="excluded");
  const members=conditions.map(condition=>{
   const node=unitMap.get(key(condition,text(mapping[condition])));
   requireValue(node&&node.pair===pair&&node.status===row.status&&!pairedUnits.has(node.key));pairedUnits.add(node.key);return node;
  });
  pairs.push({key:key(pair),pair,status:row.status,units:members});
 }
 requireValue(design!=="paired"||pairedUnits.size===unitMap.size);
 return {ok:true,revisionId,sourceFingerprint,design,units,pairs,outOfScopeFields:[...fields.values()].filter(field=>field.status==="out_of_scope")};
}
