import type {components} from "../generated";

export type ChannelGateFilter = components["schemas"]["ChannelGateFilter"];
export type ChannelGateRequest = components["schemas"]["ChannelGateRequest"];
export type ChannelGateResult = components["schemas"]["ChannelGateResult"];
export interface GateField {fieldId:string;revisionId:string;label:string}

/** A request uses real channel IDs and saved revisions; the browser computes no scientific values. */
export function channelGateRequest(filter:ChannelGateFilter, fields:GateField[]):ChannelGateRequest {
  if(!filter.channel_id||!fields.length)throw new Error("判定するチャンネルと採用済みの核を選んでください。");
  if(filter.method==="manual"&&(filter.threshold==null||!Number.isFinite(filter.threshold)))throw new Error("平均輝度のしきい値を入力してください。");
  if(filter.method==="negative_control"&&!(filter.control_field_ids??[]).length)throw new Error("陰性対照の視野を選んでください。");
  if((filter.control_field_ids??[]).some(id=>!fields.some(field=>field.fieldId===id)))throw new Error("陰性対照の視野が現在の対象にありません。再分類してください。");
  return {filter,fields:fields.map(field=>({field_id:field.fieldId,revision_id:field.revisionId}))};
}

/** Only the server's recorded decision may be used for formal selection or positivity. */
export function recordedChannelGate(result:ChannelGateResult):ChannelGateFilter {
  const digest=result.record.decision_sha256;
  if(result.protocol!=="channel-gate/1.0.0"||typeof digest!=="string"||!/^[a-f0-9]{64}$/.test(digest))throw new Error("分類記録を確認できません。再分類してください。");
  return {...result.filter,reference_sha256:digest};
}

/** Changing inputs invalidates a classification. The returned digest itself is not an input choice. */
export function channelGateChoices(filter:ChannelGateFilter){const {reference_sha256:_,...choices}=filter;void _;return choices;}
export function channelGateInputSignature(workspace:string,target:string,sources:Array<{field:string;revision:string}>,metadata:unknown,filter:ChannelGateFilter|null){
  return JSON.stringify([workspace,target,sources.map(source=>[source.field,source.revision]),metadata,filter?channelGateChoices(filter):null]);
}
export function channelGateName(result:ChannelGateResult):string {
  const {stain,label,channel_id}=result.channel;
  return typeof stain==="string"&&stain?stain:typeof label==="string"&&label?label:String(channel_id);
}
export function channelGateThresholds(result:ChannelGateResult){
  return Object.entries(result.dates).map(([date,value])=>{
    const item=value&&typeof value==="object"?value as Record<string,unknown>:{};
    return {date:date==="all"?"全視野":date||"撮影日未設定",threshold:typeof item.threshold==="number"?item.threshold:null,
      reason:typeof item.missing_reason==="string"?item.missing_reason:null};
  });
}
