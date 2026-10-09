"use client";
import {isCellposeDetector} from "@/lib/workspace/cellpose-settings";
import {nclObjectDetector} from "@/lib/workspace/nucleolar-definition";
import type {GroupingIssue} from "@/lib/workspace/grouping";
import {Suspense,useEffect,useEffectEvent,useMemo,useReducer,useRef,useState,type CSSProperties} from "react";
import {useSearchParams} from "next/navigation";
import {useWorkspaceRuntime,type RuntimeSettings} from "@/lib/workspace/use-workspace-runtime";
import type {ReviewField,ReviewTarget} from "@/lib/workspace/review-preview";
import type {ChannelAssignment,MeasurementRow,GfpGateResult,SavedResult,RevisionRecord} from "@/lib/workspace/api-adapter";
import {API_CONFIGURED,ApiError,errorCodeMessage,errorMessage,request} from "@/lib/api";
import {ReviewImageCanvas,type ReviewImageViewport} from "./ReviewImageCanvas";
import type {components} from "@/lib/generated";
import type {Point} from "@/lib/types";
import {ConnectedBackground,type WorkspaceBackgrounds} from "./ConnectedBackground";
import {ConnectedGfp,type WorkspaceGfpFilter} from "./ConnectedGfp";
import {ConnectedResults} from "./ConnectedResults";
import {imageStageLayout} from "./image-stage-layout";
import {emptyMetadata} from "./connected-results-model";
import {initialPanelState,panelReducer} from "./panel-state";
import styles from "./connected-workspace.module.css";

type Mode="image"|"statistics"|"figure";
const targets:Record<ReviewTarget,string>={nuclei:"核",nucleoli:"核小体",nucleoplasm:"核質",cell:"細胞ROI"};
const metrics={area_px:"面積 / px²",mean:"平均輝度",median:"中央値",integrated:"積算輝度",mean_corrected:"平均輝度（背景補正）",integrated_corrected:"積算輝度（背景補正）",nucleolar_count:"核小体数",nucleolar_area_fraction:"核小体面積割合",log2_nucleoplasm_over_nucleolus:"核質／核小体 log₂ 比"};
type Runtime=ReturnType<typeof useWorkspaceRuntime>;
const paths={stop:"M6 6h12v12H6z",plus:"M12 4v16M4 12h16",compare:"M3 4h7v16H3zM14 4h7v16h-7z",settings:"M4 7h16M4 17h16M8 4v6M16 14v6",close:"m6 6 12 12M6 18 18-12",back:"m10 5-7 7 7 7M3 12h18",ai:"M4 4h16v12H9l-5 4V4M8 8h8M8 12h5",send:"M12 20V4m-7 7 7-7 7 7"};
function Icon({name}:{name:keyof typeof paths}){return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true"><path d={paths[name]}/></svg>;}
export default function ConnectedWorkspace(){return <Suspense fallback={<p>読み込み中…</p>}><WorkspaceRoute/></Suspense>;}
function WorkspaceRoute(){
  const id=useSearchParams().get("id")||undefined;
  const runtime=useWorkspaceRuntime(id);
  useEffect(()=>{
    if(id||!runtime.workspaceId||runtime.busy)return;
    const url=new URL(window.location.href);
    url.searchParams.set("id",runtime.workspaceId);
    window.history.replaceState(window.history.state,"",url);
  },[id,runtime.workspaceId,runtime.busy]);
  return <Workspace runtime={runtime}/>;
}

function Workspace({runtime:r}:{runtime:Runtime}){
  const data=r.data;const fields=useMemo(()=>data?.fields||[],[data]);
  const [mode,setMode]=useState<Mode>("image"),[selected,setSelected]=useState(""),[channelId,setChannel]=useState(""),[target,setTarget]=useState<ReviewTarget>("nuclei"),[region,setRegion]=useState<number>();
  const [lastResultMode,setLastResultMode]=useState<"statistics"|"figure">("statistics");
  const [metric,setMetric]=useState("mean"),[range,setRange]=useState("selected"),[compare,setCompare]=useState(false),[picked,setPicked]=useState<string[]>([]),[picker,setPicker]=useState(false),[table,setTable]=useState(false);
  const [panelState,dispatchPanel]=useReducer(panelReducer,initialPanelState);
  const ai=panelState.view==="ai",panel=panelState.view==="settings";
  const [instruction,setInstruction]=useState(""),[assignments,setAssignments]=useState(false),[editing,setEditing]=useState(false),[search,setSearch]=useState(""),[returnMode,setReturnMode]=useState<Mode|null>(null);
  const sourceReturn=useRef<{mode:Mode;field:string;channel:string;target:ReviewTarget;metric:string;region:number|undefined;historical:{target:ReviewTarget;result:SavedResult}|null}|null>(null);
  const [localError,setLocalError]=useState(""),[viewport,setViewport]=useState<Record<string,ReviewImageViewport|null>>({});
  const [previewRequest,setPreviewRequest]=useState<{field:string;target:ReviewTarget;sequence:number}|null>(null);
  const [gfpSaved,setGfpSaved]=useState<{signature:string;result:GfpGateResult;filter:WorkspaceGfpFilter}|null>(null);
  const [backgroundDraw,setBackgroundDraw]=useState<{field:string;channels:string[];id:string}|null>(null);
  const [historical,setHistorical]=useState<{target:ReviewTarget;result:SavedResult}|null>(null);
  const sourceRequest=useRef(0);
  const fileInput=useRef<HTMLInputElement>(null),folderInput=useRef<HTMLInputElement>(null);
  const field=fields.find(value=>value.id===selected)||fields[0];
  const actualChannel=field?.channels.find(value=>value.id===channelId)?.id||field?.nuclearChannelId||field?.channels.find(value=>value.role==="nuclear")?.id||field?.channels[0]?.id||"";
  const historicResult=historical?.target===target&&historical.result.field===field?.id?historical.result:undefined;
  const candidate=field&&!historicResult?r.candidateResult(field.id,target):undefined;
  const result=historicResult||candidate||(field?r.currentResult(field.id,target):undefined);
  const rows=result?.rows.filter(value=>value.channel_id===actualChannel)||[];
  const planes=fields.flatMap(value=>value.channels.map(ch=>({field:value,channel:ch,key:`${value.id}:${ch.id}`})));
  const visible=compare?planes.filter(value=>picked.includes(value.key)):planes.filter(value=>value.field.id===field?.id&&value.channel.id===actualChannel);
  const busy=r.busy||editing||!API_CONFIGURED;
  const intakeDisabled=!data||r.busy||!API_CONFIGURED;
  const gfpUnit=target==="cell"?"cell_roi":"nucleus";
  const classificationTarget=target==="cell"?"cell":"nuclei";
  const nuclearFields=fields.flatMap(value=>{const current=r.currentResult(value.id,classificationTarget);return current&&!value.exclusionReason?[{fieldId:value.id,label:value.label,revisionId:current.revision}]:[];});
  const nuclearSignature=JSON.stringify([data?.workspaceId,gfpUnit,nuclearFields.map(value=>[value.fieldId,value.revisionId])]);
  const storedSpec=r.specification().spec as components["schemas"]["AnalysisSpec"]|null;
  const backgrounds:WorkspaceBackgrounds=Object.fromEntries(Object.entries(storedSpec?.backgrounds||{}).map(([id,channels])=>[id,
    Object.fromEntries(Object.entries(channels).map(([channel,roi])=>[channel,{confirmed:true as const,
      polygon:roi.polygon.filter(point=>point.length===2).map(point=>[point[0],point[1]] as Point)}]))]));
  const storedSelection=r.specification().spec?.selection as {gfp?:WorkspaceGfpFilter|null}|undefined;
  const savedFilter=storedSelection?.gfp||null;
  const gfpFilter=savedFilter&&(savedFilter.version==="1.1.0"?savedFilter.unit||"nucleus":"nucleus")===gfpUnit?savedFilter:null;
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
  const sourceTarget=["nucleolar_count","nucleolar_area_fraction","log2_nucleoplasm_over_nucleolus"].includes(metric)?"nucleoplasm":target;
  const sources=useMemo(()=>fields.map(value=>({fieldId:value.id,label:value.label,result:value.results[sourceTarget],metadata:{...emptyMetadata,...Object.fromEntries(Object.keys(emptyMetadata).map(key=>[key,value.metadata?.[key]??null]))},excluded:!!value.exclusionReason})),[fields,sourceTarget]);
  async function act(action:()=>Promise<unknown>){setLocalError("");try{await action();}catch(error){setLocalError(error instanceof ApiError?errorMessage(error):error instanceof Error?errorCodeMessage(error.message):"処理を完了できませんでした。");}}
  function openField(id:string,ch?:string){if(editing)return;setPreviewRequest(null);++sourceRequest.current;setHistorical(null);setSelected(id);if(ch)setChannel(ch);setRegion(undefined);setCompare(false);if(target==="cell"&&r.settings.cellDefinition?.source!=="cellpose"&&!fields.find(value=>value.id===id)?.results.cell&&!busy)void act(()=>r.run("cell",id));}
  async function openSource(id:string,n?:number,revision?:string,sourceStructure?:ReviewTarget,sourceChannel?:string|null){
    if(editing)return;
    setPreviewRequest(null);
    const generation=++sourceRequest.current;
    await act(async()=>{
      const resolvedTarget=sourceStructure||sourceTarget;
      const sourceField=fields.find(value=>value.id===id);
      if(!sourceField)throw new Error("図の元画像を確認できません。");
      if(sourceChannel&&!sourceField.channels.some(value=>value.id===sourceChannel))throw new Error("図の測定チャンネルと元画像が一致しません。");
      let saved:SavedResult|undefined;
      if(revision){
        let record=await request<RevisionRecord & {config:RevisionRecord["config"] & {cohort_sources?:Record<string,{revision_id:string}>}}>(`/v1/revisions/${encodeURIComponent(revision)}`);
        const pinned=record.config.cohort_sources?.[id]?.revision_id;
        if(pinned){revision=pinned;record=await request<RevisionRecord>(`/v1/revisions/${encodeURIComponent(pinned)}`);}
        if(!record.config.field_ids.includes(id))throw new Error("図の出典と視野が一致しません。");
        saved=await r.adapter.readResult(revision,id,record.config.recipe);
        if(saved.field!==id||saved.regionSet!==resolvedTarget)throw new Error("図の測定対象と保存された領域が一致しません。");
      }
      const sourceResult=saved||sourceField.results[resolvedTarget];
      if(n!==undefined&&!sourceResult?.masks.regions.some(value=>value.id===n))throw new Error("図の対象領域を保存されたマスクで確認できません。");
      if(generation!==sourceRequest.current)return;
      sourceReturn.current={mode,field:selected,channel:channelId,target,metric,region,historical};
      setHistorical(saved?{target:resolvedTarget,result:saved}:null);
      setReturnMode(mode);setSelected(id);setTarget(resolvedTarget);setRegion(n);setCompare(false);setMode("image");
      setChannel(sourceChannel||sourceField.nuclearChannelId||sourceField.channels[0]?.id||"");
    });
  }
  function returnToResult(){if(editing)return;const context=sourceReturn.current;if(!context)return;++sourceRequest.current;setSelected(context.field);setChannel(context.channel);setTarget(context.target);setMetric(context.metric);setRegion(context.region);setHistorical(context.historical);setMode(context.mode);setReturnMode(null);sourceReturn.current=null;}
  function newWorkspace(){++sourceRequest.current;sourceReturn.current=null;r.newWorkspace();const url=new URL(window.location.href);url.searchParams.delete("id");window.history.replaceState(window.history.state,"",url);setHistorical(null);setSelected("");setChannel("");setPicked([]);setRegion(undefined);setGfpSaved(null);setViewport({});setPreviewRequest(null);setMode("image");setReturnMode(null);setLocalError("");}
  function changeMode(value:Mode){if(editing)return;dispatchPanel("work");if(returnMode===value){returnToResult();return;}++sourceRequest.current;sourceReturn.current=null;setPreviewRequest(null);if(value!=="image")setLastResultMode(value);setMode(value);setReturnMode(null);setAssignments(false);setPicker(false);if(value!=="image"&&!data?.workspaceId&&!r.busy)void act(()=>r.ensureWorkspace());}
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
  const previewSettings=JSON.stringify([r.settings,r.processing]);
  useEffect(()=>{if(!previewRequest||busy)return;const timer=setTimeout(()=>void previewNow(previewRequest),650);return()=>clearTimeout(timer);},[previewRequest,busy,previewSettings]);
  useEffect(()=>{setTarget(r.activeTarget);setRegion(undefined);},[r.activeTarget]);
  async function classify(result:GfpGateResult,filter:WorkspaceGfpFilter){await act(async()=>{await r.saveSelection({field_ids:nuclearFields.map(value=>value.fieldId),gfp:filter});setGfpSaved({signature:nuclearSignature,result,filter});});}
  async function saveBackground(polygon:Point[]){
    if(!backgroundDraw)return;
    const updated={...backgrounds,[backgroundDraw.field]:{...backgrounds[backgroundDraw.field]}};
    for(const channel of backgroundDraw.channels)updated[backgroundDraw.field][channel]={polygon,confirmed:true};
    await r.saveBackgrounds(updated,[...new Set([...(storedSpec?.confirmed_channel_ids||[]),...backgroundDraw.channels])]);
    setBackgroundDraw(null);queuePreview();
  }
  function changeTarget(value:ReviewTarget){
    ++sourceRequest.current;setPreviewRequest(null);setHistorical(null);setTarget(value);setRegion(undefined);
    if(value==="cell"&&r.settings.cellDefinition?.source!=="cellpose"&&field&&!field.results.cell&&!busy)void act(()=>r.run("cell",field.id));
  }
  async function measure(){await act(()=>r.run(target,range==="selected"?field?.id:undefined));}
  function showSettings(){if(ai)setMode("image");dispatchPanel("settings");}
  async function send(){dispatchPanel("open-ai");await act(()=>r.requestProposal(instruction,field?.id));}
  function add(list:FileList|null){if(list)void act(()=>r.importFiles(list));}
  useEffect(()=>{folderInput.current?.setAttribute("webkitdirectory","");},[]);
  const chooseComparison=()=>{if(!picked.length&&field)setPicked(field.channels.map(ch=>`${field.id}:${ch.id}`));setCompare(true);setPicker(true);};

  return <main className={styles.workspace} data-mode={mode} data-panel={ai||(mode==="image"&&panel)} data-ai={ai}>
    <header className={styles.header}><a className={styles.brand} href="/workspace">cytellect</a><nav aria-label="作業の切替">{([["image","画像"],["statistics","統計"],["figure","グラフ"]] as const).map(([value,label])=><button key={value} disabled={editing} aria-current={mode===value?"page":undefined} onClick={()=>changeMode(value)}>{label}</button>)}</nav><span className={styles.status} role="status">{r.operation}</span>{r.busy&&<button className={styles.icon} aria-label="実行を中止" onClick={()=>r.stop()}><Icon name="stop"/></button>}{mode==="image"&&<><select className={styles.range} aria-label="測定する視野" value={range} onChange={e=>setRange(e.target.value)}><option value="selected">選択視野</option><option value="all">全視野</option></select><button className={styles.primary} disabled={busy||!field||field.kind==="reference"} onClick={()=>void measure()}>測定</button></>}<button className={styles.icon} aria-label="設定パネル" aria-pressed={panel} onClick={showSettings}><Icon name="settings"/></button></header>
    <aside className={styles.sidebar} aria-label={mode==="image"?"視野一覧":"解析対象"}><div className={styles.sideHeading}><button className={styles.icon} disabled={busy} title="新しいワークスペース" aria-label="新しいワークスペース" onClick={newWorkspace}><Icon name="plus"/></button>{mode==="image"?`視野 ${fields.length}`:targets[target]}</div>{mode==="image"?<><input className={styles.search} aria-label="視野を検索" placeholder="検索" value={search} onChange={e=>setSearch(e.target.value)}/><div className={styles.fieldList}>{fields.filter(value=>value.label.toLowerCase().includes(search.toLowerCase())).map((value,index)=>{const ch=value.nuclearChannelId||value.channels[0]?.id;const current=r.currentResult(value.id,target);return <button className={styles.fieldCard} disabled={editing} aria-pressed={value.id===field?.id} key={value.id} onClick={()=>openField(value.id)} title={value.label}>{value.previews[ch]&&<img src={value.previews[ch]} alt={value.label}/>}<span>{index+1} {value.label}</span><small>{value.kind==="reference"?"補助画像":value.exclusionReason?"対象外":current?`${targets[target]} ${new Set(current.masks.regions.map(region=>region.id)).size}`:"未測定"}</small></button>;})}</div><div className={styles.addMenu}><button disabled={intakeDisabled} onClick={()=>fileInput.current?.click()}><Icon name="plus"/>画像</button><button disabled={intakeDisabled} onClick={()=>folderInput.current?.click()}>フォルダ</button></div></>:<div className={styles.resultOptions}><label>領域<select value={target} onChange={e=>{changeTarget(e.target.value as ReviewTarget);}}>{Object.entries(targets).map(([id,label])=><option value={id} key={id}>{label}</option>)}</select></label><label>指標<select value={metric} onChange={e=>setMetric(e.target.value)}>{Object.entries(metrics).map(([id,label])=><option key={id} value={id}>{label}</option>)}</select></label><label>染色<select value={actualChannel} onChange={e=>setChannel(e.target.value)}>{(field?.channels||data?.channels)?.map(ch=><option value={ch.id} key={ch.id}>{ch.stain?`${ch.stain} · ${ch.id}`:ch.id}</option>)}</select></label></div>}</aside>

    <div className={styles.body}>
      {(r.error||localError)&&<div className={styles.error} role="alert">{localError||r.error}<button aria-label="保存状態を再読み込み" disabled={busy} onClick={()=>void act(()=>r.reload())}>再読み込み</button></div>}
      <section hidden={mode!=="image"} className={styles.imageWork}>
        {!field?<div className={styles.start}><h1>画像解析</h1><div className={styles.startActions}><button className={styles.primary} disabled={intakeDisabled} onClick={()=>fileInput.current?.click()}>画像を追加</button><button disabled={intakeDisabled} onClick={()=>folderInput.current?.click()}>フォルダを追加</button></div><p>TIFF・OME-TIFF</p><button onClick={()=>changeMode("statistics")}>測定済みデータを使う</button></div>:<>
          <div className={styles.channelBar}>{returnMode&&<button className={styles.icon} aria-label="元の結果へ戻る" disabled={editing} onClick={returnToResult}><Icon name="back"/></button>}<strong title={field.label}>{field.label}</strong>{field.channels.map(ch=><button disabled={editing} aria-pressed={actualChannel===ch.id&&!compare} key={ch.id} onClick={()=>{setChannel(ch.id);setCompare(false);}}>{ch.stain?`${ch.stain} · ${ch.id}`:ch.id}</button>)}<button className={styles.assignButton} disabled={busy} onClick={()=>setAssignments(!assignments)}>染色対応</button><button className={styles.icon} disabled={editing} aria-label="画像を比較" aria-pressed={compare} onClick={chooseComparison}><Icon name="compare"/></button><details className={styles.fieldMenu}><summary aria-label="画像の用途">⋯</summary><label>画像の用途<select disabled={busy} value={field.kind||"analysis"} onChange={e=>void act(()=>r.saveFieldLink(field.id,e.target.value as "analysis"|"reference"))}><option value="analysis">解析画像</option><option value="reference">補助画像</option></select></label>{field.kind==="reference"&&<label>対応する視野<select disabled={busy} value={field.referenceFor||""} onChange={e=>void act(()=>r.saveFieldLink(field.id,"reference",e.target.value||null))}><option value="">指定なし</option>{fields.filter(value=>value.id!==field.id&&value.kind!=="reference").map(value=><option key={value.id} value={value.id}>{value.label}</option>)}</select></label>}</details></div>
          {assignments&&<AssignmentEditor key={field.id} field={field} runtime={r} onDone={()=>{setAssignments(false);queuePreview("nuclei");}} onError={setLocalError}/>}
          {picker&&<div className={styles.comparisonPicker}>{planes.map(value=><label key={value.key}><input type="checkbox" checked={picked.includes(value.key)} onChange={e=>setPicked(previous=>e.target.checked?[...previous,value.key]:previous.filter(key=>key!==value.key))}/>{value.field.label} · {value.channel.stain||value.channel.id}</label>)}<button className={styles.icon} aria-label="比較対象を閉じる" onClick={()=>setPicker(false)}><Icon name="close"/></button></div>}
          <ImageStage planes={visible} target={target} fieldId={field.id} region={region} rows={rows} onRegion={setRegion} onSelect={(id,ch,n)=>{setSelected(id);setChannel(ch);setRegion(n);}} onOpen={openField} runtime={r} editing={editing} onEditing={setEditing} classification={target==="nuclei"||target==="cell"?classification:undefined} historical={historical} backgrounds={backgrounds} backgroundDraw={backgroundDraw?{field:backgroundDraw.field,requestId:backgroundDraw.id,onSave:saveBackground,onCancel:()=>setBackgroundDraw(null)}:undefined} viewport={viewport} onViewport={(fid,value)=>setViewport(previous=>({...previous,[fid]:value}))}/>
          <div className={styles.measureToggle}><button aria-expanded={table} onClick={()=>setTable(!table)}>測定値{rows.length?` · ${rows.length}`:""}</button><span>{targets[target]}{historicResult?" · 図の保存時の版":candidate?" · 検出候補":result?"":" · 未測定"}</span>{candidate&&<button disabled={busy} onClick={()=>void act(()=>r.acceptCandidates(field.id,target))}>候補を採用</button>}{field.exclusionReason?<button onClick={()=>void act(()=>r.excludeField(field.id,null))}>解析対象に戻す</button>:field.error?<button onClick={()=>void act(()=>r.excludeField(field.id,"利用者が解析対象から除外"))}>この視野を除外</button>:null}</div>
          {table&&<div className={styles.tableDrawer}><MeasurementTable rows={rows} selected={region} onSelect={setRegion}/></div>}
        </>}
      </section>
      <section className={styles.resultWork} hidden={mode==="image"}><ConnectedResults adapter={r.adapter} workspace={data?.workspaceId||""} selection={r.adapter.selection()} items={sources} target={sourceTarget} metric={metric} channel={metric.startsWith("area_")?null:actualChannel||null} mode={mode==="image"?lastResultMode:mode} onSource={(id,n,revision,structure,ch)=>void openSource(id,n,revision,structure,ch)} onAnalysisTargetChange={setTarget} onPrepareMissing={()=>r.run(sourceTarget)} disabled={r.busy} gfp={gfpFilter} initialSpec={storedSpec||undefined} onSaveDraft={draft=>r.saveResultDraft(draft)} onMetricChange={(nextMetric,nextChannel)=>{setMetric(nextMetric);if(nextChannel)setChannel(nextChannel);}}/></section>
    </div>

    {(mode==="image"||ai)&&(panel||ai)&&<aside className={styles.inspector} aria-label={ai?"AI":"画像解析"}><div className={styles.panelHeading}><h2>{ai?"AI":"画像解析"}</h2><button className={styles.icon} aria-label="パネルを閉じる" onClick={()=>dispatchPanel("close")}><Icon name="close"/></button></div><div className={styles.inspectorBody}>
      {ai?<><button onClick={showSettings}>解析設定を表示</button><div className={styles.userMessage}>{instruction}</div>{r.proposal?<><p>{r.proposal.draft.rationale}</p><dl>{r.proposal.draft.channels.map(ch=><div key={ch.token}><dt>{ch.token}</dt><dd>{ch.stain||ch.role}</dd></div>)}</dl>{r.proposal.draft.missing_information.length>0&&<ul>{r.proposal.draft.missing_information.map(text=><li key={text}>{text}</li>)}</ul>}{r.canUndoProposal()&&<button disabled={busy} onClick={()=>void act(()=>r.undoProposal())}>AIによる設定変更を戻す</button>}</>:<p>下の入力欄から解析の指示を送信できます。</p>}</>:<>
        <label>領域<select disabled={busy} value={target} onChange={e=>{changeTarget(e.target.value as ReviewTarget);}}>{Object.entries(targets).map(([id,label])=><option key={id} value={id}>{label}</option>)}</select></label>
        <section><h3>検出</h3>{target==="nuclei"?<><label>核染色<select value={field?.channels.find(ch=>ch.role==="nuclear")?.id||field?.nuclearChannelId||""} disabled={busy} onChange={e=>void act(()=>r.saveAssignments((field?.channels||[]).map(ch=>({channel_id:ch.id,stain:ch.stain,role:ch.id===e.target.value?"nuclear":ch.role==="unused"?"unused":"measure"})),field?.id).then(()=>queuePreview("nuclei")))}><option value="">チャンネルを指定</option>{(field?.channels||data?.channels)?.map(ch=><option key={ch.id} value={ch.id}>{ch.stain?`${ch.stain} · ${ch.id}`:ch.id}</option>)}</select></label><p className={styles.method}>StarDist 2D</p><details><summary>検出条件</summary><NumberSetting label="確率閾値" value={r.settings.nuclearProbability} min={0} max={1} step={.05} onChange={v=>setSetting("nuclearProbability",v??.5)}/><NumberSetting label="NMS閾値" value={r.settings.nuclearNms} min={0} max={1} step={.05} onChange={v=>setSetting("nuclearNms",v??.3)}/><NumberSetting label="検出用画像の長辺 / px" value={r.settings.nuclearMaxSide} min={64} max={2048} onChange={v=>setSetting("nuclearMaxSide",v)}/></details></>:target==="cell"?<><label>検出アルゴリズム<select disabled={busy} value={r.settings.cellDefinition?.source||"manual"} onChange={e=>setSetting("cellDefinition",{source:e.target.value as "manual"|"cellpose",channel:r.settings.cellDefinition?.channel||""})}><option value="manual">手描き</option><option value="cellpose">Cellpose-SAM</option></select></label>{r.settings.cellDefinition?.source==="cellpose"?<><label>細胞を検出する画像<select disabled={busy} value={r.settings.cellDefinition.channel} onChange={e=>{setSetting("cellDefinition",{source:"cellpose",channel:e.target.value});if(e.target.value)setChannel(e.target.value);}}><option value="">チャンネルを指定</option>{(field?.channels||data?.channels)?.map(ch=><option key={ch.id} value={ch.id}>{ch.stain?`${ch.stain} · ${ch.id}`:ch.id}</option>)}</select></label>{field&&<CellposeSettings runtime={r} field={field.id} target="cell" disabled={busy} onChanged={()=>queuePreview()}/>}</>:<p>画像上で細胞の輪郭を描けます。</p>}</>:target==="nucleoplasm"?<p>採用した核から、核小体を除いた領域です。</p>:<><label>核小体の定義<select value={r.settings.nucleolarDefinition.source} disabled={busy} onChange={e=>selectNucleolarSource(e.target.value as "dapi_poor"|"marker"|"ncl")}><option value="dapi_poor">核染色の低輝度領域</option><option value="marker">核小体マーカー</option><option value="ncl">NCL陽性領域</option></select></label>{r.settings.nucleolarDefinition.source!=="dapi_poor"&&<label>{r.settings.nucleolarDefinition.source==="ncl"?"NCL画像":"マーカー画像"}<select value={r.settings.nucleolarDefinition.marker} onChange={e=>{setSetting("nucleolarDefinition",{...r.settings.nucleolarDefinition,marker:e.target.value,...(r.settings.nucleolarDefinition.source==="ncl"?{algorithm:nclAlgorithm}:{})});setChannel(e.target.value);}}><option value="">チャンネルを指定</option>{(field?.channels||data?.channels)?.map(ch=><option value={ch.id} key={ch.id}>{ch.stain?`${ch.stain} · ${ch.id}`:ch.id}</option>)}</select></label>}{r.settings.nucleolarDefinition.source==="ncl"&&<label>検出アルゴリズム<select value={rawNclCellpose?"cellpose-raw":nclAlgorithm} disabled={busy} onChange={e=>{if(e.target.value==="cellpose-raw")return;r.selectNucleolarSource("ncl",r.settings.nucleolarDefinition.marker,e.target.value as "cellpose"|"objects"|"legacy");queuePreview();}}><option value="cellpose">Cellpose-SAM（局所背景除去）</option>{rawNclCellpose&&<option value="cellpose-raw">Cellpose-SAM（前処理なし）</option>}<option value="objects">局所輝度差・形状</option><option value="legacy">NCLしきい値</option></select></label>}{r.settings.nucleolarDefinition.source==="ncl"&&nclAlgorithm==="cellpose"?field&&<CellposeSettings runtime={r} field={field.id} target="nucleoli" disabled={busy} onChanged={()=>queuePreview()}/>:<details><summary>検出条件</summary>{r.settings.nucleolarDefinition.source==="dapi_poor"&&<NumberSetting label="核内中央値に対する輝度比" value={r.settings.nucleolarDefinition.relative} min={.01} max={.99} step={.05} onChange={v=>setSetting("nucleolarDefinition",{...r.settings.nucleolarDefinition,relative:v??.7})}/>}<NumberSetting label="平滑化 σ / px" value={r.settings.nucleolarSigma??(r.settings.nucleolarDefinition.source==="ncl"?nclDefaults.smoothing_sigma_px:null)} min={0} max={r.settings.nucleolarDefinition.source==="ncl"?10:20} step={.1} onChange={v=>{r.setNucleolarSigma(v);queuePreview();}}/>{r.settings.nucleolarDefinition.source!=="ncl"&&<NumberSetting label="核辺縁の除外 / px" value={r.settings.nucleolarRim} min={0} onChange={v=>setSetting("nucleolarRim",v)}/>}<NumberSetting label="最小面積 / px²" value={r.settings.nucleolarMinimumArea??(r.settings.nucleolarDefinition.source==="ncl"?nclDefaults.minimum_area_px:null)} min={1} onChange={v=>setSetting("nucleolarMinimumArea",v)}/><NumberSetting label="最大面積 / px²" value={r.settings.nucleolarMaximumArea??(r.settings.nucleolarDefinition.source==="ncl"?nclDefaults.maximum_area_px:null)} min={1} onChange={v=>setSetting("nucleolarMaximumArea",v)}/>{r.settings.nucleolarDefinition.source==="ncl"&&nclAlgorithm==="objects"&&field&&<>
  {([["core_contrast","候補中心の輝度差",0,65535,1],["minimum_peak_difference","局所背景との輝度差",0,65535,1],["minimum_peak_ratio","局所背景との輝度比",1,100,.1],["boundary_fraction","境界の輝度割合",.01,.99,.05],["minimum_solidity","充実度",0,1,.05],["minimum_circularity","円形度",0,1,.05]] as const).map(([key,label,min,max,step])=><NumberSetting key={key} label={label} value={nclDefaults[key]} min={min} max={max} step={step} onChange={v=>{if(v!==null){r.setNclParameter(field.id,key,v);queuePreview();}}}/>) }
</>}</details>}</>}</section>
        {<details><summary>GFPによる対象選別</summary><ConnectedGfp key={gfpUnit} unit={gfpUnit} adapter={r.adapter} workspace={data?.workspaceId||""} fields={nuclearFields} channels={field?.channels||data?.channels||[]} disabled={busy} onClassified={(result,filter)=>void classify(result,filter)}/>{gfpFilter&&<button disabled={busy} onClick={()=>void act(async()=>{await r.saveSelection({field_ids:nuclearFields.map(value=>value.fieldId),gfp:null});setGfpSaved(null);})}>すべての{targets[classificationTarget]}を対象にする</button>}</details>}
        <section><h3>測定</h3><label>指標<select value={metric} onChange={e=>setMetric(e.target.value)}>{Object.entries(metrics).map(([id,label])=><option key={id} value={id}>{label}</option>)}</select></label><label>背景補正<select value={r.settings.background} disabled={busy} onChange={e=>setSetting("background",e.target.value as RuntimeSettings["background"])}><option value="raw">なし（原値）</option><option value="automatic">自動推定</option><option value="confirmed_roi">背景ROI</option></select></label>{r.settings.background==="confirmed_roi"&&field&&<ConnectedBackground fieldId={field.id} fieldLabel={field.label} channels={field.channels.map(ch=>({...ch,role:ch.role||undefined}))} backgrounds={backgrounds} confirmedChannelIds={storedSpec?.confirmed_channel_ids||[]} disabled={r.busy} drawing={!!backgroundDraw} onDraw={channels=>{setCompare(false);setBackgroundDraw({field:field.id,channels,id:crypto.randomUUID()});}} onRemove={async channels=>{const updated={...backgrounds,[field.id]:{...backgrounds[field.id]}};for(const ch of channels)delete updated[field.id][ch];await r.saveBackgrounds(updated,storedSpec?.confirmed_channel_ids||[]);}}/>}</section>
      </>}
    </div></aside>}
    <footer className={styles.composer}>{r.importIssues.length>0&&<details className={styles.importIssues}><summary>取込 {r.importIssues.length}件</summary><ul>{r.importIssues.map((issue,index)=><li key={index}>{importIssueText(issue)}</li>)}</ul></details>}<button className={styles.icon} aria-label="AIの会話を開く" aria-pressed={ai} onClick={()=>dispatchPanel("toggle-ai")}><Icon name="ai"/></button><textarea aria-label="AIへの指示" placeholder="AIに指示" value={instruction} onChange={e=>setInstruction(e.target.value)} rows={1}/><button className={styles.send} aria-label="AIへ送信" disabled={busy||(!instruction.trim()&&!fields.length)} onClick={()=>void send()}><Icon name="send"/></button></footer>
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
function NumberSetting({label,value,onChange,min,max,step=1}:{label:string;value:number|null;onChange:(value:number|null)=>void;min?:number;max?:number;step?:number}){return <label>{label}<input type="number" value={value??""} placeholder="自動" min={min} max={max} step={step} onChange={e=>onChange(e.target.value===""?null:Number(e.target.value))}/></label>;}
function CellposeSettings({runtime:r,field,target,disabled,onChanged}:{runtime:Runtime;field:string;target:"cell"|"nucleoli";disabled:boolean;onChanged:()=>void}){
  const settings=r.cellposeSettings(field,target);
  return <details><summary>検出条件</summary><fieldset className={styles.detectorSettings} disabled={disabled}>
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
  </fieldset></details>;
}
function AssignmentEditor({field,runtime:r,onDone,onError}:{field:ReviewField;runtime:Runtime;onDone:()=>void;onError:(s:string)=>void}){
  const [draft,setDraft]=useState<ChannelAssignment[]>(()=>field.channels.map(ch=>({channel_id:ch.id,stain:ch.stain,role:ch.role||"measure"})));
  return <div className={styles.assignments}>{draft.map((ch,index)=><label key={ch.channel_id}>{field.previews[ch.channel_id]&&<img src={field.previews[ch.channel_id]} alt={ch.channel_id}/>}<strong>{ch.channel_id}</strong><input aria-label={`${ch.channel_id}の染色名`} placeholder="染色名" value={ch.stain||""} onChange={e=>setDraft(previous=>previous.map((item,i)=>i===index?{...item,stain:e.target.value||null}:item))}/><select aria-label={`${ch.channel_id}の役割`} value={ch.role} onChange={e=>setDraft(previous=>previous.map((item,i)=>({...item,role:i===index?e.target.value as ChannelAssignment["role"]:e.target.value==="nuclear"&&item.role==="nuclear"?"measure":item.role})))}><option value="nuclear">核検出</option><option value="measure">測定</option><option value="unused">使用しない</option></select></label>)}<button disabled={r.busy} className={styles.primary} onClick={()=>{void r.saveAssignments(draft,field.id).then(onDone).catch(e=>onError(e instanceof Error?e.message:"保存できませんでした。"));}}>保存</button></div>;
}
function MeasurementTable({rows,selected,onSelect}:{rows:MeasurementRow[];selected?:number;onSelect:(n:number)=>void}){
  const corrected=rows.some(row=>"mean_corrected" in row);
  return <table><thead><tr><th>番号</th><th>面積 / px²</th><th>平均輝度</th><th>積算輝度</th>{corrected&&<><th>平均（背景補正）</th><th>積算（背景補正）</th></>}</tr></thead><tbody>{rows.map(row=><tr key={row.region_id} aria-selected={row.region_id===selected}><td><button onClick={()=>onSelect(row.region_id)}>{row.region_id}</button></td>{[row.area_px,row.mean,row.integrated,...(corrected?[row.mean_corrected,row.integrated_corrected]:[])].map((value,i)=><td key={i} title={value==null?row.correction_missing_reason||row.intensity_missing_reason||row.area_missing_reason||undefined:undefined}>{value?.toLocaleString(undefined,{maximumFractionDigits:2})??"—"}</td>)}</tr>)}</tbody></table>;
}

function ImageStage({planes,target,fieldId,region,rows,onRegion,onSelect,onOpen,runtime:r,editing,onEditing,classification,historical,backgrounds,backgroundDraw,viewport,onViewport}:{planes:Array<{field:ReviewField;channel:{id:string;stain:string|null};key:string}>;target:ReviewTarget;fieldId:string;region?:number;rows:MeasurementRow[];onRegion:(n:number)=>void;onSelect:(field:string,ch:string,n:number)=>void;onOpen:(field:string,ch:string)=>void;runtime:Runtime;editing:boolean;onEditing:(v:boolean)=>void;classification?:GfpGateResult["nuclei"];historical:{target:ReviewTarget;result:SavedResult}|null;backgrounds:WorkspaceBackgrounds;backgroundDraw?:{field:string;requestId:string;onSave:(polygon:Point[])=>Promise<void>;onCancel:()=>void};viewport:Record<string,ReviewImageViewport|null>;onViewport:(fid:string,value:ReviewImageViewport|null)=>void}){
  const ref=useRef<HTMLDivElement>(null),[size,setSize]=useState({width:800,height:600});
  useEffect(()=>{const node=ref.current;if(!node)return;const observer=new ResizeObserver(entries=>{const {width,height}=entries[0].contentRect;setSize({width,height});});observer.observe(node);return()=>observer.disconnect();},[]);
  const single=planes.length===1;const layout=imageStageLayout(planes.map(plane=>plane.field),size);
  const showTable=single&&size.width-(layout.tiles[0]?.width||0)>230;
  return <div ref={ref} className={styles.stage} data-single={single} style={{"--columns":layout.columns} as CSSProperties}>
    {planes.map((plane,index)=>{
      const old=historical?.target===target&&historical.result.field===plane.field.id?historical.result:undefined;
      const candidate=old?undefined:r.candidateResult(plane.field.id,target),value=old||candidate||r.currentResult(plane.field.id,target),tile=layout.tiles[index];
      const editable=single&&!!value&&!old&&!candidate&&target!=="nucleoplasm";
      return <div className={styles.tile} key={plane.key} style={{width:tile.width,height:tile.height}}>
        {!single&&<div className={styles.tileCaption}>{plane.field.label} · {plane.channel.stain||plane.channel.id}</div>}
        {plane.field.previews[plane.channel.id]?<ReviewImageCanvas
          src={plane.field.previews[plane.channel.id]} width={plane.field.width} height={plane.field.height}
          contours={value?.masks.regions||[]} classification={Object.fromEntries((classification||[]).filter(item=>item.field_id===plane.field.id).map(item=>[item.region_id,item.gfp_positive]))} selected={plane.field.id===fieldId?region:undefined}
          label={`${plane.field.label} ${plane.channel.stain||plane.channel.id}`}
          onSelect={n=>onSelect(plane.field.id,plane.channel.id,n)} onOpen={!single?()=>onOpen(plane.field.id,plane.channel.id):undefined}
          editingKey={`${plane.field.id}:${target}:${value?.revision||"none"}`} editDisabled={r.busy||!editable}
          onEdit={editable?(operation,polygon,n,merged)=>r.editMask(plane.field.id,target,value!.revision,operation,polygon,n,merged):undefined}
          onDelete={editable?n=>r.correct(plane.field.id,target,value!.revision,"delete",n):undefined}
          onUndo={editable?()=>r.undo(plane.field.id,target):undefined} onRedo={editable?()=>r.redo(plane.field.id,target):undefined}
          canUndo={!r.busy&&r.canUndo(plane.field.id,target)} canRedo={!r.busy&&r.canRedo(plane.field.id,target)}
          backgroundPolygon={backgrounds[plane.field.id]?.[plane.channel.id]?.polygon} backgroundEdit={single&&backgroundDraw?.field===plane.field.id?backgroundDraw:undefined} onEditingChange={onEditing} viewport={viewport[plane.field.id]} onViewportChange={value=>onViewport(plane.field.id,value)}
          style={{width:tile.width,height:tile.imageHeight,flex:"none"}}/>:<p>画像を読み込み中…</p>}
      </div>;
    })}
    {showTable&&<div className={styles.sideMeasurements}><h3>{targets[target]}の測定値</h3>{rows.length?<MeasurementTable rows={rows} selected={region} onSelect={onRegion}/>:<p>測定結果はここに表示されます。</p>}{editing&&<p>描画を保存または取消して続けてください。</p>}</div>}
  </div>;
}
