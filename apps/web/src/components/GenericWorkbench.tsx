"use client";
import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { download, errorCodeMessage, errorMessage, post, request } from "@/lib/api";
import { formatValue, type Job, type Operation, type Point, type Session, type Workspace } from "@/lib/types";
import { regionFigureOptions, regionRecipe, type RegionConfig, type RegionField, type RegionMasks, type RegionReport, type RegionRevision } from "@/lib/region-types";
import { regionSubmission, sameRegionRecipe } from "@/lib/region-submission";
import {changeRegionMeasurement,isAreaOnly,loadedRegionConfig,measurementMode,type RegionMeasurementMode} from "@/lib/region-measurement";
import RegionUploadPanel from "./RegionUploadPanel";
import RegionBatchUploadPanel from "./RegionBatchUploadPanel";
import DescriptivePanel from "./DescriptivePanel";
import RegionComparisonPanel from "./RegionComparisonPanel";
import PlanResolutionPanel,{planChanges} from "./PlanResolutionPanel";
import {regionFieldTraceMismatch,regionTraceMismatch,traceDisplayChannel,type RegionFieldTraceTarget,type RegionTraceTarget} from "@/lib/region-trace";
import styles from "./workspace.module.css";

const FieldCanvas=dynamic(()=>import("./FieldCanvas"),{ssr:false,loading:()=> <div className={styles.canvasLoading}>画像を準備しています…</div>});
const operations:Record<Operation,string>={select:"選択",background:"背景",add:"追加",replace:"輪郭修正",delete:"削除",merge:"結合",split:"分割"};
type Props={id:string;session:Session;onBack:()=>void;onError:(message:string)=>void};

export default function GenericWorkbench({id,onBack,onError}:Props){
 const client=useQueryClient();const loaded=useRef<string|undefined>(undefined);const editor=useRef<HTMLDivElement>(null);const values=useRef<HTMLElement>(null);
 const [busy,setBusy]=useState(false);const [tab,setTab]=useState("analysis");const [fieldId,setFieldId]=useState("");const [channelId,setChannelId]=useState("");
 const [config,setConfig]=useState<RegionConfig>({recipe:{...regionRecipe},backgrounds:{},exclusions:[]});const [dirty,setDirty]=useState(false);
 const [operation,setOperation]=useState<Operation>("select");const [selected,setSelected]=useState<number[]>([]);const [polygon,setPolygon]=useState<Point[]>([]);const [coordinates,setCoordinates]=useState("");const [gain,setGain]=useState(1);const [showMasks,setShowMasks]=useState(true);
 const [pendingTrace,setPendingTrace]=useState<{target:RegionTraceTarget;channelId:string}|null>(null);const [traceError,setTraceError]=useState("");const [verifiedTrace,setVerifiedTrace]=useState<{target:RegionTraceTarget;channelId:string}|null>(null);
 const [traceTransition,setTraceTransition]=useState(false);const [traceRecovery,setTraceRecovery]=useState(false);
 const [appliedRevisionId,setAppliedRevisionId]=useState("");const [settledViewKey,setSettledViewKey]=useState("");
 const [pendingField,setPendingField]=useState<{revisionId:string;fieldId:string;source?:RegionFieldTraceTarget;channelId?:string}|null>(null);
 const [verifiedField,setVerifiedField]=useState<{target:RegionFieldTraceTarget;channelId:string}|null>(null);
 const traceGuard=useRef(false);const draftRegion=polygon.length>0||coordinates.trim().length>0;
 const [reviewed,setReviewed]=useState(false);const [exclusionReason,setExclusionReason]=useState("");const [redoBranches,setRedoBranches]=useState<Record<string,string>>({});const [includeRaw,setIncludeRaw]=useState(false);const [deleteConfirmed,setDeleteConfirmed]=useState(false);
 const [nuclearConfirmed,setNuclearConfirmed]=useState(false);const [pendingScope,setPendingScope]=useState<"add"|"batch"|"redetect"|null>(null);const methodChosen=useRef(false);
 const space=useQuery({queryKey:["workspace",id],queryFn:({signal})=>request<Workspace>(`/v1/workspaces/${id}`,{signal})});
 const fields=useQuery({queryKey:["region-fields",id],queryFn:({signal})=>request<RegionField[]>(`/v1/workspaces/${id}/region-fields`,{signal})});
 const revisions=useQuery({queryKey:["revisions",id],queryFn:({signal})=>request<RegionRevision[]>(`/v1/workspaces/${id}/revisions`,{signal})});
 const jobs=useQuery({queryKey:["jobs",id],queryFn:({signal})=>request<Job[]>(`/v1/workspaces/${id}/jobs`,{signal}),refetchInterval:query=>query.state.data?.some(job=>["queued","running"].includes(job.state))?1500:false});
 const history=(revisions.data||[]).filter(revision=>revision.config.analysis_kind==="region-2d").toSorted((a,b)=>a.created-b.created);
 const active=history.find(revision=>revision.id===space.data?.active_revision);const index=history.findIndex(revision=>revision.id===active?.id);
 const effectiveFields=(fields.data||[]).map(item=>({...item,metadata:active?.config.field_snapshot?.[item.id]?.metadata||item.metadata}));
 const fid=fieldId||fields.data?.[0]?.id||"";const field=effectiveFields.find(item=>item.id===fid);const channels=field?.image_info.channels||[];const channel=channels.find(item=>item.channel_id===channelId)||channels[0];const cid=channel?.channel_id||"";
 const viewKey=JSON.stringify([active?.id||"",fid,cid]);
 const processing=(jobs.data||[]).some(job=>["queued","running"].includes(job.state));const blocked=busy||processing||!!pendingTrace;const included=!!active?.config.field_ids?.includes(fid);
 useEffect(()=>{traceGuard.current=dirty||draftRegion||processing;},[dirty,draftRegion,processing]);
 const report=useQuery({queryKey:["region-measurements",active?.id],queryFn:()=>request<RegionReport>(`/v1/revisions/${active!.id}/region-measurements`),enabled:active?.state==="succeeded"});
 const masks=useQuery({queryKey:["region-masks",active?.id,fid],queryFn:({signal})=>request<RegionMasks>(`/v1/revisions/${active!.id}/region-masks?field_id=${encodeURIComponent(fid)}`,{signal}),enabled:active?.state==="succeeded"&&included});
 const statusKey=(jobs.data||[]).map(job=>job.id+job.state).join("|");
 useEffect(()=>{void client.invalidateQueries({queryKey:["workspace",id]});void client.invalidateQueries({queryKey:["revisions",id]});},[statusKey,client,id]);
 useEffect(()=>{if(active&&loaded.current!==active.id){loaded.current=active.id;setConfig(current=>loadedRegionConfig(active.config,current));setAppliedRevisionId(active.id);setDirty(false);setReviewed(false);setNuclearConfirmed(active.config.recipe.source==="stardist_nuclear");setPendingScope(null);if(isAreaOnly(active.config.measurement))setOperation("select");}},[active]);
 useEffect(()=>{setSelected([]);setPolygon([]);setCoordinates("");setSettledViewKey(viewKey);},[viewKey]);
 useEffect(()=>{setPolygon([]);setCoordinates("");},[operation]);
 useEffect(()=>{
  if(!pendingTrace)return;
  const {target,channelId:displayChannel}=pendingTrace;
  if(traceGuard.current){setPendingTrace(null);setTraceTransition(false);setTraceError("未保存の領域・設定があるため、画像への切り替えを中止しました。");return;}
  // Wait for query refresh and the reset/config state to commit before applying the exact selection.
  if(busy||active?.id!==target.revisionId||appliedRevisionId!==target.revisionId||settledViewKey!==viewKey||fid!==target.fieldId||cid!==displayChannel)return;
  if(masks.isError){setPendingTrace(null);setTraceTransition(false);setTraceError("領域を読み込めませんでした。図の測定値からもう一度お試しください。");return;}
  if(!masks.data||!field)return;
  const mismatch=regionTraceMismatch(target,field,masks.data);
  if(mismatch){setPendingTrace(null);setTraceTransition(false);setTraceError(mismatch);return;}
  setSelected([target.regionId]);setOperation("select");setShowMasks(true);setPendingTrace(null);setTraceTransition(false);
  setVerifiedTrace(pendingTrace);
  editor.current?.scrollIntoView({behavior:"smooth",block:"center"});
 },[pendingTrace,busy,active,appliedRevisionId,settledViewKey,viewKey,fid,cid,masks.data,masks.isError,field,channel]);
 useEffect(()=>{
  if(!pendingTrace||busy)return;
  const timeout=setTimeout(()=>{void client.cancelQueries({queryKey:["region-masks",pendingTrace.target.revisionId,pendingTrace.target.fieldId]}).then(()=>{setPendingTrace(null);setTraceTransition(false);setTraceError("保存済みの領域を開けませんでした。図の測定値からもう一度お試しください。");});},15000);
  return()=>clearTimeout(timeout);
 },[pendingTrace,busy,client]);
 useEffect(()=>{
  if(!pendingField)return;
  if(traceGuard.current){setPendingField(null);setTraceTransition(false);setTraceError("未保存の領域・設定があるため、画像への切り替えを中止しました。");return;}
  if(busy||active?.id!==pendingField.revisionId||appliedRevisionId!==pendingField.revisionId||settledViewKey!==viewKey||fid!==pendingField.fieldId)return;
  if(pendingField.source&&cid!==pendingField.channelId)return;
  if(masks.isError){setPendingField(null);setTraceTransition(false);setTraceError("保存済みの視野を読み込めませんでした。図の履歴からもう一度お試しください。");return;}
  if(!masks.data||!field)return;
  if(pendingField.source){
   const mismatch=regionFieldTraceMismatch(pendingField.source,field,masks.data);
   if(mismatch){setPendingField(null);setTraceTransition(false);setTraceError(mismatch);return;}
   setSelected([]);setOperation("select");setShowMasks(true);
   setVerifiedField({target:pendingField.source,channelId:pendingField.channelId!});
  }
  setPendingField(null);setTraceTransition(false);editor.current?.scrollIntoView({behavior:"smooth",block:"center"});
 },[pendingField,busy,active,appliedRevisionId,settledViewKey,viewKey,fid,cid,field,masks.data,masks.isError]);
 useEffect(()=>{
  if(!pendingField||busy)return;
  const timeout=setTimeout(()=>{void client.cancelQueries({queryKey:["region-masks",pendingField.revisionId,pendingField.fieldId]}).then(()=>{setPendingField(null);setTraceTransition(false);setTraceError("保存済みの視野を開けませんでした。図の履歴からもう一度お試しください。");});},15000);
  return()=>clearTimeout(timeout);
 },[pendingField,busy,client]);
 useEffect(()=>{if(!active&&!loaded.current&&!methodChosen.current&&fields.data?.[0])setConfig(current=>({...current,recipe:{...regionRecipe,label:current.recipe.label,source:fields.data[0].image_info.labels_array?"imported":"manual"}}));},[active,fields.data]);
 useEffect(()=>{const plan=space.data?.analysis_plan;if(!plan||active||methodChosen.current)return;const candidate=plan.decision.candidates.find(item=>item.id===plan.selected_candidate_id);if(candidate?.workflow!=="regions")return;methodChosen.current=true;setNuclearConfirmed(false);setConfig(current=>({...current,...(candidate.measurement?{measurement:candidate.measurement,backgrounds:{}}:{}),recipe:candidate.source==="stardist_nuclear"?{...regionRecipe,version:"1.1.0",source:"stardist_nuclear",defining_channel_id:"",nuclear_stain_confirmed:true,detector:{engine:"fiji-stardist-2d",model:"Versatile (fluorescent nuclei)",probability:.5,nms:.3,percentile_low:1,percentile_high:99.8}}:{...regionRecipe,source:candidate.source==="imported"?"imported":"manual"}}));},[space.data,active]);
 async function refresh(){await Promise.all([client.invalidateQueries({queryKey:["workspace",id]}),client.invalidateQueries({queryKey:["region-fields",id]}),client.invalidateQueries({queryKey:["revisions",id]}),client.invalidateQueries({queryKey:["jobs",id]})]);}
 async function refreshNavigation(){
  const keys=[["workspace",id],["region-fields",id],["revisions",id],["jobs",id]];
  let timer:ReturnType<typeof setTimeout>|undefined;
  try{await Promise.race([Promise.all(keys.map(queryKey=>client.invalidateQueries({queryKey},{throwOnError:true}))),new Promise<never>((_,reject)=>{timer=setTimeout(()=>reject(Error("navigation_refresh_timeout")),15000);})]);}
  catch(error){await Promise.all(keys.map(queryKey=>client.cancelQueries({queryKey})));throw error;}
  finally{if(timer)clearTimeout(timer);}
 }
 async function navigate(work:()=>Promise<void>){
  setBusy(true);setTraceRecovery(false);onError("");let pending=false;
  try{await work();pending=true;}catch(error){setPendingTrace(null);setPendingField(null);setTraceError(error instanceof Error&&!("code" in error)&&error.name!=="TimeoutError"?error.message:"保存済みの画像を開けませんでした。図の履歴からもう一度お試しください。");}
  try{await refreshNavigation();if(!pending)setTraceTransition(false);}
  catch{setPendingTrace(null);setPendingField(null);setTraceRecovery(true);setTraceError("採用中の解析版を確認できません。作業を開き直してください。");}
  finally{setBusy(false);}
 }
 async function act(work:()=>Promise<void>){setBusy(true);onError("");try{await work();await refresh();}catch(error){onError(errorMessage(error));}finally{setBusy(false);}}
 const run=(work:()=>Promise<void>)=>{void act(work);};
 function change(next:Partial<RegionConfig>){setConfig(current=>({...current,...next,...(next.recipe&&current.plan_resolution?{plan_resolution:{...current.plan_resolution,changes_acknowledged:false}}:{})}));setDirty(true);setReviewed(false);setPendingScope(null);}
 const recipeChanged=!!active&&!sameRegionRecipe(config.recipe,active.config.recipe);const nuclear=config.recipe.source==="stardist_nuclear";
 const areaOnly=isAreaOnly(config.measurement);const savedAreaOnly=isAreaOnly(active?.config.measurement);const measurementChanged=!!active&&areaOnly!==savedAreaOnly;
 const planOptions=effectiveFields.length?regionFigureOptions(config.recipe,effectiveFields,config.measurement).map(option=>({...option,metric:option.selection.metric,channel_id:option.selection.channel_id})):[];
 const planReady=!space.data?.analysis_plan||!!config.plan_resolution&&planOptions.some(option=>option.metric===config.plan_resolution?.metric&&option.channel_id===config.plan_resolution.channel_id)&&(!planChanges(space.data.analysis_plan,config.recipe,config.plan_resolution.metric,config.measurement).length||config.plan_resolution.changes_acknowledged);
 const recipeReady=!!config.recipe.label.trim()&&(!nuclear||(nuclearConfirmed&&!!config.recipe.defining_channel_id))&&planReady;
 function chooseSource(source:"manual"|"imported"|"stardist_nuclear"){
  methodChosen.current=true;setNuclearConfirmed(false);
  change({recipe:source==="stardist_nuclear"?{id:"region-2d",version:"1.1.0",region_set_id:config.recipe.region_set_id,label:config.recipe.label,source,defining_channel_id:channels[0]?.channel_id||"",nuclear_stain_confirmed:true,detector:{engine:"fiji-stardist-2d",model:"Versatile (fluorescent nuclei)",probability:.5,nms:.3,percentile_low:1,percentile_high:99.8}}:{...regionRecipe,region_set_id:config.recipe.region_set_id,label:config.recipe.label,source}});
 }
 function chooseMeasurement(mode:RegionMeasurementMode){
  if(draftRegion){onError("未保存の領域を保存するか、下書きを消してから測定する量を変更してください。");return;}
  setConfig(current=>changeRegionMeasurement(current,mode));setDirty(true);setReviewed(false);setPendingScope(null);setOperation("select");
 }
 function backgroundFor(fieldId:string,channelId:string){return config.backgrounds[fieldId]?.[channelId];}
 const missing=areaOnly?[]:(fields.data||[]).flatMap(item=>config.exclusions.some(exclusion=>exclusion.field_id===item.id&&exclusion.region_id===null)?[]:item.image_info.channels.filter(ch=>!backgroundFor(item.id,ch.channel_id)?.confirmed).map(ch=>({field:item,channel:ch})));
 const missingSelected=missing.filter(item=>item.field.id===fid);const table=report.data?.field_tables[fid];const rows=(table?.rows||[]).filter(row=>row.channel_id===cid);const regionIds=[...new Set((table?.rows||[]).map(row=>row.region_id))];
 const failures=report.data?.field_failures||[];const noRegions=report.data?.field_outcomes[fid]==="no_regions";const hasRegions=Object.values(report.data?.field_tables||{}).some(item=>item.rows.length>0);
 const availableFields=effectiveFields.filter(item=>active?.config.field_ids?.includes(item.id));const options=regionFigureOptions(active?.config.recipe||config.recipe,availableFields,active?active.config.measurement:config.measurement);
 const nextMissing=missing[0];const canEdit=active?.state==="succeeded"&&included&&!!masks.data?.metadata;
 const redo=history.find(revision=>revision.id===redoBranches[active?.id||""]&&revision.parent_id===active?.id&&revision.state==="succeeded")||history.toReversed().find(revision=>revision.parent_id===active?.id&&revision.state==="succeeded");
 const exports=(jobs.data||[]).filter(job=>job.kind==="export"&&job.state==="succeeded"&&history.some(revision=>revision.id===job.revision_id)).toSorted((a,b)=>b.created-a.created);
 function payload(fieldIds:string[]):RegionConfig{return {recipe:config.recipe,field_ids:fieldIds,backgrounds:areaOnly?{}:Object.fromEntries(fieldIds.map(fieldId=>[fieldId,config.backgrounds[fieldId]||{}])),exclusions:config.exclusions.filter(exclusion=>fieldIds.includes(exclusion.field_id)),...(config.measurement?{measurement:config.measurement}:{}),...(config.plan_resolution?{plan_resolution:config.plan_resolution}:{})};}
 const submission=(scope:"add"|"batch"|"redetect")=>regionSubmission(config,active,(fields.data||[]).map(item=>item.id),fid,scope);
 async function initialize(scope:"add"|"batch"|"redetect",confirmed=false){
  const spec=submission(scope);if(spec.confirmationRequired&&!confirmed){setPendingScope(scope);return;}
  if(!recipeReady)return;
  await post(`/v1/workspaces/${id}/region-analyses`,{...payload(spec.field_ids),reuse_revision:spec.reuse_revision});setPendingScope(null);
 }
 async function adopt(revisionId:string){if(active?.parent_id===revisionId)setRedoBranches(current=>({...current,[revisionId]:active.id}));await post(`/v1/workspaces/${id}/current`,{revision_id:revisionId});}
 function inspectRegion(target:RegionTraceTarget){
  if(blocked||traceTransition||traceGuard.current)return;
  setTraceTransition(true);
  void navigate(async()=>{
   setTraceError("");setVerifiedTrace(null);setVerifiedField(null);
    const revision=history.find(item=>item.id===target.revisionId);const sourceField=fields.data?.find(item=>item.id===target.fieldId);
    if(!revision||revision.state!=="succeeded"||!revision.config.field_ids?.includes(target.fieldId)||!sourceField)throw Error("保存済みの解析版または視野を確認できません。図の履歴から選び直してください。");
    const displayChannel=traceDisplayChannel(target,sourceField,cid);
    if(!displayChannel)throw Error("保存済みの測定チャンネルを確認できません。図の履歴から選び直してください。");
    const savedMasks=await request<RegionMasks>(`/v1/revisions/${target.revisionId}/region-masks?field_id=${encodeURIComponent(target.fieldId)}`,{signal:AbortSignal.timeout(15000)});
    const mismatch=regionTraceMismatch(target,sourceField,savedMasks);if(mismatch)throw Error(mismatch);
    if(traceGuard.current)throw Error("未保存の領域・設定があるため、画像への切り替えを中止しました。");
    if(active?.id!==target.revisionId)await request(`/v1/workspaces/${id}/current`,{method:"POST",body:JSON.stringify({revision_id:target.revisionId}),signal:AbortSignal.timeout(15000)});
    setFieldId(target.fieldId);setChannelId(displayChannel.channel_id);setTab("analysis");setPendingTrace({target,channelId:displayChannel.channel_id});
  });
 }
 function inspectField(fieldId:string,revisionId:string){
  if(blocked||traceTransition||traceGuard.current)return;
  setTraceTransition(true);setVerifiedTrace(null);setVerifiedField(null);setTraceError("");
  void navigate(async()=>{
   try{
    const revision=history.find(item=>item.id===revisionId);
    if(!revision||revision.state!=="succeeded"||!revision.config.field_ids?.includes(fieldId)||!fields.data?.some(item=>item.id===fieldId))throw Error();
    if(active?.id!==revisionId)await request(`/v1/workspaces/${id}/current`,{method:"POST",body:JSON.stringify({revision_id:revisionId}),signal:AbortSignal.timeout(15000)});
    setFieldId(fieldId);setTab("analysis");setPendingField({revisionId,fieldId});
   }catch{throw Error("保存済みの視野を開けませんでした。図の履歴からもう一度お試しください。");}
  });
 }
 function inspectSourceField(target:RegionFieldTraceTarget){
  if(blocked||traceTransition||traceGuard.current)return;
  setTraceTransition(true);setVerifiedTrace(null);setVerifiedField(null);setTraceError("");
  void navigate(async()=>{
   const revision=history.find(item=>item.id===target.revisionId);const sourceField=fields.data?.find(item=>item.id===target.fieldId);
   if(!revision||revision.state!=="succeeded"||!revision.config.field_ids?.includes(target.fieldId)||!sourceField)throw Error("保存済みの解析版または視野を確認できません。図の履歴から選び直してください。");
   const displayChannel=traceDisplayChannel(target,sourceField,cid);
   if(!displayChannel)throw Error("保存済みの測定チャンネルを確認できません。図の履歴から選び直してください。");
   const savedMasks=await request<RegionMasks>(`/v1/revisions/${target.revisionId}/region-masks?field_id=${encodeURIComponent(target.fieldId)}`,{signal:AbortSignal.timeout(15000)});
   const mismatch=regionFieldTraceMismatch(target,sourceField,savedMasks);if(mismatch)throw Error(mismatch);
   if(traceGuard.current)throw Error("未保存の領域・設定があるため、画像への切り替えを中止しました。");
   if(active?.id!==target.revisionId)await request(`/v1/workspaces/${id}/current`,{method:"POST",body:JSON.stringify({revision_id:target.revisionId}),signal:AbortSignal.timeout(15000)});
   setFieldId(target.fieldId);setChannelId(displayChannel.channel_id);setTab("analysis");
   setPendingField({revisionId:target.revisionId,fieldId:target.fieldId,source:target,channelId:displayChannel.channel_id});
  });
 }
 function applyPolygon(){
  if(operation==="background"){if(areaOnly)return;change({backgrounds:{...config.backgrounds,[fid]:{...config.backgrounds[fid],[cid]:{polygon,confirmed:true}}}});setPolygon([]);setCoordinates("");return;}
  run(()=>saveEdit());
 }
 async function saveEdit(){if(!active||!masks.data)return;await post(`/v1/revisions/${active.id}/region-edits`,{field_id:fid,region_set_id:config.recipe.region_set_id,operation,ids:operation==="add"?[]:selected,polygon:["delete","merge"].includes(operation)?[]:polygon,expected_mask_revision_id:masks.data.metadata.mask_revision_id});setPolygon([]);setCoordinates("");setSelected([]);}
 function exclude(regionId:number|null){if(!exclusionReason.trim()){onError("除外理由を入力してください。");return;}change({exclusions:[...config.exclusions.filter(exclusion=>!(exclusion.field_id===fid&&exclusion.region_id===regionId)),{field_id:fid,region_id:regionId,reason:exclusionReason.trim()}]});}
 const scopeCount=active?.config.field_ids?.length||0;const remaining=(fields.data?.length||0)-scopeCount;
 const traceVisible=verifiedTrace&&active?.id===verifiedTrace.target.revisionId&&fid===verifiedTrace.target.fieldId&&cid===verifiedTrace.channelId&&selected.length===1&&selected[0]===verifiedTrace.target.regionId&&showMasks&&!dirty&&!draftRegion&&field&&masks.data&&!regionTraceMismatch(verifiedTrace.target,field,masks.data);
 const fieldTraceVisible=verifiedField&&active?.id===verifiedField.target.revisionId&&fid===verifiedField.target.fieldId&&cid===verifiedField.channelId&&showMasks&&!dirty&&!draftRegion&&field&&masks.data&&!regionFieldTraceMismatch(verifiedField.target,field,masks.data);
 const message=processing?"処理を実行しています。完了後に領域と値を確認してください。":nextMissing?"測定するチャンネルごとに、信号を含まない背景を指定してください。":!active||!included?(areaOnly?"代表視野の領域を用意し、面積を確認します。背景の指定は不要です。":"背景を確認したら、代表視野の領域を用意します。"):failures.length?(areaOnly?"処理できなかった視野があります。領域を修正するか、理由を記録して除外してください。":"処理できなかった視野があります。背景・領域を修正するか、理由を記録して除外してください。"):noRegions?"画像を囲んで測りたい領域を追加してください。":recipeChanged?"検出条件を変更しました。再作成する範囲と修正領域の扱いを確認してください。":dirty?(measurementChanged?"測定する量を変更しました。領域を保持して再測定し、品質を確認してください。":areaOnly?"除外の変更を再測定へ反映してください。":"背景や除外の変更を再測定へ反映してください。"):!active.reviewed?(savedAreaOnly?"領域と面積、失敗・除外理由を確認してから図へ進みます。":"領域と背景、測定値を確認してから図へ進みます。"):remaining>0?`採用した領域を保持して、残り ${remaining} 視野を測定できます。`:"品質確認済みです。測定値の分布を図にできます。";
 function nextAction(){if(nextMissing){setFieldId(nextMissing.field.id);setChannelId(nextMissing.channel.channel_id);setOperation("background");editor.current?.scrollIntoView({behavior:"smooth",block:"center"});}else if(noRegions){setOperation("add");editor.current?.scrollIntoView({behavior:"smooth",block:"center"});}else if(active?.reviewed&&!dirty&&!remaining)setTab("figures");else values.current?.scrollIntoView({behavior:"smooth",block:"start"});}
 if(fields.isPending)return <main className={styles.workbench}><p>画像を確認しています…</p></main>;
 return <main className={styles.workbench}>
  {traceError&&<div role="alert" className={styles.notice}>{traceError} {traceRecovery?<button className={styles.linkButton} onClick={onBack}>作業一覧へ戻る</button>:<button className={styles.linkButton} onClick={()=>setTraceError("")}>閉じる</button>}</div>}
  {traceTransition&&!traceRecovery&&<div role="status" className={styles.notice}>保存済みの領域を開いています。{!busy&&(pendingTrace||pendingField)&&<button className={styles.linkButton} onClick={()=>{setPendingTrace(null);setPendingField(null);setTraceTransition(false);}}>中止</button>}</div>}
  <div inert={traceTransition} aria-busy={traceTransition}>
  <div className={styles.workHeader}><div><button className={styles.back} onClick={onBack}>← 作業一覧</button><h1>{space.data?.title||"ワークスペース"}</h1><span className={styles.muted}>{fields.data?.length||0} 視野 · {active?`解析版 ${index+1} / 対象 ${scopeCount} 視野`:"解析前"} · {active?.reviewed?"品質確認済み":"品質確認前"}</span></div><div className={styles.workHeaderRight}><span className={styles.small}>有効期限 {space.data?new Date(space.data.expires*1000).toLocaleString("ja-JP"):"—"}</span><button className={styles.secondary} disabled={busy} onClick={()=>run(async()=>{await post(`/v1/workspaces/${id}/touch`);})}>保存期限を24時間延長</button></div></div>
  <nav className={styles.tabs} aria-label="解析工程"><button className={tab==="analysis"?styles.activeTab:""} onClick={()=>setTab("analysis")}>01 <b>画像と領域</b></button><button className={tab==="figures"?styles.activeTab:""} onClick={()=>setTab("figures")}>02 <b>分布と図</b></button><button className={tab==="comparison"?styles.activeTab:""} onClick={()=>setTab("comparison")}>03 <b>実験単位で比較</b></button><button className={tab==="export"?styles.activeTab:""} onClick={()=>setTab("export")}>04 <b>保存と履歴</b></button><span className={styles.tabStatus}>{processing?"● 処理中":dirty?"● 未反映の変更があります":"画像・領域・測定値を同じ解析版で保存します"}</span></nav>
  {(fields.error||space.error)&&<p role="alert" className={styles.error}>{errorMessage(fields.error||space.error)}</p>}
  {traceVisible&&tab==="analysis"&&<p role="status" className={styles.notice}>図に記録された領域 {verifiedTrace.target.regionId} を表示しています。{verifiedTrace.target.channelId===null?`面積測定にはチャンネルを使用していません。表示: ${channel?.label||verifiedTrace.channelId}`:`測定チャンネル: ${verifiedTrace.target.channelLabel}`}</p>}
  {fieldTraceVisible&&tab==="analysis"&&<p role="status" aria-label="保存済み比較の視野" className={styles.notice}>この集計に記録された視野と領域を表示しています。{verifiedField.target.channelId===null?`面積測定にはチャンネルを使用していません。表示: ${channel?.label||verifiedField.channelId}`:`測定チャンネル: ${verifiedField.target.channelLabel}`} 採用・除外の内訳は、比較の集計表から確認できます。</p>}
  {tab==="analysis"&&<>
   <RegionUploadPanel wid={id} channels={fields.data?.[0]?.image_info.channels} maskSource={fields.data?.length?(fields.data[0].image_info.labels_array?"imported":"manual"):config.recipe.source==="imported"?"imported":"manual"} hasFields={!!fields.data?.length} run={run} onDone={registered=>{setFieldId(registered.id);if(!fields.data?.length&&!active&&!methodChosen.current)setConfig(current=>({...current,recipe:{...regionRecipe,label:current.recipe.label,source:registered.image_info.labels_array?"imported":"manual"}}));}}/>
   <RegionBatchUploadPanel backgroundRequired={!areaOnly} onInspect={()=>editor.current?.closest("section")?.scrollIntoView({behavior:"smooth",block:"start"})} wid={id} channels={fields.data?.[0]?.image_info.channels} maskSource={fields.data?.length?(fields.data[0].image_info.labels_array?"imported":"manual"):config.recipe.source==="imported"?"imported":"manual"} hasFields={!!fields.data?.length} run={run} onDone={registered=>{setFieldId(registered.id);if(!fields.data?.length&&!active&&!methodChosen.current)setConfig(current=>({...current,recipe:{...regionRecipe,label:current.recipe.label,source:registered.image_info.labels_array?"imported":"manual"}}));}}/>
   <PlanResolutionPanel plan={space.data?.analysis_plan} measurement={config.measurement} recipe={config.recipe} options={planOptions} value={config.plan_resolution} blocked={blocked} saved={!!active?.config.plan_resolution&&!dirty} onChange={value=>change({plan_resolution:value})}/>
   {!!fields.data?.length&&<><div className={styles.nextStep} aria-label="次の操作"><p>{message}</p>{(nextMissing||noRegions||active)&&<button className={styles.secondary} disabled={blocked} onClick={nextAction}>{nextMissing?"背景を設定":noRegions?"領域を追加":active?.reviewed&&!dirty&&!remaining?"分布と図へ":"測定値を確認"} →</button>}</div>
   <div className={styles.analysisGrid}>
    <aside className={styles.fieldSidebar}><div className={styles.sidebarTitle}><b>視野</b><span>{fields.data.length}</span></div>{effectiveFields.map((item,i)=><button key={item.id} className={item.id===fid?styles.activeField:styles.field} onClick={()=>setFieldId(item.id)}><div><span className={styles.fieldNumber}>{String(i+1).padStart(2,"0")}</span><b>{item.metadata.condition||"条件未設定"}</b></div><small>{item.metadata.sample||`視野 ${i+1}`}</small><small>{item.image_info.channels.map(ch=>ch.label).join(" / ")}</small><div className={styles.fieldBadges}><span>{areaOnly?"面積のみ":missing.some(value=>value.field.id===item.id)?"背景未確認":"背景 ✓"}</span><span>{report.data?.field_outcomes[item.id]==="failed"?"要修正":report.data?.field_outcomes[item.id]==="no_regions"?"領域なし":active?.config.field_ids?.includes(item.id)?"解析対象":"未測定"}</span></div></button>)}</aside>
    <section className={styles.viewer}><div className={styles.viewerToolbar}><div className={styles.segmented}>{channels.map(ch=><button key={ch.channel_id} className={cid===ch.channel_id?styles.segmentActive:""} onClick={()=>setChannelId(ch.channel_id)}>{ch.label}</button>)}</div><label className={styles.inlineLabel}>表示ゲイン<input aria-label="表示ゲイン" type="range" min={.1} max={5} step={.1} value={gain} onChange={event=>setGain(Number(event.target.value))}/></label><label className={styles.checkbox}><input type="checkbox" checked={showMasks} onChange={event=>setShowMasks(event.target.checked)}/>輪郭</label></div>
     {field&&channel&&<FieldCanvas fieldId={fid} shape={field.image_info.shape} masks={masks.data?{regions:masks.data.regions}:undefined} layer="regions" operation={operation} selected={selected} onSelect={setSelected} polygon={polygon} onPolygon={setPolygon} background={backgroundFor(fid,cid)?.polygon} channel={cid} gain={gain} showMasks={showMasks} regionLabel={config.recipe.label} showBackgroundLegend={!areaOnly} channelLabels={Object.fromEntries(field.image_info.channels.map(item=>[item.channel_id,item.label]))} previewPath={`/v1/region-fields/${fid}/preview?channel_id=${encodeURIComponent(cid)}&gain=${gain}`}/>}
     <div className={styles.editor} ref={editor}><div className={styles.editorTop}><b>{config.recipe.label}</b><div className={styles.revisionButtons}><button disabled={!active?.parent_id||!history.some(revision=>revision.id===active.parent_id)||blocked} onClick={()=>run(()=>adopt(active!.parent_id!))}>↶ Undo</button><button disabled={!redo||blocked} onClick={()=>run(()=>adopt(redo!.id))}>↷ Redo</button></div></div>
      <div className={styles.toolButtons}>{(Object.entries(operations) as [Operation,string][]).filter(([value])=>!areaOnly||value!=="background").map(([value,label])=><button key={value} className={operation===value?styles.toolActive:""} disabled={blocked||(!["select","background"].includes(value)&&!canEdit)} onClick={()=>setOperation(value)}>{label}</button>)}</div>
      <p className={styles.small}>{operation==="background"?`${channel?.label||"チャンネル"} の信号を含まない背景を囲んで確定します。測定領域と重ならない場所を選んでください。`:operation==="select"?"輪郭または表の領域IDで選択します。複数の輪郭を選ぶこともできます。":operation==="replace"?"対象を1つ選び、新しい輪郭を囲んで保存します。":operation==="split"?"対象を1つ選び、切り分ける部分を多角形で囲みます。":operation==="add"?"測定したい領域を多角形で囲んで保存します。":"対象領域を選んでから実行します。"}</p>
      <label>選択した領域ID<input aria-label="選択した領域ID" value={selected.join(",")} onChange={event=>setSelected(event.target.value.split(",").map(value=>Number(value.trim())).filter(value=>Number.isInteger(value)&&value>0))} placeholder="複数はカンマ区切り"/></label>
      {["background","add","replace","split"].includes(operation)&&<><details><summary className={styles.small}>座標から多角形を指定</summary><label>頂点（x,y を空白または改行で区切る）<textarea value={coordinates} onChange={event=>setCoordinates(event.target.value)} rows={2}/></label><button className={styles.secondary} onClick={()=>{const points=coordinates.trim().split(/\s+/).map(pair=>pair.split(",").map(Number));if(points.length<3||points.some(point=>point.length!==2||!point.every(Number.isFinite))){onError("3点以上の x,y 座標を入力してください。");return;}setPolygon(points as Point[]);}}>座標を反映</button></details><div className={styles.actionRow}><button className={styles.secondary} disabled={!polygon.length} onClick={()=>setPolygon(current=>current.slice(0,-1))}>頂点を戻す</button><button className={styles.secondary} onClick={()=>setPolygon([])}>クリア</button><button className={styles.primary} disabled={blocked||polygon.length<3||(operation!=="background"&&(dirty||!canEdit||(["replace","split"].includes(operation)&&selected.length!==1)))} onClick={applyPolygon}>{operation==="background"?"背景を確定":"領域を保存・再測定"} · {polygon.length} 点</button></div></>}
      {["delete","merge"].includes(operation)&&<button className={styles.primary} disabled={blocked||dirty||!canEdit||selected.length<(operation==="merge"?2:1)} onClick={()=>run(()=>saveEdit())}>選択した領域を{operations[operation]}・再測定</button>}
     </div>
    </section>
    <aside className={`${styles.controlPanel} ${styles.genericControls}`}><div className={styles.panelTitle}><h2>測定の準備</h2></div>
     <label>測定する量<select aria-label="測定する量" value={measurementMode(config.measurement)} disabled={blocked||draftRegion} onChange={event=>chooseMeasurement(event.target.value as RegionMeasurementMode)}><option value="area_and_intensity">面積と輝度（背景補正あり）</option><option value="area_only">面積のみ</option></select></label>
     <p className={styles.small}>{areaOnly?"領域の面積を測定します。背景ROIは不要です。輝度と信号の飽和率は測定しません。":"原値と背景補正後の輝度を測定します。チャンネルごとに背景ROIを確認してください。"}</p>
     {measurementChanged&&<p className={styles.notice}>測定する量の変更は、新しい解析版へ保存します。現在の領域を保持し、保存後に品質を確認し直します。</p>}
     <label>領域名<input aria-label="領域名" value={config.recipe.label} readOnly={!!active} maxLength={120} onChange={event=>change({recipe:{...config.recipe,label:event.target.value}})}/></label>
     <label>領域の作り方<select aria-label="領域の作り方" value={config.recipe.source} disabled={blocked} onChange={event=>chooseSource(event.target.value as "manual"|"imported"|"stardist_nuclear")}><option value="manual" disabled={fields.data?.some(item=>!!item.image_info.labels_array)}>手動で囲む</option>{fields.data?.some(item=>item.image_info.labels_array)&&<option value="imported">登録したマスクを使う</option>}<option value="stardist_nuclear" disabled={fields.data?.some(item=>!!item.image_info.labels_array)}>核染色から自動検出</option></select></label>
     {config.recipe.source==="stardist_nuclear"?<>
      <label>核の検出に使うチャンネル<select aria-label="核の検出に使うチャンネル" value={config.recipe.defining_channel_id} disabled={blocked} onChange={event=>{if(config.recipe.source!=="stardist_nuclear")return;setNuclearConfirmed(false);change({recipe:{...config.recipe,defining_channel_id:event.target.value}});}}><option value="">実画像のチャンネルを選択</option>{channels.map(ch=><option key={ch.channel_id} value={ch.channel_id}>{ch.label}{ch.stain?` · ${ch.stain}`:""}</option>)}</select></label>
      <label className={styles.checkbox}><input type="checkbox" checked={nuclearConfirmed} disabled={blocked} onChange={event=>{setNuclearConfirmed(event.target.checked);setPendingScope(null);}}/>このチャンネルが核を染めた画像であることを確認しました。</label>
      <p className={styles.small}>代表視野で検出し、輪郭を確認・修正します。核以外の領域や細胞全体の境界は推定しません。</p>
      <details><summary>検出の詳細設定</summary><p className={styles.small}>Fiji / StarDist 2D · Versatile (fluorescent nuclei)。開始値は画像への適合を保証しません。</p><div className={styles.formGrid}>{([['probability','確率閾値',.001,.999,.01],['nms','重なりの閾値（NMS）',.001,.999,.01],['percentile_low','正規化の下限 percentile',0,99.9,.1],['percentile_high','正規化の上限 percentile',.1,100,.1]] as const).map(([key,label,min,max,step])=><label key={key}>{label}<input aria-label={label} type="number" min={min} max={max} step={step} value={config.recipe.source==="stardist_nuclear"?config.recipe.detector[key]:0} disabled={blocked} onChange={event=>{if(config.recipe.source!=="stardist_nuclear")return;change({recipe:{...config.recipe,detector:{...config.recipe.detector,[key]:Number(event.target.value)}}});}}/></label>)}</div></details>
     </>:<><p className={styles.small}>{config.recipe.source==="imported"?"登録した整数マスクから開始します。取り込み後も修正できます。":"手動で領域を囲んで測定します。"}</p>{!active&&<details><summary>領域の定義（任意）</summary><label>定義に使うチャンネル<select value={config.recipe.defining_channel_id||""} onChange={event=>{if(config.recipe.source==="stardist_nuclear")return;change({recipe:{...config.recipe,defining_channel_id:event.target.value||null}});}}><option value="">指定しない</option>{channels.map(ch=><option key={ch.channel_id} value={ch.channel_id}>{ch.label}</option>)}</select></label><p className={styles.small}>測る信号を使って領域を定義すると、領域選択もその信号に依存します。</p></details>}</>}
     {recipeChanged&&<p className={styles.notice}>領域の作成条件が変わっています。反映には再作成が必要です。修正済みの領域は旧版に残ります。<button className={styles.linkButton} onClick={()=>{change({recipe:active!.config.recipe});setNuclearConfirmed(active!.config.recipe.source==="stardist_nuclear");}}>保存済みの条件に戻す</button></p>}
     {!areaOnly&&<div className={styles.backgroundStatus}><b>選択した視野の背景</b>{channels.map(ch=><button className={styles.linkButton} key={ch.channel_id} onClick={()=>{setChannelId(ch.channel_id);setOperation("background");}}>{ch.label} {backgroundFor(fid,ch.channel_id)?.confirmed?"✓":"未確認"}</button>)}</div>}
     <div className={styles.analysisLaunch}>{!included&&<><button className={styles.secondary} disabled={blocked||!!missingSelected.length||!recipeReady} onClick={()=>run(()=>initialize("add"))}>{active&&!recipeChanged?"この視野を解析対象に追加":nuclear?"この視野で検出を試す":"この視野で始める"}</button><p className={styles.small}>{active&&!recipeChanged?"すでに解析した視野の領域を保持します。":areaOnly?"代表視野の領域と面積を確認してから、全視野へ進めます。":"背景を確認してから代表視野で始めます。"}</p></>}
      {included&&nuclear&&<button className={styles.secondary} disabled={blocked||!!missingSelected.length||!recipeReady} onClick={()=>run(()=>initialize("redetect"))}>この視野を再検出</button>}
      <button className={styles.primary} disabled={blocked||!!missing.length||!recipeReady} onClick={()=>run(()=>initialize("batch"))}>{active&&!recipeChanged?"領域を保持して全視野を測定":active?"新しい条件で全視野を再作成":nuclear?"全視野を検出・測定":"全視野の領域を用意"}</button><p className={styles.small}>{active&&!recipeChanged?"修正済みの領域を保持し、新しい視野だけ同じ条件で解析します。":nuclear?"検出条件を代表視野で確認してから全視野へ適用します。":"手動の場合は空の領域から始め、取り込みの場合は登録したマスクを使います。"}</p>
      {pendingScope&&<div className={styles.notice} role="alert"><p>{submission(pendingScope).replacedCount} 視野の領域を作り直します。修正済みの輪郭は引き継がれません。現在の領域は旧版から確認できます。</p><button className={styles.danger} disabled={blocked||!recipeReady} onClick={()=>run(()=>initialize(pendingScope,true))}>修正領域を引き継がず再作成</button><button className={styles.secondary} onClick={()=>setPendingScope(null)}>戻る</button></div>}
      {active&&<button className={styles.secondary} disabled={blocked||!dirty||recipeChanged||!planReady||missing.some(item=>active.config.field_ids?.includes(item.field.id))} onClick={()=>run(async()=>{await post(`/v1/revisions/${active.id}/region-reconfigure`,payload(active.config.field_ids||[]));})}>{measurementChanged?"測定する量を変更して再測定":areaOnly?"除外を反映して再測定":"背景・除外を反映して再測定"}</button>}
     </div>
     <details><summary>測定の定義</summary><p className={styles.small}>{areaOnly?"原画像座標の領域マスクから面積を測定します。輝度・背景補正・信号の飽和率は未測定です。":"原画像の画素から面積・平均・中央値・積算を測定します。背景補正は各チャンネルの背景中央値を引き、負の値も保持します。"}画素サイズ不明の場合、面積はpx²です。</p></details>
    </aside>
   </div></>}
   {active&&<section className={styles.measurements} ref={values}><div className={styles.sectionHeader}><h2>測定値と品質確認</h2><span className={styles.statusPill}>{regionIds.length} 領域{savedAreaOnly?"":` · ${channel?.label||"—"}`}</span></div>
    {report.error&&<p role="alert" className={styles.error}>{errorMessage(report.error)}</p>}
    {!!failures.length&&<div className={styles.error}>{failures.map(failure=><p key={failure.field_id}>視野 {(fields.data||[]).findIndex(item=>item.id===failure.field_id)+1}：{errorCodeMessage(failure.reason)}</p>)}{areaOnly?"領域を修正して再測定するか、理由を記録して視野を除外してください。":"領域と背景を修正して再測定するか、理由を記録して視野を除外してください。"}</div>}
    {noRegions&&<p className={styles.notice}>領域はまだありません。画像を囲んで追加してください。領域なしを輝度0として扱いません。</p>}
    {table?.protocol_version==="2.0.0"&&<p className={styles.notice}>保存済みの測定：面積のみ。輝度・背景補正・信号の飽和率は、測定対象に含めていません。</p>}
    {measurementChanged&&<p className={styles.small}>表は保存済みの測定値です。変更した測定内容は再測定後に反映されます。</p>}
    <div className={styles.tableWrap}><table><thead><tr><th>領域ID</th><th>面積 px²</th>{field?.image_info.calibration&&<th>面積 µm²</th>}{table?.protocol_version!=="2.0.0"&&<><th>平均（原値）</th><th>平均（背景補正）</th><th>中央値（背景補正）</th><th>積算（背景補正）</th></>}<th>状態</th></tr></thead><tbody>{rows.map(row=><tr key={row.region_id} className={selected.includes(row.region_id)?styles.selectedRegionRow:""}><td><button className={styles.linkButton} onClick={()=>{setSelected([row.region_id]);setOperation("select");}}>{row.region_id}</button></td><td>{formatValue(row.area_px)}</td>{field?.image_info.calibration&&<td>{formatValue(row.area_um2)}</td>}{table?.protocol_version!=="2.0.0"&&<><td>{formatValue(row.mean)}</td><td>{formatValue(row.mean_corrected)}</td><td>{formatValue(row.median_corrected)}</td><td>{formatValue(row.integrated_corrected)}</td></>}<td>{config.exclusions.some(exclusion=>exclusion.field_id===fid&&(exclusion.region_id===null||exclusion.region_id===row.region_id))?"除外指定":"採用"}{row.touches_border?" / 画像端":""}{row.storage_limit_fraction!==null&&row.storage_limit_fraction>0?" / 保存形式の上限値あり":""}{row.acquisition_saturation_fraction!==null&&row.acquisition_saturation_fraction>0?" / 取得時飽和あり":""}</td></tr>)}</tbody></table>{!rows.length&&!noRegions&&<p className={styles.small}>この視野の測定値はまだありません。</p>}</div>
    {table&&<details className={styles.measurementDetails}><summary>{table.protocol_version==="2.0.0"?"測定条件":"背景・測定条件"}</summary>{table.protocol_version==="2.0.0"?<><p className={styles.small}>背景：面積測定には不要。輝度と信号の飽和率：未測定（面積のみ）。</p>{table.channel_provenance.map(item=><p className={styles.small} key={item.channel.channel_id}>{item.channel.label} / {item.channel.stain||"染色名未設定"} · 表示・領域確認用の画像</p>)}</>:table.channel_provenance.map(item=><p className={styles.small} key={item.channel.channel_id}>{item.channel.label}：背景 {item.background_pixel_count} px / 中央値 {formatValue(item.background_median)} / {item.channel.stain||"染色名未設定"}{item.channel.acquisition_saturation_value===null?" / 取得時の飽和値は不明":""}</p>)}<p className={styles.small}>1領域を複数チャンネルで測定しても、領域数や独立反復数は増えません。</p></details>}
    <div className={styles.qcActions}><label>除外理由<input aria-label="領域の除外理由" value={exclusionReason} maxLength={200} onChange={event=>setExclusionReason(event.target.value)}/></label><button className={styles.secondary} disabled={selected.length!==1} onClick={()=>exclude(selected[0])}>選択領域を除外指定</button><button className={styles.secondary} onClick={()=>exclude(null)}>この視野を除外指定</button></div>
    {!!config.exclusions.length&&<details className={styles.measurementDetails}><summary>除外指定</summary>{config.exclusions.map((exclusion,i)=><div className={styles.exclusion} key={i}><span>視野 {(fields.data||[]).findIndex(item=>item.id===exclusion.field_id)+1} / {exclusion.region_id===null?"全体":`領域 ${exclusion.region_id}`}：{exclusion.reason}</span><button className={styles.linkButton} onClick={()=>change({exclusions:config.exclusions.filter((_,index)=>index!==i)})}>解除</button></div>)}</details>}
    <div className={styles.reviewBox}><label className={styles.checkbox}><input type="checkbox" checked={reviewed} onChange={event=>setReviewed(event.target.checked)}/>{savedAreaOnly?"領域と面積、失敗・除外理由を確認しました。":"領域、チャンネルごとの背景、失敗・除外理由を確認しました。"}</label><button className={styles.primary} disabled={blocked||dirty||!reviewed||!hasRegions||!!failures.length||active.state!=="succeeded"||active.reviewed} onClick={()=>run(async()=>{await post(`/v1/revisions/${active.id}/review`,{});})}>品質確認を完了</button>{dirty&&<p className={styles.small}>変更を再測定へ反映してから確認してください。</p>}</div>
   </section>}
  </>}
  {tab==="figures"&&<DescriptivePanel backgroundRequired={!savedAreaOnly} onInspectRegion={inspectRegion} traceBlocked={draftRegion} planSelection={active?.config.plan_resolution} revisionId={active?.id} reviewed={!!active?.reviewed} options={options} jobs={(jobs.data||[]).filter(job=>history.some(revision=>revision.id===job.revision_id))} blocked={blocked} dirty={dirty} run={run} fieldLabels={Object.fromEntries(effectiveFields.map((field,i)=>[field.id,`画像一覧の視野 ${i+1} · ${field.metadata.sample||"試料未記録"}`]))} revisionLabels={Object.fromEntries(history.map((revision,i)=>[revision.id,`解析版 ${i+1}`]))} onInspectField={inspectField}/>}
  {tab==="comparison"&&<RegionComparisonPanel key={active?.id||"no-revision"} revision={active} fields={availableFields} options={options} jobs={(jobs.data||[]).filter(job=>history.some(revision=>revision.id===job.revision_id))} blocked={blocked} dirty={dirty} traceBlocked={draftRegion} run={run} onReview={()=>setTab("analysis")} revisionLabels={Object.fromEntries(history.map((revision,i)=>[revision.id,`解析版 ${i+1}`]))} onInspectField={inspectField} onInspectSourceField={inspectSourceField} fieldLabels={Object.fromEntries(effectiveFields.map((item,i)=>[item.id,`視野 ${i+1}`]))}/>}
  {tab==="export"&&<section className={styles.exportPage}><div className={styles.card}><h2>測定値と条件を保存</h2><p>{savedAreaOnly?"面積の測定表、領域、Methodsと実行条件をまとめます。輝度は未測定として記録し、背景ROIは含めません。":"測定表、領域、背景、Methodsと実行条件をまとめます。"}</p><label className={styles.checkbox}><input type="checkbox" checked={includeRaw} onChange={event=>setIncludeRaw(event.target.checked)}/>原画像もZIPへ含める</label><button className={styles.primary} disabled={blocked||dirty||!active?.reviewed} onClick={()=>run(async()=>{await post(`/v1/revisions/${active!.id}/export?include_raw=${includeRaw}`);})}>解析パッケージを生成</button>{exports.map(job=><div className={styles.downloadRow} key={job.id}><span>{job.revision_id===active?.id?"採用中の版":"旧版"} · {new Date(job.created*1000).toLocaleString("ja-JP")}</span><button onClick={()=>run(()=>download(`/v1/jobs/${job.id}/files/analysis.zip`,"cytellect-regions.zip"))}>ZIPを保存 ↓</button><button onClick={()=>run(()=>download(`/v1/jobs/${job.id}/files/methods.md`,"methods.md"))}>Methods ↓</button></div>)}</div>
   <div className={styles.card}><h2>解析版の履歴</h2>{history.map((revision,i)=><div className={styles.downloadRow} key={revision.id}><span>解析版 {i+1} · {revision.reviewed?"確認済み":"未確認"}{revision.id===active?.id?" / 採用中":""}</span><button disabled={blocked||revision.state!=="succeeded"||revision.id===active?.id} onClick={()=>run(()=>adopt(revision.id))}>この版を採用</button></div>)}</div>
   <div className={styles.card}><h2>作業を削除</h2><p>画像・領域・測定値へのアクセスを遮断し、実行を停止してから削除します。</p><label className={styles.checkbox}><input type="checkbox" checked={deleteConfirmed} onChange={event=>setDeleteConfirmed(event.target.checked)}/>必要な結果を保存しました。この作業を削除します。</label><button className={styles.danger} disabled={busy||!deleteConfirmed} onClick={()=>run(async()=>{await request(`/v1/workspaces/${id}`,{method:"DELETE"});onBack();})}>この作業を削除</button></div>
  </section>}
  {!!jobs.data?.length&&<details className={styles.jobs}><summary>処理履歴 · {processing?"実行中":"待機中"}</summary>{jobs.data.toSorted((a,b)=>b.created-a.created).map(job=><div key={job.id}><span>{job.kind==="analysis"?"領域・測定":job.kind==="statistics"?"図の生成":job.kind==="export"?"パッケージ":"処理"} / {job.state}{job.error&&` — ${errorCodeMessage(job.error)}`}</span>{["queued","running"].includes(job.state)&&<button onClick={()=>run(async()=>{await post(`/v1/jobs/${job.id}/cancel`);})}>中止</button>}{["failed","cancelled"].includes(job.state)&&<button disabled={blocked} onClick={()=>run(async()=>{await post(`/v1/jobs/${job.id}/retry`);})}>再試行</button>}</div>)}</details>}
 </div></main>;
}
