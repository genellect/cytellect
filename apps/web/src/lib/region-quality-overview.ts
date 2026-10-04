import type {RegionRevision} from "./region-types";
import type {RegionFieldTraceTarget,RegionTraceTarget} from "./region-trace";

export type QualityIssue={regionId:number;excluded:boolean;exclusionReasons:string[];value:number|boolean;target:RegionTraceTarget};
export type QualityDiagnostic={status:"measured"|"unknown"|"not_measured"|"no_regions";reason:string|null;includedCount:number|null;excludedCount:number|null;items:QualityIssue[]};
export type RegionQualityChannel={channelId:string;label:string;stain:string|null;target:RegionFieldTraceTarget;storageLimit:QualityDiagnostic;acquisitionSaturation:QualityDiagnostic};
export type RegionQualityField={
 fieldId:string;outcome:"measured"|"no_regions"|"failed"|"excluded_failed";
 regionCount:number|null;includedRegionCount:number|null;excludedRegionCount:number|null;
 exclusionReasons:string[];failureReason:string|null;calibration:"known"|"unknown"|null;
 border:QualityDiagnostic|null;channels:RegionQualityChannel[];target:RegionFieldTraceTarget|null;
 excludedRegions:{regionId:number;reasons:string[];target:RegionTraceTarget}[];
};
export type RegionQualityOverview=
 |{ok:true;revisionId:string;mode:"area_and_intensity"|"area_only";fields:RegionQualityField[]}
 |{ok:false;reason:"saved_region_quality_inconsistent"};

type Row=Record<string,unknown>;
class InvalidQuality extends Error {}
function requireValue(value:unknown):asserts value {if(!value)throw new InvalidQuality();}
function record(value:unknown):Row {requireValue(value!==null&&typeof value==="object"&&!Array.isArray(value));return value as Row;}
function rows(value:unknown):Row[]{requireValue(Array.isArray(value));return value.map(record);}
function text(value:unknown):string {requireValue(typeof value==="string"&&!!value.trim()&&![...value].some(char=>char.charCodeAt(0)<32));return value;}
function id(value:unknown):string {const result=text(value);requireValue(/^[A-Za-z0-9_-]{1,80}$/.test(result));return result;}
function digest(value:unknown):string {const result=text(value);requireValue(/^[a-f0-9]{64}$/.test(result));return result;}
function finite(value:unknown):number {requireValue(typeof value==="number"&&Number.isFinite(value));return value;}
function positiveInt(value:unknown):number {const result=finite(value);requireValue(Number.isSafeInteger(result)&&result>0);return result;}
function fraction(value:unknown):number {const result=finite(value);requireValue(result>=0&&result<=1);return result;}
function shape(value:unknown):number[]{requireValue(Array.isArray(value)&&value.length===2);const result=value.map(positiveInt);requireValue(result.every(size=>size<=4096));return result;}
function equal(a:unknown,b:unknown):boolean {
 if(a===b)return true;
 if(Array.isArray(a)&&Array.isArray(b))return a.length===b.length&&a.every((v,i)=>equal(v,b[i]));
 if(a===null||b===null||typeof a!=="object"||typeof b!=="object"||Array.isArray(a)||Array.isArray(b))return false;
 const av=a as Row,bv=b as Row,keys=Object.keys(av);return keys.length===Object.keys(bv).length&&keys.every(k=>Object.hasOwn(bv,k)&&equal(av[k],bv[k]));
}
function sameKeys(actual:Row,expected:string[]){requireValue(Object.keys(actual).length===expected.length&&expected.every(key=>Object.hasOwn(actual,key)));}
function policy(value:unknown):boolean {if(value===undefined||value===null)return false;requireValue(equal(value,{version:"1.0.0",mode:"area_only"}));return true;}
function unique<T>(map:Map<string,T>,key:string,value:T){requireValue(!map.has(key));map.set(key,value);}
function emptyDiagnostic(status:QualityDiagnostic["status"],reason:string|null=null):QualityDiagnostic {
 return {status,reason,includedCount:status==="no_regions"?0:null,excludedCount:status==="no_regions"?0:null,items:[]};
}
function measured(items:QualityIssue[]):QualityDiagnostic {
 return {status:"measured",reason:null,includedCount:items.filter(item=>!item.excluded).length,excludedCount:items.filter(item=>item.excluded).length,items};
}

/** Saved flags/counts for display only. No measurements, inferential n, approval or exclusion is created. */
export function regionQualityOverview(report:unknown,revision:Pick<RegionRevision,"id"|"config">):RegionQualityOverview {
 try{return build(record(report),revision);}catch(error){if(!(error instanceof InvalidQuality))throw error;return {ok:false,reason:"saved_region_quality_inconsistent"};}
}

function build(report:Row,revision:Pick<RegionRevision,"id"|"config">):Extract<RegionQualityOverview,{ok:true}> {
 const revisionId=id(revision.id),config=record(revision.config),recipe=record(report.recipe);
 requireValue(report.analysis_kind==="region-2d"&&report.revision_id===revisionId&&equal(recipe,config.recipe));
 const areaOnly=policy(config.measurement);
 requireValue(report.protocol_version===(areaOnly?"2.0.0":"1.0.0"));
 if(areaOnly)requireValue(policy(report.measurement));else requireValue(!Object.hasOwn(report,"measurement"));
 requireValue(recipe.id==="region-2d"&&["manual","imported","stardist_nuclear"].includes(text(recipe.source)));
 requireValue(recipe.version===(recipe.source==="stardist_nuclear"?"1.1.0":"1.0.0"));
 id(recipe.region_set_id);text(recipe.label);
 requireValue(recipe.defining_channel_id===null||typeof recipe.defining_channel_id==="string");
 const fields=config.field_ids;requireValue(Array.isArray(fields)&&fields.length>0&&fields.length<=100);
 const order=fields.map(id);requireValue(new Set(order).size===order.length);
 const outcomes=record(report.field_outcomes),tables=record(report.field_tables),masks=record(report.field_masks);
 sameKeys(outcomes,order);
 requireValue(Object.keys(tables).every(fid=>order.includes(fid))&&Object.keys(masks).every(fid=>order.includes(fid)));
 const failures=new Map<string,string>(),excludedFailures=new Map<string,{reason:string;error:string}>();
 for(const failure of rows(report.field_failures)){const code=text(failure.reason);requireValue(/^[a-z0-9_]+$/.test(code));unique(failures,id(failure.field_id),code);}
 for(const failure of rows(report.excluded_failed_fields)){const code=text(failure.error);requireValue(/^[a-z0-9_]+$/.test(code));unique(excludedFailures,id(failure.field_id),{reason:text(failure.reason),error:code});}
 requireValue([...failures.keys(),...excludedFailures.keys()].every(fid=>order.includes(fid)));
 const exclusions=rows(report.exclusions);requireValue(equal(exclusions,config.exclusions));
 const exclusionKeys=new Set<string>();
 for(const exclusion of exclusions){
  const fid=id(exclusion.field_id);requireValue(order.includes(fid));text(exclusion.reason);
  if(exclusion.region_id!==null)positiveInt(exclusion.region_id);
  const key=JSON.stringify([fid,exclusion.region_id]);requireValue(!exclusionKeys.has(key));exclusionKeys.add(key);
 }
 const result=order.map(fieldId=>{
  const outcome=outcomes[fieldId],fieldExclusions=exclusions.filter(item=>item.field_id===fieldId);
  const fieldReasons=fieldExclusions.filter(item=>item.region_id===null).map(item=>text(item.reason));
  requireValue(["measured","no_regions","failed","excluded_failed"].includes(String(outcome)));
  if(outcome==="failed"||outcome==="excluded_failed"){
   requireValue(!Object.hasOwn(tables,fieldId));
   const failure=excludedFailures.get(fieldId);
   requireValue(outcome==="failed"?failures.has(fieldId)&&!failure:!!failure&&!failures.has(fieldId)&&fieldReasons.includes(failure.reason));
   // A mask may survive a measurement failure; it does not prove any measured objects.
   return {fieldId,outcome,regionCount:null,includedRegionCount:null,excludedRegionCount:null,exclusionReasons:fieldReasons,
    failureReason:outcome==="failed"?failures.get(fieldId)!:failure!.error,calibration:null,border:null,channels:[],target:null,excludedRegions:[]} satisfies RegionQualityField;
  }
  requireValue(!failures.has(fieldId)&&!excludedFailures.has(fieldId));
  return tableField(record(tables[fieldId]),record(masks[fieldId]),fieldId,outcome as "measured"|"no_regions",recipe,revisionId,areaOnly,fieldExclusions,config);
 });
 return {ok:true,revisionId,mode:areaOnly?"area_only":"area_and_intensity",fields:result};
}

function tableField(table:Row,mask:Row,fieldId:string,outcome:"measured"|"no_regions",recipe:Row,revisionId:string,areaOnly:boolean,exclusions:Row[],config:Row):RegionQualityField {
 const region=record(table.region_set),dimensions=shape(table.shape_yx);
 requireValue(table.protocol_version===(areaOnly?"2.0.0":"1.0.0")&&table.status===outcome&&table.field_id===fieldId&&table.analysis_revision_id===revisionId);
 if(areaOnly)requireValue(policy(table.measurement));else requireValue(!Object.hasOwn(table,"measurement"));
 requireValue(table.hash_format==="cytellect-array-v1"&&equal(shape(mask.shape),dimensions));
 const maskRevisionId=id(region.mask_revision_id),maskSha256=digest(table.mask_sha256);
 requireValue(mask.mask_revision_id===maskRevisionId&&mask.mask_sha256===maskSha256&&mask.region_set_id===recipe.region_set_id&&mask.source===recipe.source);
 requireValue(region.region_set_id===recipe.region_set_id&&region.label===recipe.label&&region.source===recipe.source&&region.defining_channel_id===recipe.defining_channel_id);
 if(table.calibration!==null){const calibration=record(table.calibration);requireValue(calibration.confirmed===true&&finite(calibration.pixel_size_x_um)>0&&finite(calibration.pixel_size_y_um)>0);}
 const provenance=rows(table.channel_provenance);requireValue(provenance.length>=1&&provenance.length<=3);
 const channels=provenance.map(item=>{
  const channel=record(item.channel);id(channel.channel_id);text(channel.label);
  requireValue(channel.identity_confirmed===true&&(channel.stain===null||typeof channel.stain==="string"));if(channel.stain!==null)text(channel.stain);
  requireValue(item.dtype==="uint8"||item.dtype==="uint16");digest(item.pixel_sha256);
  const maximum=item.dtype==="uint8"?255:65535;requireValue(item.storage_maximum===maximum);
  if(channel.acquisition_saturation_value===null)requireValue(channel.acquisition_saturation_confirmed===false);
  else requireValue(channel.acquisition_saturation_confirmed===true&&positiveInt(channel.acquisition_saturation_value)<=maximum);
  if(areaOnly)requireValue(equal(item.background,{status:"not_measured",reason:"not_required_for_area"}));
  else {digest(item.background_mask_sha256);id(item.background_revision_id);positiveInt(item.background_pixel_count);finite(item.background_median);}
  return channel;
 });
 const channelIds=channels.map(channel=>id(channel.channel_id));requireValue(new Set(channelIds.map(cid=>cid.toLowerCase())).size===channels.length);
 requireValue(recipe.defining_channel_id===null||channelIds.includes(String(recipe.defining_channel_id)));
 // Actual API snapshots include immutable image metadata; compare it when present.
 if(config.field_snapshot!==undefined){const snapshot=record(record(config.field_snapshot)[fieldId]);if(snapshot.image_info!==undefined){const info=record(snapshot.image_info);requireValue(equal(info.shape,dimensions)&&equal(info.calibration,table.calibration)&&equal(info.channels,channels));}}
 const base:RegionFieldTraceTarget={revisionId,fieldId,regionSetId:id(region.region_set_id),maskRevisionId,maskSha256,maskSource:text(region.source),shape:dimensions,
  channelId:null,channelLabel:null,channelStain:null,regionLabel:text(region.label)};
 const observations=rows(table.rows),objects=new Map<number,Map<string,Row>>();
 requireValue((observations.length>0)===(outcome==="measured"));
 for(const row of observations){
  const regionId=positiveInt(row.region_id),channelId=id(row.channel_id),area=positiveInt(row.area_px);
  requireValue(row.field_id===fieldId&&row.analysis_revision_id===revisionId&&row.region_set_id===region.region_set_id&&row.mask_revision_id===maskRevisionId&&channelIds.includes(channelId));
  requireValue(area<=dimensions[0]*dimensions[1]&&typeof row.touches_border==="boolean");
  if(table.calibration===null)requireValue(row.area_um2===null&&row.area_missing_reason==="calibration_unknown");
  else requireValue(finite(row.area_um2)>0&&row.area_missing_reason===null);
  const channel=channels[channelIds.indexOf(channelId)];
  if(areaOnly){
   for(const metric of ["mean","median","integrated","mean_corrected","median_corrected","integrated_corrected","storage_limit_fraction","acquisition_saturation_fraction"])requireValue(row[metric]===null);
   requireValue(row.intensity_missing_reason==="not_requested"&&row.storage_limit_missing_reason==="not_requested"&&row.acquisition_saturation_missing_reason==="not_requested");
  }else{
   for(const metric of ["mean","median","integrated","mean_corrected","median_corrected","integrated_corrected"])finite(row[metric]);
   fraction(row.storage_limit_fraction);
   if(channel.acquisition_saturation_value===null)requireValue(row.acquisition_saturation_fraction===null&&row.acquisition_saturation_missing_reason==="acquisition_limit_unknown");
   else {fraction(row.acquisition_saturation_fraction);requireValue(row.acquisition_saturation_missing_reason===null);}
  }
  const group=objects.get(regionId)||new Map<string,Row>();requireValue(!group.has(channelId));group.set(channelId,row);objects.set(regionId,group);
 }
 for(const group of objects.values()){
  requireValue(group.size===channels.length);const reference=group.values().next().value!;
  requireValue([...group.values()].every(row=>["area_px","area_um2","area_missing_reason","touches_border"].every(key=>row[key]===reference[key])));
 }
 requireValue(exclusions.every(exclusion=>exclusion.region_id===null||objects.has(Number(exclusion.region_id))));
 // At most one field exclusion and one region exclusion apply. Keep their saved
 // order without rescanning a potentially large exclusion ledger per object.
 const exclusionLookup=new Map(exclusions.map((item,index)=>[item.region_id,{index,reason:text(item.reason)}]));
 const reasons=(regionId:number)=>[exclusionLookup.get(null),exclusionLookup.get(regionId)]
  .filter(item=>item!==undefined).toSorted((a,b)=>a.index-b.index).map(item=>item.reason);
 const target=(channel:Row|null):RegionFieldTraceTarget=>channel?{...base,channelId:id(channel.channel_id),channelLabel:text(channel.label),channelStain:channel.stain as string|null}:{...base};
 const issue=(row:Row,value:number|boolean,channel:Row|null):QualityIssue=>{
  const regionId=positiveInt(row.region_id),exclusionReasons=reasons(regionId);
  return {regionId,excluded:exclusionReasons.length>0,exclusionReasons,value,target:{...target(channel),regionId,observationId:JSON.stringify([fieldId,region.region_set_id,regionId])}};
 };
 const borderItems=[...objects.values()].map(group=>group.values().next().value!).filter(row=>row.touches_border).map(row=>issue(row,true,null));
 const outputChannels=channels.map(channel=>{
  const channelId=id(channel.channel_id),channelRows=observations.filter(row=>row.channel_id===channelId);
  const diagnostic=(metric:"storage_limit_fraction"|"acquisition_saturation_fraction")=>{
   if(areaOnly)return emptyDiagnostic("not_measured","not_requested");
   if(metric==="acquisition_saturation_fraction"&&channel.acquisition_saturation_value===null)return emptyDiagnostic("unknown","acquisition_limit_unknown");
   if(outcome==="no_regions")return emptyDiagnostic("no_regions","no_regions");
   return measured(channelRows.filter(row=>Number(row[metric])>0).map(row=>issue(row,finite(row[metric]),channel)));
  };
  return {channelId,label:text(channel.label),stain:channel.stain as string|null,target:target(areaOnly?null:channel),storageLimit:diagnostic("storage_limit_fraction"),acquisitionSaturation:diagnostic("acquisition_saturation_fraction")};
 });
 const excludedRegions=[...objects.values()].map(group=>group.values().next().value!).filter(row=>reasons(Number(row.region_id)).length>0).map(row=>{
  const item=issue(row,true,null);return {regionId:item.regionId,reasons:item.exclusionReasons,target:item.target};
 });
 const excludedCount=excludedRegions.length;
 return {fieldId,outcome,regionCount:objects.size,includedRegionCount:objects.size-excludedCount,excludedRegionCount:excludedCount,
  exclusionReasons:exclusions.filter(item=>item.region_id===null).map(item=>text(item.reason)),failureReason:null,calibration:table.calibration===null?"unknown":"known",
  border:outcome==="no_regions"?emptyDiagnostic("no_regions","no_regions"):measured(borderItems),channels:outputChannels,target:base,excludedRegions};
}
