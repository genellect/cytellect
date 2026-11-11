"use client";
import {isCellposeDetector} from "@/lib/workspace/cellpose-settings";
import {nclObjectDetector} from "@/lib/workspace/nucleolar-definition";
import type {GroupingIssue} from "@/lib/workspace/grouping";
import {Suspense,useEffect,useEffectEvent,useMemo,useReducer,useRef,useState,type CSSProperties,type DragEvent,type ReactNode} from "react";
import {useSearchParams} from "next/navigation";
import {useWorkspaceRuntime,type RuntimeSettings} from "@/lib/workspace/use-workspace-runtime";
import type {ReviewField,ReviewTarget} from "@/lib/workspace/review-preview";
import {metricChoice,metricStructure,metricTarget,metricUsesChannel} from "@/lib/workspace/metric-catalog";
import {MetricSelect} from "./MetricSelect";
import type {ChannelAssignment,MeasurementRow,GfpGateResult,Recipe,SavedResult,RevisionRecord} from "@/lib/workspace/api-adapter";
import {API_CONFIGURED,ApiError,errorCodeMessage,errorMessage,request} from "@/lib/api";
import {activateShowcase,closestExample,isShowcaseNotice,loadShowcaseExtras,type ProposalExample,type ShowcaseDataset,type ShowcaseScene} from "@/lib/showcase";
import {droppedFiles} from "@/lib/workspace/dropped-files";
import {ReviewImageCanvas,type ReviewImageViewport} from "./ReviewImageCanvas";
import type {components} from "@/lib/generated";
import type {Point} from "@/lib/types";
import {ConnectedBackground,type WorkspaceBackgrounds} from "./ConnectedBackground";
import {ConnectedGfp,type WorkspaceGfpFilter} from "./ConnectedGfp";
import {ConnectedResults} from "./ConnectedResults";
import {ExperimentSetup,type AddTarget} from "./ExperimentSetup";
import {MeasurementTable} from "./MeasurementTable";
import {ConnectedNucleusTable,type NucleusTableSource} from "./NucleusTable";
import {ConnectedPartition} from "./ConnectedPartition";
import {ConnectedChannelGate} from "./ConnectedChannelGate";
import {channelGateRequest,recordedChannelGate,type ChannelGateFilter,type ChannelGateResult} from "@/lib/workspace/channel-gate";
import {PARTITION_DIRECTION,colorByChoices,gateLegend,gateStates,nextComparison,shownColorBy,tableHeading,type ColorBy,type NextComparison} from "@/lib/workspace/color-by";
import type {RegionClassification} from "./ReviewImageCanvas";
import type {NucleusTableGate} from "./nucleus-table-model";
import {NextStep,TableHeading,type ColorView,type NextAction} from "./ColorView";
import {UnfinishedImports} from "./UnfinishedImports";
import {PairStage,pairDisplayText,pairRuns,type Historical,type PairDisplay} from "./PairStage";
import {assignFields,fieldsIn,type ExperimentDesign} from "@/lib/workspace/experiment-design";
import {centre,densestPoint,imageStageLayout} from "./image-stage-layout";
import {emptyMetadata} from "./connected-results-model";
import {experimentSetupShown,initialPanelState,panelReducer} from "./panel-state";
import {compositeLayers} from "./composite-layers";
import styles from "./connected-workspace.module.css";
import {DemoBadge,DemoGuide,SceneSwitcher,SideCredit,DOWNLOAD_HREF,LiveStatus,ProposalExamples,ShowcaseContext,UploadDialog,useShowcaseUi,type DemoStep,type ShowcaseUi} from "./showcase-ui";
import showcaseStyles from "./showcase.module.css";
import {AccountIndicator,CloudNotices,CloudPhase,GpuStatus} from "../CloudAccount";

type Mode="experiment"|"image"|"statistics"|"figure";
const targets:Record<ReviewTarget,string>={nuclei:"核",nucleoli:"核小体",nucleoplasm:"核質",cell:"細胞ROI"};
/** The stain names a channel; its id is added only when another channel shows the same stain. */
function channelLabel(ch:{id:string;stain:string|null},all:Array<{id:string;stain:string|null}>){
  if(!ch.stain)return ch.id;
  return all.filter(other=>other.stain===ch.stain).length>1?`${ch.stain} · ${ch.id}`:ch.stain;
}
type Runtime=ReturnType<typeof useWorkspaceRuntime>;
const paths={stop:"M6 6h12v12H6z",plus:"M12 4v16M4 12h16",compare:"M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z",pair:"M3 5h8v14H3zM13 5h8v14h-8z",link:"M10 14l4-4M8.5 11.5 6 14a3 3 0 0 0 4 4l2.5-2.5M15.5 12.5 18 10a3 3 0 0 0-4-4l-2.5 2.5",table:"M4 5h16v14H4zM4 10h16M10 10v9",settings:"M4 7h16M4 17h16M8 4v6M16 14v6",close:"m6 6 12 12M6 18 18-12",back:"m10 5-7 7 7 7M3 12h18",ai:"M4 4h16v12H9l-5 4V4M8 8h8M8 12h5",send:"M12 20V4m-7 7 7-7 7 7"};
function Icon({name}:{name:keyof typeof paths}){return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true"><path d={paths[name]}/></svg>;}
/** `showcase`: the public demo (/demo) — the same workspace on the serverless transport (docs/showcase.md). */
export default function ConnectedWorkspace({showcase=false}:{showcase?:boolean}={}){
  const route=<Suspense fallback={<p>読み込み中…</p>}><WorkspaceRoute/></Suspense>;
  // The provider reads the scene from the query, so it renders inside the same boundary.
  return showcase?<Suspense fallback={<p>読み込み中…</p>}><ShowcaseProvider>{route}</ShowcaseProvider></Suspense>:route;
}
function ShowcaseProvider({children}:{children:ReactNode}){
  // Activated during render so the first runtime request already uses the demo transport.
  useState(()=>activateShowcase());
  const [extras,setExtras]=useState<{examples:ProposalExample[];dataset:ShowcaseDataset|null;scenes:ShowcaseScene[]}>({examples:[],dataset:null,scenes:[]});
  const [upload,setUpload]=useState<"image"|"csv"|null>(null);
  const id=useSearchParams().get("id");
  useEffect(()=>{let live=true;void loadShowcaseExtras().then(value=>{if(live)setExtras(value);});return()=>{live=false;};},[]);
  // The scene of the opened workspace; without one named, the first scene (the newest workspace).
  const scene=extras.scenes.find(item=>item.workspaceId===id)??extras.scenes[0]??null;
  const value=useMemo<ShowcaseUi>(()=>({enabled:true,examples:scene?.examples??extras.examples,
    dataset:scene?.dataset??extras.dataset,scenes:extras.scenes,scene,requestUpload:setUpload}),[extras,scene]);
  const close=useMemo(()=>()=>setUpload(null),[]);
  return <ShowcaseContext.Provider value={value}>{children}<UploadDialog kind={upload} onClose={close}/></ShowcaseContext.Provider>;
}
const steps=new Set(["image","statistics","figure"]);
function WorkspaceRoute(){
  const params=useSearchParams();
  const id=params.get("id")||undefined;
  // `?step=image|statistics|figure` opens that tab (the demo and production alike).
  const step=steps.has(params.get("step")||"")?params.get("step") as DemoStep:undefined;
  const runtime=useWorkspaceRuntime(id);
  useEffect(()=>{
    if(id||!runtime.workspaceId||runtime.busy)return;
    const url=new URL(window.location.href);
    url.searchParams.set("id",runtime.workspaceId);
    window.history.replaceState(window.history.state,"",url);
  },[id,runtime.workspaceId,runtime.busy]);
  return <Workspace runtime={runtime} initialMode={step}/>;
}

function Workspace({runtime:r,initialMode}:{runtime:Runtime;initialMode?:DemoStep}){
  const data=r.data;const fields=useMemo(()=>data?.fields||[],[data]);
  const showcase=useShowcaseUi(),demo=showcase.enabled;
  // The demo offers the region sets it recorded (no cell ROI); production offers every region set.
  // Physical units need every analysed field to have a confirmed pixel size (M-02).
  const calibrated=fields.length>0&&fields.every(value=>value.kind==="reference"||!!value.pixelSizeUm);
  const regionOffered=(id:ReviewTarget)=>!demo||(id!=="cell"&&(!showcase.dataset?.regions||showcase.dataset.regions.includes(id)));
  const [mode,setMode]=useState<Mode>(initialMode??"image"),[selected,setSelected]=useState(""),[channelId,setChannel]=useState(""),[target,setTarget]=useState<ReviewTarget>("nuclei"),[region,setRegion]=useState<number>(),[nucleusView,setNucleusView]=useState(true);
  // The partition's target and reference by name, shared by every pane and the table heading: nucleoplasm ÷ nucleoli,
  // the direction of the statistics metric (owner decision 1, MV-05).
  const [partitionPair,setPartitionPair]=useState<{target:string;reference:string}>({...PARTITION_DIRECTION});
  // How the image colours its regions; the colour mode is the entry to a measurement (MV-01).
  const [colorBy,setColorBy]=useState<ColorBy>("outline");
  // A saved decision that no longer matches the nuclei and fields (MV-10), and a request to judge again in statistics (MV-09).
  const [gateStale,setGateStale]=useState(""),[reclassifyRequest,setReclassifyRequest]=useState(0);
  const explicitMetric=useRef(false);
  // Whether the image leaves room for the table beside it (then the 測定値 button moves it below).
  const [sideRoom,setSideRoom]=useState(false);
  const [lastResultMode,setLastResultMode]=useState<"statistics"|"figure">("statistics");
  // The first images of a workspace without a form, held until the form is chosen (see add).
  const [pending,setPending]=useState<File[]|null>(null);
  const [metric,setMetric]=useState("mean"),[range,setRange]=useState("selected"),[compare,setCompare]=useState(false),[picked,setPicked]=useState<string[]>([]),[picker,setPicker]=useState(false),[table,setTable]=useState(false);
  // The images come first: the panel starts closed, in the demo and in production alike; 設定 opens it.
  const [panelState,dispatchPanel]=useReducer(panelReducer,initialPanelState);
  // Several stains open as a colour merge; choosing one stain shows it alone.
  const [composite,setComposite]=useState(true);
  const ai=panelState.view==="ai",panel=panelState.view==="settings";
  const [instruction,setInstruction]=useState(""),[assignments,setAssignments]=useState(false),[editing,setEditing]=useState(false),[search,setSearch]=useState(""),[returnMode,setReturnMode]=useState<Mode|null>(null);
  const sourceReturn=useRef<{mode:Mode;field:string;channel:string;target:ReviewTarget;metric:string;region:number|undefined;historical:Historical|null}|null>(null);
  const [localError,setLocalError]=useState(""),[viewport,setViewport]=useState<Record<string,ReviewImageViewport|null>>({});
  const [previewRequest,setPreviewRequest]=useState<{field:string;target:ReviewTarget;sequence:number}|null>(null);
  const [gfpSaved,setGfpSaved]=useState<{signature:string;result:GfpGateResult;filter:WorkspaceGfpFilter}|null>(null);
  const [channelSaved,setChannelSaved]=useState<{signature:string;result:ChannelGateResult;filter:ChannelGateFilter}|null>(null);
  const [backgroundDraw,setBackgroundDraw]=useState<{field:string;channels:string[];id:string}|null>(null);
  const [historical,setHistorical]=useState<Historical|null>(null);
  const sourceRequest=useRef(0);
  const fileInput=useRef<HTMLInputElement>(null),folderInput=useRef<HTMLInputElement>(null);
  const field=fields.find(value=>value.id===selected)||fields[0];
  // Nucleoli and nucleoplasm open on the nucleolar marker (the defined one, else the first other used stain) unless a stain was chosen.
  const markerChannel=target==="nucleoli"||target==="nucleoplasm"?(field?.channels.find(value=>value.id===r.settings.nucleolarDefinition.marker&&value.id!==field?.nuclearChannelId&&value.role!=="nuclear")??field?.channels.find(value=>value.id!==field?.nuclearChannelId&&value.role!=="nuclear"&&value.role!=="unused"))?.id:undefined;
  const actualChannel=field?.channels.find(value=>value.id===channelId)?.id||markerChannel||field?.nuclearChannelId||field?.channels.find(value=>value.role==="nuclear")?.id||field?.channels[0]?.id||"";
  const historicResult=historical?.target===target&&historical.result.field===field?.id?historical.result:undefined;
  const candidate=field&&!historicResult?r.candidateResult(field.id,target):undefined;
  const result=historicResult||candidate||(field?r.currentResult(field.id,target):undefined);
  const rows=result?.rows.filter(value=>value.channel_id===actualChannel)||[];
  // Nuclei of the shown field (the demo answers its tables from the recording).
  const nuclearResult=target==="nuclei"&&!historicResult&&!candidate&&field?r.currentResult(field.id,"nuclei"):undefined;
  const nucleusTableSource:NucleusTableSource|undefined=field&&nuclearResult?{shown:nucleusView,onShow:setNucleusView,load:r.adapter.nucleusTable,save:r.adapter.saveNucleusTable,field:field.id,caption:field.label,exclusion:field.exclusionReason,
    nuclearRevision:nuclearResult.revision,nucleolarRevision:r.currentResult(field.id,"nucleoli")?.revision,channels:field.channels}:undefined;
  const planes=fields.flatMap(value=>value.channels.map(ch=>({field:value,channel:ch,key:`${value.id}:${ch.id}`})));
  const visible=compare?planes.filter(value=>picked.includes(value.key)):planes.filter(value=>value.field.id===field?.id&&value.channel.id===actualChannel);
  // The table beside one image lists `rows` (the selected field in the selected channel), which a comparison may not show:
  // its heading names those rows' stain, and their field when the image is another field's.
  // The field the rows come from, named when the images in view include another field.
  const rowsField=field&&visible.some(value=>value.field.id!==field.id)?field.label:"";
  const mergeable=!!field&&compositeLayers(field).length>1,merged=composite&&mergeable&&!compare;
  const transportAvailable=API_CONFIGURED||demo;
  const busy=r.busy||editing||!transportAvailable;
  const intakeDisabled=!data||r.busy||!transportAvailable;
  const [guide,setGuide]=useState(false);
  // The in-browser API downloads after the recorded view has painted (capable devices only).
  const loaded=!!data;
  useEffect(()=>{if(!demo||!loaded)return;const timer=setTimeout(()=>activateShowcase().prepare(),1500);return()=>clearTimeout(timer);},[demo,loaded]);
  // A link to a result tab (?step=) opens it as choosing the tab does: with a workspace to save into.
  const linkedResult=useRef(initialMode==="statistics"||initialMode==="figure");
  const openLinkedResult=useEffectEvent(()=>{if(!data?.workspaceId)void act(()=>r.ensureWorkspace());});
  useEffect(()=>{if(!linkedResult.current||!loaded||r.busy)return;linkedResult.current=false;openLinkedResult();},[loaded,r.busy]);
  useEffect(()=>closeDismissible(),[mode,field?.id]);
  useEffect(()=>{
    const outside=(event:PointerEvent)=>closeDismissible(event.target instanceof Node?event.target:null);
    const escape=(event:KeyboardEvent)=>{if(event.key==='Escape')closeDismissible();};
    document.addEventListener('pointerdown',outside);document.addEventListener('keydown',escape);
    return()=>{document.removeEventListener('pointerdown',outside);document.removeEventListener('keydown',escape);};
  },[]);
  function chooseFiles(folder=false){if(demo){showcase.requestUpload("image");return;}(folder?folderInput:fileInput).current?.click();}
  const gfpUnit=target==="cell"?"cell_roi":"nucleus";
  const classificationTarget=target==="cell"?"cell":"nuclei";
  const nuclearFields=fields.flatMap(value=>{const current=r.currentResult(value.id,classificationTarget);return current&&!value.exclusionReason?[{fieldId:value.id,label:value.label,revisionId:current.revision}]:[];});
  const nuclearSignature=JSON.stringify([data?.workspaceId,gfpUnit,nuclearFields.map(value=>[value.fieldId,value.revisionId])]);
  const storedSpec=r.specification().spec as components["schemas"]["AnalysisSpec"]|null;
  const backgrounds:WorkspaceBackgrounds=Object.fromEntries(Object.entries(storedSpec?.backgrounds||{}).map(([id,channels])=>[id,
    Object.fromEntries(Object.entries(channels).map(([channel,roi])=>[channel,{confirmed:true as const,
      polygon:roi.polygon.filter(point=>point.length===2).map(point=>[point[0],point[1]] as Point)}]))]));
  const storedSelection=r.specification().spec?.selection as {gfp?:WorkspaceGfpFilter|null;channel_gate?:ChannelGateFilter|null}|undefined;
  const savedFilter=storedSelection?.gfp||null;
  const gfpFilter=savedFilter&&(savedFilter.version==="1.1.0"?savedFilter.unit||"nucleus":"nucleus")===gfpUnit?savedFilter:null;
  const channelFields=fields.flatMap(value=>{const current=r.currentResult(value.id,"nuclei");return current&&!value.exclusionReason?[{fieldId:value.id,label:value.label,revisionId:current.revision}]:[];});
  const channelSignature=JSON.stringify([data?.workspaceId,channelFields,fields.map(value=>[value.id,value.metadata,value.channels])]);
  const channelFilter=metricTarget(metric,target)!=="cell"?storedSelection?.channel_gate??null:null;
  const channelClassification=!historical&&channelSaved?.signature===channelSignature&&JSON.stringify(channelSaved.filter)===JSON.stringify(channelFilter)?channelSaved.result.nuclei:undefined;
  const classificationCurrent=gfpSaved?.signature===nuclearSignature&&JSON.stringify(gfpSaved.filter)===JSON.stringify(gfpFilter);
  const classification=!historical&&classificationCurrent?gfpSaved.result.objects??gfpSaved.result.nuclei:undefined;
  const filterKey=JSON.stringify(gfpFilter);
  const restoreClassification=useEffectEvent(async()=>{
    if(!gfpFilter||!data?.workspaceId||!nuclearFields.length)return null;
    const legacy=gfpFilter.version==="1.0.0";
    const response=await r.adapter.gfpGate(data.workspaceId,{
      gfp_channel_id:gfpFilter.gfp_channel_id,unit:gfpUnit,percentile:legacy?gfpFilter.percentile:99,
      method:legacy?"negative_control":gfpFilter.method,values:legacy?"raw":gfpFilter.values,
      ...(!legacy&&gfpFilter.method==="manual"&&gfpFilter.threshold!==null?{threshold:gfpFilter.threshold}:{}),
      fields:nuclearFields.map(value=>({field_id:value.fieldId,revision_id:value.revisionId,
        control:legacy&&gfpFilter.control_field_ids.includes(value.fieldId)})),
    });
    return {signature:nuclearSignature,result:response,filter:gfpFilter};
  });
  useEffect(()=>{
    if(busy||classificationCurrent||filterKey==="null")return;
    let cancelled=false;
    void restoreClassification().then(value=>{if(value&&!cancelled)setGfpSaved(value);}).catch(error=>{
      if(!cancelled)setLocalError(error instanceof Error?error.message:"GFPの分類を読み込めませんでした。");
    });
    return()=>{cancelled=true;};
  },[busy,classificationCurrent,filterKey,nuclearSignature]);
  const sourceTarget=metricTarget(metric,target),checkedTarget=metricStructure(metric,target);
  const sources=useMemo(()=>fields.map(value=>({fieldId:value.id,label:value.label,result:value.results[sourceTarget],metadata:{...emptyMetadata,...Object.fromEntries(Object.keys(emptyMetadata).map(key=>[key,value.metadata?.[key]??null]))},excluded:!!value.exclusionReason})),[fields,sourceTarget]);
  async function act(action:()=>Promise<unknown>){setLocalError("");try{await action();}catch(error){setLocalError(error instanceof ApiError?errorMessage(error):error instanceof Error?errorCodeMessage(error.message):"処理を完了できませんでした。");}}
  function openField(id:string,ch?:string){if(editing)return;setPreviewRequest(null);++sourceRequest.current;setHistorical(null);setSelected(id);
    // Side by side, a field chosen in the list brings its own run into the two panes.
    const fieldRun=experiment?.fields?.[id]?.run_id;if(fieldRun)setPairRun(fieldRun);
    if(ch)setChannel(ch);setRegion(undefined);setCompare(false);if(target==="cell"&&r.settings.cellDefinition?.source!=="cellpose"&&!fields.find(value=>value.id===id)?.results.cell&&!busy)void act(()=>r.run("cell",id));}
  async function openSource(id:string,n?:number,revision?:string,sourceStructure?:ReviewTarget,sourceChannel?:string|null,shownStructure?:ReviewTarget){
    if(editing)return;
    setPreviewRequest(null);
    const generation=++sourceRequest.current;
    await act(async()=>{
      // The values come from one region set; they are checked on the structure they describe.
      const resolvedTarget=sourceStructure||sourceTarget,shown=shownStructure||(sourceStructure?resolvedTarget:metricStructure(metric,target));
      const sourceField=fields.find(value=>value.id===id);
      if(!sourceField)throw new Error("図の元画像を確認できません。");
      if(sourceChannel&&!sourceField.channels.some(value=>value.id===sourceChannel))throw new Error("図の測定チャンネルと元画像が一致しません。");
      let saved:SavedResult|undefined,recipe:Recipe|undefined;
      if(revision){
        let record=await request<RevisionRecord & {config:RevisionRecord["config"] & {cohort_sources?:Record<string,{revision_id:string}>}}>(`/v1/revisions/${encodeURIComponent(revision)}`);
        const pinned=record.config.cohort_sources?.[id]?.revision_id;
        if(pinned){revision=pinned;record=await request<RevisionRecord>(`/v1/revisions/${encodeURIComponent(pinned)}`);}
        if(!record.config.field_ids.includes(id))throw new Error("図の出典と視野が一致しません。");
        saved=await r.adapter.readResult(revision,id,record.config.recipe);recipe=record.config.recipe;
        if(saved.field!==id||saved.regionSet!==resolvedTarget)throw new Error("図の測定対象と保存された領域が一致しません。");
      }
      const sourceResult=saved||sourceField.results[resolvedTarget];
      if(n!==undefined&&!sourceResult?.masks.regions.some(value=>value.id===n))throw new Error("図の対象領域を保存されたマスクで確認できません。");
      // A per-nucleus value (a nucleus's nucleoli) is checked on that analysis's own nucleoli,
      // with the nucleus it belongs to outlined (Q-05, V-04).
      let checked=saved,context:Historical["context"],nucleus:number|undefined;
      if(shown!==resolvedTarget){
        nucleus=n;
        if(saved&&recipe){
          const structureRevision=shown==="nucleoli"?recipe.nucleolar_revision_id:shown==="nuclei"?recipe.nuclear_revision_id:undefined,nuclearRevision=recipe.nuclear_revision_id;
          if(!structureRevision)throw new Error("図の値を確かめる構造を、保存された解析版で確認できません。");
          checked=await r.adapter.readResult(structureRevision,id);
          if(checked.field!==id||checked.regionSet!==shown)throw new Error("図の測定対象と保存された領域が一致しません。");
          if(nuclearRevision)context=(await request<SavedResult["masks"]>(`/v1/revisions/${encodeURIComponent(nuclearRevision)}/region-masks?field_id=${encodeURIComponent(id)}`)).regions;
        }
      }
      if(generation!==sourceRequest.current)return;
      sourceReturn.current={mode,field:selected,channel:channelId,target,metric,region,historical};
      setHistorical(checked?{target:shown,result:checked,context,nucleus}:null);
      setReturnMode(mode);setSelected(id);setTarget(shown);setRegion(shown===resolvedTarget?n:undefined);setCompare(false);setMode("image");
      setChannel(sourceChannel||sourceField.nuclearChannelId||sourceField.channels[0]?.id||"");
    });
  }
  function returnToResult(){if(editing)return;const context=sourceReturn.current;if(!context)return;++sourceRequest.current;setSelected(context.field);setChannel(context.channel);setTarget(context.target);setMetric(context.metric);setRegion(context.region);setHistorical(context.historical);setMode(context.mode);setReturnMode(null);sourceReturn.current=null;}
  function newWorkspace(){++sourceRequest.current;sourceReturn.current=null;r.newWorkspace();const url=new URL(window.location.href);url.searchParams.delete("id");window.history.replaceState(window.history.state,"",url);setHistorical(null);setSelected("");setChannel("");setPicked([]);setRegion(undefined);setGfpSaved(null);setViewport({});setPreviewRequest(null);setMode("image");setReturnMode(null);setLocalError("");setPending(null);}
  function changeMode(value:Mode){if(editing)return;dispatchPanel("work");if(returnMode===value){returnToResult();return;}++sourceRequest.current;sourceReturn.current=null;setPreviewRequest(null);if(value==="statistics"||value==="figure")setLastResultMode(value);setMode(value);setReturnMode(null);setAssignments(false);setPicker(false);if(value!=="image"&&!data?.workspaceId&&!r.busy)void act(()=>r.ensureWorkspace());}
  function queuePreview(nextTarget:ReviewTarget=target){if(field)setPreviewRequest({field:field.id,target:nextTarget,sequence:Date.now()});}
  function setSetting<K extends keyof RuntimeSettings>(key:K,value:RuntimeSettings[K]){r.setSettings(previous=>({...previous,[key]:value}));queuePreview();}
  const previewNow=useEffectEvent(async(request:{field:string;target:ReviewTarget})=>{
    const definition=r.settings.nucleolarDefinition;
    if(request.target==="cell"&&r.settings.cellDefinition?.source==="cellpose"&&!r.settings.cellDefinition.channel)return;
    if((request.target==="nucleoli"||request.target==="nucleoplasm")&&definition.source!=="dapi_poor"&&!definition.marker)return;
    setPreviewRequest(null);
    await act(()=>r.preview(request.field,request.target));
  });
  function selectNucleolarSource(source:RuntimeSettings["nucleolarDefinition"]["source"]){
    const channels=field?.channels||[];
    const markers=channels.filter(ch=>ch.role==="measure"&&ch.stain?.trim().toLowerCase()==="ncl");
    const marker=source==="ncl"?(markers.length===1?markers[0].id:""):source==="marker"?r.settings.nucleolarDefinition.marker:"";
    r.selectNucleolarSource(source,marker);
    if(marker)setChannel(marker);
    queuePreview();
  }
  const nclDefaults=(field?r.nclDetector(field.id):undefined)||nclObjectDetector();
  const nclAlgorithm=r.settings.nucleolarDefinition.algorithm||(isCellposeDetector(r.processing?.nucleoli?.detector)?"cellpose":r.processing?.nucleoli?.detector.engine==="fiji-nucleolar-compartments"?"legacy":"objects");
  const nclProcessing=r.processing?.nucleoli;
  const rawNclCellpose=!!nclProcessing&&nclAlgorithm==="cellpose"&&nclProcessing.channel===r.settings.nucleolarDefinition.marker&&nclProcessing.detector.engine==="cellpose-sam";
  // A Cellpose detector is chosen for the region on screen (the GPU phase shows while it runs).
  const cellposeChosen=(target==="cell"&&r.settings.cellDefinition?.source==="cellpose")||((target==="nucleoli"||target==="nucleoplasm")&&r.settings.nucleolarDefinition.source==="ncl"&&nclAlgorithm==="cellpose");
  const previewSettings=JSON.stringify([r.settings,r.processing]);
  useEffect(()=>{if(!previewRequest||busy)return;const timer=setTimeout(()=>void previewNow(previewRequest),650);return()=>clearTimeout(timer);},[previewRequest,busy,previewSettings]);
  useEffect(()=>{setTarget(r.activeTarget);setRegion(undefined);},[r.activeTarget]);
  // A demo scene opens on the channel its opening comparison measures, unless one was already chosen.
  const openingChannel=demo?showcase.scene?.channel:undefined;
  useEffect(()=>{if(openingChannel)setChannel(previous=>previous||openingChannel);},[openingChannel]);
  async function classify(result:GfpGateResult,filter:WorkspaceGfpFilter){await act(async()=>{await r.saveSelection({field_ids:nuclearFields.map(value=>value.fieldId),gfp:filter});setGfpSaved({signature:nuclearSignature,result,filter});});}
  async function classifyChannel(result:ChannelGateResult,filter:ChannelGateFilter){await r.saveSelection({field_ids:channelFields.map(value=>value.fieldId),gfp:null,channel_gate:filter});setGfpSaved(null);setGateStale("");setChannelSaved({signature:channelSignature,result,filter});}
  /** The colour mode chosen on the image. Positive and negative nuclei are judged in the side panel, which opens with it (MV-04). */
  function chooseColorBy(value:ColorBy){setColorBy(value);if(value!=="outline"&&target!=="nuclei")changeTarget("nuclei");if(value==="positivity")dispatchPanel("settings");}
  /** The next step (MV-09): statistics with what the image shows; positivity judges the compared fields again by the same rule. */
  function compareGroups(next:NextComparison){
    explicitMetric.current=true;setMetric(next.metric);if(next.channel)setChannel(next.channel);
    if(next.reclassify)setReclassifyRequest(Date.now());changeMode("statistics");
  }
  async function saveBackground(polygon:Point[]){
    if(!backgroundDraw)return;
    const updated={...backgrounds,[backgroundDraw.field]:{...backgrounds[backgroundDraw.field]}};
    for(const channel of backgroundDraw.channels)updated[backgroundDraw.field][channel]={polygon,confirmed:true};
    await r.saveBackgrounds(updated,[...new Set([...(storedSpec?.confirmed_channel_ids||[]),...backgroundDraw.channels])]);
    setBackgroundDraw(null);queuePreview();
  }
  function changeTarget(value:ReviewTarget){
    ++sourceRequest.current;setPreviewRequest(null);setHistorical(null);setTarget(value);setRegion(undefined);
    // The colour modes are per nucleus; another region shows its outlines.
    if(value!=="nuclei")setColorBy("outline");
    if(value==="cell"&&r.settings.cellDefinition?.source!=="cellpose"&&field&&!field.results.cell&&!busy)void act(()=>r.run("cell",field.id));
  }
  async function measure(){await act(()=>r.run(target,range==="selected"?field?.id:undefined));}
  function showSettings(){if(ai)setMode("image");dispatchPanel("settings");}
  async function send(){await sendInstruction(instruction);}
  // The demo answers any wording: it maps the request onto the closest recorded analysis, or explains what this dataset supports.
  const [demoReply,setDemoReply]=useState("");
  async function sendInstruction(value:string){
    dispatchPanel("open-ai");setDemoReply("");
    if(demo&&!showcase.examples.some(example=>example.instruction===value.trim())){
      const example=closestExample(value,showcase.examples);
      if(!example){setDemoReply(`${showcase.scene?.assistantScope??"このデモは、記録した公開画像の解析だけに答えます。"}たとえば下の指示で試せます。`);return;}
      await act(()=>r.requestProposal(example.instruction,field?.id));return;
    }
    await act(()=>r.requestProposal(value,field?.id));
  }
  // The 画像 and フォルダ buttons and a drop of files or folders add images the same way. A chosen list is read at once
  // (the input is cleared right after); a drop's files arrive once its folders are read.
  // The first images of a workspace without a form wait for the choice (1 画面, 2 画面 or none), so they never land in a
  // view the researcher did not choose; later images follow the choice already made.
  function add(list:FileList|Promise<File[]>|null){
    if(!demo&&!experiment&&!fields.length){void (list instanceof Promise?list:Promise.resolve(list?Array.from(list):[])).then(files=>{if(files.length){setPending(files);setMode("experiment");}});return;}
    if(list instanceof Promise)void act(async()=>r.importFiles(await list));else if(list)void act(()=>r.importFiles(list));
  }
  // Experiment design (requirements E-01–E-08): saving never runs or changes analyses.
  const experiment=r.experiment();
  // The demo classifies nuclei only by the stains its scene names (positive and negative must mean something).
  const sceneGate=demo?showcase.dataset?.gateChannels:null;
  const gateChannels=(field?.channels||data?.channels||[]).filter(value=>!sceneGate||sceneGate.includes(value.id));
  // The colour modes the shown field can be coloured by, and the one in effect (MV-01). They are per nucleus.
  const colorChoices=colorByChoices({nuclei:!!field&&!!r.currentResult(field.id,"nuclei"),gateChannels:gateChannels.length,
    nucleoli:!!field&&!!r.currentResult(field.id,"nucleoli"),nucleoplasm:!!field&&!!r.currentResult(field.id,"nucleoplasm"),saved:!!historicResult||!!candidate});
  const colorShown:ColorBy=target==="nuclei"?shownColorBy(colorBy,colorChoices):"outline";
  const stainName=(id:string)=>{const ch=(field?.channels||data?.channels||[]).find(value=>value.id===id);return ch?ch.stain||ch.id:id;};
  const gateStain=channelFilter?stainName(channelFilter.channel_id):"";
  /** Each region's state on one field's image: the saved channel decision in the positivity mode, the GFP decision on outlines. */
  function regionStates(fieldId:string):Record<number,RegionClassification>|undefined{
    if(colorShown==="positivity")return channelClassification?gateStates(channelClassification,fieldId):undefined;
    if(colorShown==="outline"&&classification&&(target==="nuclei"||target==="cell"))return Object.fromEntries(classification.filter(item=>item.field_id===fieldId)
      .map(item=>[item.region_id,item.gfp_positive===null?"unknown":item.gfp_positive?"positive":"negative"]));
    return undefined;
  }
  function legendFor(fieldId:string){
    if(colorShown==="positivity"){const states=regionStates(fieldId);return states?gateLegend(states as Record<number,"positive">).map(item=>({key:item.status,label:item.label,count:item.count})):undefined;}
    if(colorShown==="compartments")return [{key:"nucleoplasm",label:"核質"},{key:"nucleoli",label:"核小体"}];
    return undefined;
  }
  const fillsFor=(fieldId:string)=>colorShown==="compartments"?r.currentResult(fieldId,"nucleoli")?.masks.regions:undefined;
  function gateTableFor(fieldId:string):NucleusTableGate|undefined{
    if(colorShown!=="positivity"||!channelClassification)return undefined;
    return {stain:gateStain,nuclei:Object.fromEntries(channelClassification.filter(item=>item.field_id===fieldId)
      .map(item=>[item.region_id,{status:item.status,value:item.channel_mean,threshold:item.threshold,reason:item.reason}]))};
  }
  /** What the table under an image lists (MV-06). */
  function headingFor(nucleusTable:boolean,shownRows:MeasurementRow[]){
    if(colorShown==="positivity")return channelFilter?tableHeading({colorBy:"positivity",stain:gateStain,method:channelFilter.method,values:channelFilter.values}):"核ごと · 陽性・陰性は未判定";
    if(colorShown==="compartments")return tableHeading({colorBy:"compartments",stain:stainName(actualChannel),target:targets[partitionPair.target as ReviewTarget]??partitionPair.target,reference:targets[partitionPair.reference as ReviewTarget]??partitionPair.reference});
    return tableHeading({colorBy:"outline",target,stain:stainName(actualChannel),corrected:shownRows.some(row=>row.mean_corrected!=null),nucleusTable});
  }
  // The one next step beside the table (MV-09), for a two-group design.
  const nextStep=experiment?.layout==="pair"&&!historicResult&&!candidate?nextComparison({colorBy:colorShown,metric,target,channel:actualChannel,stain:stainName(actualChannel)}):null;
  /** The partition table of one field (MV-05): nucleoli and nucleoplasm of its adopted nuclei, in the stain chosen above the image. */
  function partitionFor(value:ReviewField){
    const nuclear=r.currentResult(value.id,"nuclei"),ch=value.channels.find(item=>item.id===actualChannel);
    const sources=(["nucleoli","nucleoplasm"] as const).flatMap(name=>{const current=r.currentResult(value.id,name);return current?[{name,revisionId:current.revision,label:targets[name]}]:[];});
    return <ConnectedPartition key={`${value.id}:${nuclear?.revision??""}`} fieldId={value.id} fieldLabel={value.label} nuclearRevisionId={nuclear?.revision}
      sources={sources} pair={partitionPair} onPair={setPartitionPair} channel={{id:actualChannel,label:ch?channelLabel(ch,value.channels):actualChannel,stain:ch?.stain}}
      load={request=>explained(()=>r.adapter.regionPartition(request))} exportCsv={request=>explained(()=>r.adapter.saveRegionPartition(request))}
      selectedNucleus={value.id===field?.id?region:undefined} onSelectNucleus={id=>{setSelected(value.id);setRegion(id);}}/>;
  }
  const nextAction=nextStep?{...nextStep,disabled:colorShown==="positivity"&&!channelFilter,onClick:()=>compareGroups(nextStep)}:null;
  // A saved decision colours the image again after a reload, when it still matches the nuclei and fields (MV-10).
  const restoreKey=JSON.stringify([channelSignature,channelFilter]);
  const restoredFor=useRef("");
  const restoreGate=useEffectEvent(async()=>{
    if(!channelFilter||!data?.workspaceId||!channelFields.length)return;
    restoredFor.current=restoreKey;
    try{
      const result=await r.adapter.channelGate(data.workspaceId,channelGateRequest({...channelFilter,reference_sha256:null},channelFields));
      if(restoredFor.current!==restoreKey)return;
      if(result.record.decision_sha256!==channelFilter.reference_sha256){setGateStale("保存した判定の記録が、今の核や視野と合いません。右の「陽性・陰性の判定」で判定し直してください。");return;}
      setGateStale("");setChannelSaved({signature:channelSignature,result,filter:recordedChannelGate(result)});
    }catch(error){if(restoredFor.current===restoreKey&&!isShowcaseNotice(error instanceof Error?error.message:""))setGateStale(error instanceof Error?error.message:"保存した判定の記録を読み込めませんでした。");}
  });
  useEffect(()=>{if(colorShown!=="positivity"||busy||!channelFilter||channelClassification||restoredFor.current===restoreKey)return;void restoreGate();},[colorShown,busy,channelFilter,channelClassification,restoreKey]);
  // Two-group designs open side by side (V-01); the single view stays one click away.
  const [pairView,setPairView]=useState(true);
  const pairActive=pairView&&experiment?.layout==="pair"&&!compare&&!backgroundDraw;
  // The pair's run, zoom link and per-pane measurements sit in the one image toolbar row.
  const [pairRun,setPairRun]=useState(""),[pairLinked,setPairLinked]=useState(true),[pairTables,setPairTables]=useState(true);
  const [pairDisplay,setPairDisplay]=useState<PairDisplay|null>(null);
  const runsShown=experiment?.layout==="pair"?pairRuns(experiment):[];
  // The selected field decides what the pair shows (V-02): its run, in its group's pane. Choosing a run
  // selects that run's first field; selecting a field (the list, a pane, a figure's source) shows its run.
  const selectedRun=field?experiment?.fields?.[field.id]?.run_id:undefined;
  const pairRunId=selectedRun&&runsShown.some(run=>run.id===selectedRun)?selectedRun:runsShown.some(run=>run.id===pairRun)?pairRun:runsShown[0]?.id??"";
  function choosePairRun(id:string){
    if(!experiment)return;setPairRun(id);
    // The selected field (measurement, candidates, the side panel) follows the run shown (control first).
    const groups=[...experiment.groups].sort((a,b)=>(a.id===experiment.control_group_id?-1:0)-(b.id===experiment.control_group_id?-1:0));
    const first=groups.flatMap(group=>fieldsIn(experiment,group.id,id).map(([fid])=>fid))[0];
    if(first){setSelected(first);setRegion(undefined);}
  }
  // Another method's published objects for this scene's images (demo only, display only).
  async function explained<T>(task:()=>Promise<T>){try{return await task();}catch(error){throw new Error(error instanceof ApiError?errorMessage(error):error instanceof Error?errorCodeMessage(error.message):"処理を完了できませんでした。");}}
  const saveExperiment=(design:ExperimentDesign)=>explained(async()=>{if(!r.workspaceId)await r.ensureWorkspace();await r.saveExperiment(design);if(mode==="image"&&!fields.length)setMode("experiment");});
  const addToExperiment=(target:AddTarget,list:FileList|File[],design:ExperimentDesign)=>explained(async()=>{const ids=await r.importFiles(list);if(ids.length)await r.saveExperiment(assignFields(design,ids,{group_id:target.groupId,run_id:target.runId,sample:target.sample}));return ids;});
  // The images that waited for the choice go where the researcher puts them; one screen has one place, and opens on them.
  const placePending=async(target:AddTarget,design:ExperimentDesign)=>{if(!pending)return;const ids=await addToExperiment(target,pending,design);setPending(null);if(design.layout==="single"&&ids[0]){setSelected(ids[0]);setMode("image");}};
  const setup=<ExperimentSetup design={experiment} fields={fields.filter(value=>value.kind!=="reference").map(value=>{const ch=value.nuclearChannelId||value.channels[0]?.id;return {id:value.id,label:value.label,preview:ch?value.previews[ch]:undefined};})}
    busy={r.busy||!transportAvailable} readOnly={demo} onSave={saveExperiment} onAdd={addToExperiment} pending={pending&&!demo?{count:pending.length,onPlace:placePending,onWithoutForm:()=>{const files=pending;setPending(null);setMode("image");void act(()=>r.importFiles(files));},onDiscard:()=>setPending(null)}:undefined} onOpenField={id=>{setSelected(id);changeMode("image");}} onCsv={()=>changeMode("statistics")}/>;
  const setupShown=experimentSetupShown(mode,!!field,demo);
  // The nucleus table step shows one field's nuclei (the table lists one field's nuclei) with its table open.
  // The view the visitor had before the guide's nucleus-table step, restored when the guide leaves that step.
  const guidePair=useRef<boolean|null>(null);
  function guideStep(next:DemoStep,openTable:boolean,nucleus=false){changeMode(next);if(openTable){setTable(true);setPairTables(true);}
    if(nucleus){guidePair.current??=pairView;setPairView(false);setCompare(false);changeTarget("nuclei");setNucleusView(true);}
    else{setNucleusView(false);if(guidePair.current!==null){setPairView(guidePair.current);guidePair.current=null;}}}
  useEffect(()=>{folderInput.current?.setAttribute("webkitdirectory","");},[]);
  const chooseComparison=()=>{if(!picked.length&&field)setPicked(field.channels.map(ch=>`${field.id}:${ch.id}`));setCompare(true);setPicker(true);};

  // Files and folders dropped anywhere on the workspace; the demo explains that it cannot add them. While adding is
  // unavailable a drop is refused (never opened by the browser in place of the workspace).
  const dropFiles={onDragOver:(event:DragEvent)=>{if(!event.dataTransfer.types.includes("Files"))return;event.preventDefault();event.dataTransfer.dropEffect=demo||!intakeDisabled?"copy":"none";},
    onDrop:(event:DragEvent)=>{if(!event.dataTransfer.types.includes("Files"))return;event.preventDefault();if(demo)showcase.requestUpload("image");else if(!intakeDisabled)add(droppedFiles(event.dataTransfer));}};
  return <main className={styles.workspace} data-mode={mode} data-panel={ai||(mode==="image"&&!!field&&panel)} data-ai={ai} {...dropFiles}>
    <header className={styles.header}><a className={styles.brand} href={demo?"/":"/workspace"}>cytellect</a>{demo&&<DemoBadge dataset={showcase.dataset} onGuide={()=>setGuide(true)}/>}{demo&&<SceneSwitcher scenes={showcase.scenes} scene={showcase.scene}/>}<nav aria-label="作業の切替">{([["experiment","実験"],["image","画像"],["statistics","統計"],["figure","グラフ"]] as const).filter(([value])=>value!=="experiment"||!demo||!!experiment).map(([value,label])=><button key={value} disabled={editing} aria-current={mode===value?"page":undefined} data-lp-event={demo?`demo_${value}`:undefined} onClick={()=>changeMode(value)}>{label}</button>)}</nav><span className={styles.status} role="status">{r.operation}</span><CloudPhase running={r.busy&&!r.loading&&cellposeChosen}/>{demo&&<LiveStatus/>}{r.busy&&!r.loading&&<button className={styles.icon} aria-label="実行を中止" onClick={()=>r.stop()}><Icon name="stop"/></button>}{mode==="image"&&<><select className={styles.range} aria-label="測定する視野" value={range} onChange={e=>setRange(e.target.value)}><option value="selected">選択視野</option><option value="all">全視野</option></select><button className={styles.primary} disabled={busy||!field||field.kind==="reference"} onClick={()=>void measure()}>測定</button></>}<AccountIndicator/><button className={styles.settingsButton} aria-label="設定パネル" title="検出と測定の設定" aria-pressed={panel} onClick={showSettings}><Icon name="settings"/><span>設定</span></button>{demo&&<><button className={showcaseStyles.guideButton} aria-pressed={guide} data-lp-event="demo_guide" onClick={()=>setGuide(!guide)}>使い方</button><a className={showcaseStyles.download} href={DOWNLOAD_HREF} data-lp-event="demo_download">ダウンロード</a></>}</header>
    <aside className={styles.sidebar} aria-label={mode==="image"||mode==="experiment"?"視野一覧":"解析対象"}><div className={styles.sideHeading}>{/* The demo keeps its registered example; a new workspace could not be filled without uploads. */}{!demo&&<button className={styles.icon} disabled={busy} title="新しいワークスペース" aria-label="新しいワークスペース" onClick={newWorkspace}><Icon name="plus"/></button>}{mode==="image"||mode==="experiment"?`視野 ${fields.length}`:targets[checkedTarget]}</div>{mode==="image"||mode==="experiment"?<><input className={styles.search} aria-label="視野を検索" placeholder="検索" value={search} onChange={e=>setSearch(e.target.value)}/><div className={styles.fieldList}>{fields.filter(value=>value.label.toLowerCase().includes(search.toLowerCase())).map((value,index)=>{const ch=value.nuclearChannelId||value.channels[0]?.id;const current=r.currentResult(value.id,target);return <button className={styles.fieldCard} disabled={editing} aria-pressed={value.id===field?.id} data-shown={pairActive&&!!pairDisplay?.fields?.includes(value.id)} key={value.id} onClick={()=>openField(value.id)} title={value.label}>{value.previews[ch]&&<img src={value.previews[ch]} alt={value.label}/>}<span>{index+1} {value.label}</span><small>{value.kind==="reference"?"補助画像":value.exclusionReason?"対象外":current?`${targets[target]} ${new Set(current.masks.regions.map(region=>region.id)).size}`:"未測定"}</small></button>;})}</div>{demo&&showcase.dataset&&<SideCredit dataset={showcase.dataset}/>}<div className={styles.addMenu}><button disabled={intakeDisabled} onClick={()=>chooseFiles()}><Icon name="plus"/>画像</button><button disabled={intakeDisabled} onClick={()=>chooseFiles(true)}>フォルダ</button></div></>:<div className={styles.resultOptions}><MetricSelect value={metric} onChange={setMetric} describe calibrated={calibrated} offered={id=>regionOffered(metricTarget(id,target))}/>{metricChoice(metric)?.target?<p className={styles.fixedTarget}>領域：{targets[checkedTarget]}{checkedTarget!==sourceTarget?"（核ごとの値）":""}</p>:<label>領域<select value={target} onChange={e=>{changeTarget(e.target.value as ReviewTarget);}}>{Object.entries(targets).filter(([id])=>regionOffered(id as ReviewTarget)).map(([id,label])=><option value={id} key={id}>{label}</option>)}</select></label>}{metricUsesChannel(metric)&&<label>染色<select value={actualChannel} onChange={e=>setChannel(e.target.value)}>{(field?.channels||data?.channels)?.map(ch=><option value={ch.id} key={ch.id}>{ch.stain?`${ch.stain} · ${ch.id}`:ch.id}</option>)}</select></label>}</div>}</aside>

    <div className={styles.body}>
      <CloudNotices/>
      {(r.error||localError)&&(isShowcaseNotice(localError||r.error)?<div className={`${styles.error} ${showcaseStyles.notice}`} role="status">{localError||r.error}<button aria-label="案内を閉じる" onClick={()=>{setLocalError("");r.dismissError();}}>閉じる</button></div>:<div className={styles.error} role="alert">{localError||r.error}<button aria-label="保存状態を再読み込み" disabled={busy} onClick={()=>void act(()=>r.reload())}>再読み込み</button></div>)}
      {/* One instance for both views: the first save switches to the experiment view (E-01). */}
      <section hidden={!setupShown} className={styles.imageWork}>{setupShown&&setup}</section>
      <section hidden={mode!=="image"||setupShown} className={styles.imageWork}>
        {!field&&demo&&!fields.length&&!r.error?<div className={styles.start}><p role="status">公開画像と保存済みの解析結果を読み込み中…</p></div>:!field&&!demo?null:!field?<div className={styles.start}><h1>画像解析</h1><div className={styles.startActions}><button className={styles.primary} disabled={intakeDisabled} onClick={()=>chooseFiles()}>画像を追加</button><button disabled={intakeDisabled} onClick={()=>chooseFiles(true)}>フォルダを追加</button></div><p>TIFF・OME-TIFF</p><button onClick={()=>changeMode("statistics")}>測定済みデータを使う</button></div>:<>
          {/* What the image shows on the left (region, stain, colour mode), how it is laid out on the right (MV-08). */}
          <div className={styles.channelBar} role="toolbar" aria-label="画像の表示">
            <div className={styles.barGroup} role="group" aria-label="何を見るか">{returnMode&&<button className={styles.icon} aria-label="元の結果へ戻る" disabled={editing} onClick={returnToResult}><Icon name="back"/></button>}{!pairActive&&<strong title={field.label}>{field.label}</strong>}
              <label className={styles.inline}>領域<select disabled={busy} value={target} onChange={e=>changeTarget(e.target.value as ReviewTarget)}>{Object.entries(targets).filter(([id])=>regionOffered(id as ReviewTarget)).map(([id,label])=><option key={id} value={id}>{label}</option>)}</select></label>
              <span className={styles.stains} role="group" aria-label="染色"><span aria-hidden="true">染色</span>{!pairActive&&mergeable&&<button data-composite disabled={editing} aria-pressed={merged} onClick={()=>{setComposite(true);setCompare(false);}}>重ねて表示</button>}{field.channels.map(ch=><button disabled={editing} aria-pressed={actualChannel===ch.id&&!compare&&!(merged&&!pairActive)} key={ch.id} title={ch.id} aria-label={ch.stain?`${ch.stain} · ${ch.id}`:undefined} data-channel={ch.id} onClick={()=>{setChannel(ch.id);setCompare(false);setComposite(false);}}>{channelLabel(ch,field.channels)}</button>)}</span>
              <label className={styles.inline}>色分け<select disabled={editing} value={colorShown} onChange={e=>chooseColorBy(e.target.value as ColorBy)}>{colorChoices.map(choice=><option key={choice.id} value={choice.id} disabled={choice.reason!==null} title={choice.reason??undefined}>{choice.label}{choice.reason?`（${choice.reason}）`:""}</option>)}</select></label></div>
            <div className={styles.barGroup} data-arrange role="group" aria-label="並べ方">
              {pairActive&&runsShown.length>0&&<label className={styles.inline}>実験回<select disabled={editing} value={pairRunId} onChange={e=>choosePairRun(e.target.value)}>{runsShown.map(run=><option key={run.id} value={run.id}>{run.label}</option>)}</select></label>}
              {pairActive&&<button className={styles.arrange} disabled={editing} aria-pressed={pairLinked} aria-label="拡大を連動" title="2 つの画像の拡大と位置を連動します" onClick={()=>setPairLinked(!pairLinked)}><Icon name="link"/><span>連動</span></button>}
              {pairActive&&pairDisplay&&<details className={styles.rangeInfo} data-shared={pairDisplay.shared}><summary>{pairDisplayText(pairDisplay).label}</summary><p>{pairDisplayText(pairDisplay).detail}</p></details>}
              {pairActive&&<button className={styles.arrange} disabled={editing} aria-pressed={pairTables} aria-label="測定値" title="各画像の表を表示します" onClick={()=>setPairTables(!pairTables)}><Icon name="table"/><span>測定値</span></button>}
              {experiment?.layout==="pair"&&<button className={styles.arrange} disabled={editing} aria-pressed={pairActive} aria-label="2 画面" title="2 つの群の視野を並べます" onClick={()=>{setPairView(!pairActive);setCompare(false);}}><Icon name="pair"/><span>2 画面</span></button>}
              {!pairActive&&<button className={styles.icon} disabled={editing} aria-label="画像を比較" title="視野やチャンネルを選んで並べる" aria-pressed={compare} onClick={chooseComparison}><Icon name="compare"/></button>}
              <details className={styles.fieldMenu} data-dismissible><summary aria-label="画像の設定">⋯</summary><div className={styles.menuPanel}><label>画像の用途<select disabled={busy} value={field.kind||"analysis"} onChange={e=>void act(()=>r.saveFieldLink(field.id,e.target.value as "analysis"|"reference"))}><option value="analysis">解析画像</option><option value="reference">補助画像</option></select></label>{field.kind==="reference"&&<label>対応する視野<select disabled={busy} value={field.referenceFor||""} onChange={e=>void act(()=>r.saveFieldLink(field.id,"reference",e.target.value||null))}><option value="">指定なし</option>{fields.filter(value=>value.id!==field.id&&value.kind!=="reference").map(value=><option key={value.id} value={value.id}>{value.label}</option>)}</select></label>}
                {/* Channel names and roles are set once per image set; they are kept here, out of the way of the work above (MV-08). */}
                <button className={styles.menuButton} disabled={busy} onClick={event=>{(event.currentTarget.closest("details") as HTMLDetailsElement|null)?.removeAttribute("open");setAssignments(!assignments);}}>染色対応</button></div></details></div>
          </div>
          {assignments&&<AssignmentEditor key={field.id} field={field} runtime={r} onDone={()=>{setAssignments(false);queuePreview("nuclei");}} onError={setLocalError}/>}
          {picker&&<div className={styles.comparisonPicker}>{planes.map(value=><label key={value.key}><input type="checkbox" checked={picked.includes(value.key)} onChange={e=>setPicked(previous=>e.target.checked?[...previous,value.key]:previous.filter(key=>key!==value.key))}/>{value.field.label} · {value.channel.stain||value.channel.id}</label>)}<button className={styles.icon} aria-label="比較対象を閉じる" onClick={()=>setPicker(false)}><Icon name="close"/></button></div>}
          {pairActive?<PairStage design={experiment!} fields={fields} runtime={r} target={target} channel={actualChannel} selectedField={field.id} region={region} historical={historical} onSelect={(id,ch,n)=>{setSelected(id);setChannel(ch);setRegion(n);}} onEditing={setEditing} runId={pairRunId} linked={pairLinked} tables={pairTables} onDisplay={setPairDisplay}
            colorBy={colorShown} states={regionStates} legend={legendFor} fills={fillsFor} gateTable={gateTableFor} heading={headingFor} next={nextAction} partition={partitionFor}/>:<ImageStage planes={visible} target={target} fieldId={field.id} region={region} rows={rows} onRegion={setRegion} onSelect={(id,ch,n)=>{setSelected(id);setChannel(ch);setRegion(n);}} onOpen={openField} runtime={r} editing={editing} onEditing={setEditing} colorBy={colorShown} states={regionStates} legend={legendFor} fills={fillsFor} gateTable={gateTableFor} heading={headingFor} next={nextAction} partition={colorShown==="compartments"?partitionFor(field):undefined} historical={historical} backgrounds={backgrounds} backgroundDraw={backgroundDraw?{field:backgroundDraw.field,requestId:backgroundDraw.id,onSave:saveBackground,onCancel:()=>setBackgroundDraw(null)}:undefined} viewport={viewport} onViewport={(fid,value)=>setViewport(previous=>({...previous,[fid]:value}))} composite={merged} demo={demo} rowsField={rowsField} nucleusTable={nucleusTableSource} sideTable={!table} onSideTable={setSideRoom}/>}
          {/* Side by side, each pane lists its own measurements; this row then only carries the selected field's actions. */}
          {(!pairActive||!!candidate||!!field.exclusionReason||!!field.error)&&<div className={styles.measureToggle}>{pairActive?<strong>{field.label}</strong>:<button aria-expanded={table} aria-label={sideRoom?`測定値${rows.length?` · ${rows.length}`:""}（${table?"画像の横に戻す":"画像の下に広げる"}）`:undefined} title={sideRoom?(table?"測定値を画像の横に戻します":"測定値を画像の下に広げます"):undefined} onClick={()=>setTable(!table)}>測定値{rows.length?` · ${rows.length}`:""}</button>}<span>{targets[target]}{historicResult?" · 図の保存時の版":candidate?" · 検出候補":result?"":" · 未測定"}</span>{candidate&&<button disabled={busy} onClick={()=>void act(()=>r.acceptCandidates(field.id,target))}>候補を採用</button>}{field.exclusionReason?<button onClick={()=>void act(()=>r.excludeField(field.id,null))}>解析対象に戻す</button>:field.error?<button onClick={()=>void act(()=>r.excludeField(field.id,"利用者が解析対象から除外"))}>この視野を除外</button>:null}</div>}
          {table&&!pairActive&&<div className={styles.tableDrawer}><MeasurementsPanel heading={headingFor(!!nucleusTableSource?.shown,rows)} rowsField={rowsField} mode={colorShown} gate={field?gateTableFor(field.id):undefined} next={nextAction} partition={colorShown==="compartments"?partitionFor(field):undefined} rows={rows} region={region} onRegion={setRegion} editing={editing} nucleusTable={nucleusTableSource}/></div>}

        </>}
      </section>
      <section className={styles.resultWork} hidden={mode==="image"||mode==="experiment"}>{r.unfinishedImports.length>0&&<p role="status" className={styles.unfinishedNotice}>登録できなかった画像が {r.unfinishedImports.length} 件あります。比較の前に、画面下の「取込」の一覧で理由を付けて除外してください。</p>}<ConnectedResults adapter={r.adapter} workspace={data?.workspaceId||""} selection={r.adapter.selection()} items={sources} target={sourceTarget} metric={metric} channel={metricUsesChannel(metric)?actualChannel||null:null} mode={mode==="image"||mode==="experiment"?lastResultMode:mode} onOpening={(openedMetric,openedChannel)=>{if(explicitMetric.current)return;if(metric==="mean")setMetric(openedMetric);if(openedChannel&&!channelId)setChannel(openedChannel);}} reclassifyRequest={reclassifyRequest} experiment={experiment} experimentSha256={r.experimentSha256()} onEditExperiment={()=>changeMode("experiment")} onSource={(id,n,revision,source,ch,structure)=>void openSource(id,n,revision,source,ch,structure)} onAnalysisTargetChange={setTarget} onPrepareMissing={()=>r.run(sourceTarget)} disabled={r.busy} gfp={gfpFilter} channelGate={channelFilter} onChannelGateRecorded={classifyChannel} initialSpec={storedSpec||undefined} onSaveDraft={draft=>r.saveResultDraft(draft)} onMetricChange={(nextMetric,nextChannel)=>{setMetric(nextMetric);if(nextChannel)setChannel(nextChannel);}}/></section>
    </div>

    {(mode==="image"&&!!field||ai)&&(panel||ai)&&<aside className={styles.inspector} aria-label={ai?"AI":"画像解析"}><div className={styles.panelHeading}><h2>{ai?"AI":"画像解析"}</h2><button className={styles.icon} aria-label="パネルを閉じる" onClick={()=>dispatchPanel("close")}><Icon name="close"/></button></div><div className={styles.inspectorBody}>
      {ai?<><button onClick={showSettings}>解析設定を表示</button><div className={styles.userMessage}>{instruction}</div>{demoReply?<p>{demoReply}</p>:r.proposal?<><p>{r.proposal.draft.rationale}</p><dl>{r.proposal.draft.channels.map(ch=><div key={ch.token}><dt>{ch.token}</dt><dd>{ch.stain||ch.role}</dd></div>)}</dl>{r.proposal.draft.missing_information.length>0&&<ul>{r.proposal.draft.missing_information.map(text=><li key={text}>{text}</li>)}</ul>}{r.canUndoProposal()&&<button disabled={busy} onClick={()=>void act(()=>r.undoProposal())}>AIによる設定変更を戻す</button>}</>:<p>下の入力欄から解析の指示を送信できます。</p>}{demo&&<ProposalExamples examples={showcase.examples} disabled={busy} onChoose={value=>{setInstruction(value);void sendInstruction(value);}}/>}</>:<>
        {colorShown==="positivity"&&<section aria-label="陽性・陰性の判定"><h3>陽性・陰性の判定</h3>
          {gateStale&&<p role="status">{gateStale}</p>}
          <ConnectedChannelGate recorded={demo} adapter={r.adapter} workspace={data?.workspaceId||""} fields={channelFields} channels={gateChannels} disabled={busy}
            initialChannel={channelFilter?.channel_id??(gateChannels.some(ch=>ch.id===actualChannel)?actualChannel:"")} decision={channelClassification&&channelSaved?{result:channelSaved.result,filter:channelSaved.filter}:null}
            selected={field&&region!==undefined?{fieldId:field.id,regionId:region}:null} onClassified={classifyChannel}/>
          {channelFilter&&<button disabled={busy} onClick={()=>void act(async()=>{await r.saveSelection({field_ids:channelFields.map(value=>value.fieldId),gfp:null});setChannelSaved(null);setGateStale("");})}>チャンネルによる分類を解除</button>}</section>}
        <label>領域<select disabled={busy} value={target} onChange={e=>{changeTarget(e.target.value as ReviewTarget);}}>{Object.entries(targets).filter(([id])=>regionOffered(id as ReviewTarget)).map(([id,label])=><option key={id} value={id}>{label}</option>)}</select></label>
        <section><h3>検出</h3>{demo?<RecordedDetection target={target} recipe={field?r.resultRecipe(field.id,target):undefined} settings={r.settings} channels={field?.channels||data?.channels||[]} nuclear={field?.channels.find(ch=>ch.role==="nuclear")?.id||field?.nuclearChannelId||""}/>:<fieldset className={styles.plain}>{target==="nuclei"?<><label>核染色<select value={field?.channels.find(ch=>ch.role==="nuclear")?.id||field?.nuclearChannelId||""} disabled={busy} onChange={e=>void act(()=>r.saveAssignments((field?.channels||[]).map(ch=>({channel_id:ch.id,stain:ch.stain,role:ch.id===e.target.value?"nuclear":ch.role==="unused"?"unused":"measure"})),field?.id).then(()=>queuePreview("nuclei")))}><option value="">チャンネルを指定</option>{(field?.channels||data?.channels)?.map(ch=><option key={ch.id} value={ch.id}>{ch.stain?`${ch.stain} · ${ch.id}`:ch.id}</option>)}</select></label><p className={styles.method}>StarDist 2D</p><details><summary>検出条件</summary><NumberSetting label="確率閾値" value={r.settings.nuclearProbability} min={0} max={1} step={.05} onChange={v=>setSetting("nuclearProbability",v??.5)}/><NumberSetting label="NMS閾値" value={r.settings.nuclearNms} min={0} max={1} step={.05} onChange={v=>setSetting("nuclearNms",v??.3)}/><NumberSetting label="検出用画像の長辺 / px" value={r.settings.nuclearMaxSide} min={64} max={2048} onChange={v=>setSetting("nuclearMaxSide",v)}/></details></>:target==="cell"?<><label>検出アルゴリズム<select disabled={busy} value={r.settings.cellDefinition?.source||"manual"} onChange={e=>setSetting("cellDefinition",{source:e.target.value as "manual"|"cellpose",channel:r.settings.cellDefinition?.channel||""})}><option value="manual">手描き</option><option value="cellpose">Cellpose-SAM</option></select></label>{r.settings.cellDefinition?.source==="cellpose"?<><label>細胞を検出する画像<select disabled={busy} value={r.settings.cellDefinition.channel} onChange={e=>{setSetting("cellDefinition",{source:"cellpose",channel:e.target.value});if(e.target.value)setChannel(e.target.value);}}><option value="">チャンネルを指定</option>{(field?.channels||data?.channels)?.map(ch=><option key={ch.id} value={ch.id}>{ch.stain?`${ch.stain} · ${ch.id}`:ch.id}</option>)}</select></label>{field&&<CellposeSettings runtime={r} field={field.id} target="cell" disabled={busy} onChanged={()=>queuePreview()}/>}</>:<p>画像上で細胞の輪郭を描けます。</p>}</>:target==="nucleoplasm"?<p>採用した核から、核小体を除いた領域です。</p>:<><label>核小体の定義<select value={r.settings.nucleolarDefinition.source} disabled={busy} onChange={e=>selectNucleolarSource(e.target.value as "dapi_poor"|"marker"|"ncl")}><option value="dapi_poor">核染色の低輝度領域</option><option value="marker">核小体マーカー</option><option value="ncl">NCL陽性領域</option></select></label>{r.settings.nucleolarDefinition.source!=="dapi_poor"&&<label>{r.settings.nucleolarDefinition.source==="ncl"?"NCL画像":"マーカー画像"}<select value={r.settings.nucleolarDefinition.marker} onChange={e=>{setSetting("nucleolarDefinition",{...r.settings.nucleolarDefinition,marker:e.target.value,...(r.settings.nucleolarDefinition.source==="ncl"?{algorithm:nclAlgorithm}:{})});setChannel(e.target.value);}}><option value="">チャンネルを指定</option>{(field?.channels||data?.channels)?.map(ch=><option value={ch.id} key={ch.id}>{ch.stain?`${ch.stain} · ${ch.id}`:ch.id}</option>)}</select></label>}{r.settings.nucleolarDefinition.source==="ncl"&&<label>検出アルゴリズム<select value={rawNclCellpose?"cellpose-raw":nclAlgorithm} disabled={busy} onChange={e=>{if(e.target.value==="cellpose-raw")return;r.selectNucleolarSource("ncl",r.settings.nucleolarDefinition.marker,e.target.value as "cellpose"|"objects"|"legacy");queuePreview();}}><option value="cellpose">Cellpose-SAM（局所背景除去）</option>{rawNclCellpose&&<option value="cellpose-raw">Cellpose-SAM（前処理なし）</option>}<option value="objects">局所輝度差・形状</option><option value="legacy">NCLしきい値</option></select></label>}{r.settings.nucleolarDefinition.source==="ncl"&&nclAlgorithm==="cellpose"?field&&<CellposeSettings runtime={r} field={field.id} target="nucleoli" disabled={busy} onChanged={()=>queuePreview()}/>:<details><summary>検出条件</summary>{r.settings.nucleolarDefinition.source==="dapi_poor"&&<NumberSetting label="核内中央値に対する輝度比" value={r.settings.nucleolarDefinition.relative} min={.01} max={.99} step={.05} onChange={v=>setSetting("nucleolarDefinition",{...r.settings.nucleolarDefinition,relative:v??.7})}/>}<NumberSetting label="平滑化 σ / px" value={r.settings.nucleolarSigma??(r.settings.nucleolarDefinition.source==="ncl"?nclDefaults.smoothing_sigma_px:null)} min={0} max={r.settings.nucleolarDefinition.source==="ncl"?10:20} step={.1} onChange={v=>{r.setNucleolarSigma(v);queuePreview();}}/>{r.settings.nucleolarDefinition.source!=="ncl"&&<NumberSetting label="核辺縁の除外 / px" value={r.settings.nucleolarRim} min={0} onChange={v=>setSetting("nucleolarRim",v)}/>}<NumberSetting label="最小面積 / px²" value={r.settings.nucleolarMinimumArea??(r.settings.nucleolarDefinition.source==="ncl"?nclDefaults.minimum_area_px:null)} min={1} onChange={v=>setSetting("nucleolarMinimumArea",v)}/><NumberSetting label="最大面積 / px²" value={r.settings.nucleolarMaximumArea??(r.settings.nucleolarDefinition.source==="ncl"?nclDefaults.maximum_area_px:null)} min={1} onChange={v=>setSetting("nucleolarMaximumArea",v)}/>{r.settings.nucleolarDefinition.source==="ncl"&&nclAlgorithm==="objects"&&field&&<>
  {([["core_contrast","候補中心の輝度差",0,65535,1],["minimum_peak_difference","局所背景との輝度差",0,65535,1],["minimum_peak_ratio","局所背景との輝度比",1,100,.1],["boundary_fraction","境界の輝度割合",.01,.99,.05],["minimum_solidity","充実度",0,1,.05],["minimum_circularity","円形度",0,1,.05]] as const).map(([key,label,min,max,step])=><NumberSetting key={key} label={label} value={nclDefaults[key]} min={min} max={max} step={step} onChange={v=>{if(v!==null){r.setNclParameter(field.id,key,v);queuePreview();}}}/>) }
</>}</details>}</>}</fieldset>}</section>
        {!demo&&<details><summary>GFPによる対象選別</summary><ConnectedGfp key={gfpUnit} unit={gfpUnit} adapter={r.adapter} workspace={data?.workspaceId||""} fields={nuclearFields} channels={field?.channels||data?.channels||[]} disabled={busy} onClassified={(result,filter)=>void classify(result,filter)}/>{gfpFilter&&<button disabled={busy} onClick={()=>void act(async()=>{await r.saveSelection({field_ids:nuclearFields.map(value=>value.fieldId),gfp:null});setGfpSaved(null);})}>すべての{targets[classificationTarget]}を対象にする</button>}</details>}
        <section><h3>測定</h3><MetricSelect value={metric} onChange={setMetric} calibrated={calibrated} offered={id=>regionOffered(metricTarget(id,target))}/>{demo?<dl className={styles.recordedSettings}><div><dt>背景補正</dt><dd>{{raw:"なし（原値）",automatic:"自動推定",confirmed_roi:"背景ROI"}[r.settings.background]}</dd></div></dl>:<label>背景補正<select value={r.settings.background} disabled={busy} onChange={e=>setSetting("background",e.target.value as RuntimeSettings["background"])}><option value="raw">なし（原値）</option><option value="automatic">自動推定</option><option value="confirmed_roi">背景ROI</option></select></label>}{r.settings.background==="confirmed_roi"&&field&&<ConnectedBackground fieldId={field.id} fieldLabel={field.label} channels={field.channels.map(ch=>({...ch,role:ch.role||undefined}))} backgrounds={backgrounds} confirmedChannelIds={storedSpec?.confirmed_channel_ids||[]} disabled={r.busy} drawing={!!backgroundDraw} onDraw={channels=>{setCompare(false);setBackgroundDraw({field:field.id,channels,id:crypto.randomUUID()});}} onRemove={async channels=>{const updated={...backgrounds,[field.id]:{...backgrounds[field.id]}};for(const ch of channels)delete updated[field.id][ch];await r.saveBackgrounds(updated,storedSpec?.confirmed_channel_ids||[]);}}/>}</section>
      </>}
    </div></aside>}
    <footer className={styles.composer}>{r.importIssues.length+r.unfinishedImports.length>0&&<details className={styles.importIssues} data-dismissible><summary>取込 {r.importIssues.length+r.unfinishedImports.length}件</summary><ul>{r.importIssues.map((issue,index)=><li key={index}>{importIssueText(issue)}</li>)}<UnfinishedImports items={r.unfinishedImports} disabled={busy} onExclude={(entries,reason)=>void act(()=>r.excludeImports(entries,reason))}/></ul></details>}<button className={styles.icon} aria-label="AIの会話を開く" aria-pressed={ai} onClick={()=>dispatchPanel("toggle-ai")}><Icon name="ai"/></button><textarea aria-label="AIへの指示" placeholder={demo&&showcase.examples.length?"AIに指示（例から選べます）":"AIに指示"} value={instruction} onFocus={!ai?()=>dispatchPanel("open-ai"):undefined} onChange={e=>setInstruction(e.target.value)} rows={1}/><button className={styles.send} aria-label="AIへ送信" disabled={busy||(!instruction.trim()&&!fields.length)} onClick={()=>void send()}><Icon name="send"/></button></footer>
    {demo&&<DemoGuide open={guide} onClose={()=>setGuide(false)} onStep={guideStep} dataset={showcase.dataset}/>}
    <input hidden type="file" multiple accept=".tif,.tiff" ref={fileInput} data-testid="file-input" disabled={intakeDisabled} onChange={e=>{add(e.target.files);e.target.value="";}}/><input hidden type="file" multiple ref={folderInput} data-testid="folder-input" disabled={intakeDisabled} onChange={e=>{add(e.target.files);e.target.value="";}}/>
  </main>;
}

function importIssueText(issue:GroupingIssue){
  switch(issue.kind){
    case "channel_range_reference":return `${issue.path}：チャンネル合成画像`;
    case "duplicate_channel":return `${issue.field}：${issue.token}に複数の画像`;
    case "duplicate_content":return `${issue.paths.join("、")}：同一内容`;
    case "missing_channel":return `${issue.field}：${issue.token}は未登録`;
    case "channel_unidentified":return `${issue.path}：染色名未指定`;
    case "channels_pending":return `${issue.path}：OMEメタデータから読み込み`;
  }
}
/**
 * The public demo measures with its recorded detection conditions: they are shown as the settings of
 * the adopted result (or the saved settings before one), not offered as choices that cannot answer.
 */
function RecordedDetection({target,recipe,settings,channels,nuclear}:{target:ReviewTarget;recipe?:{defining_channel_id?:string;detector?:object};settings:RuntimeSettings;channels:ReviewField["channels"];nuclear:string}){
  const stain=(id:string)=>{const ch=channels.find(value=>value.id===id);return ch?.stain?`${ch.stain} · ${ch.id}`:id||"—";};
  const detector=(recipe?.detector??{}) as Record<string,unknown>;
  const value=(key:string,fallback:number|null,none="自動")=>{const number=key in detector?detector[key]:fallback;return typeof number==="number"?number.toLocaleString(undefined,{maximumFractionDigits:6}):none;};
  const definition=settings.nucleolarDefinition;
  const items:Array<[string,string]>=target==="nuclei"?[["核染色",stain(recipe?.defining_channel_id||nuclear)],["検出","StarDist 2D"],["確率閾値",value("probability",settings.nuclearProbability)],["NMS閾値",value("nms",settings.nuclearNms)],["検出用画像の長辺 / px",value("detection_max_side_px",settings.nuclearMaxSide)]]
    :target==="nucleoli"?[["核小体の定義",{dapi_poor:"核染色の低輝度領域",marker:"核小体マーカー",ncl:"NCL陽性領域"}[definition.source]],
      ...(definition.source==="dapi_poor"?[["核内中央値に対する輝度比",value("relative_threshold",definition.relative)] as [string,string]]:[["マーカー画像",stain(recipe?.defining_channel_id||definition.marker)] as [string,string]]),
      ["平滑化 σ / px",value("smoothing_sigma_px",settings.nucleolarSigma)],["核辺縁の除外 / px",value("rim_exclusion_px",settings.nucleolarRim)],["最小面積 / px²",value("minimum_area_px",settings.nucleolarMinimumArea)],["最大面積 / px²",value("maximum_area_px",settings.nucleolarMaximumArea,"上限なし")]]
    :[];
  return <>
    <p className={styles.demoNote} title="お手元の画像では、Windows 版で条件を変えて検出できます。">記録した条件で検出しています。条件を変える例は「AIに指示」で試せます。</p>
    {target==="nucleoplasm"?<p>採用した核から、核小体を除いた領域です。</p>:<dl className={styles.recordedSettings}>{items.map(([label,text])=><div key={label}><dt>{label}</dt><dd>{text}</dd></div>)}</dl>}
  </>;
}
/** A detector value; the public demo shows its recorded conditions as text instead (RecordedDetection). */
function NumberSetting({label,value,onChange,min,max,step=1}:{label:string;value:number|null;onChange:(value:number|null)=>void;min?:number;max?:number;step?:number}){
  return <label>{label}<input type="number" value={value??""} placeholder="自動" min={min} max={max} step={step} onChange={e=>onChange(e.target.value===""?null:Number(e.target.value))}/></label>;
}
function CellposeSettings({runtime:r,field,target,disabled,onChanged}:{runtime:Runtime;field:string;target:"cell"|"nucleoli";disabled:boolean;onChanged:()=>void}){
  const settings=r.cellposeSettings(field,target);
  return <><GpuStatus/><details><summary>検出条件</summary><fieldset className={styles.detectorSettings} disabled={disabled}>
    {target==="nucleoli"&&settings.engine==="cellpose-sam-ncl-parent"&&settings.protocol_version==="4.3.0"&&<>
    <label>核小体の検出モデル<select value={settings.model} onChange={event=>{const model=event.target.value;if(model==="cpsam_v2"||model==="ncl-r1-step0375"||model==="ncl-r1-step0750"){r.selectNclModel(field,model);onChanged();}}}>
      <option value="cpsam_v2">Cellpose-SAM（標準）</option>
      <option value="ncl-r1-step0375">Cytellect R1 / 375</option>
      <option value="ncl-r1-step0750">Cytellect R1 / 750</option>
    </select></label>
    {settings.model!=="cpsam_v2"&&<p>核小体の輪郭で追加学習したモデルです。選択したモデルは解析条件とともに保存されます。</p>}
    </>}
    {target==="nucleoli"&&settings.engine==="cellpose-sam-ncl"&&<>
    <NumberSetting label="平滑化 σ / 原画像px" value={settings.smoothing_sigma_px} min={.1} max={16} step={.1} onChange={value=>{if(value!==null){r.setCellposeParameter(field,target,"smoothing_sigma_px",value);onChanged();}}}/>
    <NumberSetting label="背景推定の半径 / 原画像px" value={settings.background_radius_px} min={1} max={128} onChange={value=>{if(value!==null){r.setCellposeParameter(field,target,"background_radius_px",value);onChanged();}}}/>
    </>}
    {target==="nucleoli"&&settings.engine==="cellpose-sam-ncl-parent"&&<>
    <NumberSetting label="平滑化 σ / 原画像px" value={settings.smoothing_sigma_px} min={.1} max={16} step={.1} onChange={value=>{if(value!==null){r.setCellposeParameter(field,target,"smoothing_sigma_px",value);onChanged();}}}/>
    <NumberSetting label="核内背景 / 百分位" value={settings.parent_background_percentile} min={0} max={99} onChange={value=>{if(value!==null){r.setCellposeParameter(field,target,"parent_background_percentile",value);onChanged();}}}/>
    <NumberSetting label="対象径 / 核の直径比" value={settings.nuclear_diameter_fraction} min={.01} max={1} step={.05} onChange={value=>{if(value!==null){r.setCellposeParameter(field,target,"nuclear_diameter_fraction",value);onChanged();}}}/>
    <NumberSetting label="最低信号 / ノイズ比" value={settings.minimum_contrast_snr} min={.1} max={100} step={.5} onChange={value=>{if(value!==null){r.setCellposeParameter(field,target,"minimum_contrast_snr",value);onChanged();}}}/>
    </>}
    <NumberSetting label="対象の直径 / px" value={settings.diameter_px} min={1} max={4096} onChange={value=>{r.setCellposeParameter(field,target,"diameter_px",value);onChanged();}}/>
    <NumberSetting label="輪郭の整合性閾値" value={settings.flow_threshold} min={.01} max={10} step={.05} onChange={value=>{if(value!==null){r.setCellposeParameter(field,target,"flow_threshold",value);onChanged();}}}/>
    <NumberSetting label="検出スコアの閾値" value={settings.cellprob_threshold} min={-20} max={20} step={.5} onChange={value=>{if(value!==null){r.setCellposeParameter(field,target,"cellprob_threshold",value);onChanged();}}}/>
    <NumberSetting label="最小面積 / px²" value={settings.minimum_area_px} min={1} onChange={value=>{if(value!==null){r.setCellposeParameter(field,target,"minimum_area_px",value);onChanged();}}}/>
    <NumberSetting label="検出用画像の下限 / 百分位" value={settings.normalization_percentile_low} min={0} max={99.9} step={1} onChange={value=>{if(value!==null){r.setCellposeParameter(field,target,"normalization_percentile_low",value);onChanged();}}}/>
    <NumberSetting label="検出用画像の上限 / 百分位" value={settings.normalization_percentile_high} min={.1} max={100} step={.1} onChange={value=>{if(value!==null){r.setCellposeParameter(field,target,"normalization_percentile_high",value);onChanged();}}}/>
  </fieldset></details></>;
}
function AssignmentEditor({field,runtime:r,onDone,onError}:{field:ReviewField;runtime:Runtime;onDone:()=>void;onError:(s:string)=>void}){
  const [draft,setDraft]=useState<ChannelAssignment[]>(()=>field.channels.map(ch=>({channel_id:ch.id,stain:ch.stain,role:ch.role||"measure"})));
  const fromFilename=new Map(field.channels.filter(ch=>ch.stainSource==="filename").map(ch=>[ch.id,ch.stain]));
  return <div className={styles.assignments}>{draft.map((ch,index)=><label key={ch.channel_id}>{field.previews[ch.channel_id]&&<img src={field.previews[ch.channel_id]} alt={ch.channel_id}/>}<strong>{ch.channel_id}</strong><input aria-label={`${ch.channel_id}の染色名`} placeholder="染色名" value={ch.stain||""} onChange={e=>setDraft(previous=>previous.map((item,i)=>i===index?{...item,stain:e.target.value||null}:item))}/>{ch.stain&&fromFilename.get(ch.channel_id)===ch.stain&&<small className={styles.stainHint}>ファイル名から読み取った名前です。撮影記録の染色名と合っているか確かめてください。</small>}<select aria-label={`${ch.channel_id}の役割`} value={ch.role} onChange={e=>setDraft(previous=>previous.map((item,i)=>({...item,role:i===index?e.target.value as ChannelAssignment["role"]:e.target.value==="nuclear"&&item.role==="nuclear"?"measure":item.role})))}><option value="nuclear">核検出</option><option value="measure">測定</option><option value="unused">使用しない</option></select></label>)}<button disabled={r.busy} className={styles.primary} onClick={()=>{void r.saveAssignments(draft,field.id).then(onDone).catch(e=>onError(e instanceof Error?e.message:"保存できませんでした。"));}}>保存</button></div>;
}

function ImageStage({planes,target,fieldId,region,rows,rowsField,onRegion,onSelect,onOpen,runtime:r,editing,onEditing,colorBy,states,legend,fills,gateTable,heading,next,partition,historical,backgrounds,backgroundDraw,viewport,onViewport,composite=false,demo=false,nucleusTable,sideTable=true,onSideTable}:ColorView&{partition?:ReactNode;composite?:boolean;demo?:boolean;sideTable?:boolean;onSideTable?:(shown:boolean)=>void;rowsField:string;nucleusTable?:NucleusTableSource;planes:Array<{field:ReviewField;channel:{id:string;stain:string|null};key:string}>;target:ReviewTarget;fieldId:string;region?:number;rows:MeasurementRow[];onRegion:(n:number)=>void;onSelect:(field:string,ch:string,n:number)=>void;onOpen:(field:string,ch:string)=>void;runtime:Runtime;editing:boolean;onEditing:(v:boolean)=>void;historical:Historical|null;backgrounds:WorkspaceBackgrounds;backgroundDraw?:{field:string;requestId:string;onSave:(polygon:Point[])=>Promise<void>;onCancel:()=>void};viewport:Record<string,ReviewImageViewport|null>;onViewport:(fid:string,value:ReviewImageViewport|null)=>void}){
  const ref=useRef<HTMLDivElement>(null),[size,setSize]=useState({width:800,height:600});
  useEffect(()=>{const node=ref.current;if(!node)return;const observer=new ResizeObserver(entries=>{const {width,height}=entries[0].contentRect;setSize({width,height});});observer.observe(node);return()=>observer.disconnect();},[]);
  const single=planes.length===1;const layout=imageStageLayout(planes.map(plane=>plane.field),size);
  const showTable=sideTable&&single&&size.width-(layout.tiles[0]?.width||0)>230;
  // The workspace names the 測定値 button by where the table is (beside the image or below it).
  const roomBeside=single&&size.width-(layout.tiles[0]?.width||0)>230;
  useEffect(()=>{onSideTable?.(roomBeside);},[roomBeside,onSideTable]);
  return <div ref={ref} className={styles.stage} data-single={single} style={{"--columns":layout.columns} as CSSProperties}>
    {planes.map((plane,index)=>{
      const savedView=historical?.target===target&&historical.result.field===plane.field.id?historical:undefined,old=savedView?.result;
      const nucleus=savedView?.context?.find(outline=>outline.id===savedView.nucleus);
      const candidate=old?undefined:r.candidateResult(plane.field.id,target),value=old||candidate||r.currentResult(plane.field.id,target),tile=layout.tiles[index];
      const editable=single&&!!value&&!old&&!candidate&&target!=="nucleoplasm";
      return <div className={styles.tile} key={plane.key} style={{width:tile.width,height:tile.height}}>
        {!single&&<div className={styles.tileCaption}>{plane.field.label} · {plane.channel.stain||plane.channel.id}</div>}
        {plane.field.previews[plane.channel.id]?<ReviewImageCanvas
          src={plane.field.previews[plane.channel.id]} width={plane.field.width} height={plane.field.height}
          contours={value?.masks.regions||[]} classification={old||candidate?undefined:states(plane.field.id)} colorBy={colorBy} legend={old||candidate?undefined:legend(plane.field.id)} fills={fills(plane.field.id)} selected={plane.field.id===fieldId?region:undefined}
          label={`${plane.field.label} ${plane.channel.stain||plane.channel.id}`}
          onSelect={n=>onSelect(plane.field.id,plane.channel.id,n)} onOpen={!single?()=>onOpen(plane.field.id,plane.channel.id):undefined}
          editingKey={`${plane.field.id}:${target}:${value?.revision||"none"}`} editDisabled={r.busy||!editable}
          onEdit={editable?(operation,polygon,n,merged)=>r.editMask(plane.field.id,target,value!.revision,operation,polygon,n,merged):undefined}
          onDelete={editable?n=>r.correct(plane.field.id,target,value!.revision,"delete",n):undefined}
          onUndo={editable?()=>r.undo(plane.field.id,target):undefined} onRedo={editable?()=>r.redo(plane.field.id,target):undefined}
          canUndo={!r.busy&&r.canUndo(plane.field.id,target)} canRedo={!r.busy&&r.canRedo(plane.field.id,target)}
          backgroundPolygon={backgrounds[plane.field.id]?.[plane.channel.id]?.polygon} backgroundEdit={single&&backgroundDraw?.field===plane.field.id?backgroundDraw:undefined} onEditingChange={onEditing} viewport={viewport[plane.field.id]} onViewportChange={value=>onViewport(plane.field.id,value)}
          style={{width:tile.width,height:tile.imageHeight,flex:"none"}}
          outlineTone={target==="nuclei"||target==="cell"?"nuclear":"marker"}
          layers={single&&composite?compositeLayers(plane.field):undefined}
          // Nucleoli and nucleoplasm are seen within the adopted nuclei, outlined faintly (display only).
          context={savedView?.context??(target==="nucleoli"||target==="nucleoplasm"?r.currentResult(plane.field.id,"nuclei")?.masks.regions:undefined)} contextSelected={savedView?.nucleus}
          initialZoom={demo&&single?1.8:undefined} initialFocus={demo&&single?nucleus?centre(nucleus.points):densestPoint(r.currentResult(plane.field.id,"nuclei")?.masks.regions||[],plane.field.width/4):undefined}/>:<p>画像を読み込み中…</p>}
      </div>;
    })}
    {showTable&&<div className={styles.sideMeasurements}><MeasurementsPanel heading={heading(!!nucleusTable?.shown,rows)} rowsField={rowsField} mode={colorBy} gate={gateTable(fieldId)} next={next} partition={partition} rows={rows} region={region} onRegion={onRegion} editing={editing} nucleusTable={nucleusTable}/></div>}
  </div>;
}

/** The table of what the image shows (MV-06, MV-07): its heading names per what, which stain and which values; the
 * colour mode decides the rows. Values come from the API. Shown once, beside the image or below it, with the next step. */
function MeasurementsPanel({heading,mode,gate,next,rows,rowsField,region,onRegion,editing,nucleusTable,partition}:{heading:string;mode:ColorBy;gate?:NucleusTableGate;next?:NextAction|null;
  rows:MeasurementRow[];rowsField:string;region?:number;onRegion:(n:number)=>void;editing:boolean;nucleusTable?:NucleusTableSource;partition?:ReactNode}){
  // In a comparison of images the table may list another field than the one in view: its heading names it.
  const field=rowsField?`${rowsField} · `:"";
  const nucleusRows=mode==="positivity"||!!nucleusTable?.shown;
  return <>
    <TableHeading heading={`${field}${heading}`} next={nucleusRows&&nucleusTable&&mode!=="compartments"?null:next}>
      {mode==="outline"&&nucleusTable&&<div className={styles.tableViews} role="group" aria-label="表の切り替え"><button aria-pressed={!nucleusTable.shown} onClick={()=>nucleusTable.onShow(false)}>このチャンネル</button><button aria-pressed={nucleusTable.shown} onClick={()=>nucleusTable.onShow(true)}>核ごとの表</button></div>}
    </TableHeading>
    {mode==="compartments"?partition
    :<>
    {nucleusRows&&nucleusTable?<ConnectedNucleusTable load={nucleusTable.load} save={nucleusTable.save} field={nucleusTable.field} nuclearRevision={nucleusTable.nuclearRevision} nucleolarRevision={nucleusTable.nucleolarRevision} channels={nucleusTable.channels} exclusion={nucleusTable.exclusion} gate={mode==="positivity"?gate:undefined} selected={region} onSelect={onRegion} aside={next?<NextStep next={next}/>:undefined}/>
    :mode==="positivity"?<p>核を検出して採用すると、核ごとの判定を表示します。</p>
    :rows.length?<MeasurementTable rows={rows} selected={region} onSelect={onRegion}/>:<p>測定結果はここに表示されます。</p>}</>}
    {editing&&<p>描画を保存または取消して続けてください。</p>}
  </>;
}


/** Closes open menus (`details[data-dismissible]`) that do not contain the pointer target. */
function closeDismissible(target:Node|null=null){
  for(const menu of document.querySelectorAll<HTMLDetailsElement>("details[data-dismissible][open]"))if(!target||!menu.contains(target))menu.open=false;
}
