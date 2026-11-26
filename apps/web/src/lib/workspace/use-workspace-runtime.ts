"use client";
import {useEffect, useState, useSyncExternalStore} from "react";
import {ApiError, errorCodeMessage, errorMessage, request} from "../api";
import type {Point} from "../types";
import type {PrimaryOutcome} from "./primary-outcome";
import {automaticBackground, createApiAdapter, nuclearRecipe, rawMeasurement, type ChannelAssignment, type ChannelAssignments, type AssistantMessage, type ImportedField, type IntakeRecord, type IntakeTarget, type SelectionEntry, type MaskOperation, type Recipe, type SavedResult, type ValidatedProposal, type WorkspaceRun} from "./api-adapter";
import {rememberGoal} from "./ai-settings";
import type {Suggestion} from "./assignment-suggestions";
import {effectiveChannelAssignments} from "./channel-assignments";
import {intakePath} from "./dropped-files";
import {groupFiles, isSupportedImage, type AddedFile, type ChannelDefinition, type Grouping} from "./grouping";
import {nclObjectDetector,nucleolarDetectorV2, type NucleolarDefinition} from "./nucleolar-definition";
import {cellposeDetector,nclCellposeDetector,isCellposeDetector,selectNclModel,type AnyCellposeProcessingDetector,type NclParentCellposeProcessingDetector} from "./cellpose-settings";
import {applicableProcessing, preserveNclModelSelection, savedProcessing, withProcessingSettings, type ProposalProcessing} from "./proposal-processing";
import {loadReviewPreview, newestWorkspaceId, releaseReviewPreview, type ReviewData, type ReviewTarget} from "./review-preview";
import {validTargetResults, type TargetResult} from "./target-results";
import {tiffInputMode,tiffHasOmeMetadata} from "./tiff-intake";
import {assignFields,labelProblem,openingPair,type ExperimentDesign} from "./experiment-design";
import {completedFields,fieldProgress,progressLine,type FieldProgress} from "./run-progress";

export interface RuntimeSettings {
  nuclearMaxSide: number | null; nuclearProbability: number; nuclearNms: number;
  nucleolarDefinition: NucleolarDefinition;
  cellDefinition?: {source:"manual"|"cellpose";channel:string};
  nucleolarSigma: number | null; nucleolarRim: number | null; nucleolarMinimumArea: number | null; nucleolarMaximumArea: number | null;
  background: "raw" | "automatic" | "confirmed_roi";
}
export const defaultRuntimeSettings = (): RuntimeSettings => ({nuclearMaxSide:null,nuclearProbability:.5,nuclearNms:.3,
  nucleolarDefinition:{source:"dapi_poor",marker:"",pixelUm:null,relative:.7,algorithm:null},cellDefinition:{source:"manual",channel:""},nucleolarSigma:null,nucleolarRim:null,nucleolarMinimumArea:null,nucleolarMaximumArea:null,background:"raw"});
const normalizedRuntimeSettings=(settings:RuntimeSettings):RuntimeSettings=>({...defaultRuntimeSettings(),...settings,
  nucleolarDefinition:{...defaultRuntimeSettings().nucleolarDefinition,...settings.nucleolarDefinition},cellDefinition:settings.cellDefinition??{source:"manual",channel:""}});
export interface RuntimeSnapshot {
  data: ReviewData | null; busy: boolean; operation: string; error: string; assignments: ChannelAssignments;
  /** True while fields and saved results load (nothing to stop; analyses wait). */
  loading: boolean;
  activeTarget: ReviewTarget; settings: RuntimeSettings; proposal: ValidatedProposal | null; processing: ProposalProcessing | null; importIssues: Grouping["issues"];
  /** Saved rows of images that did not become a field (#284): they stay named after a restart. */
  intakeRows: IntakeRow[];
  /** What the last addition of images did, including what it did not register (no saved row). */
  intake: IntakeOutcome | null;
  /** The researcher's messages to the AI in this workspace and what came back (#284 W2), oldest first. */
  messages: AssistantMessage[];
  /** Each field's state in the current or last analysis run (#284 W8); absent for fields outside it. */
  progress: Record<string, FieldProgress>;
  /** Run and group suggestions from the latest AI answer that made any (#284 W7). Shown in the experiment table and
   * saved only by the researcher's 「案を適用」; nothing here changes the design. */
  assignmentSuggestions: Suggestion[];
}
/** What an answer received in this session offers (#284 W7, plan 5.6): the kind of request, the fields a run covers,
 * the items to confirm, and how many assignment suggestions it made. `intent` null is an earlier draft. */
/** `applies`: the answer carries an analysis or processing settings (something 「設定を適用」 would apply). */
export interface AnswerView {intent: "answer" | "settings" | "run" | null; scope: "selected" | "all" | null; choices: Array<{question: string; options: string[]}>; assignments: number; applies: boolean}
/** The fields 「適用して実行」 runs: the selected one, or every registered field the researcher has not excluded. */
/** A channel an answer proposes as the nuclear stain, awaiting the researcher's own choice. */
export interface ChannelConfirmation {channel: string; label: string}
export interface RunTargets {scope: "selected" | "all"; fields: Array<{id: string; label: string}>; excluded: number}
/** A saved row without a field. `legacy` rows come from before rows carried names (#284). */
export interface IntakeRow {entry:string; names:string[]; state:"pending"|"rejected"|"legacy"; code:string|null; mask:boolean; target:IntakeTarget|null}
/** The result of adding images, item by item (#284 implementation plan, section 5.4): one item's failure is not the batch's. */
export interface IntakeOutcome {
  registered: Array<{fieldId:string; names:string[]}>;
  /** entry is null when no row could be written (the record is full). */
  /** `stage: "inspect"`: the judgement before adding found the file unreadable (never a mask candidate). */
  rejected: Array<{entry:string|null; names:string[]; code:string; stage?:"inspect"|"register"}>;
  /** 実行を中止 ended the addition: the fields not sent stay in the list of chosen files. */
  stopped?: boolean;
  /** Two different images name the same field and channel: the field waits for the researcher (not sent). */
  held: Array<{names:string[]; reason:"duplicate_channel"}>;
  /** Same bytes as another image: not a field unless the researcher records it as a separate acquisition. */
  duplicates: Array<{id:string; name:string; sameAs:string}>;
  /** Not a TIFF. */
  skipped: Array<{name:string}>;
  /** The selection held no file at all, or no TIFF (shown so a choice never ends silently). */
  empty?: "nothing" | "no_images";
}
/** The addition could not go on (no answer, ended session, changed workspace); the outcome holds what was done. */
/** A row is a mask candidate only when registration refused a 32-bit image the judgement before adding did not
 * see. A file that judgement found unreadable (a float or signed image shares the reason code) is a missing image. */
export function isMaskRow(intake:IntakeRecord|undefined|null):boolean{return !!intake&&intake.code===MASK_CANDIDATE_CODE&&intake.stage!=="inspect";}
/** A name as a row can hold it (255 characters, no control characters): a longer folder-relative path keeps its file name. */
function recordedName(name:string):string{const clean=name.replace(/[\u0000-\u001f\u007f]/g,"_");return clean.length<=255?clean:(clean.split("/").at(-1)||clean).slice(-255);}
/** The cause of an `IntakeInterrupted` that 実行を中止 raised: the researcher's own action, reported as a status. */
export const ADD_STOPPED="追加：中止";
/** Shown when a nuclear detection is asked for while no chosen field has a nuclear stain; the screen offers 設定 with it. */
export const NUCLEAR_STAIN_REQUIRED="核の検出には、核染色の指定が必要です。";
/** A field's failure in a run of several fields when it has no nuclear stain; the screen offers 設定 with it too. */
export const NUCLEAR_STAIN_MISSING="核染色の指定なし";
export class IntakeInterrupted extends Error {constructor(public outcome:IntakeOutcome, public cause:unknown){super(message(cause));}}
/** The bit depth the API refuses as an image: a 32-bit integer label image (a mask), not missing data (#284 input 5). */
export const MASK_CANDIDATE_CODE="region_image_bit_depth_unsupported";
const FIELD_FILE_LIMIT=256*1024*1024,LEDGER_LIMIT=100;
const emptyOutcome=():IntakeOutcome=>({registered:[],rejected:[],held:[],duplicates:[],skipped:[]});
const hex=(digest:ArrayBuffer)=>Array.from(new Uint8Array(digest),value=>value.toString(16).padStart(2,"0")).join("");
/** A refusal of this item only: the next field can still be sent. Anything else stops the addition. */
const itemRefusal=(error:unknown):error is ApiError=>error instanceof ApiError&&(error.status===422||error.status===413||error.code==="region_upload_id_conflict"||error.code==="unregistered_upload");
type Adapter = ReturnType<typeof createApiAdapter>;
export interface RuntimeCandidate {result:SavedResult;recipe:Recipe;settingsFingerprint:string;runId?:string;runState?:WorkspaceRun["state"];backgroundPending?:boolean}
type RuntimeTargets = Partial<Record<ReviewTarget, TargetResult>>;
export interface RuntimeSpecification {version:number; experiment_sha256?:string; spec:({channel_assignment_version:number;target:ReviewTarget;settings:RuntimeSettings;processing:ProposalProcessing|null;measurement:typeof rawMeasurement|null;selection?:unknown;statistics?:unknown;figure?:unknown;metrics?:unknown[];additional_analyses?:unknown[];figure_proposals?:unknown[];figure_presentation?:unknown;experiment?:ExperimentDesign|null;backgrounds?:Record<string,Record<string,{polygon:Point[];confirmed:true}>>;confirmed_channel_ids?:string[]})|null}

type Dependencies = {adapter?:Adapter; loadPreview?:typeof loadReviewPreview; releasePreview?:typeof releaseReviewPreview;
  readSpecification?:(workspace:string)=>Promise<RuntimeSpecification>; writeSpecification?:(workspace:string,value:RuntimeSpecification)=>Promise<RuntimeSpecification>};
const emptyData = (): ReviewData => ({workspaceId:"",title:"画像解析",fields:[],channels:[]});
const labels = {nuclei:"核",nucleoli:"核小体",nucleoplasm:"核質",cell:"細胞ROI"};
const message = (error:unknown) => error instanceof ApiError ? errorMessage(error) : error instanceof Error ? errorCodeMessage(error.message) : "処理できませんでした。";
// Each import gets a private batch folder; researchers only ever see their own relative path.
const shownPath = (path:string) => path.replace(/^import-[0-9a-f-]+\/(?:image-[0-9a-f-]+\/)?/,"");
const shownIssue = (issue:Grouping["issues"][number]):Grouping["issues"][number] => ({...issue,
  ..."path" in issue?{path:shownPath(issue.path)}:{},..."paths" in issue?{paths:issue.paths.map(shownPath)}:{},..."field" in issue?{field:shownPath(issue.field)}:{}});
const fingerprint = (value:unknown):string => JSON.stringify(value,(_,item) => item && typeof item === "object" && !Array.isArray(item) ? Object.fromEntries(Object.entries(item).sort(([a],[b])=>a.localeCompare(b))) : item);
// The API stores an absent nucleolar parent as null (RegionCompartmentRecipe); the client omits it.
const comparableRecipe = (recipe:Recipe) => {const {nucleolar_revision_id,...rest}=recipe as Recipe&{nucleolar_revision_id?:string|null};return nucleolar_revision_id==null?rest:recipe;};
export const sameRuntimeRecipe = (a:Recipe,b:Recipe) => fingerprint(comparableRecipe(a)) === fingerprint(comparableRecipe(b));

/** Legacy marker records store an unused sigma; display the operation actually replayed. */
function visibleNucleolarSettings(settings:RuntimeSettings,processing:ProposalProcessing|null):RuntimeSettings {
  const child=processing?.nucleoli;
  return settings.nucleolarDefinition.source==="marker" && child?.channel===settings.nucleolarDefinition.marker
    && child.detector.engine==="cytellect-nucleolar-v2" && child.detector.source==="marker" && child.detector.protocol_version==="2.0.0"
    ? {...settings,nucleolarSigma:.7}:settings;
}

/** Cell detection and GFP classification are separate; nuclei stay pinned to StarDist. */
export function runtimeRecipe(target:ReviewTarget,channel:ChannelDefinition,settings:RuntimeSettings,targets:RuntimeTargets,processing:ProposalProcessing|null):Recipe {
  if(target === "cell") {
    const definition=settings.cellDefinition;
    const defining=definition?.source==="cellpose"?definition.channel:channel.token;
    if(definition?.source==="cellpose") {
      if(!definition.channel)throw new Error("analysis_run_cell_channel_required");
      const detector=processing?.cells?.channel===defining?processing.cells.detector:cellposeDetector();
      const parent=targets.nuclei;
      return {id:"region-2d",version:"1.8.0",source:"cellpose_cell",region_set_id:"cell",label:"細胞",defining_channel_id:defining,detector,
        ...(parent?{nuclear_revision_id:parent.result.revision,nuclear_channel_id:parent.recipe.defining_channel_id}:{})};
    }
    return {id:"region-2d",version:"1.0.0",source:"manual",region_set_id:"cell",label:"細胞ROI",defining_channel_id:defining};
  }
  if(target === "nuclei") {
    const base=nuclearRecipe(channel,settings.nuclearMaxSide);
    const saved=targets.nuclei?.recipe;
    if(saved?.defining_channel_id===channel.token && saved.nuclear_role_source)base.nuclear_role_source=saved.nuclear_role_source;
    // Saved automatically scaled nuclei keep their scale protocol (as run_recipes.py).
    if(saved?.defining_channel_id===channel.token && saved.version==="1.7.0" && saved.detection_scale && base.detection_scale)base.detection_scale=saved.detection_scale;
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

/** An explicit pixel minimum is the minimum: marker protocol 2.2.0 then has no physical minimum (as in run_recipes.py). */
function withExplicitMinimum<T extends {protocol_version:string;minimum_area_px:number;minimum_area_um2?:number|null}>(detector:T,minimum:number|null):T{
  if(minimum===null)return detector;
  return {...detector,minimum_area_px:minimum,...(detector.protocol_version==="2.2.0"?{minimum_area_um2:null}:{})};
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
  const detector=definition.source === "ncl" ? definition.algorithm==="cellpose" ? isCellposeDetector(previous)?previous:nclCellposeDetector()
    : definition.algorithm==="legacy" ? previous?.engine==="fiji-nucleolar-compartments"?previous:{engine:"fiji-nucleolar-compartments" as const,protocol_version:"1.1.0" as const,threshold_method:"otsu" as const,threshold:null,smoothing_sigma_px:0,minimum_area_px:1,maximum_area_px:null,split_touching:false}
    : previous?.engine === "fiji-nucleolar-compartments" || previous?.engine === "cytellect-ncl-objects" || (!definition.algorithm&&isCellposeDetector(previous)) ? previous : nclObjectDetector()
    : withExplicitMinimum({...nucleolarDetectorV2(definition),...(settings.nucleolarSigma !== null ? {smoothing_sigma_px:settings.nucleolarSigma}:{}),...(settings.nucleolarRim !== null ? {rim_exclusion_px:settings.nucleolarRim}:{}),maximum_area_px:settings.nucleolarMaximumArea},settings.nucleolarMinimumArea);
  const recipe:Recipe={id:"region-2d",version:"1.4.0",source:"fiji_nuclear_compartment",region_set_id:"nucleoli",label:labels.nucleoli,compartment:"nucleoli",defining_channel_id:defining,detector};
  const proposed=withProcessingSettings(recipe,processing);
  if(proposed.detector?.engine === "cytellect-nucleolar-v2") return {...proposed,detector:withExplicitMinimum({...proposed.detector,relative_threshold:definition.relative,
    ...(settings.nucleolarSigma !== null && !(proposed.detector.source==="marker" && proposed.detector.protocol_version==="2.0.0") ? {smoothing_sigma_px:settings.nucleolarSigma}:{}),...(settings.nucleolarRim !== null ? {rim_exclusion_px:settings.nucleolarRim}:{}),
    maximum_area_px:settings.nucleolarMaximumArea},settings.nucleolarMinimumArea)};
  if(proposed.detector?.engine === "cytellect-ncl-objects") return {...proposed,detector:{...proposed.detector,
    ...(settings.nucleolarSigma !== null ? {smoothing_sigma_px:settings.nucleolarSigma}:{}),
    ...(settings.nucleolarMinimumArea !== null ? {minimum_area_px:settings.nucleolarMinimumArea}:{}),
    ...(settings.nucleolarMaximumArea !== null ? {maximum_area_px:settings.nucleolarMaximumArea}:{})}};
  if(proposed.detector?.engine === "fiji-nucleolar-compartments") return {...proposed,detector:{...proposed.detector,
    ...(settings.nucleolarSigma !== null ? {smoothing_sigma_px:settings.nucleolarSigma}:{}),
    ...(settings.nucleolarMinimumArea !== null ? {minimum_area_px:settings.nucleolarMinimumArea}:{}),maximum_area_px:settings.nucleolarMaximumArea}};
  return proposed;
}

/** The AI sees the same current controls and compatible historical detector used at execution. */
export function runtimeProposalProcessing(channel:ChannelDefinition,settings:RuntimeSettings,targets:RuntimeTargets,processing:ProposalProcessing|null):ProposalProcessing {
  const nucleus=runtimeRecipe("nuclei",channel,settings,targets,processing);
  const child=settings.nucleolarDefinition.source==="dapi_poor"||settings.nucleolarDefinition.marker?runtimeNucleolarRecipe(channel,settings,targets,processing):undefined;
  const cell=settings.cellDefinition?.source==="cellpose"&&settings.cellDefinition.channel?runtimeRecipe("cell",channel,settings,targets,processing):undefined;
  return savedProcessing(nucleus,child,undefined,cell)!;
}
export function createWorkspaceRuntime(dependencies:Dependencies={}) {
  const adapter=dependencies.adapter ?? createApiAdapter(), loadPreview=dependencies.loadPreview ?? loadReviewPreview, releasePreview=dependencies.releasePreview ?? releaseReviewPreview;
  let state:RuntimeSnapshot={data:null,busy:false,loading:false,operation:"",error:"",assignments:{version:0,assignments:[]},activeTarget:"nuclei",settings:defaultRuntimeSettings(),proposal:null,processing:null,importIssues:[],intakeRows:[],intake:null,messages:[],progress:{},assignmentSuggestions:[]};
  const readSpecification=dependencies.readSpecification ?? ((id:string)=>request<RuntimeSpecification>(`/v1/workspaces/${id}/analysis-spec`));
  // Only the version and the spec are written: read-only fields of the response (e.g. experiment_sha256) are never sent back.
  const writeSpecification=dependencies.writeSpecification ?? ((id:string,value:RuntimeSpecification)=>request<RuntimeSpecification>(`/v1/workspaces/${id}/analysis-spec`,{method:"PUT",body:JSON.stringify({version:value.version,spec:value.spec})}));
  let specification:RuntimeSpecification={version:0,spec:null},specificationDirty=false;
  let beforeProposal:{settings:RuntimeSettings;processing:ProposalProcessing|null;specification:RuntimeSpecification}|null=null;
  let closed=false,epoch=0,stopped=false,activeRunId:string|null=null,opened:string|undefined;
  const runRequests=new Map<string,string>();
  let currentTargets=new Map<string,RuntimeTargets>(),registered=new Map<string,ImportedField>();
  const omeFiles=new Map<string,File>();
  const added:AddedFile[]=[],files=new Map<string,File>(),uploadKeys=new Map<string,string>(),sentPaths=new Set<string>(),uploaded=new Map<string,string>(),names=new Map<string,string>();
  // Hashes of files waiting to be sent (copies are found by content, #284 control A) and copies kept for
  // "別の撮影として追加" until the researcher decides or the workspace changes.
  const hashes=new Map<string,string>(),copies=new Map<string,{file:File;name:string}>();
  // Answers received in this session, by message: only these can be applied (a reload shows the text; applying it
  // again needs the message's 「再送」, answered from the record without a model call). The latest applicable answer and
  // the message that produced it continue the conversation (previous_goal, previous_proposal).
  const answers=new Map<string,ValidatedProposal>();let lastApplicable:{goal:string;proposal:ValidatedProposal}|null=null;
  /** The run and group suggestions of an answer, by workspace field (the response's `fields` resolve `f1`…). */
  function suggestionsOf(proposal:ValidatedProposal,links:readonly {token:string;field_id:string}[]):Suggestion[]{
    const byToken=new Map(links.map(link=>[link.token,link.field_id]));
    return (proposal.draft.assignments??[]).flatMap(value=>{const fieldId=byToken.get(value.field);
      return fieldId&&!labelProblem(value.run)&&!labelProblem(value.group)?[{fieldId,runLabel:value.run,groupLabel:value.group,source:"ai" as const}]:[];});
  }
  const intentOf=(id:string)=>answers.get(id)?.draft.intent??null;
  async function storeAssignments(assignments:ChannelAssignment[],fieldId?:string){
    const selected=fieldId?registered.get(fieldId):null;
    if(fieldId&&!selected)throw new Error("登録した画像が見つかりません。");
    const configuration=(field:ImportedField)=>fingerprint({mode:field.image_info.input_mode??"native",channels:field.image_info.channels.map(channel=>channel.channel_id).sort()});
    const field_ids=selected?[...registered.values()].filter(field=>configuration(field)===configuration(selected)).map(field=>field.id):undefined;
    await adapter.saveChannelAssignments(workspace(),{version:state.assignments.version,assignments,...(field_ids?{field_ids}:{})});histories.clear();publish({proposal:null,processing:null});await refresh(workspace());
  }
  /** The field an answer is about: the one selected when its message was sent (the model saw that field's channel
   * configuration), while it is still registered; otherwise the field selected now. */
  const channelSet=(fieldId:string)=>(state.data?.fields.find(value=>value.id===fieldId)?.channels??[]).map(value=>value.id).sort().join("\u0000");
  const answerField=(messageId:string,selectedFieldId?:string)=>{
    const recorded=state.messages.find(value=>value.id===messageId)?.field_id,sent=recorded&&state.data?.fields.some(value=>value.id===recorded)?recorded:undefined;
    // The selected field, when it has the channels the answer was made for; the answer's own field otherwise.
    if(sent&&selectedFieldId&&channelSet(sent)!==channelSet(selectedFieldId))return sent;
    return selectedFieldId||sent||state.data?.fields.find(value=>!value.exclusionReason)?.id;};
  /** The channels an answer proposes as the nuclear stain while the workspace has no nuclear channel for them yet
   * (the API's `needs_confirmation`): the researcher sets the role before the answer's settings can be applied. */
  function pendingConfirmation(messageId:string,selectedFieldId?:string):ChannelConfirmation[]{
    const proposal=answers.get(messageId);if(!proposal?.needs_confirmation.length)return [];
    const field=state.data?.fields.find(value=>value.id===answerField(messageId,selectedFieldId));
    return proposal.needs_confirmation.flatMap(token=>{const channel=field?.channels.find(value=>value.id===token);
      return channel&&channel.role!=="nuclear"?[{channel:token,label:channel.stain||channel.label||token}]:[];});
  }
  const withMessage=(message:AssistantMessage)=>state.messages.some(value=>value.id===message.id)?state.messages.map(value=>value.id===message.id?message:value):[...state.messages,message];
  async function readMessages(id:string){try{return await adapter.listMessages(id);}catch{return state.messages;}}
  const candidateStore=new Map<string,Partial<Record<ReviewTarget,RuntimeCandidate>>>();
  const histories=new Map<string,{undo:TargetResult[];redo:TargetResult[]}>(),listeners=new Set<()=>void>();
  function publish(patch:Partial<RuntimeSnapshot>){if(closed)return;state={...state,...patch};for(const listener of listeners)listener();}
  function replaceData(data:ReviewData){const previous=state.data;publish({data});if(previous && previous!==data)releasePreview(previous,data);}
  const workspace=()=>{if(!state.data?.workspaceId)throw new Error("画像を追加してください。");return state.data.workspaceId;};
  const history=(field:string,target:ReviewTarget)=>{const key=`${field}:${target}`;if(!histories.has(key))histories.set(key,{undo:[],redo:[]});return histories.get(key)!;};
  const definitions=(fieldId?:string):ChannelDefinition[]=>(fieldId?state.data?.fields.find(field=>field.id===fieldId)?.channels??[]:state.data?.channels??[]).map(value=>({token:value.id,stain:value.stain,role:value.role === "unused" ? null:value.role,evidence:"user"}));
  function nuclearChannel(fieldId?:string){let choices=definitions(fieldId).filter(value=>value.role === "nuclear");if(!choices.length && !state.assignments.version){const adopted=new Set(state.data?.fields.filter(field=>!fieldId||field.id===fieldId).map(field=>field.nuclearChannelId).filter(Boolean));if(adopted.size===1)choices=definitions(fieldId).filter(value=>adopted.has(value.token)).map(value=>({...value,role:"nuclear"}));}if(choices.length!==1)throw new Error("核検出に使うチャンネルを1つ指定してください。");return choices[0];}
  function bound(field:string,target:ReviewTarget,revision?:string){const result=currentTargets.get(field)?.[target];if(!result || (revision && result.result.revision!==revision))throw new Error("操作対象の解析版が変更されています。再読み込みしてください。");return result;}
  /** Lets the browser draw what was just published before more loading occupies it. */
  const painted=()=>new Promise<void>(resolve=>typeof requestAnimationFrame==="function"?requestAnimationFrame(()=>setTimeout(resolve,0)):resolve());
  async function refresh(id?:string,restoreSettings=false,limit?:number,fieldIds?:readonly string[]){
    const ticket=++epoch;let next:ReviewData;
    // Previews already shown are kept: a field's image does not change, only its results do.
    try{next=await loadPreview(id || state.data?.workspaceId || undefined,fieldIds,{...(limit===undefined?{}:{limit}),reuse:state.data});}catch(error){if(error instanceof Error && error.message==="no_saved_workspace"){replaceData(emptyData());return;}throw error;}
    if(closed || ticket!==epoch){releasePreview(next,state.data);return;}
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
      if(restoreSettings){histories.clear();const first=[...targets.values()].find(value=>value.nuclei||value.cell);processing=savedProcessing(first?.nuclei?.recipe,first?.nucleoli?.recipe,undefined,first?.cell?.recipe);if(processing?.nuclei)settings={...settings,nuclearMaxSide:processing.nuclei.detection_max_side_px,nuclearProbability:processing.nuclei.detector.probability,nuclearNms:processing.nuclei.detector.nms};const child=processing?.nucleoli;if(child?.detector.engine==="cytellect-nucleolar-v2")settings={...settings,nucleolarDefinition:{...settings.nucleolarDefinition,source:child.detector.source,marker:child.detector.source==="marker"?child.channel:"",relative:child.detector.relative_threshold},nucleolarSigma:child.detector.smoothing_sigma_px,nucleolarRim:child.detector.rim_exclusion_px,nucleolarMinimumArea:child.detector.minimum_area_px,nucleolarMaximumArea:child.detector.maximum_area_px};}
      if(restoreSettings && (processing?.nucleoli?.detector.engine==="fiji-nucleolar-compartments"||processing?.nucleoli?.detector.engine==="cytellect-ncl-objects"))settings={...settings,nucleolarDefinition:{...settings.nucleolarDefinition,source:"ncl",marker:processing.nucleoli.channel},nucleolarSigma:processing.nucleoli.detector.smoothing_sigma_px,nucleolarMinimumArea:processing.nucleoli.detector.minimum_area_px,nucleolarMaximumArea:processing.nucleoli.detector.maximum_area_px};
      if(restoreSettings && processing?.nucleoli && isCellposeDetector(processing.nucleoli.detector))settings={...settings,nucleolarDefinition:{...settings.nucleolarDefinition,source:"ncl",marker:processing.nucleoli.channel,algorithm:"cellpose"},nucleolarSigma:null,nucleolarMinimumArea:null,nucleolarMaximumArea:null};
      if(restoreSettings && processing?.cells)settings={...settings,cellDefinition:{source:"cellpose",channel:processing.cells.channel}};
      if(restoreSettings && [...targets.values()].some(value=>value.nucleoplasm?.result.protocol==="4.0.0"))settings={...settings,background:"automatic"};
      specification=recordedSpecification;specificationDirty=false;
      if(restoreSettings && specification.spec){
        settings=normalizedRuntimeSettings(specification.spec.settings);
        const historical=processing?.nucleoli;
        const preserveLegacyMarker=!specification.spec.processing && settings.nucleolarDefinition.source==="marker"
          && historical?.channel===settings.nucleolarDefinition.marker && historical.detector.engine==="cytellect-nucleolar-v2"
          && historical.detector.source==="marker" && historical.detector.protocol_version==="2.0.0";
        const preserveHistoricalCellpose=!specification.spec.processing&&settings.nucleolarDefinition.source==="ncl"
          &&historical?.channel===settings.nucleolarDefinition.marker&&isCellposeDetector(historical.detector)
          &&(!settings.nucleolarDefinition.algorithm||settings.nucleolarDefinition.algorithm==="cellpose");
        processing=preserveLegacyMarker||preserveHistoricalCellpose?processing:specification.spec.processing;
      }
      settings=visibleNucleolarSettings(settings,processing);
      publish({assignments,settings,processing,activeTarget:recordedSpecification.spec?.target??state.activeTarget,intakeRows:intakeRows(saved.selection?.entries??[])});replaceData(next);
    }catch(error){releasePreview(next);throw error;}
  }
  async function exclusive<T>(operation:string,task:()=>Promise<T>){if(state.busy)throw new Error("現在の処理が終わるまでお待ちください。");publish({busy:true,error:"",operation});try{return await task();}catch(error){publish({error:message(error)});throw error;}finally{publish({busy:false,operation:""});}}
  async function checkCurrent(){const id=workspace();if(!await adapter.isSelectionCurrent(id))throw new Error("別の画面で採用状態が変わりました。再読み込みしてください。");if((await adapter.getChannelAssignments(id)).version!==state.assignments.version)throw new Error("染色設定が変更されています。再読み込みしてください。");}
  function currentSpecification(target:ReviewTarget){
    return {...specification.spec,channel_assignment_version:state.assignments.version,target,settings:state.settings,processing:state.processing?{...state.processing,cells:state.processing.cells??null}:null,
      measurement:state.settings.background === "confirmed_roi" ? null : state.settings.background === "automatic" ? automaticBackground : rawMeasurement};
  }
  async function persistSpecification(target:ReviewTarget){
    const spec=currentSpecification(target);
    if(!specificationDirty&&fingerprint(specification.spec)===fingerprint(spec))return;
    specification=await writeSpecification(workspace(),{version:specification.version,spec});specificationDirty=false;
  }
  function adopted(field:string,target:ReviewTarget,result:SavedResult,recipe:Recipe){const targets={...currentTargets.get(field)};if(target==="nuclei"){delete targets.nucleoli;delete targets.nucleoplasm;}if(target==="nucleoli")delete targets.nucleoplasm;targets[target]={result,recipe};currentTargets.set(field,targets);}
  // A candidate answers the specification it was detected under, by content: a later save that only declares the primary
  // measure (#257 RP-04) keeps it adoptable, as the server does (workspace_runs.same_detection_spec); any other change does not.
  function candidateSignature(field:string){const detection:Record<string,unknown>={...specification.spec};delete detection.primary_outcome;return fingerprint({settings:state.settings,processing:state.processing,spec:detection,assignments:state.assignments.version,adopted:Object.fromEntries(Object.entries(currentTargets.get(field)??{}).map(([target,value])=>[target,value?.result.revision]))});}
  function candidate(field:string,target:ReviewTarget){const value=candidateStore.get(field)?.[target];return value?.settingsFingerprint===candidateSignature(field)?value:undefined;}
  async function acceptPrepared(field:string,target:ReviewTarget){
    if(!candidate(field,target))return false;
    const serverRun=candidate(field,target)?.runId;if(serverRun){const run=await adapter.waitWorkspaceRun(workspace(),serverRun);if(run.state!=="succeeded"&&run.state!=="adopted")return false;await adapter.acceptWorkspaceRun(workspace(),serverRun);rememberRunAdoption(run);candidateStore.delete(field);await refresh(workspace());return true;}
    const ordered:ReviewTarget[]=target==="cell"?["cell"]:target==="nuclei"?["nuclei"]:target==="nucleoli"?["nuclei","nucleoli"]:["nuclei","nucleoli","nucleoplasm"];
    const prepared=ordered.flatMap(key=>{const value=candidate(field,key);return value?[{key,value}]:[];});
    for(const {key,value} of prepared){const previous=currentTargets.get(field)?.[key];const result=await adapter.selectRevision(workspace(),value.result.revision,field);if(previous){history(field,key).undo.push(previous);history(field,key).redo=[];}adopted(field,key,result,value.recipe);}
    candidateStore.delete(field);const progress={...state.progress};delete progress[field];publish({progress});return true;
  }
  async function runField(field:string,target:ReviewTarget,preview=false){
    if(!preview && await acceptPrepared(field,target))return;
    const input=registered.get(field);if(!input)throw new Error("登録した画像が見つかりません。");
    const channel=target==="cell"?definitions(field).find(value=>state.settings.cellDefinition?.source==="cellpose"?value.token===state.settings.cellDefinition.channel:value.role!==null&&input.image_info.channels.some(plane=>plane.channel_id===value.token)):nuclearChannel(field);
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
    if(target==="cell"){const recipe=runtimeRecipe("cell",channel,state.settings,targets,state.processing);if(!targets.cell||!sameRuntimeRecipe(targets.cell.recipe,recipe))await perform("cell",recipe);return;}
    const parentRecipe=runtimeRecipe("nuclei",channel,state.settings,targets,state.processing);
    if(!targets.nuclei||!sameRuntimeRecipe(targets.nuclei.recipe,parentRecipe))await perform("nuclei",parentRecipe);
    if(target==="nuclei")return;
    if(target==="nucleoplasm"&&!targets.nucleoli)await perform("nucleoli",runtimeRecipe("nucleoli",channel,state.settings,targets,state.processing));
    const recipe=runtimeRecipe(target,channel,state.settings,targets,state.processing),existing=targets[target];
    if(existing&&sameRuntimeRecipe(existing.recipe,recipe)&&(target!=="nucleoplasm"||(existing.result.protocol==="4.0.0")===(state.settings.background==="automatic")))return;
    await perform(target,recipe);
  }
  function rememberRunAdoption(run:WorkspaceRun){for(const step of run.steps){const previous=currentTargets.get(step.field_id)?.[step.target];if(previous&&previous.result.revision!==step.revision_id){history(step.field_id,step.target).undo.push(previous);history(step.field_id,step.target).redo=[];}}}
  async function readCandidates(run:WorkspaceRun,signatures?:Map<string,string>){
    for(const step of run.steps){if(!step.revision_id||!step.recipe||!["succeeded","reused"].includes(step.state))continue;
      const result=await adapter.readResult(step.revision_id,step.field_id,step.recipe),values={...candidateStore.get(step.field_id)};
      values[step.target]={result,recipe:step.recipe,settingsFingerprint:signatures?.get(step.field_id)??candidateSignature(step.field_id),runId:run.id,runState:run.state,backgroundPending:step.background_pending};candidateStore.set(step.field_id,values);
    }
    if(state.data){const included=new Set(run.steps.map(step=>step.field_id));publish({data:{...state.data,fields:state.data.fields.map(field=>{
      if(!included.has(field.id))return field;
      const failures=run.steps.filter(step=>step.field_id===field.id&&(step.state==="failed"||step.state==="blocked")).map(step=>`解析処理：${labels[step.target]} — ${step.error?errorCodeMessage(step.error):"依存する領域の処理が完了しませんでした。"}`);
      const existing=field.error?.split("\n").filter(value=>!value.startsWith("解析処理："))??[];
      return {...field,error:[...new Set([...existing,...failures])].join("\n")||undefined};
    })}});}else publish({});
  }
  async function recoverRun(){
    if(!state.data?.workspaceId||!("listWorkspaceRuns" in adapter))return;
    const runs=await adapter.listWorkspaceRuns(workspace());
    // The newest run of these settings. When it was adopted (for example the run of the fields that succeeded after
    // another failed), nothing is recovered: an older, failed run's candidates are not shown over adopted results.
    const latest=runs.filter(run=>run.spec_version===specification.version||run.spec_current===true).sort((a,b)=>b.created-a.created)[0];
    if(!latest||!["queued","running","succeeded","failed","cancelled"].includes(latest.state))return;
    activeRunId=latest.id;
    try{const run=!["queued","running"].includes(latest.state)?latest:await adapter.waitWorkspaceRun(workspace(),latest.id,value=>publish({operation:`保存した処理を再開中 · ${progressLine(value,fieldName,targetName)}`,progress:{...state.progress,...fieldProgress(value)}}),attempt=>publish({operation:`接続：確認中 · 再試行 ${attempt}`}));publish({progress:{...state.progress,...fieldProgress(run)}});await readCandidates(run);}
    finally{activeRunId=null;}
  }
  const fieldName=(id:string)=>names.get(id)||state.data?.fields.find(value=>value.id===id)?.label||"視野";
  const targetName=(value:string)=>labels[value as keyof typeof labels]??value;
  const progressOf=(ids:readonly string[],value:FieldProgress)=>({...state.progress,...Object.fromEntries(ids.map(id=>[id,value]))});
  /** Starts a run for the fields and follows it per field; a lost connection while following is retried, not failed. */
  async function followRun(target:ReviewTarget,ids:string[],preview:boolean){
    const key=fingerprint({workspace:workspace(),version:specification.version,target,purpose:preview?"preview":"measurement",fields:ids.map(id=>({id,signature:candidateSignature(id)}))});
    if(!runRequests.has(key))runRequests.set(key,crypto.randomUUID());
    const created=await adapter.startWorkspaceRun(workspace(),{request_id:runRequests.get(key)!,spec_version:specification.version,target,field_ids:ids,purpose:preview?"preview":"measurement"});
    activeRunId=created.id;publish({progress:{...state.progress,...fieldProgress(created)}});
    const run=await adapter.waitWorkspaceRun(workspace(),created.id,value=>publish({operation:progressLine(value,fieldName,targetName),progress:{...state.progress,...fieldProgress(value)}}),
      attempt=>publish({operation:`接続：確認中 · 再試行 ${attempt} · ${Object.values(state.progress).filter(value=>value==="候補を確認"||value==="保存済み").length} 視野 完了`}));
    publish({progress:{...state.progress,...fieldProgress(run)}});
    return {run,key};
  }
  async function runServer(target:ReviewTarget,fieldId?:string,preview=false){
    const chosen=state.data!.fields.filter(field=>!field.exclusionReason&&(!fieldId||field.id===fieldId));if(!chosen.length)throw new Error("解析する画像を選択してください。");
    if(!preview&&chosen.length===1&&candidate(chosen[0].id,target)?.runId&&candidate(chosen[0].id,target)?.runState==="succeeded"&&!candidate(chosen[0].id,target)?.backgroundPending){await acceptPrepared(chosen[0].id,target);return;}
    // Without a nuclear stain on any chosen field the detection cannot start: said here, by its cause.
    if(target==="nuclei"&&chosen.every(field=>{try{nuclearChannel(field.id);return false;}catch{return true;}}))throw new Error(NUCLEAR_STAIN_REQUIRED);
    publish({progress:progressOf(chosen.map(field=>field.id),"準備中")});
    // A request that never started leaves no 準備中 behind: the saved results show again (#284 W8).
    try{await persistSpecification(target);}catch(error){const progress={...state.progress};for(const field of chosen)if(progress[field.id]==="準備中")delete progress[field.id];publish({progress});throw error;}
    if(!preview)publish({activeTarget:target});stopped=false;
    const signatures=new Map(chosen.map(field=>[field.id,candidateSignature(field.id)]));
    try{let {run,key}=await followRun(target,chosen.map(field=>field.id),preview);
      await readCandidates(run,signatures);
      if(run.state==="cancelled"){runRequests.delete(key);throw new Error("処理を中止しました。採用済みの領域は保持されています。");}
      // A field without a nuclear stain fails its nuclear detection for that reason, not for its settings' values.
      const unstained=(field:string)=>{if(target!=="nuclei")return false;try{nuclearChannel(field);return false;}catch{return true;}};
      const failure=()=>run.steps.filter(step=>step.error).map(step=>`${fieldName(step.field_id)}：${unstained(step.field_id)?NUCLEAR_STAIN_MISSING:errorCodeMessage(step.error!)}`).join("\n");
      if(run.state==="failed"){runRequests.delete(key);
        // One field's failure does not hold the others back (#284 W8): the same run without the failed fields reuses
        // their finished steps, and its fields are adopted. The failed fields keep 「失敗」 and their reason.
        const done=completedFields(run).filter(id=>signatures.has(id));
        if(preview||!done.length)throw new Error(failure());
        const failed=failure(),again=await followRun(target,done,preview);run=again.run;key=again.key;
        await readCandidates(run,signatures);
        if(run.state!=="succeeded"){runRequests.delete(key);throw new Error(failed);}
        publish({error:failed});
      }
      if(!preview){const adopted=run.steps.map(step=>step.field_id).filter((id,index,all)=>all.indexOf(id)===index);
        publish({progress:progressOf(adopted,"採用中")});
        await adapter.acceptWorkspaceRun(workspace(),run.id);rememberRunAdoption(run);for(const id of adopted)candidateStore.delete(id);
        // 採用中 stays until the adopted results are read, so a field never shows 未測定 in between.
        await refresh(workspace());
        const progress={...state.progress};for(const id of adopted)delete progress[id];publish({progress});}
    }catch(error){
      // A field still marked 準備中 or 待機 did not start: the request itself failed.
      const progress={...state.progress};for(const field of chosen)if(progress[field.id]==="準備中")delete progress[field.id];publish({progress});throw error;
    }finally{activeRunId=null;}
  }
  async function runInternal(target:ReviewTarget,fieldId?:string,preview=false){
    await checkCurrent();
    if(target==="cell"&&state.settings.cellDefinition?.source==="cellpose"){
      const defining=state.settings.cellDefinition.channel;if(!defining)throw new Error("analysis_run_cell_channel_required");
      if(state.data!.fields.filter(field=>!field.exclusionReason&&(!fieldId||field.id===fieldId)).some(field=>!field.channels.some(ch=>ch.id===defining&&ch.role!=="unused")))throw new Error("analysis_run_cell_channel_unknown");
    }
    if(target==="nucleoli"||target==="nucleoplasm"){
      const chosen=state.data!.fields.filter(field=>!field.exclusionReason&&(!fieldId||field.id===fieldId));
      for(const field of chosen){
        const definition=state.settings.nucleolarDefinition;
        const channel=nuclearChannel(field.id);
        if(!channel)throw new Error("analysis_run_nuclear_parent_required");
        if(definition.source==="ncl"&&state.processing?.nucleoli?.detector.engine!=="fiji-nucleolar-compartments"){
          const parents=currentTargets.get(field.id)??{},parent=parents.nuclei;
          if(!parent||!sameRuntimeRecipe(parent.recipe,runtimeRecipe("nuclei",channel,state.settings,parents,state.processing)))throw new Error("analysis_run_nuclear_parent_required");
        }
        if(definition.source!=="dapi_poor"){
          if(!definition.marker)throw new Error("analysis_run_nucleolar_marker_required");
          if(definition.marker===channel.token||!field.channels.some(ch=>ch.id===definition.marker&&ch.role!=="unused"))throw new Error("analysis_run_nucleolar_marker_unknown");
        }
      }
    }
    if("startWorkspaceRun" in adapter){await runServer(target,fieldId,preview);return;}
    await persistSpecification(target);if(!preview)publish({activeTarget:target});stopped=false;
    const fields=state.data!.fields.filter(field=>!field.exclusionReason&&(!fieldId||field.id===fieldId));if(!fields.length)throw new Error("解析する画像を選択してください。");
    const failures:string[]=[];for(const field of fields){if(stopped||closed)break;try{await runField(field.id,target,preview);}catch(error){failures.push(`${field.label}：${message(error)}`);}}
    if(!preview)await refresh(workspace());if(failures.length)throw new Error(failures.join("\n"));
  }
  function applyProposal(fieldId?:string){
    if(!state.proposal)throw new Error("解析案がありません。");const channels=definitions(fieldId);try{const nucleus=nuclearChannel(fieldId),index=channels.findIndex(value=>value.token===nucleus.token);if(index>=0)channels[index]=nucleus;}catch{}
    const hasImages=!!state.data?.fields.length,automatic=hasImages&&(["nuclear-intensity","nuclear-ncl"].includes(state.proposal.draft.recipe)||!!state.proposal.draft.processing?.cells),processing=automatic?applicableProcessing(state.proposal,channels):null;if(automatic&&!processing?.nuclei&&!processing?.cells)throw new Error("核のチャンネルを確認してから解析案を適用してください。");
    let selectedProcessing:ProposalProcessing|null=null;
    const selectedField=fieldId||state.data?.fields.find(value=>!value.exclusionReason)?.id;
    if(selectedField){try{selectedProcessing=runtimeProposalProcessing(nuclearChannel(selectedField),state.settings,currentTargets.get(selectedField)??{},state.processing);}catch{/* Missing live selection cannot authorize an experimental model. */}}
    preserveNclModelSelection(processing,selectedProcessing);
    if(hasImages&&state.proposal.draft.recipe==="supplied-regions"&&!processing?.cells){const cell=fieldId?currentTargets.get(fieldId)?.cell:undefined;if(!["manual","cellpose_cell"].includes(cell?.recipe.source??"")||cell?.recipe.region_set_id!=="cell"||!cell.result.masks.regions.length)throw new Error("選択視野の採用済み細胞ROIを確認してください。");}
    let settings=processing?.nuclei?{...state.settings,nuclearMaxSide:processing.nuclei.detection_max_side_px,nuclearProbability:processing.nuclei.detector.probability,nuclearNms:processing.nuclei.detector.nms}:{...state.settings};
    const child=processing?.nucleoli;if(child?.detector.engine==="cytellect-nucleolar-v2")settings={...settings,nucleolarDefinition:{...settings.nucleolarDefinition,source:child.detector.source,marker:child.detector.source==="marker"?child.channel:"",relative:child.detector.relative_threshold},nucleolarSigma:child.detector.smoothing_sigma_px,nucleolarRim:child.detector.rim_exclusion_px,nucleolarMinimumArea:child.detector.minimum_area_px,nucleolarMaximumArea:child.detector.maximum_area_px};else if(child&&isCellposeDetector(child.detector))settings={...settings,nucleolarDefinition:{...settings.nucleolarDefinition,source:"ncl",marker:child.channel,algorithm:"cellpose"},nucleolarSigma:null,nucleolarMinimumArea:null,nucleolarMaximumArea:null};else if(child&&(child.detector.engine==="cytellect-ncl-objects"||child.detector.engine==="fiji-nucleolar-compartments"))settings={...settings,nucleolarDefinition:{...settings.nucleolarDefinition,source:"ncl",marker:child.channel,algorithm:child.detector.engine==="cytellect-ncl-objects"?"objects":"legacy"},nucleolarSigma:child.detector.smoothing_sigma_px,nucleolarMinimumArea:child.detector.minimum_area_px,nucleolarMaximumArea:child.detector.maximum_area_px};
    if(processing?.cells)settings={...settings,cellDefinition:{source:"cellpose",channel:processing.cells.channel}};
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
      const {channel_gate:priorChannelGate,...legacySelection}=priorSelection;void priorChannelGate;
      const previousGate=priorSelection.gfp&&typeof priorSelection.gfp==="object"?priorSelection.gfp as Record<string,unknown>:{};
      if(gate.method==="negative_control"&&gate.unit==="nucleus"){
        const controls=previousGate.control_field_ids;
        if(Array.isArray(controls)&&controls.length)selection={...legacySelection,gfp:{version:"1.0.0",gate_protocol:"gfp-gate/2.0.0",gfp_channel_id:gate.channel,percentile:gate.percentile,control_field_ids:controls,keep:gate.keep}};
      }else if(gate.method!=="negative_control")selection={...legacySelection,gfp:{...(gate.unit==="cell_roi"?{unit:"cell_roi"}:{}),version:"1.1.0",gate_protocol:"gfp-gate/3.0.0",gfp_channel_id:gate.channel,method:gate.method,threshold:gate.threshold,values:gate.values,keep:gate.keep}};
    }
    const statistical=prior?.statistics&&typeof prior.statistics==="object"?prior.statistics:{};
    const figure=prior?.figure&&typeof prior.figure==="object"?prior.figure:{};
    const target:ReviewTarget=processing?.cells&&!processing.nucleoli?"cell":draft.recipe==="supplied-regions"?"cell":draft.recipe==="none"?(prior?.target??state.activeTarget):first?.region==="nucleoplasm"||["ncl_log2_nucleoplasm_over_nucleoli","nucleolar_area_fraction","nucleolar_count"].includes(first?.metric??"")?"nucleoplasm":first?.region==="nucleoli"?"nucleoli":processing?.nucleoli?"nucleoli":"nuclei";
    specificationDirty=true;specification={...specification,spec:{...prior,channel_assignment_version:state.assignments.version,target,settings,processing:automatic?processing?{...processing,signal:null}:null:state.processing,measurement:settings.background==="confirmed_roi"?null:settings.background==="automatic"?automaticBackground:rawMeasurement,
      metrics,selection,additional_analyses:draft.additional_analyses??[],figure_proposals:draft.figures,
      // The figure's composition and legend facts (prompt 2026-11-19.1); an earlier draft has none.
      figure_presentation:(draft as {figure_presentation?:unknown}).figure_presentation??null,
      statistics:{...statistical,method:draft.statistics,...(metric?{metric,channel_id:first.channel}: {}),...(draft.statistics.y?{metric:metricMap[draft.statistics.y.metric]??draft.statistics.y.metric,channel_id:draft.statistics.y.channel}:{}),...(draft.statistics.x?{x_metric:metricMap[draft.statistics.x.metric]??draft.statistics.x.metric,x_channel_id:draft.statistics.x.channel}:{x_metric:null,x_channel_id:null})},
      ...(firstFigure?{figure:{...figure,metric:metricMap[firstFigure.metric]??firstFigure.metric,channel_id:firstFigure.channel}}:{})}};
    publish({processing:automatic?processing?{...processing,signal:null}:null:state.processing,settings,activeTarget:target});
  }
  function dropImport(key:string,paths:string[]){for(const path of paths){files.delete(path);omeFiles.delete(path);hashes.delete(path);const index=added.findIndex(value=>value.path===path);if(index>=0)added.splice(index,1);}uploadKeys.delete(key);}
  async function showImported(saved:ImportedField,key:string){uploaded.set(key,saved.id);names.set(saved.id,key.split("/").at(-1)||key);registered.set(saved.id,saved);const partial=await loadPreview(workspace(),[saved.id]);const freshField=partial.fields.find(value=>value.id===saved.id);if(freshField&&state.data){freshField.label=names.get(saved.id)||freshField.label;const retained=state.data.fields.filter(value=>value.id!==saved.id);const previous=state.data.fields.find(value=>value.id===saved.id);if(previous)releasePreview({...partial,fields:[previous]});const channels=[...state.data.channels];for(const channel of freshField.channels)if(!channels.some(value=>value.id===channel.id))channels.push(channel);publish({data:{...state.data,fields:[...retained,freshField],channels},operation:`${uploaded.size} 視野を登録済み`});}
  }
  /** The two fields a saved two-group design opens on, read before any image; undefined otherwise. */
  async function openingFields(id?:string):Promise<string[]|undefined>{
    try{const workspaceId=id??await newestWorkspaceId();if(!workspaceId)return undefined;const pair=openingPair((await readSpecification(workspaceId)).spec?.experiment??null);return pair.length>1?pair:undefined;}
    catch{return undefined;}
  }
  function intakeRows(entries:readonly SelectionEntry[]):IntakeRow[]{
    return entries.filter(entry=>!entry.field_id&&!entry.exclusion_reason).map(entry=>({entry:entry.id,names:entry.intake?.names??[],
      state:entry.intake?(entry.intake.state==="rejected"?"rejected":"pending"):"legacy",code:entry.intake?.code??null,mask:isMaskRow(entry.intake),target:entry.intake?.target??null}));
  }
  /** Puts registered fields where the researcher asked (the row's target), once, then forgets the target (#284 control C).
   * Run after every addition and when a workspace opens, so an interrupted addition is placed after a restart. */
  async function applyTargets(){
    const selection=adapter.selection(),design=specification.spec?.experiment;if(!selection)return;
    const placed=selection.entries.filter(entry=>entry.field_id&&entry.intake?.target);if(!placed.length||!design)return;
    let next=design;
    for(const entry of placed){const target=entry.intake!.target!;
      if(design.fields?.[entry.field_id!]||!(design.runs??[]).some(run=>run.id===target.run_id)||!(design.groups??[]).some(group=>group.id===target.group_id))continue;
      next=assignFields(next,[entry.field_id!],{run_id:target.run_id,group_id:target.group_id,sample:target.sample});}
    if(next!==design){specification=await writeSpecification(workspace(),{version:specification.version,spec:{...specification.spec!,experiment:next}});specificationDirty=false;}
    await adapter.clearTargets(workspace(),placed.map(entry=>entry.id));
  }
  /** Forgets the files this session holds for a row (removed, or replaced by other files): they are never resent under it. */
  function forgetEntry(entry:string){for(const [key,id] of [...uploadKeys])if(id===entry){const grouped=groupFiles(added).fields.find(field=>field.key===key);dropImport(key,grouped?Object.values(grouped.files).map(file=>file.path):[key]);}}
  /** An addition interrupted before its fields were placed is placed when the workspace opens again. */
  async function placeAfterRestart(){if(!state.data?.workspaceId||!adapter.selection()?.entries.some(entry=>entry.field_id&&entry.intake?.target))return false;await applyTargets();return true;}
  /** Adds images (implementation plan, sections 5.2-5.4). Order: not a TIFF → same content → fields → name conflicts. */
  /** Forgets every file this session holds that did not become a field. Whatever ends an addition early (no answer
   * before or while sending, a changed workspace, 実行を中止, a file that cannot be read any more), nothing unsent
   * stays behind for a later addition to send on its own, into that addition's run and group. */
  function dropUnsent(){
    for(const path of [...files.keys()])if(!sentPaths.has(path)){files.delete(path);omeFiles.delete(path);hashes.delete(path);}
    for(let index=added.length-1;index>=0;index--)if(!sentPaths.has(added[index].path))added.splice(index,1);
    for(const key of [...uploadKeys.keys()])if(!uploaded.has(key))uploadKeys.delete(key);
  }
  async function intake(list:File[],mode:"automatic"|"single",target:IntakeTarget|null,options:{entry?:string;separate?:boolean}={}):Promise<IntakeOutcome>{
    try{return await intakeOnce(list,mode,target,options);}
    catch(error){
      dropUnsent();
      publish({importIssues:groupFiles(added,mode).issues.filter(issue=>issue.kind!=="duplicate_content"&&issue.kind!=="duplicate_channel").map(shownIssue)});
      throw error;
    }
  }
  async function intakeOnce(list:File[],mode:"automatic"|"single",target:IntakeTarget|null,options:{entry?:string;separate?:boolean}):Promise<IntakeOutcome>{
    stopped=false;const outcome=emptyOutcome();let halted=false;
    if(!list.length){outcome.empty="nothing";publish({intake:outcome});return outcome;}
    // A batch has its own identity: names in a later drop cannot overwrite earlier pixels.
    const batch=`import-${crypto.randomUUID()}`,fresh:AddedFile[]=[],freshOme:string[]=[],oversized=new Set<string>();
    const known=new Map<string,string>();
    for(const field of registered.values())for(const input of Object.values(field.image_info.inputs??{}))known.set(input.sha256,names.get(field.id)||field.display_name||field.id);
    // A row sent again (差し替え, e.g. after a reconnection) may hold the very files it still keeps: they are not copies of themselves.
    const replacing=new Set<string>();
    if(options.entry)for(const [key,id] of uploadKeys)if(id===options.entry){const grouped=groupFiles(added).fields.find(field=>field.key===key);for(const path of grouped?Object.values(grouped.files).map(file=>file.path):[key])replacing.add(path);}
    for(const [path,sha256] of hashes)if(!replacing.has(path))known.set(sha256,shownPath(path));
    for(const file of list){
      const originalPath=intakePath(file);if(!isSupportedImage(originalPath)){outcome.skipped.push({name:originalPath});continue;}
      let path=`${batch}/${originalPath}`;
      if(files.has(path))path=`${batch}/image-${crypto.randomUUID()}/${originalPath}`;
      let sha256:string|undefined;
      if(file.size>FIELD_FILE_LIMIT)oversized.add(path);
      else{sha256=hex(await crypto.subtle.digest("SHA-256",await file.arrayBuffer()));
        const same=known.get(sha256);
        if(same!==undefined&&!options.separate){const id=crypto.randomUUID();copies.set(id,{file,name:originalPath});outcome.duplicates.push({id,name:originalPath,sameAs:same});continue;}
        known.set(sha256,originalPath);hashes.set(path,sha256);}
      if(!oversized.has(path)&&await tiffHasOmeMetadata(file)){omeFiles.set(path,file);freshOme.push(path);}
      else fresh.push({path,size:file.size,...(sha256?{sha256}:{}),inputMode:oversized.has(path)?"native":await tiffInputMode(file)});
      files.set(path,file);
    }
    if(!fresh.length&&!freshOme.length){if(!outcome.duplicates.length)outcome.empty="no_images";publish({intake:outcome});return outcome;}
    added.push(...fresh);let grouping=groupFiles(added,mode);
    // A name conflict holds its own field only (unsent, no row); the other fields are registered (#284 control B).
    for(const issue of grouping.issues){if(issue.kind!=="duplicate_channel")continue;
      const field=grouping.fields.find(value=>value.key===issue.field);if(!field||uploaded.has(field.key))continue;
      const paths=[...new Set([...issue.paths,...Object.values(field.files).map(file=>file.path)])];
      outcome.held.push({names:paths.map(shownPath),reason:"duplicate_channel"});dropImport(field.key,paths);}
    if(outcome.held.length)grouping=groupFiles(added,mode);
    publish({importIssues:grouping.issues.filter(issue=>issue.kind!=="duplicate_content"&&issue.kind!=="duplicate_channel").map(shownIssue)});
    const batchFields=grouping.fields.filter(field=>!uploaded.has(field.key)&&(!options.entry||field.key.startsWith(`${batch}/`)));
    const batchOme=[...omeFiles.keys()].filter(key=>!uploaded.has(key)&&(!options.entry||freshOme.includes(key)));
    if(options.entry&&batchFields.length+batchOme.length!==1){for(const field of batchFields)dropImport(field.key,Object.values(field.files).map(file=>file.path));for(const key of batchOme)dropImport(key,[key]);
      throw new Error("差し替えには、この行と同じ 1 視野の画像が必要です。");}
    if(!state.data?.workspaceId){const created=await adapter.create();replaceData({...emptyData(),workspaceId:created.id,title:created.title});}else await checkCurrent();
    if(options.entry)forgetEntry(options.entry);
    const ledgerSize=()=>adapter.selection()?.entries.length??0;
    try{
      const send=async(key:string,paths:string[],refusal:string|null,upload:(entry:string)=>Promise<ImportedField>)=>{
        const shown=paths.map(path=>recordedName(shownPath(path)));
        if(options.entry)uploadKeys.set(key,options.entry);
        if(!uploadKeys.has(key)){
          // Images added again under the names of a row whose upload was interrupted resolve that row, when they go
          // where the row was going (the same run and group, or none for both). A refused row, or a row going
          // elsewhere, is another image's record: it stays, and never passes its group on.
          const taken=new Set(uploadKeys.values()),wanted=[...shown].sort().join("\u0000"),place=(value:IntakeTarget|null|undefined)=>value?`${value.run_id}\u0000${value.group_id}\u0000${value.sample??""}`:"";
          const earlier=adapter.selection()?.entries.find(value=>!value.field_id&&!value.exclusion_reason&&!taken.has(value.id)&&value.intake?.state==="pending"
            &&[...value.intake.names].sort().join("\u0000")===wanted&&place(value.intake.target)===place(target));
          if(earlier)uploadKeys.set(key,earlier.id);
          else{if(ledgerSize()>=LEDGER_LIMIT){outcome.rejected.push({entry:null,names:shown,code:"ledger_full"});dropImport(key,paths);return;}uploadKeys.set(key,crypto.randomUUID());}
        }
        const entry=uploadKeys.get(key)!;
        // This addition's run and group; a row sent again without one keeps what it recorded.
        const recorded=options.entry?undefined:adapter.selection()?.entries.find(value=>value.id===entry)?.intake;
        const rowTarget=target??recorded?.target??null,separate=options.separate??recorded?.separate;
        await adapter.registerImport(workspace(),entry,{names:shown,state:"pending",...(rowTarget?{target:rowTarget}:{}),...(separate?{separate:true}:{})});
        let saved:ImportedField;
        try{if(refusal)throw new ApiError(refusal,422);saved=await upload(entry);}
        catch(error){if(!itemRefusal(error))throw error;
          await adapter.recordImport(workspace(),entry,{state:"rejected",stage:"register",code:error.code});
          outcome.rejected.push({entry,names:shown,code:error.code});dropImport(key,paths);return;}
        // Counted as registered once the upload answered, whatever fails after it (reading the preview, a re-read).
        for(const path of paths)sentPaths.add(path);
        outcome.registered.push({fieldId:saved.id,names:shown});
        await showImported(saved,key);
      };
      for(const field of batchFields){if(stopped||closed){halted=true;break;}
        const present=grouping.channels.filter(channel=>field.files[channel.token]),paths=Object.values(field.files).map(file=>file.path);
        const modes=new Set(present.map(channel=>field.files[channel.token].inputMode||"native"));
        const refusal=paths.some(path=>oversized.has(path))||paths.reduce((sum,path)=>sum+(files.get(path)?.size??0),0)>FIELD_FILE_LIMIT?"field_upload_limit":present.length>4?"field_channel_limit":modes.size>1?"field_input_modes_mixed":null;
        await send(field.key,paths,refusal,entry=>adapter.upload(workspace(),field,present,files,entry));}
      for(const key of batchOme){if(stopped||closed){halted=true;break;}const file=omeFiles.get(key)!;await send(key,[key],null,entry=>adapter.uploadOme(workspace(),file,entry));}
    }catch(error){
      // What was registered stays; rows not answered stay "pending" and are named after a restart (#284 W1). The
      // list before adding still holds the files (`intake` forgets them here), and adding them again resolves the
      // pending row.
      dropUnsent();
      try{await refresh(workspace());await applyTargets();}catch{/* the interruption is what is reported */}
      publish({intake:outcome});throw new IntakeInterrupted(outcome,error);
    }
    if(halted&&!closed){
      // 実行を中止: the fields not sent yet stay in the list of chosen files, never in this session's memory.
      dropUnsent();
      await refresh(workspace());await applyTargets();await refresh(workspace());
      outcome.stopped=true;publish({intake:outcome});throw new IntakeInterrupted(outcome,new Error(ADD_STOPPED));
    }
    await refresh(workspace());await applyTargets();await refresh(workspace());
    // Refused, held and copied files have left the record: the grouping notes describe what remains.
    publish({intake:outcome,importIssues:groupFiles(added,mode).issues.filter(issue=>issue.kind!=="duplicate_content"&&issue.kind!=="duplicate_channel").map(shownIssue)});
    return outcome;
  }
  async function reloadSaved(){await refresh(workspace(),true);if(await placeAfterRestart())await refresh(workspace());await recoverRun();}
  async function travel(field:string,target:ReviewTarget,direction:"undo"|"redo"){return exclusive(direction==="undo"?"前の版に戻しています":"次の版を採用しています",async()=>{await checkCurrent();const stack=history(field,target),destination=stack[direction].at(-1);if(!destination)return;const previous=bound(field,target),result=await adapter.selectRevision(workspace(),destination.result.revision,field);stack[direction].pop();stack[direction==="undo"?"redo":"undo"].push(previous);adopted(field,target,result,destination.recipe);await refresh(workspace());});}
  const runtime={
    adapter,subscribe(listener:()=>void){listeners.add(listener);return()=>{listeners.delete(listener);};},getSnapshot:()=>state,
    async load(id?:string){closed=false;opened=id;publish({busy:true,loading:true,error:"",operation:"画像と保存結果を読み込み中",...(id!==state.data?.workspaceId?{assignmentSuggestions:[]}:{})});
      // What is shown first loads first: a two-group design opens side by side on the first run's field
      // of each group (V-01), both together; any other design on its first field. The others follow.
      try{const opening=await openingFields(id);await refresh(id,true,opening?undefined:1,opening);if(state.data?.workspaceId)publish({messages:await readMessages(state.data.workspaceId)});}catch(error){publish({busy:false,loading:false,operation:"",error:message(error)});throw error;}
      try{
        if(registered.size>(state.data?.fields.length??0)){publish({operation:"残りの視野を読み込み中"});await painted();await refresh(workspace());}if(await placeAfterRestart())await refresh(workspace());await recoverRun();}catch(error){publish({error:message(error)});throw error;}finally{publish({busy:false,loading:false,operation:""});}},
    reload(){return exclusive("保存結果を再読み込み中",reloadSaved);},
    /** The local service answers again (#284 W9): re-read the rows and fields. A row whose upload reached the API shows as
     * registered (the API joins it by the row's ID), a row still "pending" keeps its names, and recorded targets are placed.
     * Nothing is sent again here; sending a row again uses the same row ID, so the API returns the same field. */
    reconnected(){
      if(state.busy)return Promise.resolve();
      // The first load never finished: open what the page was opening. A new workspace the researcher started has
      // nothing saved to re-read, and is never replaced by the workspace that was open before it.
      if(!state.data)return runtime.load(opened);
      if(!state.data.workspaceId)return Promise.resolve();
      return exclusive("保存結果を再読み込み中",reloadSaved);
    },
    /** Hide the last message (used for demo notices, which need no reload). */
    dismissError(){if(state.error)publish({error:""});},
    newWorkspace(){if(state.busy)throw new Error("現在の処理が終わるまでお待ちください。");++epoch;beforeProposal=null;runRequests.clear();added.length=0;omeFiles.clear();files.clear();uploadKeys.clear();sentPaths.clear();uploaded.clear();names.clear();hashes.clear();copies.clear();histories.clear();candidateStore.clear();currentTargets.clear();registered.clear();specification={version:0,spec:null};publish({assignments:{version:0,assignments:[]},activeTarget:"nuclei",settings:defaultRuntimeSettings(),processing:null,proposal:null,error:"",importIssues:[],intakeRows:[],intake:null,messages:[],progress:{},assignmentSuggestions:[]});answers.clear();lastApplicable=null;replaceData(emptyData());},
    dispose(){closed=true;++epoch;if(state.data)releasePreview(state.data);},
    nclDetector(field:string){
      try {const recipe=runtimeNucleolarRecipe(nuclearChannel(field),state.settings,currentTargets.get(field)??{},state.processing);return recipe.detector?.engine==="cytellect-ncl-objects"?recipe.detector:undefined;}catch{return undefined;}
    },
    cellposeSettings(field:string,target:"cell"|"nucleoli"):AnyCellposeProcessingDetector {
      const defining=target==="cell"?state.settings.cellDefinition?.channel:state.settings.nucleolarDefinition.marker;
      const saved=target==="cell"?state.processing?.cells:state.processing?.nucleoli;
      if(saved&&saved.channel===defining&&isCellposeDetector(saved.detector))return saved.detector;
      return target==="cell"?cellposeDetector():nclCellposeDetector();
    },
    selectNclModel(field:string,model:NclParentCellposeProcessingDetector["model"]){
      if(state.busy||state.settings.nucleolarDefinition.source!=="ncl")return;
      const defining=state.settings.nucleolarDefinition.marker;
      if(!defining)return;
      const previous=state.processing?.nucleoli;
      const base=previous?.channel===defining?previous.detector:nclCellposeDetector();
      if(base?.engine!=="cellpose-sam-ncl-parent"||base.protocol_version!=="4.3.0")return;
      const detector=selectNclModel(base,model);
      publish({processing:{...(state.processing??{version:"1.0.0",nuclei:null,nucleoli:null,signal:null}),nucleoli:{channel:defining,detector}}});
    },
    setCellposeParameter(field:string,target:"cell"|"nucleoli",key:"diameter_px"|"flow_threshold"|"cellprob_threshold"|"minimum_area_px"|"normalization_percentile_low"|"normalization_percentile_high"|"smoothing_sigma_px"|"background_radius_px"|"parent_background_percentile"|"nuclear_diameter_fraction"|"minimum_contrast_snr",value:number|null){
      if(state.busy)return;
      const defining=target==="cell"?state.settings.cellDefinition?.channel:state.settings.nucleolarDefinition.marker;
      if(!defining)return;
      const previous=target==="cell"?state.processing?.cells:state.processing?.nucleoli;
      const base=previous&&previous.channel===defining&&isCellposeDetector(previous.detector)?previous.detector:target==="cell"?cellposeDetector():nclCellposeDetector();
      if(key==="smoothing_sigma_px"&&base.engine==="cellpose-sam")return;
      if(key==="background_radius_px"&&base.engine!=="cellpose-sam-ncl")return;
      if((key==="parent_background_percentile"||key==="nuclear_diameter_fraction"||key==="minimum_contrast_snr")&&base.engine!=="cellpose-sam-ncl-parent")return;
      const detector={...base,[key]:value};
      publish({processing:{...(state.processing??{version:"1.0.0",nuclei:null,nucleoli:null,signal:null}),[target==="cell"?"cells":"nucleoli"]:{channel:defining,detector}}});
    },
    setNclParameter(field:string,key:keyof ReturnType<typeof nclObjectDetector>,value:number|null){
      if(state.busy||state.settings.nucleolarDefinition.source!=="ncl"||!state.settings.nucleolarDefinition.marker)return;
      const recipe=runtimeNucleolarRecipe(nuclearChannel(field),state.settings,currentTargets.get(field)??{},state.processing);
      if(recipe.detector?.engine!=="cytellect-ncl-objects")return;
      const detector={...recipe.detector,[key]:value};
      const settings={...state.settings,...(key==="smoothing_sigma_px"?{nucleolarSigma:value}:{}),...(key==="minimum_area_px"?{nucleolarMinimumArea:value}:{}),...(key==="maximum_area_px"?{nucleolarMaximumArea:value}:{})};
      publish({settings,processing:{...(state.processing??{version:"1.0.0",nuclei:null,nucleoli:null,signal:null}),nucleoli:{channel:recipe.defining_channel_id,detector}}});
    },
    selectNucleolarSource(source:NucleolarDefinition["source"],marker:string,algorithm:NucleolarDefinition["algorithm"]=source==="ncl"?"cellpose":null){
      if(state.busy)return;
      const settings={...state.settings,nucleolarDefinition:{...state.settings.nucleolarDefinition,source,marker,algorithm},nucleolarSigma:null,nucleolarRim:null,nucleolarMinimumArea:null,nucleolarMaximumArea:null};
      const processing=source==="ncl"&&algorithm==="cellpose"&&marker
        ?{...(state.processing??{version:"1.0.0" as const,nuclei:null,nucleoli:null,signal:null}),nucleoli:{channel:marker,detector:nclCellposeDetector()}}
        :state.processing?{...state.processing,nucleoli:null}:null;
      publish({settings,processing});
    },
    setSettings(value:RuntimeSettings|((previous:RuntimeSettings)=>RuntimeSettings)){
      if(state.busy)return;
      const settings=normalizedRuntimeSettings(typeof value==="function"?value(state.settings):value),definition=settings.nucleolarDefinition;
      let processing=state.processing;
      if(definition.source==="ncl"&&definition.algorithm==="cellpose"){
        const previous=processing?.nucleoli;
        processing={...(processing??{version:"1.0.0",nuclei:null,nucleoli:null,signal:null}),nucleoli:definition.marker
          ?{channel:definition.marker,detector:previous&&isCellposeDetector(previous.detector)?previous.detector:nclCellposeDetector()}:null};
      }
      publish({settings,processing});
    },
    setNucleolarSigma(value:number|null){
      if(state.busy)return;
      const settings={...state.settings,nucleolarSigma:value},definition=settings.nucleolarDefinition;
      let processing=state.processing;
      if(definition.source==="marker" && definition.marker){
        const previous=processing?.nucleoli?.channel===definition.marker?processing.nucleoli.detector:null;
        const detector=previous?.engine==="cytellect-nucleolar-v2" && previous.source==="marker"?previous:nucleolarDetectorV2(definition);
        processing={...(processing??{version:"1.0.0",nuclei:null,nucleoli:null,signal:null}),nucleoli:{channel:definition.marker,
          detector:{...detector,source:"marker",protocol_version:detector.protocol_version==="2.2.0"?"2.2.0":"2.1.0",smoothing_sigma_px:value??.7}}};
      }
      publish({settings,processing});
    },
    saveSettings(target:ReviewTarget=specification.spec?.target || "nuclei"){return exclusive("解析条件を保存中",async()=>{await checkCurrent();await persistSpecification(target);});},
    specification:()=>specification,
    ensureWorkspace(){return exclusive("ワークスペースを準備中",async()=>{if(state.data?.workspaceId)return state.data.workspaceId;const created=await adapter.create();replaceData({...emptyData(),workspaceId:created.id,title:created.title});return created.id;});},
    saveResultDraft(draft:{statistics?:unknown;figure?:unknown;additional_analyses?:unknown[];figure_proposals?:unknown[]}){return exclusive("統計・図の条件を保存中",async()=>{await checkCurrent();const spec={...currentSpecification(specification.spec?.target??state.activeTarget),...draft};specification=await writeSpecification(workspace(),{version:specification.version,spec});specificationDirty=false;publish({});});},
    saveBackgrounds(backgrounds:Record<string,Record<string,{polygon:Point[];confirmed:true}>>,confirmed_channel_ids:string[]){return exclusive("背景領域を保存中",async()=>{await checkCurrent();publish({settings:{...state.settings,background:"confirmed_roi"}});specificationDirty=true;specification={...specification,spec:{...(specification.spec??{channel_assignment_version:state.assignments.version,target:state.activeTarget,settings:state.settings,processing:state.processing,measurement:null}),backgrounds,confirmed_channel_ids}};await persistSpecification(state.activeTarget);publish({});});},
    saveSelection(selection:unknown){return exclusive("対象選択を保存中",async()=>{await checkCurrent();await persistSpecification(specification.spec?.target??state.activeTarget);specification=await writeSpecification(workspace(),{version:specification.version,spec:{...specification.spec!,selection}});publish({});});},
    resultRecipe(field:string,target:ReviewTarget){return currentTargets.get(field)?.[target]?.recipe;},canUndo(field:string,target:ReviewTarget){return history(field,target).undo.length>0;},canRedo(field:string,target:ReviewTarget){return history(field,target).redo.length>0;},stop(){stopped=true;if(activeRunId)void adapter.cancelWorkspaceRun(workspace(),activeRunId).catch(error=>publish({error:message(error)}));},
    /** Registers the images item by item (#284). A refused image, a name conflict or a copy never stops the others,
     * and the images go to `target` (a run and group) once they are fields, whatever the caller does next. */
    importFiles(list:FileList|File[],mode:"automatic"|"single"="automatic",target?:IntakeTarget|null){return exclusive("画像を登録中",()=>intake(Array.from(list),mode,target??null));},
    /** Sends the images again for one saved row (the same row and upload key): the row is resolved, not duplicated. */
    replaceImport(entry:string,list:FileList|File[]){return exclusive("画像を差し替え中",async()=>{
      const row=adapter.selection()?.entries.find(value=>value.id===entry&&!value.field_id);if(!row)throw new Error("差し替えには、保存状態の再読み込みが必要です。");
      return intake(Array.from(list),"automatic",row.intake?.target??null,{entry});
    });},
    /** Registers a copy the researcher recorded as a separate acquisition (from the list before adding, #284 W5). */
    importSeparately(list:File[],target?:IntakeTarget|null){return exclusive("別の撮影として追加中",()=>intake(list,"automatic",target??null,{separate:true}));},
    /** True when 実行を中止 was pressed during the last addition or run: a 追加 of several additions ends there. */
    stopRequested(){return stopped;},
    /** Shows the result of one 追加 as a whole, when it took several calls of registration (the list before adding). */
    reportIntake(outcome:IntakeOutcome){publish({intake:outcome});},
    /** Records files the judgement before adding found unreadable, as rows with their reason (stage inspect, W5). */
    /** Returns how many were recorded, in order: at the record's limit the rest is not saved, and the caller says so. */
    recordRefused(refused:Array<{names:string[];code:string;target:IntakeTarget|null}>):Promise<number>{return exclusive("取り込みの記録を保存中",async()=>{
      if(!refused.length)return 0;
      if(!state.data?.workspaceId){const created=await adapter.create();replaceData({...emptyData(),workspaceId:created.id,title:created.title});}else await checkCurrent();
      let saved=0;
      for(const item of refused){if((adapter.selection()?.entries.length??0)>=LEDGER_LIMIT)break;
        await adapter.registerImport(workspace(),crypto.randomUUID(),{names:item.names,state:"rejected",stage:"inspect",code:item.code,...(item.target?{target:item.target}:{})});saved++;}
      await refresh(workspace());
      return saved;
    });},
    /** What the list before adding compares against: the hashes of registered inputs and each field's size. */
    registeredFacts(){const known=new Map<string,string>(),fields:Array<{name:string;shape:readonly number[]}>=[];
      for(const field of registered.values()){const name=names.get(field.id)||field.display_name||field.id;fields.push({name,shape:field.image_info.shape});for(const input of Object.values(field.image_info.inputs??{}))known.set(input.sha256,name);}
      return {known,fields};},
    /** "記録から削除": removes the row of an image that never became a field. Registered fields are not touched. */
    cancelImport(entry:string){return exclusive("取り込みの行を削除中",async()=>{await checkCurrent();await adapter.removeImport(workspace(),entry);forgetEntry(entry);await refresh(workspace());});},
    /** Records that a copy (same pixels as another image) is a separate acquisition, and registers it. */
    addSeparately(id:string){return exclusive("別の撮影として追加中",async()=>{const copy=copies.get(id);if(!copy)throw new Error("別の撮影としての追加には、画像の再選択が必要です。");copies.delete(id);
      const outcome=await intake([copy.file],"automatic",null,{separate:true});publish({intake:{...outcome,duplicates:[...(state.intake?.duplicates??[]).filter(value=>value.id!==id),...outcome.duplicates]}});return outcome;});},
    /** The saved experiment design (groups, runs, samples), or null. */
    experiment(){return specification.spec?.experiment??null;},
    /** Hash of the saved stratified design, as the API names it (cohort requests carry it). */
    experimentSha256(){return specification.experiment_sha256??null;},
    /** Saves the experiment design; it never runs, adopts or changes measurements. */
    saveExperiment(experiment:ExperimentDesign){return exclusive("実験デザインを保存中",async()=>{await checkCurrent();const spec={...currentSpecification(specification.spec?.target??state.activeTarget),experiment};specification=await writeSpecification(workspace(),{version:specification.version,spec});specificationDirty=false;publish({});});},
    /** Declares the primary measure (#257 RP-04), or removes the declaration with null; the server records the time. */
    savePrimaryOutcome(primary:PrimaryOutcome|null){return exclusive("主要指標を保存中",async()=>{await checkCurrent();const spec:Record<string,unknown>={...currentSpecification(specification.spec?.target??state.activeTarget)};if(primary)spec.primary_outcome=primary;else delete spec.primary_outcome;specification=await writeSpecification(workspace(),{version:specification.version,spec:spec as typeof specification.spec});specificationDirty=false;publish({});});},
    saveAssignments(assignments:ChannelAssignment[],fieldId?:string){return exclusive("染色設定を保存中",()=>storeAssignments(assignments,fieldId));},
    saveFieldLink(fieldId:string,kind:"analysis"|"reference",referenceFor:string|null=null){return exclusive("画像の対応を保存中",async()=>{await checkCurrent();const links=await adapter.getFieldLinks(workspace());await adapter.saveFieldLink(workspace(),fieldId,{version:links.version,selection_version:adapter.selection()?.version??0,kind,reference_for_field_id:referenceFor});await refresh(workspace());});},
    currentResult(field:string,target:ReviewTarget){
      const saved=currentTargets.get(field)?.[target];
      if(!saved)return undefined;
      if(target!=="nucleoli"&&target!=="nucleoplasm"&&target!=="cell")return saved.result;
      try {const channel=target==="cell"?definitions(field).find(ch=>ch.token===(state.settings.cellDefinition?.source==="cellpose"?state.settings.cellDefinition.channel:saved.recipe.defining_channel_id)):nuclearChannel(field);if(!channel)return undefined;const recipe=runtimeRecipe(target,channel,state.settings,currentTargets.get(field)??{},state.processing);return sameRuntimeRecipe(saved.recipe,recipe)?saved.result:undefined;} catch{return undefined;}
    },
    candidates:candidate, candidateResult(field:string,target:ReviewTarget){return candidate(field,target)?.result;},
    preview(field:string,target:ReviewTarget){return exclusive("候補をプレビュー中",()=>runInternal(target,field,true));},
    acceptCandidates(field:string,target:ReviewTarget){return exclusive("候補を採用中",async()=>{await checkCurrent();if(!await acceptPrepared(field,target))throw new Error("現在の条件に一致する候補がありません。");await refresh(workspace());});},
    run(target:ReviewTarget,fieldId?:string){return exclusive(`${labels[target]}を解析中`,()=>runInternal(target,fieldId));},
    editMask(field:string,target:ReviewTarget,expectedRevision:string,operation:MaskOperation,polygon:Point[],region?:number,merged:number[]=[]){return exclusive("領域を保存・再測定中",async()=>{if(target==="nucleoplasm")throw new Error("核質は核と核小体から計算するため、直接編集できません。");await checkCurrent();const source=bound(field,target,expectedRevision),result=await adapter.editMask(workspace(),source.result,source.recipe,operation,polygon,region,merged);history(field,target).undo.push(source);history(field,target).redo=[];adopted(field,target,result,source.recipe);await refresh(workspace());});},
    correct(field:string,target:ReviewTarget,expectedRevision:string,kind:"delete"|"exclude",region:number){return exclusive("領域を更新中",async()=>{if(target==="nucleoplasm"&&kind==="delete")throw new Error("核質のマスクは直接変更できません。");await checkCurrent();const source=bound(field,target,expectedRevision),result=await adapter.correct(workspace(),source.result,kind,region,source.recipe);history(field,target).undo.push(source);history(field,target).redo=[];adopted(field,target,result,source.recipe);await refresh(workspace());});},
    undo(field:string,target:ReviewTarget){return travel(field,target,"undo");},redo(field:string,target:ReviewTarget){return travel(field,target,"redo");},
    excludeField(field:string,reason:string|null){return exclusive("解析対象を更新中",async()=>{await checkCurrent();const entry=adapter.selection()?.entries.find(value=>value.field_id===field);if(!entry)throw new Error("保存した視野の登録状態を確認できません。");await adapter.excludeField(workspace(),entry.id,reason);await refresh(workspace());});},
    applyProposal,canUndoProposal:()=>beforeProposal!==null,
    undoProposal(){return exclusive("AI適用前の条件に戻しています",async()=>{await checkCurrent();if(!beforeProposal)return;const previous=beforeProposal;publish({settings:previous.settings,processing:previous.processing,activeTarget:previous.specification.spec?.target??"nuclei"});specificationDirty=true;specification={...specification,spec:previous.specification.spec};await persistSpecification(state.activeTarget);beforeProposal=null;candidateStore.clear();publish({});});},
    /** Sends a message to the AI and shows the answer (#284 W2). It changes no setting and runs nothing: the answer
     * is applied, or applied and tried, only by `applyAnswer`, from the researcher's own action (decision 4). */
    requestProposal(goal:string,selectedFieldId?:string,retryFailed=false,messageId?:string){return exclusive("AIに送信中",async()=>{
      if(!state.data?.fields.length&&!goal.trim())throw new Error("AI への送信には、画像または指示が必要です。");
      if(!state.data?.workspaceId){const created=await adapter.create();replaceData({...emptyData(),workspaceId:created.id,title:created.title});}
      await checkCurrent();await persistSpecification(state.activeTarget);
      const field=selectedFieldId||state.data?.fields.find(value=>!value.exclusionReason)?.id;let currentProcessing:ProposalProcessing|null=null;
      if(field){try{currentProcessing=runtimeProposalProcessing(nuclearChannel(field),state.settings,currentTargets.get(field)??{},state.processing);}catch{const cell=state.settings.cellDefinition?.channel;const channel=definitions(field).find(ch=>ch.token===cell);currentProcessing=channel&&state.settings.cellDefinition?.source==="cellpose"?savedProcessing(undefined,undefined,undefined,runtimeRecipe("cell",channel,state.settings,currentTargets.get(field)??{},state.processing)):null;}}
      // A proposal made for another channel configuration is not continued: its channels do not exist in this field.
      const here=new Set(definitions(field).map(value=>value.token));
      const continued=lastApplicable&&lastApplicable.proposal.draft.channels.every(value=>here.has(value.token))?lastApplicable:null;
      let response:Awaited<ReturnType<typeof adapter.draft>>;
      try{response=await adapter.draft(workspace(),goal,retryFailed,{current_processing:currentProcessing,previous_goal:continued?.goal??"",previous_proposal:continued?.proposal.draft??null,...(selectedFieldId?{field_id:selectedFieldId}:{})},messageId);}
      catch(error){publish({messages:await readMessages(workspace())});throw error;}
      rememberGoal(workspace(),goal);
      // An answer to a question continues no settings: the conversation continues from the last proposal (#284 W7).
      if(response.proposal){answers.set(response.message.id,response.proposal);if(response.message.applicable!==false&&response.proposal.draft.intent!=="answer")lastApplicable={goal,proposal:response.proposal};}
      // Assignment suggestions are shown in the experiment table; they replace the previous answer's only when made.
      const suggested=response.proposal?suggestionsOf(response.proposal,response.fields??[]):[];
      publish({messages:withMessage(response.message),...(suggested.length?{assignmentSuggestions:suggested}:{})});
      return response;
    });},
    /** A field's run state, without a 候補を確認 whose candidates were since discarded or adopted (#284 W8). */
    progressOf(field:string,target:ReviewTarget){const value=state.progress[field];return value==="候補を確認"&&!candidate(field,target)?undefined:value;},
    /** Shows 準備中 on fields whose preview or measurement is about to be requested (#284 W8). */
    markPreparing(ids:string[]){if(!state.busy)publish({progress:progressOf(ids,"準備中")});},
    /** Removes 準備中 that no request followed (a preview that did not start, or one that ran without a server run). */
    clearPreparing(ids:string[]){if(!ids.some(id=>state.progress[id]==="準備中"))return;const progress={...state.progress};for(const id of ids)if(progress[id]==="準備中")delete progress[id];publish({progress});},
    /** True when the applicable answer proposes an analysis that can be tried on an image. An answer that declares its
     * kind of request (#284 W7) offers 「設定を適用」 or 「適用して実行」 instead. */
    canTry(messageId:string,selectedFieldId?:string){return this.canApply(messageId,selectedFieldId)&&intentOf(messageId)===null&&!!state.data?.fields.length&&answers.get(messageId)?.draft.recipe!=="none";},
    /** True when this session holds the applicable answer of the message and it proposes settings (not a question's answer). */
    canApply(messageId:string,selectedFieldId?:string){const message=state.messages.find(value=>value.id===messageId),draft=answers.get(messageId)?.draft;
      // An answer without an analysis (recipe none, no processing) has no settings: applying it would only clear the
      // saved measurements. What it settles (a stain's role) is recorded by 「核染色に … を指定」.
      return !!draft&&message?.applicable!==false&&draft.intent!=="answer"&&(draft.recipe!=="none"||!!draft.processing)&&!pendingConfirmation(messageId,selectedFieldId).length;},
    /** The nuclear channels the answer proposes that the researcher has not set yet; applying and running wait for them. */
    confirmationOf(messageId:string,selectedFieldId?:string):ChannelConfirmation[]{const message=state.messages.find(value=>value.id===messageId);
      return message?.applicable===false||message?.effect!=="none"||intentOf(messageId)==="answer"?[]:pendingConfirmation(messageId,selectedFieldId);},
    /** 「核染色に指定」: records the proposed channel as the nuclear stain of the selected field's channel configuration
     * (the researcher's own confirmation, as in 染色対応). It applies no settings and runs nothing. */
    confirmNuclear(messageId:string,channel:string,selectedFieldId?:string){return exclusive("染色設定を保存中",async()=>{
      const proposal=answers.get(messageId),fieldId=answerField(messageId,selectedFieldId),field=state.data?.fields.find(value=>value.id===fieldId);
      if(!proposal||!field||!proposal.needs_confirmation.includes(channel)||!field.channels.some(value=>value.id===channel))throw new Error("核染色の指定には、この発言の再送が必要です。");
      await checkCurrent();
      // Only the named channel's role is the researcher's choice here: the others keep theirs, and one without a role is
      // measured, as when the nuclear stain is chosen in 染色対応. What the answer proposed for them is not recorded.
      await storeAssignments(field.channels.map(value=>({channel_id:value.id,stain:value.stain,role:value.id===channel?"nuclear":value.role==="unused"?"unused":"measure"})),field.id);
      answers.set(messageId,{...proposal,needs_confirmation:proposal.needs_confirmation.filter(value=>value!==channel)});
      if(lastApplicable?.proposal===proposal)lastApplicable={...lastApplicable,proposal:answers.get(messageId)!};
      publish({});
    });},
    /** What the answer of a message received in this session offers; null when it is not held (a reload, a failure). */
    answerOf(messageId:string):AnswerView|null{const proposal=answers.get(messageId);if(!proposal)return null;const draft=proposal.draft;
      return {intent:draft.intent??null,scope:draft.scope??null,choices:draft.choices??[],assignments:(draft.assignments??[]).length,applies:draft.intent!=="answer"&&(draft.recipe!=="none"||!!draft.processing)};},
    /** The fields a run request covers: the selected field, or every registered field that is not excluded. A row
     * without a field (an image that was not registered) is not a field and is never among them. */
    runTargets(messageId:string,selectedFieldId?:string):RunTargets|null{
      const proposal=answers.get(messageId);if(!proposal||proposal.draft.intent!=="run"||!state.data)return null;
      const scope=proposal.draft.scope==="selected"?"selected":"all",eligible=state.data.fields.filter(field=>!field.exclusionReason);
      const chosen=selectedFieldId?answerField(messageId,selectedFieldId):undefined;
      const fields=(scope==="selected"?eligible.filter(field=>field.id===chosen):eligible).map(field=>({id:field.id,label:field.label}));
      return {scope,fields,excluded:state.data.fields.length-eligible.length};
    },
    /** True when the message's applicable run request has an analysis and fields to run it on. */
    canRun(messageId:string,selectedFieldId?:string){return this.canApply(messageId,selectedFieldId)&&answers.get(messageId)?.draft.recipe!=="none"&&!!this.runTargets(messageId,selectedFieldId)?.fields.length;},
    /** Applies the answer's settings and, with `trial`, previews them on the selected field (the researcher's action). */
    applyAnswer(messageId:string,trial:boolean,selectedFieldId?:string){return exclusive(trial?"AIの解析案を試行中":"AIの解析案を適用中",async()=>{
      const proposal=answers.get(messageId),message=state.messages.find(value=>value.id===messageId);
      if(!proposal||!message||message.applicable===false)throw new Error("解析案の適用には、この発言の再送が必要です。");
      await checkCurrent();publish({proposal});
      const field=answerField(messageId,selectedFieldId);
      const run=trial&&!!state.data?.fields.length&&proposal.draft.recipe!=="none";
      if(run&&!field)throw new Error("試行には、視野の選択が必要です。");
      applyProposal(field);
      // A field that failed does not undo what was saved: the message says what was done, then the failure is reported.
      const saved=specification.version;let failure:unknown=null;
      try{if(run)await runInternal(state.activeTarget,field!,true);else await persistSpecification(state.activeTarget);}catch(error){if(specification.version===saved&&!(run&&candidate(field!,state.activeTarget)))throw error;failure=error;}
      const recorded=await adapter.recordEffect(workspace(),messageId,run?"run":"settings");
      publish({messages:withMessage(recorded??{...message,effect:run?"run":"settings"})});
      if(failure)throw failure;
    });},
    /** 「適用して実行」 of a run request (#284 W7): applies its settings and makes detection candidates on its target fields
     * (the selected one, or all eligible). Only from the researcher's action; adopting the candidates stays theirs. */
    runAnswer(messageId:string,selectedFieldId?:string){return exclusive("AIの解析案を実行中",async()=>{
      const proposal=answers.get(messageId),message=state.messages.find(value=>value.id===messageId),targets=runtime.runTargets(messageId,selectedFieldId);
      if(!proposal||!message||message.applicable===false||proposal.draft.intent!=="run")throw new Error("解析案の適用には、この発言の再送が必要です。");
      if(proposal.draft.recipe==="none"||!targets?.fields.length)throw new Error("実行には、対象の視野が必要です。");
      await checkCurrent();publish({proposal});
      // The settings are checked against the channels the answer was made for, whichever field is selected now.
      const basis=answerField(messageId,selectedFieldId);
      applyProposal(targets.scope==="selected"?targets.fields[0].id:basis&&targets.fields.some(field=>field.id===basis)?basis:targets.fields[0].id);
      // Some fields may fail (another channel configuration, an unreadable image): the settings are saved and the other
      // fields have candidates, so the message is recorded as run and the failed fields are reported after it.
      const saved=specification.version;let failure:unknown=null;
      try{await runInternal(state.activeTarget,targets.scope==="selected"?targets.fields[0].id:undefined,true);}catch(error){if(specification.version===saved&&!targets.fields.some(field=>candidate(field.id,state.activeTarget)))throw error;failure=error;}
      // With no candidate on any field, only the settings were applied.
      const effect=targets.fields.some(field=>candidate(field.id,state.activeTarget))?"run" as const:"settings" as const;
      const recorded=await adapter.recordEffect(workspace(),messageId,effect);
      publish({messages:withMessage(recorded??{...message,effect})});
      if(failure)throw failure;
    });},
  };
  return runtime;
}

export function useWorkspaceRuntime(initialWorkspaceId?:string){
  const [runtime]=useState(()=>createWorkspaceRuntime());
  const state=useSyncExternalStore(runtime.subscribe,runtime.getSnapshot,runtime.getSnapshot);
  useEffect(()=>()=>runtime.dispose(),[runtime]);
  useEffect(()=>{
    // Recording a newly created ID in the URL must not reload its live inputs,
    // settings or candidate masks. Actual route changes still restore saved data.
    const current=runtime.getSnapshot().data;
    if(current&&(current.workspaceId||undefined)===initialWorkspaceId)return;
    void runtime.load(initialWorkspaceId).catch(()=>{});
  },[runtime,initialWorkspaceId]);
  return {...state,...runtime,workspaceId:state.data?.workspaceId||undefined};
}
