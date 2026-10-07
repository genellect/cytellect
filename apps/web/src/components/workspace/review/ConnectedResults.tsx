"use client";

import {useEffect,useLayoutEffect,useMemo,useRef,useState} from "react";
import {ApiError,download,errorCodeMessage,errorMessage,post,request} from "@/lib/api";
import {formatValue,type Job} from "@/lib/types";
import {usePrivateImage} from "@/lib/usePrivateImage";
import {comparisonWarnings} from "@/lib/region-comparison-view";
import {commonWarnings} from "@/lib/common-statistics";
import {createComparisonAdapter,type Metadata,type ComparisonSource,type GfpSelectionChoice} from "@/lib/workspace/comparison-adapter";
import type {ApiAdapter,SavedResult,WorkspaceSelection} from "@/lib/workspace/api-adapter";
import type {ReviewTarget} from "@/lib/workspace/review-preview";
import {checkedPlot,emptyMetadata,resultRequest,type ResultDesign,type ResultOperation,type RenderPlot} from "./connected-results-model";
import styles from "./connected-results.module.css";
import {AxisControls,axisPlotOptions,emptyAxis,type AxisState} from "./AxisControls";
import {ConnectedCsvResults} from "./ConnectedCsvResults";
import {EditableFigure,type FigurePart,type FigureSource} from "./EditableFigure";
import type {components} from "@/lib/generated";

export interface ConnectedResultItem {fieldId:string;label:string;result?:SavedResult;metadata?:Metadata;excluded?:boolean}
export interface ConnectedResultsProps {
  adapter:ApiAdapter;workspace:string;selection:WorkspaceSelection|null;items:ConnectedResultItem[];
  target:ReviewTarget;metric:string;channel:string|null;mode:"statistics"|"figure";
  onSource:(fieldId:string,regionId?:number,revisionId?:string,target?:ReviewTarget,channelId?:string|null)=>void;beforePrepare?:()=>Promise<WorkspaceSelection|null>;disabled?:boolean;
  gfp?:GfpSelectionChoice|null;
  initialSpec?:Pick<components["schemas"]["AnalysisSpec"],"statistics"|"figure"|"additional_analyses"|"figure_proposals">;
  onSaveDraft?:(draft:{statistics?:unknown;figure?:unknown})=>Promise<unknown>;
  onMetricChange?:(metric:string,channel:string|null)=>void;
  onAnalysisTargetChange?:(target:ReviewTarget)=>void;
  onPrepareMissing?:()=>Promise<unknown>;
}
interface SavedSource {field_id:string;region_set?:{region_set_id:string}}
interface ResultPayload {revision_id:string;analysis_kind?:string;source_kind?:string;source_job_id?:string;source_fields?:SavedSource[];x_source?:{source_fields?:SavedSource[]};y_source?:{source_fields?:SavedSource[];metric?:string;channel?:{channel_id:string}|null;plot_data?:Record<string,unknown>[]};figure:{source_files:string[];status?:string};metric?:string;channel?:{channel_id:string}|null;spec?:{plot?:Record<string,unknown>;conditions?:string[];selection?:{metric:string;channel_id?:string|null}};field_summary?:Record<string,unknown>[];comparisons?:Record<string,unknown>[];associations?:Record<string,unknown>[];counts?:unknown;omnibus?:Record<string,unknown>|null;warnings?:string[];plot_data?:Record<string,unknown>[]}
interface Saved {job:string;revision:string;result:ResultPayload;identity:string;requestIdentity:string;plot:RenderPlot;figureJob:string;figure:ResultPayload["figure"];operation:ResultOperation;sources?:Array<{field:string;label:string}>;historical?:boolean;target?:ReviewTarget}
const metricLabels:Record<string,string>={area_px:"面積 / px²",area_um2:"面積 / µm²",mean:"平均輝度",median:"中央値",integrated:"積算輝度",mean_corrected:"平均輝度（背景補正）",integrated_corrected:"積算輝度（背景補正）",nucleolar_count:"核小体数",nucleolar_area_fraction:"核小体面積割合",log2_nucleoplasm_over_nucleolus:"核質／核小体 log₂ 比"};
const resultSources=(result:ResultPayload):SavedSource[]=>result.source_fields||result.x_source?.source_fields||result.y_source?.source_fields||[];
const fail=(error:unknown)=>error instanceof ApiError?errorMessage(error):error instanceof Error?errorCodeMessage(error.message):"処理を完了できませんでした。";

/** Source-bound statistics and saved-result rendering. No statistical values are computed in React. */
export function ConnectedResults(props:ConnectedResultsProps) {
  return <WorkspaceResults key={props.workspace} {...props}/>;
}

function WorkspaceResults({adapter,workspace,selection,items,target,metric,channel,mode,onSource,beforePrepare,disabled=false,gfp=null,initialSpec,onSaveDraft,onMetricChange,onAnalysisTargetChange,onPrepareMissing}:ConnectedResultsProps) {
  const comparison=useMemo(()=>createComparisonAdapter(),[]);
  const [csv,setCsv]=useState(false);
  const [operation,setOperation]=useState<ResultOperation>("distribution");
  const [proposedIndex,setProposedIndex]=useState(0);
  const proposals=[initialSpec?.statistics?.method,...(initialSpec?.additional_analyses??[])].filter((value):value is NonNullable<typeof value>=>!!value);
  const displayMetric=(value:string)=>({area:"area_px",mean_raw:"mean",integral_raw:"integrated",integral_corrected:"integrated_corrected",ncl_log2_nucleoplasm_over_nucleoli:"log2_nucleoplasm_over_nucleolus"}[value]??value);
  function selectProposal(index:number){const method=proposals[index];if(!method)return;setProposedIndex(index);setOperation(method.kind==="descriptive"?"distribution":method.kind);setRank(["mann-whitney-u","wilcoxon"].includes(method.test||"")||method.association==="spearman");setPaired(["paired-t","wilcoxon"].includes(method.test||""));setConfirmed(false);
    const figure=initialSpec?.figure_proposals?.find(value=>value.analysis_index===index),axis=method.y??figure;
    if(axis){onMetricChange?.(displayMetric(axis.metric),axis.channel??null);const region=axis.region;onAnalysisTargetChange?.(region==="nucleus"?"nuclei":region==="supplied"?"cell":region==="nucleoli"||region==="nucleoplasm"?region:target);}
    if(method.x){setXMetric(displayMetric(method.x.metric));setXChannel(method.x.channel??null);}
  }
  const [metadata,setMetadata]=useState<Record<string,Metadata>>({});
  const [paired,setPaired]=useState(false),[rank,setRank]=useState(false),[unit,setUnit]=useState(""),[pairing,setPairing]=useState("");
  const [confirmed,setConfirmed]=useState(false),[reviewed,setReviewed]=useState(false);
  const [contrasts,setContrasts]=useState<string[][]>([]);
  const [xMetric,setXMetric]=useState("area_px"),[xChannel,setXChannel]=useState<string|null>(channel);
  const [width,setWidth]=useState(183),[height,setHeight]=useState(100),[font,setFont]=useState(7);
  const [xLabel,setXLabel]=useState(""),[yLabel,setYLabel]=useState(""),[yMin,setYMin]=useState(""),[yMax,setYMax]=useState("");
  const [xAxis,setXAxis]=useState<AxisState>(emptyAxis),[yAxis,setYAxis]=useState<AxisState>(emptyAxis);
  const outputRef=useRef<HTMLDivElement>(null),scrollPositions=useRef<Record<string,number>>({});
  useLayoutEffect(()=>{const element=outputRef.current,positions=scrollPositions.current;if(!element)return;element.scrollTop=positions[mode]??0;return()=>{positions[mode]=element.scrollTop;};},[mode,csv]);
  const [figureKind,setFigureKind]=useState<RenderPlot["kind"]>("distribution");
  const [part,setPart]=useState<FigurePart>("figure"),[colors,setColors]=useState<Record<string,string>>({}),[legend,setLegend]=useState(true),[pointSize,setPointSize]=useState(18),[order,setOrder]=useState<string[]>([]);
  const [history,setHistory]=useState<Saved[]>([]);
  const receivedSpec=useRef(""),savedDraft=useRef(""),skipOwnSpec=useRef(false);
  const [selectedSeries,setSelectedSeries]=useState("");
  const [pointSource,setPointSource]=useState<{job:string;source:FigureSource}|null>(null);
  const [saved,setSaved]=useState<Saved|null>(null),[busy,setBusy]=useState(""),[error,setError]=useState("");
  const lock=useRef(false),renderCache=useRef(new Map<string,{job:string;figure:ResultPayload["figure"]}>()),renderIds=useRef(new Map<string,string>());
  useEffect(()=>{if(!workspace)return;let live=true;void request<Job[]>(`/v1/workspaces/${workspace}/jobs`).then(async jobs=>{
    const completed=jobs.filter(job=>job.state==="succeeded"&&(job.kind==="statistics"||job.kind==="figure-render")).sort((a,b)=>b.created-a.created).slice(0,30);
    const records=await Promise.all(completed.map(async job=>{try{const result=await request<ResultPayload>(`/v1/jobs/${job.id}/result`);if(result.source_kind!=="region-2d"||!result.figure)return null;const entry:Saved={job:result.source_job_id||job.id,revision:result.revision_id,result,identity:"history",requestIdentity:"history",plot:{...checkedPlot(183,100,7,"","","",""),...result.spec?.plot} as RenderPlot,figureJob:job.id,figure:result.figure,operation:result.analysis_kind==="region-comparison"?"comparison":result.analysis_kind==="region-association"?"association":"distribution",sources:resultSources(result).map(field=>({field:field.field_id,label:field.field_id})),historical:true,target:(["nuclei","nucleoli","nucleoplasm","cell"].includes(resultSources(result)[0]?.region_set?.region_set_id||"")?resultSources(result)[0]?.region_set?.region_set_id:undefined) as ReviewTarget|undefined};return entry;}catch{return null;}}));
    if(live)setHistory(previous=>[...previous,...records.filter((value):value is Saved=>!!value&&!previous.some(old=>old.figureJob===value.figureJob))]);
  }).catch(()=>undefined);return()=>{live=false;};},[workspace]);
  const sources:ComparisonSource[]=items.flatMap(item=>item.result&&!item.excluded?[{field:item.fieldId,revision:item.result.revision,label:item.label,result:item.result,metadata:metadata[item.fieldId]??item.metadata??emptyMetadata}]:[]);
  const fields=Object.fromEntries(sources.map(source=>[source.field,source.metadata]));
  const regionSet=sources[0]?.result.regionSet||target;
  const identity=JSON.stringify([target,sources.map(source=>[source.field,source.revision]),fields,selection]);
  const conditions=[...new Set(Object.values(fields).map(value=>value.condition?.trim()).filter((value):value is string=>!!value))];
  const pairs=conditions.flatMap((a,index)=>conditions.slice(index+1).map(b=>[a,b]));
  const channels=[...new Set(sources.flatMap(source=>source.result.rows.map(row=>row.channel_id)))];
  const design:ResultDesign={operation,metric,channel,regionSet,paired,rank,unit,pairing,confirmed,contrasts,xMetric,xChannel,gfp};
  const sourceIdentity=JSON.stringify([target,sources.map(source=>[source.field,source.revision])]);
  useEffect(()=>{setReviewed(false);setConfirmed(false);},[sourceIdentity]);
  useEffect(()=>{
    if(!initialSpec)return;const key=JSON.stringify(initialSpec);if(receivedSpec.current===key)return;receivedSpec.current=key;
    if(skipOwnSpec.current){skipOwnSpec.current=false;return;}
    const stat=initialSpec.statistics,figure=initialSpec.figure;
    if(stat?.method){setOperation(stat.method.kind==="descriptive"?"distribution":stat.method.kind);setPaired(stat.design==="paired");setRank(["mann-whitney-u","wilcoxon"].includes(stat.method.test||"")||stat.method.association==="spearman");setUnit(stat.unit_definition);setPairing(stat.pairing_basis);setContrasts(stat.comparisons||[]);setMetadata(stat.field_metadata||{});setConfirmed(false);
      onMetricChange?.(stat.metric==="ncl_log2_nucleoplasm_over_nucleoli"?"log2_nucleoplasm_over_nucleolus":stat.metric,stat.channel_id??null);
      const sx=stat as typeof stat & {x_metric?:string|null;x_channel_id?:string|null};if(stat.method.y)onMetricChange?.(displayMetric(stat.method.y.metric),stat.method.y.channel??null);if(stat.method.x){setXMetric(displayMetric(stat.method.x.metric));setXChannel(stat.method.x.channel??null);}else if(sx.x_metric){setXMetric(sx.x_metric);setXChannel(sx.x_channel_id??null);}
    }
    if(figure?.plot){const p=figure.plot as typeof figure.plot & {style?:RenderPlot["style"];axes?:RenderPlot["axes"]};setFigureKind(p.kind);setWidth(p.width_inches*25.4);setHeight(p.height_inches*25.4);setFont(p.font_size);setXLabel(p.x_label);setYLabel(p.y_label);setYMin(p.y_min==null?"":String(p.y_min));setYMax(p.y_max==null?"":String(p.y_max));setColors(p.style?.series_colors||{});setLegend(p.style?.show_legend??true);setPointSize(p.point_size??18);setOrder(p.group_order||[]);setXAxis({min:p.axes?.x_min==null?"":String(p.axes.x_min),max:p.axes?.x_max==null?"":String(p.axes.x_max),step:p.axes?.x_tick_step==null?"":String(p.axes.x_tick_step),scale:p.axes?.x_scale||"linear"});setYAxis({min:"",max:"",step:p.y_tick_step==null?"":String(p.y_tick_step),scale:p.axes?.y_scale||"linear"});}
  },[initialSpec,onMetricChange]);
  const requestIdentity=JSON.stringify(design);
  const stale=!!saved&&!saved.historical&&(saved.identity!==identity||saved.requestIdentity!==requestIdentity);
  const missing=items.filter(item=>!item.excluded&&!item.result).length;
  const excludedCount=items.filter(item=>item.excluded).length;
  const ready=!!sources.length&&!missing&&!disabled&&!busy&&reviewed;
  const svgFiles=saved?.figure.source_files.filter(name=>name.endsWith(".svg"))||[];
  const canRender=!!saved&&!stale&&!disabled&&!busy;
  const pointRows=saved&&pointSource?.job===saved.figureJob?(saved.result.plot_data||saved.result.y_source?.plot_data||[]).filter(row=>["condition","sample","experimental_unit"].every(key=>!(key in pointSource.source)||row[key]===pointSource.source[key as keyof FigureSource])):[];
  function openPoint(source:FigureSource){if(!saved)return;if(source.field_id){if(!resultSources(saved.result).some(field=>field.field_id===source.field_id))return;onSource(source.field_id,source.region_id??source.nucleus_id,saved.revision,saved.target,savedChannel);}else if(source.experimental_unit){setPointSource({job:saved.figureJob,source});}}
  const series=saved?.historical?(saved.operation==="distribution"?(saved.sources||[]).map(source=>source.field):saved.result.spec?.conditions||[]):operation==="distribution"?sources.map(source=>source.field):conditions;
  const plot=():RenderPlot=>({...checkedPlot(width,height,font,xLabel,yLabel,yMin,yMax),...axisPlotOptions(xAxis,{...yAxis,min:yMin,max:yMax},(saved?.historical?saved.operation:operation)==="association"),point_size:pointSize,group_order:order.length?[...order.filter(key=>series.includes(key)),...series.filter(key=>!order.includes(key))]:[],style:{version:"1.0.0",series_colors:colors,show_legend:legend}});
  async function persist(){if(!onSaveDraft)return;const display={...plot(),kind:operation==="association"?"scatter" as const:figureKind};
    const canonicalMetric=metric==="log2_nucleoplasm_over_nucleolus"?"ncl_log2_nucleoplasm_over_nucleoli":metric;
    const value={statistics:{method:{kind:operation==="distribution"?"descriptive":operation,test:operation==="comparison"?(rank?(paired?"wilcoxon":"mann-whitney-u"):(paired?"paired-t":"welch-t")):null,omnibus:operation==="comparison"&&!paired&&conditions.length>=3?(rank?"kruskal-wallis":"welch-anova"):null,association:operation==="association"?(rank?"spearman":"pearson"):null,x:operation==="association"?{metric:xMetric,channel:xChannel,region:regionSet==="nuclei"?"nucleus":regionSet==="cell"?"supplied":regionSet}:null,y:operation==="association"?{metric:canonicalMetric,channel,region:regionSet==="nuclei"?"nucleus":regionSet==="cell"?"supplied":regionSet}:null},metric:canonicalMetric,channel_id:channel,design:paired?"paired":"independent",unit_definition:unit,pairing_basis:pairing,conditions,comparisons:contrasts,field_metadata:fields,x_metric:xMetric,x_channel_id:xChannel},figure:{metric:canonicalMetric,channel_id:channel,plot:display}};
    const key=JSON.stringify(value);if(savedDraft.current===key)return;skipOwnSpec.current=true;try{await onSaveDraft(value);savedDraft.current=key;}catch(cause){skipOwnSpec.current=false;throw cause;}
  }

  async function waitJob(id:string) {
    for(;;){const jobs=await request<Job[]>(`/v1/workspaces/${workspace}/jobs`);const job=jobs.find(value=>value.id===id);
      if(!job)throw new Error("保存された処理が見つかりません。");if(job.state==="succeeded")return job;
      if(job.state==="failed"||job.state==="cancelled")throw new Error(job.error||"処理が中止されました。");
      await new Promise(resolve=>setTimeout(resolve,1000));}
  }
  async function calculate(){
    if(lock.current||!ready)return;lock.current=true;setBusy("解析中…");setError("");
    try{
      const display=plot();const base=resultRequest(design,fields,display);const chosenKind=operation==="association"?"scatter":operation==="distribution"?"distribution":figureKind==="scatter"?"distribution":figureKind;
      const spec={...base,plot:{...base.plot,kind:chosenKind}};
      await persist();
      if(sources.some(source=>(source.result.regionSet||target)!==regionSet))throw new Error("同じ領域の測定結果を選択してください。");
      let adopted=beforePrepare?await beforePrepare():selection;
      if(!beforePrepare){for(const source of sources)await adapter.selectRevision(workspace,source.revision,source.field);adopted=adapter.selection();}
      const revision=sources.length===1?sources[0].revision:await comparison.cohort(workspace,sources,fields,adopted);
      // For inferential requests the cohort persists the entered experimental metadata.
      if(operation!=="distribution"&&sources.length<2)throw new Error("統計解析には複数視野の測定結果と実験情報が必要です。");
      await comparison.review(revision,reviewed);
      const accepted=await post<{job_id:string}>(`/v1/revisions/${revision}/${operation==="distribution"?"descriptive":"common-statistics"}`,spec);
      await waitJob(accepted.job_id);
      const result=await request<ResultPayload>(`/v1/jobs/${accepted.job_id}/${operation==="distribution"?"result":"common-statistics"}`);
      if(result.revision_id!==revision)throw new Error("結果の解析版が一致しません。");
      setFigureKind(chosenKind);
      const created:Saved={job:accepted.job_id,revision,result,identity:JSON.stringify([target,sources.map(source=>[source.field,source.revision]),fields,adopted]),requestIdentity,plot:{...display,kind:chosenKind},figureJob:accepted.job_id,figure:result.figure,operation,sources:sources.map(source=>({field:source.field,label:source.label})),target:["nuclei","nucleoli","nucleoplasm","cell"].includes(regionSet)?regionSet as ReviewTarget:target};setSaved(created);setHistory(previous=>[created,...previous.filter(value=>value.job!==created.job)]);
    }catch(cause){setError(fail(cause));}finally{lock.current=false;setBusy("");}
  }
  async function render(downloadZip=false){
    if(lock.current||!saved||!canRender)return;lock.current=true;setBusy("図を更新中…");setError("");
    try{if(!saved.historical)await persist();const display={...plot(),kind:figureKind};const key=JSON.stringify([saved.job,display]);let rendered=renderCache.current.get(key);
      if(!rendered){let requestId=renderIds.current.get(key);if(!requestId){requestId=crypto.randomUUID();renderIds.current.set(key,requestId);}
        const accepted=await post<{job_id:string}>(`/v1/jobs/${saved.job}/figure-render`,{request_id:requestId,plot:{...display,y_min:display.y_min??null,y_max:display.y_max??null}});await waitJob(accepted.job_id);
        const output=await request<{source_job_id:string;figure:ResultPayload["figure"]}>(`/v1/jobs/${accepted.job_id}/figure-render`);
        if(output.source_job_id!==saved.job)throw new Error("図の元データが一致しません。");rendered={job:accepted.job_id,figure:output.figure};renderCache.current.set(key,rendered);}
      const updated={...saved,plot:display,figureJob:rendered.job,figure:rendered.figure};setSaved(updated);setHistory(previous=>[updated,...previous.filter(value=>value.figureJob!==updated.figureJob)]);
      if(downloadZip){setBusy("保存ファイルを作成中…");const exported=await post<{job_id:string}>(`/v1/revisions/${saved.revision}/export`,{});await waitJob(exported.job_id);const packaged=await post<{job_id:string}>(`/v1/jobs/${rendered.job}/publication-package`,{analysis_job_id:exported.job_id,request_id:crypto.randomUUID()});await waitJob(packaged.job_id);await download(`/v1/jobs/${packaged.job_id}/files/publication.zip`,"Cytellect-publication.zip");}
    }catch(cause){setError(fail(cause));}finally{lock.current=false;setBusy("");}
  }
  function editMetadata(id:string,key:keyof Metadata,value:string){setMetadata(previous=>({...previous,[id]:{...fields[id],[key]:value||null}}));setConfirmed(false);}
  function restoreFigure(selected:Saved){setSaved(selected);setFigureKind(selected.plot.kind);setWidth(selected.plot.width_inches*25.4);setHeight(selected.plot.height_inches*25.4);setFont(selected.plot.font_size);setXLabel(selected.plot.x_label);setYLabel(selected.plot.y_label);setYMin(selected.plot.y_min==null?"":String(selected.plot.y_min));setYMax(selected.plot.y_max==null?"":String(selected.plot.y_max));setPointSize(selected.plot.point_size??18);setColors(selected.plot.style?.series_colors||{});setLegend(selected.plot.style?.show_legend??true);setOrder(selected.plot.group_order);setXAxis({min:selected.plot.axes?.x_min==null?"":String(selected.plot.axes.x_min),max:selected.plot.axes?.x_max==null?"":String(selected.plot.axes.x_max),step:selected.plot.axes?.x_tick_step==null?"":String(selected.plot.axes.x_tick_step),scale:selected.plot.axes?.x_scale||"linear"});setYAxis({min:"",max:"",step:selected.plot.y_tick_step==null?"":String(selected.plot.y_tick_step),scale:selected.plot.axes?.y_scale||"linear"});}
  const shownTarget=saved?.historical?saved.target:target;const shownMetric=saved?.historical?(saved.result.metric||saved.result.y_source?.metric||saved.result.spec?.selection?.metric||""):metric;const shownChannel=saved?.historical?(saved.result.channel?.channel_id||saved.result.y_source?.channel?.channel_id||saved.result.spec?.selection?.channel_id||null):channel;
  const savedChannel=saved?.result.channel?.channel_id??saved?.result.y_source?.channel?.channel_id??saved?.result.spec?.selection?.channel_id??null;
  const tableRows=saved?.operation==="comparison"?saved.result.comparisons:saved?.operation==="association"?saved.result.associations:saved?.result.field_summary;
  const fieldLabels=Object.fromEntries([...(saved?.sources||[]).map((source,index)=>[source.field,source.label!==source.field?source.label:`視野 ${index+1}`]),...items.map(item=>[item.fieldId,item.label])]);

  if(csv)return <ConnectedCsvResults workspace={workspace} mode={mode} onImages={()=>setCsv(false)}/>;
  return <section className={styles.root} aria-label={mode==="figure"?"図の作成・保存":"測定結果の統計解析"}>
    <div className={styles.settings} onBlur={event=>{if(event.currentTarget.contains(event.relatedTarget))return;if(!busy&&!saved?.historical)void persist().catch(cause=>setError(fail(cause)));}}>
      <header><h2>{mode==="figure"?"グラフ":"統計解析"}</h2><span>{sources.length} 視野{excludedCount?` · 除外 ${excludedCount}`:""}</span></header>
      <button type="button" onClick={()=>setCsv(true)}>CSV の数値表を解析</button>
      <p className={styles.current}>{shownTarget==="nuclei"?"核":shownTarget==="nucleoli"?"核小体":shownTarget==="nucleoplasm"?"核質":shownTarget==="cell"?"細胞ROI":"保存した解析"} · {metricLabels[shownMetric]||shownMetric}{shownChannel?` · ${shownChannel}`:""}</p>
      {mode==="statistics"?<>
        {proposals.length>1&&<label>AIの解析案<select value={proposedIndex} disabled={!!busy} onChange={event=>selectProposal(Number(event.target.value))}>{proposals.map((value,index)=><option key={index} value={index}>{index+1} · {value.kind==="association"?"相関":value.kind==="comparison"?"群間比較":"分布"}</option>)}</select></label>}
        <label>解析<select value={operation} disabled={!!busy} onChange={event=>{setOperation(event.target.value as ResultOperation);setConfirmed(false);}}><option value="distribution">分布</option><option value="comparison">群間比較</option><option value="association">相関</option></select></label>
        {operation!=="distribution"&&<>
          <div className={styles.row}><label>方法<select value={rank?"rank":"parametric"} onChange={event=>setRank(event.target.value==="rank")}><option value="parametric">{operation==="association"?"Pearson":"t 検定 / Welch ANOVA"}</option><option value="rank">{operation==="association"?"Spearman":"順位に基づく検定"}</option></select></label>{operation==="comparison"&&<label>対応<select value={paired?"paired":"independent"} onChange={event=>{setPaired(event.target.value==="paired");setConfirmed(false);}}><option value="independent">独立した実験</option><option value="paired">対応あり</option></select></label>}</div>
          {operation==="association"&&<div className={styles.row}><label>横軸<select value={xMetric} onChange={event=>setXMetric(event.target.value)}>{["area_px","mean","median","integrated"].map(value=><option key={value} value={value}>{metricLabels[value]}</option>)}</select></label><label>横軸チャンネル<select value={xChannel||""} onChange={event=>setXChannel(event.target.value||null)}><option value="">選択</option>{channels.map(value=><option key={value}>{value}</option>)}</select></label></div>}

          <label>独立実験単位<input value={unit} maxLength={200} placeholder="例：別の日に独立に調製した培養" onChange={event=>{setUnit(event.target.value);setConfirmed(false);}}/></label>
          {paired&&operation==="comparison"&&<label>対応の根拠<input value={pairing} maxLength={200} onChange={event=>{setPairing(event.target.value);setConfirmed(false);}}/></label>}
          {operation==="comparison"&&<fieldset><legend>比較する群</legend>{pairs.length?pairs.map(pair=><label className={styles.check} key={JSON.stringify(pair)}><input type="checkbox" checked={contrasts.some(value=>JSON.stringify(value)===JSON.stringify(pair))} onChange={event=>setContrasts(previous=>event.target.checked?[...previous,pair]:previous.filter(value=>JSON.stringify(value)!==JSON.stringify(pair)))}/>{pair.join(" / ")}</label>):<p>実験情報に群名を入力してください。</p>}</fieldset>}
          <label className={styles.check}><input type="checkbox" checked={confirmed} onChange={event=>setConfirmed(event.target.checked)}/>独立実験単位、撮影・画素条件、採否と欠測の扱いを確認した</label>
        </>}
        <label className={styles.check}><input type="checkbox" checked={reviewed} onChange={event=>setReviewed(event.target.checked)}/>測定領域と採用する視野を確認した</label>
        <button className={styles.primary} disabled={!ready} onClick={()=>void calculate()}>{busy||"計算"}</button>
      </>:<>
        <nav className={styles.figureParts} aria-label="図の設定対象">{([["figure","図"],["x","横軸"],["y","縦軸"],["series","系列"]] as const).map(([key,label])=><button key={key} aria-pressed={part===key} onClick={()=>setPart(key)}>{label}</button>)}</nav>
        {part==="figure"&&<label>図の幅<select value={width===89?"89":width===183?"183":"custom"} onChange={event=>{if(event.target.value!=="custom"){setWidth(Number(event.target.value));setHeight(previous=>Math.min(previous,170));setFont(previous=>Math.min(previous,7));}}}><option value="89">1段幅 · 89 mm</option><option value="183">2段幅 · 183 mm</option><option value="custom">指定する</option></select></label>}
        {saved?.operation==="comparison"&&<label>図のレイアウト<select value={figureKind} onChange={event=>setFigureKind(event.target.value as RenderPlot["kind"])}><option value="distribution">点と分布</option><option value="box">箱ひげ図</option><option value="violin">バイオリン図</option><option value="histogram">ヒストグラム</option>{paired&&<option value="paired">対応する点を結ぶ</option>}</select></label>}
        {part==="x"&&<><label>横軸ラベル<input value={xLabel} maxLength={120} onChange={event=>setXLabel(event.target.value)}/></label><AxisControls axis="x" value={xAxis} onChange={setXAxis} numeric={(saved?.operation||operation)==="association"}/></>}
        {part==="y"&&<><label>縦軸ラベル<input value={yLabel} maxLength={120} onChange={event=>setYLabel(event.target.value)}/></label><AxisControls axis="y" value={{...yAxis,min:yMin,max:yMax}} onChange={value=>{setYAxis(value);setYMin(value.min);setYMax(value.max);}}/></>}
        {part==="figure"&&<><div className={styles.row}><label>幅 / mm<input type="number" min={76.2} max={406.4} value={width} onChange={event=>setWidth(Number(event.target.value))}/></label><label>高さ / mm<input type="number" min={25.4} max={170} value={height} onChange={event=>setHeight(Number(event.target.value))}/></label></div><label>文字 / pt<input type="number" min={5} max={24} value={font} onChange={event=>setFont(Number(event.target.value))}/></label><label className={styles.check}><input type="checkbox" checked={legend} onChange={event=>setLegend(event.target.checked)}/>凡例を表示</label></>}
        {part==="series"&&<><label>系列<select value={selectedSeries||series[0]||""} onChange={event=>setSelectedSeries(event.target.value)}>{(order.length?order:series).map(key=><option key={key} value={key}>{sources.find(source=>source.field===key)?.label||key}</option>)}</select></label><label>色<input type="color" value={colors[selectedSeries||series[0]]||"#0072b2"} onChange={event=>setColors(previous=>({...previous,[selectedSeries||series[0]]:event.target.value}))}/></label><label>点の大きさ<input type="number" min={1} max={400} value={pointSize} onChange={event=>setPointSize(Number(event.target.value))}/></label><div className={styles.row}>{[-1,1].map(direction=><button key={direction} onClick={()=>{const current=order.length?[...order]:[...series];const index=current.indexOf(selectedSeries||series[0]);if(index+direction<0||index+direction>=current.length)return;[current[index],current[index+direction]]=[current[index+direction],current[index]];setOrder(current);}}>{direction<0?"前へ":"後へ"}</button>)}</div>{operation==="distribution"&&<button onClick={()=>onSource(selectedSeries||series[0],undefined,saved?.revision,saved?.target,savedChannel)}>元の視野を表示</button>}</>}
        <button className={styles.primary} disabled={!canRender} onClick={()=>void render()}>{busy||"図を更新"}</button>
        {!saved&&<p>統計画面で計算すると、結果を使って図を編集できます。</p>}
      </>}
      {missing>0&&<><p role="status">{missing} 視野の測定が未完了です。</p>{onPrepareMissing&&<button disabled={!!busy||disabled} onClick={()=>{setBusy("必要な測定値を計算中…");void onPrepareMissing().catch(cause=>setError(fail(cause))).finally(()=>setBusy(""));}}>必要な測定値を計算</button>}</>}
      {stale&&<p role="status">測定結果または解析条件が変わりました。再計算してください。</p>}
      {error&&<p role="alert">{error}</p>}
      {saved&&<div className={styles.downloads}><button disabled={!!busy||stale} onClick={()=>void render(true)}>保存</button></div>}
    </div>
    <div className={styles.output} ref={outputRef}>
      {mode==="figure"&&history.length>0&&<label className={styles.figureHistory}>保存した図<select value={saved?.figureJob||""} onChange={event=>{const selected=history.find(value=>value.figureJob===event.target.value);if(selected)restoreFigure(selected);}}><option value="" disabled>図を選択</option>{history.map((entry,index)=><option key={entry.figureJob} value={entry.figureJob}>{entry.operation==="distribution"?"分布":entry.operation==="comparison"?"群間比較":"相関"} · {history.length-index}</option>)}</select></label>}
      {mode==="statistics"&&operation!=="distribution"&&(<details className={styles.metadata} open><summary>実験情報</summary><div className={styles.tableScroll}><table><thead><tr><th>視野</th>{["群","試料","独立実験単位","撮影日",...(paired&&operation==="comparison"?["対応ペア"]:[])].map(value=><th key={value}>{value}</th>)}</tr></thead><tbody>{sources.map(source=><tr key={source.field}><th><button onClick={()=>onSource(source.field)}>{source.label}</button></th>{(["condition","sample","experimental_unit","acquisition_date",...(paired&&operation==="comparison"?["pair"]:[])] as Array<keyof Metadata>).map(key=><td key={key}><input maxLength={80} aria-label={`${source.label} ${key}`} value={String(fields[source.field][key]??"")} onChange={event=>editMetadata(source.field,key,event.target.value)}/></td>)}</tr>)}</tbody></table></div></details>)}
      {saved?<>
        {svgFiles.map(file=>mode==="figure"?<EditableFigure key={`${saved.figureJob}:${file}`} path={`/v1/jobs/${saved.figureJob}/files/${encodeURIComponent(file)}`} onSelect={setPart} onSource={openPoint}/>:<VectorFigure key={`${saved.figureJob}:${file}`} path={`/v1/jobs/${saved.figureJob}/files/${encodeURIComponent(file)}`}/>)}
        {pointSource?.job===saved.figureJob&&pointRows.length>0&&<section aria-label="選択した点の試料・視野"><strong>この点の元データ</strong><button onClick={()=>setPointSource(null)} aria-label="点の元データを閉じる">×</button><SavedTable rows={pointRows} fieldLabels={fieldLabels} onSource={(field,region)=>onSource(field,region,saved.revision,saved.target,savedChannel)}/></section>}
        {!svgFiles.length&&<p>この設定では図を表示できません。測定表と出力条件を確認してください。</p>}
        {mode==="statistics"&&tableRows&&<SavedTable rows={tableRows} fieldLabels={fieldLabels} onSource={(field,region)=>onSource(field,region,saved.revision,saved.target,savedChannel)}/>}
        {mode==="statistics"&&saved.result.omnibus&&<p>全体検定 {String(saved.result.omnibus.method)} · p = {formatValue(saved.result.omnibus.p_value)}</p>}
        {mode==="statistics"&&Array.isArray(saved.result.counts)&&<SavedTable rows={saved.result.counts} fieldLabels={fieldLabels} onSource={(field,region)=>onSource(field,region,saved.revision,saved.target,savedChannel)}/>}
        {!!saved.result.warnings?.length&&<details><summary>解析上の注意</summary><ul>{saved.result.warnings.map(value=><li key={value}>{comparisonWarnings[value]||commonWarnings[value]||value}</li>)}</ul></details>}
        {!!saved.result.plot_data?.length&&<details><summary>図の元データ</summary><SavedTable rows={saved.result.plot_data} fieldLabels={fieldLabels} onSource={(field,region)=>onSource(field,region,saved.revision,saved.target,savedChannel)}/></details>}
        <details><summary>元の視野{saved.historical?"（保存時の解析版）":""}</summary>{(saved.sources||[]).map(source=><button key={source.field} onClick={()=>onSource(source.field,undefined,saved.revision,saved.target,savedChannel)}>{items.find(item=>item.fieldId===source.field)?.label||source.label}</button>)}</details>
      </>:<p className={styles.empty}>計算した結果とグラフをここに表示します。</p>}
    </div>
  </section>;
}

function VectorFigure({path}:{path:string}){const url=usePrivateImage(path);return url?<img className={styles.figure} src={url} alt="保存された解析結果のグラフ"/>:<p role="status">図を読み込み中…</p>;}
function SavedTable({rows,fieldLabels,onSource}:{rows:Record<string,unknown>[];fieldLabels:Record<string,string>;onSource:(fieldId:string,regionId?:number)=>void}) {
  const keys=[...new Set(rows.flatMap(row=>Object.keys(row)))];
  const names:Record<string,string>={field_id:"視野",region_id:"領域番号",nucleus_id:"親核番号",value:"測定値",condition:"群",input_rows:"入力領域数",excluded:"除外領域数",gate_unselected:"GFP選別の対象外数",missing_metric_selected:"採用対象の測定値欠測数",selected_rows:"採用領域数",mean:"平均値",median:"中央値",q1:"第1四分位",q3:"第3四分位",minimum:"最小値",maximum:"最大値",p_value:"p 値",p_adjusted:"補正 p 値",p_holm:"Holm補正 p 値",estimate:"推定値",coefficient:"相関係数",ci_low:"95% CI 下限",ci_high:"95% CI 上限",n:"対象数",missing_reason:"欠測理由",reason:"理由",group_a:"群 A",group_b:"群 B",observations:"採用領域数",input_fields:"入力視野数",selected_fields:"採用視野数",excluded_failed_fields:"除外した失敗視野数",samples:"試料数",input_units:"入力独立実験単位数",experimental_units:"採用独立実験単位数",explicitly_excluded_units:"除外独立実験単位数",complete_pairs:"完全ペア数",effect:"効果量",effect_name:"効果量の種類",method:"方法",scope:"対象",status:"状態"};
  const statuses:Record<string,string>={selected:"採用",no_regions:"領域なし",no_selected_values:"採用できる測定値なし",excluded:"除外",missing:"欠測"};
  return <div className={styles.tableScroll}><table><thead><tr>{keys.map(key=><th key={key} scope="col" style={{whiteSpace:"normal",overflowWrap:"anywhere",maxWidth:"8em"}}>{names[key]||key}</th>)}</tr></thead><tbody>{rows.map((row,index)=><tr key={index}>{keys.map(key=><td key={key}>{key==="field_id"&&typeof row[key]==="string"?<button style={{maxWidth:"14em",whiteSpace:"normal",overflowWrap:"anywhere"}} onClick={()=>onSource(row[key] as string,typeof row.region_id==="number"?row.region_id:undefined)}>{fieldLabels[row[key]]||`視野 ${index+1}`}</button>:key==="status"&&typeof row[key]==="string"?statuses[row[key]]||row[key]:row[key]!==null&&typeof row[key]==="object"?<span style={{whiteSpace:"normal",overflowWrap:"anywhere"}}>{JSON.stringify(row[key])}</span>:formatValue(row[key])}</td>)}</tr>)}</tbody></table></div>;
}
