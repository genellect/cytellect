import type {DescriptiveResult} from "./descriptive-view";
import type {RegionField,RegionMasks} from "./region-types";

export type RegionTraceTarget={
 revisionId:string;fieldId:string;regionSetId:string;regionId:number;maskRevisionId:string;
 maskSha256:string;maskSource:string;shape:number[];channelId:string|null;
 channelLabel:string|null;channelStain:string|null;regionLabel:string;observationId:string;
};
export type RegionFieldTraceTarget=Omit<RegionTraceTarget,"regionId"|"observationId">;
export type RegionTraceRow={observationId:string;fieldId:string;regionId:number|null;value:number|null;target:RegionTraceTarget|null};

// Only identities and saved values are read here; measurement arithmetic belongs to the API.
export function regionTraceRows(result:DescriptiveResult):RegionTraceRow[]{
 const selection=result.spec.selection;
 if(selection.source!=="region")return [];
 return (result.plot_data||[]).map((row,index)=>{
  const fieldId=typeof row.field_id==="string"?row.field_id:"";
  const regionId=Number.isInteger(row.region_id)&&Number(row.region_id)>0?Number(row.region_id):null;
  const value=typeof row.value==="number"&&Number.isFinite(row.value)?row.value:null;
  const observationId=typeof row.observation_id==="string"?row.observation_id:`unavailable-${index}`;
  const source=result.source_fields.find(field=>field.field_id===fieldId);
  const channel=source?.channel_provenance?.find(item=>item.channel.channel_id===selection.channel_id)?.channel;
  const shape=source?.image_info?.shape;
  const valid=regionId!==null&&value!==null&&source?.analysis_revision_id===result.revision_id&&
   row.analysis_revision_id===result.revision_id&&row.region_set_id===selection.region_set_id&&
   source?.region_set?.region_set_id===selection.region_set_id&&
   typeof row.mask_revision_id==="string"&&row.mask_revision_id===source?.region_set?.mask_revision_id&&
   source?.hash_format==="cytellect-array-v1"&&/^[a-f0-9]{64}$/.test(source?.mask_sha256||"")&&
   typeof source?.region_set?.source==="string"&&shape?.length===2&&shape.every(size=>Number.isInteger(size)&&size>0)&&
   row.channel_id===selection.channel_id&&(selection.channel_id===null||!!channel)&&
   row.observation_id===JSON.stringify([fieldId,selection.region_set_id,regionId]);
  return {observationId,fieldId,regionId,value,target:valid?{
   revisionId:result.revision_id,fieldId,regionSetId:selection.region_set_id,regionId:regionId!,
   maskRevisionId:row.mask_revision_id as string,maskSha256:source!.mask_sha256!,maskSource:source!.region_set!.source!,shape:shape!,
   channelId:selection.channel_id,channelLabel:channel?.label??null,channelStain:channel?.stain??null,
   regionLabel:source!.region_set!.label,observationId,
  }:null};
 });
}

export function traceDisplayChannel(target:RegionFieldTraceTarget,field:RegionField,currentChannelId:string){
 const channels=field.image_info.channels;
 if(target.channelId!==null){
  const channel=channels.find(item=>item.channel_id===target.channelId);
  if(!channel||channel.label!==target.channelLabel||channel.stain!==target.channelStain)return null;
  return channel;
 }
 return channels.find(item=>item.channel_id===currentChannelId)||channels[0]||null;
}

export function regionFieldTraceMismatch(target:RegionFieldTraceTarget,field:RegionField,masks:RegionMasks):string|null{
 const metadata=masks.metadata;
 if(target.shape.length!==2||field.image_info.shape.length!==2||metadata.shape.length!==2||
  field.id!==target.fieldId||field.image_info.shape.some((size,index)=>size!==target.shape[index])||
  metadata.region_set_id!==target.regionSetId||metadata.mask_revision_id!==target.maskRevisionId||
  metadata.mask_sha256!==target.maskSha256||metadata.source!==target.maskSource||
  metadata.shape.some((size,index)=>size!==target.shape[index]))
  return "保存済みの図と領域の出典が一致しません。図の履歴から選び直してください。";
 return null;
}

export function regionTraceMismatch(target:RegionTraceTarget,field:RegionField,masks:RegionMasks):string|null{
 const mismatch=regionFieldTraceMismatch(target,field,masks);if(mismatch)return mismatch;
 if(!masks.regions.some(region=>region.id===target.regionId))return "この図に記録された領域を確認できません。別の測定値を選ぶか、図の履歴を確認してください。";
 return null;
}
