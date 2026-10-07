"use client";
import {useEffect, useState, useSyncExternalStore} from "react";
import {ApiError, errorCodeMessage, errorMessage, request} from "../api";
import type {Point} from "../types";
import {automaticBackground, createApiAdapter, nuclearRecipe, rawMeasurement, type ChannelAssignment, type ChannelAssignments, type ImportedField, type MaskOperation, type Recipe, type SavedResult, type ValidatedProposal, type WorkspaceRun} from "./api-adapter";
import {effectiveChannelAssignments} from "./channel-assignments";
import {groupFiles, isSupportedImage, type AddedFile, type ChannelDefinition, type Grouping} from "./grouping";
import {nucleolarDetectorV2, type NucleolarDefinition} from "./nucleolar-definition";
import {applicableProcessing, savedProcessing, withProcessingSettings, type ProposalProcessing} from "./proposal-processing";
import {loadReviewPreview, releaseReviewPreview, type ReviewData, type ReviewTarget} from "./review-preview";
import {validTargetResults, type TargetResult} from "./target-results";
import {tiffInputMode,tiffHasOmeMetadata} from "./tiff-intake";

export interface RuntimeSettings {
  nuclearMaxSide: number | null; nuclearProbability: number; nuclearNms: number;
  nucleolarDefinition: NucleolarDefinition;
  nucleolarSigma: number | null; nucleolarRim: number | null; nucleolarMinimumArea: number | null; nucleolarMaximumArea: number | null;
  background: "raw" | "automatic" | "confirmed_roi";
}
export const defaultRuntimeSettings = (): RuntimeSettings => ({nuclearMaxSide:null,nuclearProbability:.5,nuclearNms:.3,
  nucleolarDefinition:{source:"dapi_poor",marker:"",pixelUm:null,relative:.7},nucleolarSigma:null,nucleolarRim:null,nucleolarMinimumArea:null,nucleolarMaximumArea:null,background:"raw"});
export interface RuntimeSnapshot {
  data: ReviewData | null; busy: boolean; operation: string; error: string; assignments: ChannelAssignments;
  activeTarget: ReviewTarget; settings: RuntimeSettings; proposal: ValidatedProposal | null; processing: ProposalProcessing | null; importIssues: Grouping["issues"];
}
type Adapter = ReturnType<typeof createApiAdapter>;
export interface RuntimeCandidate {result:SavedResult;recipe:Recipe;settingsFingerprint:string;runId?:string;runState?:WorkspaceRun["state"];backgroundPending?:boolean}
type RuntimeTargets = Partial<Record<ReviewTarget, TargetResult>>;
export interface RuntimeSpecification {version:number; spec:({channel_assignment_version:number;target:ReviewTarget;settings:RuntimeSettings;processing:ProposalProcessing|null;measurement:typeof rawMeasurement|null;selection?:unknown;statistics?:unknown;figure?:unknown;metrics?:unknown[];additional_analyses?:unknown[];figure_proposals?:unknown[];backgrounds?:Record<string,Record<string,{polygon:Point[];confirmed:true}>>;confirmed_channel_ids?:string[]})|null}
type Dependencies = {adapter?:Adapter; loadPreview?:typeof loadReviewPreview; releasePreview?:typeof releaseReviewPreview;
  readSpecification?:(workspace:string)=>Promise<RuntimeSpecification>; writeSpecification?:(workspace:string,value:RuntimeSpecification)=>Promise<RuntimeSpecification>};
const emptyData = (): ReviewData => ({workspaceId:"",title:"画像解析",fields:[],channels:[]});
const labels = {nuclei:"核",nucleoli:"核小体",nucleoplasm:"核質",cell:"細胞ROI"};
const message = (error:unknown) => error instanceof ApiError ? errorMessage(error) : error instanceof Error ? errorCodeMessage(error.message) : "処理できませんでした。";
const fingerprint = (value:unknown):string => JSON.stringify(value,(_,item) => item && typeof item === "object" && !Array.isArray(item) ? Object.fromEntries(Object.entries(item).sort(([a],[b])=>a.localeCompare(b))) : item);
export const sameRuntimeRecipe = (a:Recipe,b:Recipe) => fingerprint(a) === fingerprint(b);

/** Legacy marker records store an unused sigma; display the operation actually replayed. */
function visibleNucleolarSettings(settings:RuntimeSettings,processing:ProposalProcessing|null):RuntimeSettings {
  const child=processing?.nucleoli;
  return settings.nucleolarDefinition.source==="marker" && child?.channel===settings.nucleolarDefinition.marker
    && child.detector.engine==="cytellect-nucleolar-v2" && child.detector.source==="marker" && child.detector.protocol_version==="2.0.0"
    ? {...settings,nucleolarSigma:.7}:settings;
}

/** Existing explicit recipes only; a cell ROI is manual and never a GFP pixel component. */
export function runtimeRecipe(target:ReviewTarget,channel:ChannelDefinition,settings:RuntimeSettings,targets:RuntimeTargets,processing:ProposalProcessing|null):Recipe {
  if(target === "cell") return {id:"region-2d",version:"1.0.0",source:"manual",region_set_id:"cell",label:"細胞ROI",defining_channel_id:channel.token};
  if(target === "nuclei") {
    const base=nuclearRecipe(channel,settings.nuclearMaxSide);
    const saved=targets.nuclei?.recipe;
    if(saved?.defining_channel_id===channel.token && saved.nuclear_role_source)base.nuclear_role_source=saved.nuclear_role_source;
    const recipe=withProcessingSettings(base,processing);
    const detector=recipe.detector?.engine === "fiji-stardist-2d" ? recipe.detector : {engine:"fiji-stardist-2d" as const,model:"Versatile (fluorescent nuclei)" as const,percentile_low:1,percentile_high:99.8};
    return {...recipe,detector:{...detector,probability:settings.nuclearProbability,nms:settings.nuclearNms}};
  }
  const parent=targets.nuclei;
  if(!parent) throw new Error("先に核の領域を確定してください。");
  if(target === "nucleoplasm" && !targets.nucleoli) throw new Error("先に核小体を検出・確認してください。");
  return {...runtimeNucleolarRecipe(channel,settings,targets,processing),region_set_id:target,label:labels[target],compartment:target,
    nuclear_revision_id:parent.result.revision,nuclear_channel_id:parent.recipe.defining_channel_id,
    ...(target==="nucleoplasm"?{nucleolar_revision_id:targets.nucleoli!.result.revision}:{})};
}

/** Shared detector settings; parent revisions are attached only for execution. */
function runtimeNucleolarRecipe(channel:ChannelDefinition,settings:RuntimeSettings,targets:RuntimeTargets,processing:ProposalProcessing|null):Recipe {
  const definition=settings.nucleolarDefinition;
  const defining=definition.source === "dapi_poor" ? channel.token : definition.marker;
  if(!defining) throw new Error("核小体を定義するマーカーを指定してください。");
  const historical=targets.nucleoli?.recipe;
  if(!processing?.nucleoli && definition.source==="marker" && historical?.defining_channel_id===defining
    && historical.detector?.engine==="cytellect-nucleolar-v2" && historical.detector.source==="marker" && historical.detector.protocol_version==="2.0.0"){
    processing={...(processing??{version:"1.0.0",nuclei:null,nucleoli:null,signal:null}),nucleoli:{channel:defining,detector:historical.detector}};
  }
  const previous=processing?.nucleoli?.channel === defining ? processing.nucleoli.detector : undefined;
  const detector=definition.source === "ncl" ? previous?.engine === "fiji-nucleolar-compartments" ? previous : {engine:"fiji-nucleolar-compartments" as const,protocol_version:"1.1.0" as const,threshold_method:"otsu" as const,threshold:null,smoothing_sigma_px:0,minimum_area_px:1,maximum_area_px:null,split_touching:false}
    : {...nucleolarDetectorV2(definition),...(settings.nucleolarSigma !== null ? {smoothing_sigma_px:settings.nucleolarSigma}:{}),...(settings.nucleolarRim !== null ? {rim_exclusion_px:settings.nucleolarRim}:{}),...(settings.nucleolarMinimumArea !== null ? {minimum_area_px:settings.nucleolarMinimumArea}:{}),maximum_area_px:settings.nucleolarMaximumArea};
  const recipe:Recipe={id:"region-2d",version:"1.4.0",source:"fiji_nuclear_compartment",region_set_id:"nucleoli",label:labels.nucleoli,compartment:"nucleoli",defining_channel_id:defining,detector};
  const proposed=withProcessingSettings(recipe,processing);
  if(proposed.detector?.engine === "cytellect-nucleolar-v2") return {...proposed,detector:{...proposed.detector,relative_threshold:definition.relative,
    ...(settings.nucleolarSigma !== null && !(proposed.detector.source==="marker" && proposed.detector.protocol_version==="2.0.0") ? {smoothing_sigma_px:settings.nucleolarSigma}:{}),...(settings.nucleolarRim !== null ? {rim_exclusion_px:settings.nucleolarRim}:{}),
    ...(settings.nucleolarMinimumArea !== null ? {minimum_area_px:settings.nucleolarMinimumArea}:{}),maximum_area_px:settings.nucleolarMaximumArea}};
  if(proposed.detector?.engine === "fiji-nucleolar-compartments") return {...proposed,detector:{...proposed.detector,
    ...(settings.nucleolarSigma !== null ? {smoothing_sigma_px:settings.nucleolarSigma}:{}),
    ...(settings.nucleolarMinimumArea !== null ? {minimum_area_px:settings.nucleolarMinimumArea}:{}),maximum_area_px:settings.nucleolarMaximumArea}};
  return proposed;
}

/** The AI sees the same current controls and compatible historical detector used at execution. */
export function runtimeProposalProcessing(channel:ChannelDefinition,settings:RuntimeSettings,targets:RuntimeTargets,processing:ProposalProcessing|null):ProposalProcessing {
  const nucleus=runtimeRecipe("nuclei",channel,settings,targets,processing);
  const child=settings.nucleolarDefinition.source==="dapi_poor"||settings.nucleolarDefinition.marker?runtimeNucleolarRecipe(channel,settings,targets,processing):undefined;
  return savedProcessing(nucleus,child)!;
}
export function createWorkspaceRuntime(dependencies:Dependencies={}) {
  const adapter=dependencies.adapter ?? createApiAdapter(), loadPreview=dependencies.loadPreview ?? loadReviewPreview, releasePreview=dependencies.releasePreview ?? releaseReviewPreview;
  let state:RuntimeSnapshot={data:null,busy:false,operation:"",error:"",assignments:{version:0,assignments:[]},activeTarget:"nuclei",settings:defaultRuntimeSettings(),proposal:null,processing:null,importIssues:[]};
  const readSpecification=dependencies.readSpecification ?? ((id:string)=>request<RuntimeSpecification>(`/v1/workspaces/${id}/analysis-spec`));
  const writeSpecification=dependencies.writeSpecification ?? ((id:string,value:RuntimeSpecification)=>request<RuntimeSpecification>(`/v1/workspaces/${id}/analysis-spec`,{method:"PUT",body:JSON.stringify(value)}));
  let specification:RuntimeSpecification={version:0,spec:null},specificationDirty=false;
  let beforeProposal:{settings:RuntimeSettings;processing:ProposalProcessing|null;specification:RuntimeSpecification}|null=null;
  let closed=false,epoch=0,stopped=false,activeRunId:string|null=null;
  const runRequests=new Map<string,string>();
  let currentTargets=new Map<string,RuntimeTargets>(),registered=new Map<string,ImportedField>();
  const omeFiles=new Map<string,File>();
  const added:AddedFile[]=[],files=new Map<string,File>(),uploadKeys=new Map<string,string>(),uploaded=new Map<string,string>(),names=new Map<string,string>();
  const candidateStore=new Map<string,Partial<Record<ReviewTarget,RuntimeCandidate>>>();
  const histories=new Map<string,{undo:TargetResult[];redo:TargetResult[]}>(),listeners=new Set<()=>void>();
  function publish(patch:Partial<RuntimeSnapshot>){if(closed)return;state={...state,...patch};for(const listener of listeners)listener();}
  function replaceData(data:ReviewData){const previous=state.data;publish({data});if(previous && previous!==data)releasePreview(previous);}
  const workspace=()=>{if(!state.data?.workspaceId)throw new Error("画像を追加してください。");return state.data.workspaceId;};
  const history=(field:string,target:ReviewTarget)=>{const key=`${field}:${target}`;if(!histories.has(key))histories.set(key,{undo:[],redo:[]});return histories.get(key)!;};
  const definitions=(fieldId?:string):ChannelDefinition[]=>(fieldId?state.data?.fields.find(field=>field.id===fieldId)?.channels??[]:state.data?.channels??[]).map(value=>({token:value.id,stain:value.stain,role:value.role === "unused" ? null:value.role,evidence:"user"}));
  function nuclearChannel(fieldId?:string){let choices=definitions(fieldId).filter(value=>value.role === "nuclear");if(!choices.length && !state.assignments.version){const adopted=new Set(state.data?.fields.filter(field=>!fieldId||field.id===fieldId).map(field=>field.nuclearChannelId).filter(Boolean));if(adopted.size===1)choices=definitions(fieldId).filter(value=>adopted.has(value.token)).map(value=>({...value,role:"nuclear"}));}if(choices.length!==1)throw new Error("核検出に使うチャンネルを1つ指定してください。");return choices[0];}
  function bound(field:string,target:ReviewTarget,revision?:string){const result=currentTargets.get(field)?.[target];if(!result || (revision && result.result.revision!==revision))throw new Error("操作対象の解析版が変更されています。再読み込みしてください。");return result;}
  async function refresh(id?:string,restoreSettings=false){
    const ticket=++epoch;let next:ReviewData;
    try{next=await loadPreview(id || state.data?.workspaceId || undefined);}catch(error){if(error instanceof Error && error.message==="no_saved_workspace"){replaceData(emptyData());return;}throw error;}
    if(closed || ticket!==epoch){releasePreview(next);return;}
    try{
      const saved=await adapter.restore(next.workspaceId),assignments=await adapter.getChannelAssignments(next.workspaceId);
      const recordedSpecification=await readSpecification(next.workspaceId);
      if(closed || ticket!==epoch){releasePreview(next);return;}
      registered=new Map(saved.fields.map(field=>[field.id,field]));const targets=new Map<string,RuntimeTargets>();
      for(const field of next.fields){field.label=names.get(field.id)||field.label;const resultTargets:RuntimeTargets={};
        for(const target of ["nuclei","nucleoli","nucleoplasm","cell"] as const){const result=field.results[target];const recipe=saved.revisions.find(revision=>revision.id===result?.revision)?.config.recipe;if(result&&recipe){
          const revision=saved.revisions.find(value=>value.id===result.revision);
          const snapshot=(revision?.config as {field_snapshot?:Record<string,{image_info:{channels:Array<{channel_id:string;stain:string|null}>}}>})?.field_snapshot?.[field.id];
          if(snapshot && effectiveChannelAssignments(assignments,field.id).some(value=>snapshot.image_info.channels.some(channel=>channel.channel_id===value.channel_id && channel.stain!==value.stain))){delete field.results[target];field.error="染色設定が保存結果から変更されています。現在の設定で解析してください。";continue;}
          resultTargets[target]={result,recipe};
        }}
        const nuclear=effectiveChannelAssignments(assignments,field.id).find(value=>value.role==="nuclear")?.channel_id;
        const valid:RuntimeTargets={...validTargetResults(resultTargets,undefined,{nuclear}),...(resultTargets.cell?{cell:resultTargets.cell}:{})};
        if(assignments.version&&!nuclear){delete valid.nuclei;delete valid.nucleoli;delete valid.nucleoplasm;}
        for(const target of ["nuclei","nucleoli","nucleoplasm","cell"] as const)if(!valid[target])delete field.results[target];
        if(!valid.nuclei)delete field.nuclearChannelId;
        targets.set(field.id,valid);
      }
      currentTargets=targets;let settings=state.settings,processing=state.processing;
      if(restoreSettings){histories.clear();const first=[...targets.values()].find(value=>value.nuclei);processing=savedProcessing(first?.nuclei?.recipe,first?.nucleoli?.recipe);if(processing?.nuclei)settings={...settings,nuclearMaxSide:processing.nuclei.detection_max_side_px,nuclearProbability:processing.nuclei.detector.probability,nuclearNms:processing.nuclei.detector.nms};const child=processing?.nucleoli;if(child?.detector.engine==="cytellect-nucleolar-v2")settings={...settings,nucleolarDefinition:{...settings.nucleolarDefinition,source:child.detector.source,marker:child.detector.source==="marker"?child.channel:"",relative:child.detector.relative_threshold},nucleolarSigma:child.detector.smoothing_sigma_px,nucleolarRim:child.detector.rim_exclusion_px,nucleolarMinimumArea:child.detector.minimum_area_px,nucleolarMaximumArea:child.detector.maximum_area_px};}
      if(restoreSettings && processing?.nucleoli?.detector.engine==="fiji-nucleolar-compartments")settings={...settings,nucleolarDefinition:{...settings.nucleolarDefinition,source:"ncl",marker:processing.nucleoli.channel},nucleolarSigma:processing.nucleoli.detector.smoothing_sigma_px,nucleolarMinimumArea:processing.nucleoli.detector.minimum_area_px,nucleolarMaximumArea:processing.nucleoli.detector.maximum_area_px};
      if(restoreSettings && [...targets.values()].some(value=>value.nucleoplasm?.result.protocol==="4.0.0"))settings={...settings,background:"automatic"};
      specification=recordedSpecification;specificationDirty=false;
      if(restoreSettings && specification.spec){
        settings=specification.spec.settings;
        const historical=processing?.nucleoli;
        const preserveLegacyMarker=!specification.spec.processing && settings.nucleolarDefinition.source==="marker"
          && historical?.channel===settings.nucleolarDefinition.marker && historical.detector.engine==="cytellect-nucleolar-v2"
          && historical.detector.source==="marker" && historical.detector.protocol_version==="2.0.0";
        processing=preserveLegacyMarker?processing:specification.spec.processing;
      }
      settings=visibleNucleolarSettings(settings,processing);
      publish({assignments,settings,processing,activeTarget:recordedSpecification.spec?.target??state.activeTarget});replaceData(next);
    }catch(error){releasePreview(next);throw error;}
  }
  async function exclusive<T>(operation:string,task:()=>Promise<T>){if(state.busy)throw new Error("現在の処理が終わるまでお待ちください。");publish({busy:true,error:"",operation});try{return await task();}catch(error){publish({error:message(error)});throw error;}finally{publish({busy:false,operation:""});}}
  async function checkCurrent(){const id=workspace();if(!await adapter.isSelectionCurrent(id))throw new Error("別の画面で採用状態が変わりました。再読み込みしてください。");if((await adapter.getChannelAssignments(id)).version!==state.assignments.version)throw new Error("染色設定が変更されています。再読み込みしてください。");}
  function currentSpecification(target:ReviewTarget){
    return {...specification.spec,channel_assignment_version:state.assignments.version,target,settings:state.settings,processing:state.processing,
      measurement:state.settings.background === "confirmed_roi" ? null : state.settings.background === "automatic" ? automaticBackground : rawMeasurement};
  }
  async function persistSpecification(target:ReviewTarget){
    const spec=currentSpecification(target);
    if(!specificationDirty&&fingerprint(specification.spec)===fingerprint(spec))return;
    specification=await writeSpecification(workspace(),{version:specification.version,spec});specificationDirty=false;
  }
  function adopted(field:string,target:ReviewTarget,result:SavedResult,recipe:Recipe){const targets={...currentTargets.get(field)};if(target==="nuclei"){delete targets.nucleoli;delete targets.nucleoplasm;}if(target==="nucleoli")delete targets.nucleoplasm;targets[target]={result,recipe};currentTargets.set(field,targets);}
  function candidateSignature(field:string){return fingerprint({settings:state.settings,processing:state.processing,specVersion:specification.version,assignments:state.assignments.version,adopted:Object.fromEntries(Object.entries(currentTargets.get(field)??{}).map(([target,value])=>[target,value?.result.revision]))});}
  function candidate(field:string,target:ReviewTarget){const value=candidateStore.get(field)?.[target];return value?.settingsFingerprint===candidateSignature(field)?value:undefined;}
  async function acceptPrepared(field:string,target:ReviewTarget){
    if(!candidate(field,target))return false;
    const serverRun=candidate(field,target)?.runId;if(serverRun){const run=await adapter.waitWorkspaceRun(workspace(),serverRun);if(run.state!=="succeeded"&&run.state!=="adopted")return false;await adapter.acceptWorkspaceRun(workspace(),serverRun);rememberRunAdoption(run);candidateStore.delete(field);await refresh(workspace());return true;}
    const ordered:ReviewTarget[]=target==="cell"?["cell"]:target==="nuclei"?["nuclei"]:target==="nucleoli"?["nuclei","nucleoli"]:["nuclei","nucleoli","nucleoplasm"];
    const prepared=ordered.flatMap(key=>{const value=candidate(field,key);return value?[{key,value}]:[];});
    for(const {key,value} of prepared){const previous=currentTargets.get(field)?.[key];const result=await adapter.selectRevision(workspace(),value.result.revision,field);if(previous){history(field,key).undo.push(previous);history(field,key).redo=[];}adopted(field,key,result,value.recipe);}
    candidateStore.delete(field);publish({});return true;
  }
  async function runField(field:string,target:ReviewTarget,preview=false){
    if(!preview && await acceptPrepared(field,target))return;
    const input=registered.get(field);if(!input)throw new Error("登録した画像が見つかりません。");
    const channel=target==="cell"?definitions(field).find(value=>input.image_info.channels.some(plane=>plane.channel_id===value.token)):nuclearChannel(field);
    if(!channel)throw new Error("画像のチャンネルを選択してください。");
    const signature=candidateSignature(field),targets={...currentTargets.get(field)};
    if(preview)for(const key of ["nuclei","nucleoli","nucleoplasm","cell"] as const){const value=candidate(field,key);if(value)targets[key]={result:value.result,recipe:value.recipe};}
    const progress=(kind:string)=>(status:string)=>publish({operation:`${names.get(field)||state.data?.fields.find(value=>value.id===field)?.label||"視野"}：${kind} ${status==="queued"?"開始待ち":status==="running"?"検出・測定中":"結果を取得中"}`});
    async function perform(kind:ReviewTarget,recipe:Recipe){
      if(!input!.image_info.channels.some(value=>value.channel_id===recipe.defining_channel_id))throw new Error("検出用チャンネルの画像がありません。");
      const result=await adapter.run(workspace(),field,recipe,progress(labels[kind]),state.settings.background==="automatic"?automaticBackground:rawMeasurement,{adopt:!preview});
      if(preview){const values={...candidateStore.get(field)};if(kind==="nuclei"){delete values.nucleoli;delete values.nucleoplasm;}if(kind==="nucleoli")delete values.nucleoplasm;values[kind]={result,recipe,settingsFingerprint:signature};candidateStore.set(field,values);publish({});}
      else {const previous=currentTargets.get(field)?.[kind];if(previous){history(field,kind).undo.push(previous);history(field,kind).redo=[];}adopted(field,kind,result,recipe);}
      if(kind==="nuclei"){delete targets.nucleoli;delete targets.nucleoplasm;}if(kind==="nucleoli")delete targets.nucleoplasm;targets[kind]={result,recipe};
    }
    if(target==="cell"){if(!targets.cell)await perform("cell",runtimeRecipe("cell",channel,state.settings,targets,null));return;}
    const parentRecipe=runtimeRecipe("nuclei",channel,state.settings,targets,state.processing);
    if(!targets.nuclei||!sameRuntimeRecipe(targets.nuclei.recipe,parentRecipe))await perform("nuclei",parentRecipe);
    if(target==="nuclei")return;
    if(target==="nucleoplasm"&&!targets.nucleoli)await perform("nucleoli",runtimeRecipe("nucleoli",channel,state.settings,targets,state.processing));
    const recipe=runtimeRecipe(target,channel,state.settings,targets,state.processing),existing=targets[target];
    if(existing&&sameRuntimeRecipe(existing.recipe,recipe)&&(target!=="nucleoplasm"||(existing.result.protocol==="4.0.0")===(state.settings.background==="automatic")))return;
    await perform(target,recipe);
  }
  function rememberRunAdoption(run:WorkspaceRun){for(const step of run.steps){const previous=currentTargets.get(step.field_id)?.[step.target];if(previous&&previous.result.revision!==step.revision_id){history(step.field_id,step.target).undo.push(previous);history(step.field_id,step.target).redo=[];}}}
  async function readCandidates(run:WorkspaceRun){
    for(const step of run.steps){if(!step.revision_id||!step.recipe||!["succeeded","reused"].includes(step.state))continue;
      const result=await adapter.readResult(step.revision_id,step.field_id,step.recipe),values={...candidateStore.get(step.field_id)};
      values[step.target]={result,recipe:step.recipe,settingsFingerprint:candidateSignature(step.field_id),runId:run.id,runState:run.state,backgroundPending:step.background_pending};candidateStore.set(step.field_id,values);
    }
    if(state.data){const included=new Set(run.steps.map(step=>step.field_id));publish({data:{...state.data,fields:state.data.fields.map(field=>{
      if(!included.has(field.id))return field;
      const failures=run.steps.filter(step=>step.field_id===field.id&&(step.state==="failed"||step.state==="blocked")).map(step=>`解析処理：${labels[step.target]} — ${step.error||"依存する領域の処理が完了しませんでした。"}`);
      const existing=field.error?.split("\n").filter(value=>!value.startsWith("解析処理："))??[];
      return {...field,error:[...new Set([...existing,...failures])].join("\n")||undefined};
    })}});}else publish({});
  }
  async function recoverRun(){
    if(!state.data?.workspaceId||!("listWorkspaceRuns" in adapter))return;
    const runs=await adapter.listWorkspaceRuns(workspace());
    const latest=runs.filter(run=>run.spec_version===specification.version&&["queued","running","succeeded","failed","cancelled"].includes(run.state)).sort((a,b)=>b.created-a.created)[0];
    if(!latest)return;
    activeRunId=latest.id;
    try{const run=!["queued","running"].includes(latest.state)?latest:await adapter.waitWorkspaceRun(workspace(),latest.id,value=>publish({operation:`保存した処理を再開中：${value.steps.filter(step=>step.state==="succeeded"||step.state==="reused").length}/${value.steps.length}`}));await readCandidates(run);}
    finally{activeRunId=null;}
  }
  async function runServer(target:ReviewTarget,fieldId?:string,preview=false){
    const chosen=state.data!.fields.filter(field=>!field.exclusionReason&&(!fieldId||field.id===fieldId));if(!chosen.length)throw new Error("解析する画像を選択してください。");
    if(!preview&&chosen.length===1&&candidate(chosen[0].id,target)?.runId&&candidate(chosen[0].id,target)?.runState==="succeeded"&&!candidate(chosen[0].id,target)?.backgroundPending){await acceptPrepared(chosen[0].id,target);return;}
    await persistSpecification(target);if(!preview)publish({activeTarget:target});stopped=false;
    const key=fingerprint({workspace:workspace(),version:specification.version,target,purpose:preview?"preview":"measurement",fields:chosen.map(field=>({id:field.id,signature:candidateSignature(field.id)}))});
    if(!runRequests.has(key))runRequests.set(key,crypto.randomUUID());
    const created=await adapter.startWorkspaceRun(workspace(),{request_id:runRequests.get(key)!,spec_version:specification.version,target,field_ids:chosen.map(field=>field.id),purpose:preview?"preview":"measurement"});
    activeRunId=created.id;
    try{const run=await adapter.waitWorkspaceRun(workspace(),created.id,value=>publish({operation:`${value.steps.filter(step=>step.state==="succeeded"||step.state==="reused").length}/${value.steps.length}：検出・測定中`}));
      await readCandidates(run);
      if(run.state==="cancelled"){runRequests.delete(key);throw new Error("処理を中止しました。採用済みの領域は保持されています。");}
      if(run.state==="failed"){runRequests.delete(key);throw new Error(run.steps.filter(step=>step.error).map(step=>`${state.data?.fields.find(field=>field.id===step.field_id)?.label||"視野"}：${step.error}`).join("\n"));}
      if(!preview){await adapter.acceptWorkspaceRun(workspace(),run.id);rememberRunAdoption(run);for(const field of chosen)candidateStore.delete(field.id);await refresh(workspace());}
    }finally{activeRunId=null;}
  }
  async function runInternal(target:ReviewTarget,fieldId?:string,preview=false){
    await checkCurrent();
    if("startWorkspaceRun" in adapter){await runServer(target,fieldId,preview);return;}
    await persistSpecification(target);if(!preview)publish({activeTarget:target});stopped=false;
    const fields=state.data!.fields.filter(field=>!field.exclusionReason&&(!fieldId||field.id===fieldId));if(!fields.length)throw new Error("解析する画像を選択してください。");
    const failures:string[]=[];for(const field of fields){if(stopped||closed)break;try{await runField(field.id,target,preview);}catch(error){failures.push(`${field.label}：${message(error)}`);}}
    if(!preview)await refresh(workspace());if(failures.length)throw new Error(failures.join("\n"));
  }
  function applyProposal(fieldId?:string){
    if(!state.proposal)throw new Error("解析案がありません。");const channels=definitions(fieldId);try{const nucleus=nuclearChannel(fieldId),index=channels.findIndex(value=>value.token===nucleus.token);if(index>=0)channels[index]=nucleus;}catch{}
    const hasImages=!!state.data?.fields.length,automatic=hasImages&&["nuclear-intensity","nuclear-ncl"].includes(state.proposal.draft.recipe),processing=automatic?applicableProcessing(state.proposal,channels):null;if(automatic&&!processing?.nuclei)throw new Error("核のチャンネルを確認してから解析案を適用してください。");
    if(hasImages&&state.proposal.draft.recipe==="supplied-regions"){const cell=fieldId?currentTargets.get(fieldId)?.cell:undefined;if(cell?.recipe.source!=="manual"||cell.recipe.region_set_id!=="cell"||!cell.result.masks.regions.length)throw new Error("選択視野の採用済み細胞ROIを確認してください。");}
    let settings=processing?.nuclei?{...state.settings,nuclearMaxSide:processing.nuclei.detection_max_side_px,nuclearProbability:processing.nuclei.detector.probability,nuclearNms:processing.nuclei.detector.nms}:{...state.settings};
    const child=processing?.nucleoli;if(child?.detector.engine==="cytellect-nucleolar-v2")settings={...settings,nucleolarDefinition:{...settings.nucleolarDefinition,source:child.detector.source,marker:child.detector.source==="marker"?child.channel:"",relative:child.detector.relative_threshold},nucleolarSigma:child.detector.smoothing_sigma_px,nucleolarRim:child.detector.rim_exclusion_px,nucleolarMinimumArea:child.detector.minimum_area_px,nucleolarMaximumArea:child.detector.maximum_area_px};else if(child)settings={...settings,nucleolarDefinition:{...settings.nucleolarDefinition,source:"ncl",marker:child.channel},nucleolarSigma:child.detector.smoothing_sigma_px,nucleolarMinimumArea:child.detector.minimum_area_px,nucleolarMaximumArea:child.detector.maximum_area_px};
    settings=visibleNucleolarSettings(settings,processing);
    beforeProposal={settings:state.settings,processing:state.processing,specification:structuredClone(specification)};
    const draft=state.proposal.draft as ValidatedProposal["draft"] & {background?:{mode:RuntimeSettings["background"]}|null;gfp_selection?:{channel:string;unit:"nucleus"|"cell_roi";method:"manual"|"batch_otsu"|"negative_control";threshold:number|null;values:"raw"|"corrected";keep:"positive"|"negative";percentile:number}|null}, metrics=hasImages?draft.metrics:draft.metrics.filter(value=>value.channel===null), first=metrics[0], firstFigure=draft.figures.find(value=>hasImages||value.channel===null);
    const metricMap:Record<string,string>={area:"area_px",mean_raw:"mean",integral_raw:"integrated",integral_corrected:"integrated_corrected"};
    const metric=first?(metricMap[first.metric]??first.metric):null;
    if(draft.background)settings={...settings,background:draft.background.mode};
    const prior=specification.spec;
    const priorSelection=prior?.selection&&typeof prior.selection==="object"?prior.selection as Record<string,unknown>:{};
    let selection=priorSelection;
    const gate=draft.gfp_selection;
    if(gate&&hasImages){
      const previousGate=priorSelection.gfp&&typeof priorSelection.gfp==="object"?priorSelection.gfp as Record<string,unknown>:{};
      if(gate.method==="negative_control"&&gate.unit==="nucleus"){
        const controls=previousGate.control_field_ids;
        if(Array.isArray(controls)&&controls.length)selection={...priorSelection,gfp:{version:"1.0.0",gate_protocol:"gfp-gate/2.0.0",gfp_channel_id:gate.channel,percentile:gate.percentile,control_field_ids:controls,keep:gate.keep}};
      }else if(gate.method!=="negative_control")selection={...priorSelection,gfp:{...(gate.unit==="cell_roi"?{unit:"cell_roi"}:{}),version:"1.1.0",gate_protocol:"gfp-gate/3.0.0",gfp_channel_id:gate.channel,method:gate.method,threshold:gate.threshold,values:gate.values,keep:gate.keep}};
    }
    const statistical=prior?.statistics&&typeof prior.statistics==="object"?prior.statistics:{};
    const figure=prior?.figure&&typeof prior.figure==="object"?prior.figure:{};
    const target:ReviewTarget=draft.recipe==="supplied-regions"?"cell":draft.recipe==="none"?(prior?.target??state.activeTarget):first?.region==="nucleoplasm"||["ncl_log2_nucleoplasm_over_nucleoli","nucleolar_area_fraction","nucleolar_count"].includes(first?.metric??"")?"nucleoplasm":first?.region==="nucleoli"?"nucleoli":processing?.nucleoli?"nucleoli":"nuclei";
    specificationDirty=true;specification={...specification,spec:{...prior,channel_assignment_version:state.assignments.version,target,settings,processing:automatic?processing?{...processing,signal:null}:null:state.processing,measurement:settings.background==="confirmed_roi"?null:settings.background==="automatic"?automaticBackground:rawMeasurement,
      metrics,selection,additional_analyses:draft.additional_analyses??[],figure_proposals:draft.figures,
      statistics:{...statistical,method:draft.statistics,...(metric?{metric,channel_id:first.channel}: {}),...(draft.statistics.y?{metric:metricMap[draft.statistics.y.metric]??draft.statistics.y.metric,channel_id:draft.statistics.y.channel}:{}),...(draft.statistics.x?{x_metric:metricMap[draft.statistics.x.metric]??draft.statistics.x.metric,x_channel_id:draft.statistics.x.channel}:{x_metric:null,x_channel_id:null})},
      ...(firstFigure?{figure:{...figure,metric:metricMap[firstFigure.metric]??firstFigure.metric,channel_id:firstFigure.channel}}:{})}};
    publish({processing:automatic?processing?{...processing,signal:null}:null:state.processing,settings,activeTarget:target});
  }
  async function showImported(saved:ImportedField,key:string){uploaded.set(key,saved.id);names.set(saved.id,key.split("/").at(-1)||key);registered.set(saved.id,saved);const partial=await loadPreview(workspace(),[saved.id]);const freshField=partial.fields.find(value=>value.id===saved.id);if(freshField&&state.data){freshField.label=names.get(saved.id)||freshField.label;const retained=state.data.fields.filter(value=>value.id!==saved.id);const previous=state.data.fields.find(value=>value.id===saved.id);if(previous)releasePreview({...partial,fields:[previous]});const channels=[...state.data.channels];for(const channel of freshField.channels)if(!channels.some(value=>value.id===channel.id))channels.push(channel);publish({data:{...state.data,fields:[...retained,freshField],channels},operation:`${uploaded.size} 視野を登録済み`});}
  }
  async function travel(field:string,target:ReviewTarget,direction:"undo"|"redo"){return exclusive(direction==="undo"?"前の版に戻しています":"次の版を採用しています",async()=>{await checkCurrent();const stack=history(field,target),destination=stack[direction].at(-1);if(!destination)return;const previous=bound(field,target),result=await adapter.selectRevision(workspace(),destination.result.revision,field);stack[direction].pop();stack[direction==="undo"?"redo":"undo"].push(previous);adopted(field,target,result,destination.recipe);await refresh(workspace());});}
  return {
    adapter,subscribe(listener:()=>void){listeners.add(listener);return()=>{listeners.delete(listener);};},getSnapshot:()=>state,
    async load(id?:string){closed=false;publish({busy:true,error:"",operation:"画像と保存結果を読み込み中"});try{await refresh(id,true);await recoverRun();}catch(error){publish({error:message(error)});throw error;}finally{publish({busy:false,operation:""});}},
    reload(){return exclusive("保存結果を再読み込み中",async()=>{await refresh(workspace(),true);await recoverRun();});},
    newWorkspace(){if(state.busy)throw new Error("現在の処理が終わるまでお待ちください。");++epoch;beforeProposal=null;runRequests.clear();added.length=0;omeFiles.clear();files.clear();uploadKeys.clear();uploaded.clear();names.clear();histories.clear();candidateStore.clear();currentTargets.clear();registered.clear();specification={version:0,spec:null};publish({assignments:{version:0,assignments:[]},activeTarget:"nuclei",settings:defaultRuntimeSettings(),processing:null,proposal:null,error:"",importIssues:[]});replaceData(emptyData());},
    dispose(){closed=true;++epoch;if(state.data)releasePreview(state.data);},
    setSettings(value:RuntimeSettings|((previous:RuntimeSettings)=>RuntimeSettings)){if(!state.busy)publish({settings:typeof value==="function"?value(state.settings):value});},
    setNucleolarSigma(value:number|null){
      if(state.busy)return;
      const settings={...state.settings,nucleolarSigma:value},definition=settings.nucleolarDefinition;
      let processing=state.processing;
      if(definition.source==="marker" && definition.marker){
        const previous=processing?.nucleoli?.channel===definition.marker?processing.nucleoli.detector:null;
        const detector=previous?.engine==="cytellect-nucleolar-v2" && previous.source==="marker"?previous:nucleolarDetectorV2(definition);
        processing={...(processing??{version:"1.0.0",nuclei:null,nucleoli:null,signal:null}),nucleoli:{channel:definition.marker,
          detector:{...detector,source:"marker",protocol_version:"2.1.0",smoothing_sigma_px:value??.7}}};
      }
      publish({settings,processing});
    },
    saveSettings(target:ReviewTarget=specification.spec?.target || "nuclei"){return exclusive("解析条件を保存中",async()=>{await checkCurrent();await persistSpecification(target);});},
    specification:()=>specification,
    ensureWorkspace(){return exclusive("ワークスペースを準備中",async()=>{if(state.data?.workspaceId)return state.data.workspaceId;const created=await adapter.create();replaceData({...emptyData(),workspaceId:created.id,title:created.title});return created.id;});},
    saveResultDraft(draft:{statistics?:unknown;figure?:unknown;additional_analyses?:unknown[];figure_proposals?:unknown[]}){return exclusive("統計・図の条件を保存中",async()=>{await checkCurrent();const spec={...currentSpecification(specification.spec?.target??state.activeTarget),...draft};specification=await writeSpecification(workspace(),{version:specification.version,spec});specificationDirty=false;publish({});});},
    saveBackgrounds(backgrounds:Record<string,Record<string,{polygon:Point[];confirmed:true}>>,confirmed_channel_ids:string[]){return exclusive("背景領域を保存中",async()=>{await checkCurrent();publish({settings:{...state.settings,background:"confirmed_roi"}});specificationDirty=true;specification={...specification,spec:{...(specification.spec??{channel_assignment_version:state.assignments.version,target:state.activeTarget,settings:state.settings,processing:state.processing,measurement:null}),backgrounds,confirmed_channel_ids}};await persistSpecification(state.activeTarget);publish({});});},
    saveSelection(selection:unknown){return exclusive("対象選択を保存中",async()=>{await checkCurrent();await persistSpecification(specification.spec?.target??state.activeTarget);specification=await writeSpecification(workspace(),{...specification,spec:{...specification.spec!,selection}});publish({});});},
    resultRecipe(field:string,target:ReviewTarget){return currentTargets.get(field)?.[target]?.recipe;},canUndo(field:string,target:ReviewTarget){return history(field,target).undo.length>0;},canRedo(field:string,target:ReviewTarget){return history(field,target).redo.length>0;},stop(){stopped=true;if(activeRunId)void adapter.cancelWorkspaceRun(workspace(),activeRunId).catch(error=>publish({error:message(error)}));},
    importFiles(list:FileList|File[],mode:"automatic"|"single"="automatic"){return exclusive("画像を登録中",async()=>{stopped=false;
      // A batch has its own identity: names in a later drop cannot overwrite earlier pixels.
      const batch=`import-${crypto.randomUUID()}`,fresh:AddedFile[]=[];
      for(const file of Array.from(list)){
        const originalPath=file.webkitRelativePath||file.name;if(!isSupportedImage(originalPath))continue;
        if(file.size>256*1024*1024)throw new Error("画像ファイルは256 MiB以下にしてください。");
        const digest=await crypto.subtle.digest("SHA-256",await file.arrayBuffer()),sha256=Array.from(new Uint8Array(digest),value=>value.toString(16).padStart(2,"0")).join("");

        let path=`${batch}/${originalPath}`;
        if(fresh.some(value=>value.path===path))path=`${batch}/image-${crypto.randomUUID()}/${originalPath}`;
        if(await tiffHasOmeMetadata(file))omeFiles.set(path,file);else fresh.push({path,size:file.size,sha256,inputMode:await tiffInputMode(file)});files.set(path,file);
      }
      if(!fresh.length&&!added.length&&!omeFiles.size)throw new Error("TIFF画像を選択してください。");added.push(...fresh);const grouping=groupFiles(added,mode);publish({importIssues:grouping.issues});if(grouping.issues.some(value=>value.kind==="duplicate_channel"))throw new Error("同じ視野・チャンネルの画像が複数あります。画像の対応を確認してください。");
      if(!state.data?.workspaceId){const created=await adapter.create();replaceData({...emptyData(),workspaceId:created.id,title:created.title});}else await checkCurrent();
      try { for(const field of grouping.fields){if(stopped||closed)break;if(uploaded.has(field.key))continue;if(!uploadKeys.has(field.key))uploadKeys.set(field.key,crypto.randomUUID());const key=uploadKeys.get(field.key)!;await adapter.registerImport(workspace(),key);const saved=await adapter.upload(workspace(),field,grouping.channels.filter(channel=>field.files[channel.token]),files,key);await showImported(saved,field.key);} for(const [key,file] of omeFiles){if(stopped||closed)break;if(uploaded.has(key))continue;if(!uploadKeys.has(key))uploadKeys.set(key,crypto.randomUUID());const entry=uploadKeys.get(key)!;await adapter.registerImport(workspace(),entry);await showImported(await adapter.uploadOme(workspace(),file,entry),key);} } finally {await refresh(workspace());}
    });},
    saveAssignments(assignments:ChannelAssignment[],fieldId?:string){return exclusive("染色設定を保存中",async()=>{
      const selected=fieldId?registered.get(fieldId):null;
      if(fieldId&&!selected)throw new Error("登録した画像が見つかりません。");
      const configuration=(field:ImportedField)=>fingerprint({mode:field.image_info.input_mode??"native",channels:field.image_info.channels.map(channel=>channel.channel_id).sort()});
      const field_ids=selected?[...registered.values()].filter(field=>configuration(field)===configuration(selected)).map(field=>field.id):undefined;
      await adapter.saveChannelAssignments(workspace(),{version:state.assignments.version,assignments,...(field_ids?{field_ids}:{})});histories.clear();publish({proposal:null,processing:null});await refresh(workspace());
    });},
    saveFieldLink(fieldId:string,kind:"analysis"|"reference",referenceFor:string|null=null){return exclusive("画像の対応を保存中",async()=>{await checkCurrent();const links=await adapter.getFieldLinks(workspace());await adapter.saveFieldLink(workspace(),fieldId,{version:links.version,selection_version:adapter.selection()?.version??0,kind,reference_for_field_id:referenceFor});await refresh(workspace());});},
    candidates:candidate, candidateResult(field:string,target:ReviewTarget){return candidate(field,target)?.result;},
    preview(field:string,target:ReviewTarget){return exclusive("候補をプレビュー中",()=>runInternal(target,field,true));},
    acceptCandidates(field:string,target:ReviewTarget){return exclusive("候補を採用中",async()=>{await checkCurrent();if(!await acceptPrepared(field,target))throw new Error("現在の条件に一致する候補がありません。");await refresh(workspace());});},
    run(target:ReviewTarget,fieldId?:string){return exclusive(`${labels[target]}を解析中`,()=>runInternal(target,fieldId));},
    editMask(field:string,target:ReviewTarget,expectedRevision:string,operation:MaskOperation,polygon:Point[],region?:number,merged:number[]=[]){return exclusive("領域を保存・再測定中",async()=>{if(target==="nucleoplasm")throw new Error("核質は核と核小体から計算します。");await checkCurrent();const source=bound(field,target,expectedRevision),result=await adapter.editMask(workspace(),source.result,source.recipe,operation,polygon,region,merged);history(field,target).undo.push(source);history(field,target).redo=[];adopted(field,target,result,source.recipe);await refresh(workspace());});},
    correct(field:string,target:ReviewTarget,expectedRevision:string,kind:"delete"|"exclude",region:number){return exclusive("領域を更新中",async()=>{if(target==="nucleoplasm"&&kind==="delete")throw new Error("核質のマスクは直接変更できません。");await checkCurrent();const source=bound(field,target,expectedRevision),result=await adapter.correct(workspace(),source.result,kind,region,source.recipe);history(field,target).undo.push(source);history(field,target).redo=[];adopted(field,target,result,source.recipe);await refresh(workspace());});},
    undo(field:string,target:ReviewTarget){return travel(field,target,"undo");},redo(field:string,target:ReviewTarget){return travel(field,target,"redo");},
    excludeField(field:string,reason:string|null){return exclusive("解析対象を更新中",async()=>{await checkCurrent();const entry=adapter.selection()?.entries.find(value=>value.field_id===field);if(!entry)throw new Error("保存した視野の登録状態を確認できません。");await adapter.excludeField(workspace(),entry.id,reason);await refresh(workspace());});},
    applyProposal,canUndoProposal:()=>beforeProposal!==null,
    undoProposal(){return exclusive("AI適用前の条件に戻しています",async()=>{await checkCurrent();if(!beforeProposal)return;const previous=beforeProposal;publish({settings:previous.settings,processing:previous.processing,activeTarget:previous.specification.spec?.target??"nuclei"});specificationDirty=true;specification={...specification,spec:previous.specification.spec};await persistSpecification(state.activeTarget);beforeProposal=null;candidateStore.clear();publish({});});},
    requestProposal(goal:string,selectedFieldId?:string){return exclusive("AIが解析条件を確認中",async()=>{if(!state.data?.fields.length&&!goal.trim())throw new Error("画像を追加するか、解析したいことを入力してください。");if(!state.data?.workspaceId){const created=await adapter.create();replaceData({...emptyData(),workspaceId:created.id,title:created.title});}await checkCurrent();await persistSpecification(state.activeTarget);const field=selectedFieldId||state.data?.fields.find(value=>!value.exclusionReason)?.id;let currentProcessing:ProposalProcessing|null=null;if(field){try{currentProcessing=runtimeProposalProcessing(nuclearChannel(field),state.settings,currentTargets.get(field)??{},state.processing);}catch{currentProcessing=null;}}const response=await adapter.draft(workspace(),goal,false,{current_processing:currentProcessing,previous_goal:"",previous_proposal:state.proposal?.draft??null,...(selectedFieldId?{field_id:selectedFieldId}:{})});publish({proposal:response.proposal});if(!state.data?.fields.length||response.proposal.draft.recipe==="none"){applyProposal(field);await persistSpecification(state.activeTarget);return response.proposal;}if(!field)throw new Error("プレビューする画像を選択してください。");applyProposal(field);await runInternal(state.activeTarget,field,true);return response.proposal;});},
  };
}

export function useWorkspaceRuntime(initialWorkspaceId?:string){const [runtime]=useState(()=>createWorkspaceRuntime());const state=useSyncExternalStore(runtime.subscribe,runtime.getSnapshot,runtime.getSnapshot);useEffect(()=>{void runtime.load(initialWorkspaceId).catch(()=>{});return()=>runtime.dispose();},[runtime,initialWorkspaceId]);return {...state,...runtime,workspaceId:state.data?.workspaceId||undefined};}
