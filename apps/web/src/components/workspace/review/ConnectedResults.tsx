"use client";

import {useEffect,useEffectEvent,useLayoutEffect,useMemo,useRef,useState,type ReactNode} from "react";
import {ApiError,download,errorCodeMessage,errorMessage,fetchBlob,post,request} from "@/lib/api";
import {formatValue,type Job} from "@/lib/types";
import {plainFigureLegend} from "@/lib/figure-legend";
import {usePrivateImage} from "@/lib/usePrivateImage";
import {comparisonWarnings} from "@/lib/region-comparison-view";
import {commonWarnings} from "@/lib/common-statistics";
import {descriptiveWarning} from "@/lib/descriptive-view";
import {createComparisonAdapter,descriptiveSupported,MISSING_POLICY,type CohortStratum,type CompartmentLedgerEntry,type Metadata,type ComparisonSource,type GfpSelectionChoice} from "@/lib/workspace/comparison-adapter";
import type {ApiAdapter,SavedResult,WorkspaceSelection} from "@/lib/workspace/api-adapter";
import type {ReviewTarget} from "@/lib/workspace/review-preview";
import {measureLabel,metricStructure,metricUsesChannel,nucleusPositivity} from "@/lib/workspace/metric-catalog";
import {OUTCOME_ROLE_LABELS,declaredAfterResults,outcomeRole,type OutcomeRole,type PrimaryOutcome} from "@/lib/workspace/primary-outcome";
import {associationAxes,associationSupported,checkedPlot,comparisonKind,exploratoryPositivity,saturatedGroups,emptyMetadata,restoredMetric,resultRequest,resultSeries,runTable,seriesOrder,withMaskCorrections,type MaskCorrectionRow,type ResultDesign,type ResultOperation,type RenderPlot} from "./connected-results-model";
import styles from "./connected-results.module.css";
import {ErrorText,useShowcaseUi} from "./showcase-ui";
import {METRIC_HINTS} from "../../../lib/showcase/terms";
import {DiscussionPanel} from "./DiscussionPanel";
import {showcaseNotices,type RecordedStatistic,type ShowcaseDataset} from "@/lib/showcase";
import {automaticOperation,sameMethod,savedMethod,choiceFilter,conditionChannel,conditionKey,savedCondition,savedFor,savedMeasureLabel,type ResultCondition,type SavedResultLike} from "./result-choice";
import {declarations as statisticsDeclarations,remainingWork,type RemainingWork} from "./statistics-readiness";
import {AxisControls,axisPlotOptions,emptyAxis,type AxisState} from "./AxisControls";
import {ConnectedCsvResults} from "./ConnectedCsvResults";
import {EditableFigure,type FigurePart,type FigureSource} from "./EditableFigure";
import type {components} from "@/lib/generated";
import {comparisonDefaults,fieldMetadata,isStratified,scopedIdentity,strataOf,stratumRequestFor,unassignedFieldCount,type ExperimentDesign} from "@/lib/workspace/experiment-design";
import {breakdown,formatNumber,summarize,tidy,type ComparisonEstimates,type ResultBasis,type CountRow,type FieldLedgerRow,type SavedComparison} from "@/lib/result-summary";
import {channelGateInputSignature,channelGateName,channelGateRequest,channelGateThresholds,recordedChannelGate,type ChannelGateFilter,type ChannelGateResult} from "@/lib/workspace/channel-gate";

export interface ConnectedResultItem {fieldId:string;label:string;result?:SavedResult;metadata?:Metadata;excluded?:boolean}
export interface ConnectedResultsProps {
  /** A request from the image's next step (MV-09) to judge the compared fields again by the saved rule, once. */
  reclassifyRequest?:number;
  adapter:ApiAdapter;workspace:string;selection:WorkspaceSelection|null;items:ConnectedResultItem[];
  target:ReviewTarget;metric:string;channel:string|null;mode:"statistics"|"figure";
  /** The saved two-group result in words and its figure, for the image view (requirements X-01). */
  /** `target` is the region set the values come from; `structure` is what they are checked on in the image. */
  onSource:(fieldId:string,regionId?:number,revisionId?:string,target?:ReviewTarget,channelId?:string|null,structure?:ReviewTarget)=>void;beforePrepare?:()=>Promise<WorkspaceSelection|null>;disabled?:boolean;
  gfp?:GfpSelectionChoice|null;
  channelGate?:ChannelGateFilter|null;
  initialSpec?:Pick<components["schemas"]["AnalysisSpec"],"statistics"|"figure"|"additional_analyses"|"figure_proposals"|"figure_presentation">;
  onSaveDraft?:(draft:{statistics?:unknown;figure?:unknown;additional_analyses?:unknown[];figure_proposals?:unknown[]})=>Promise<unknown>;
  onMetricChange?:(metric:string,channel:string|null)=>void;
  onAnalysisTargetChange?:(target:ReviewTarget)=>void;
  /** The view opened on the latest saved result: its metric and channel, for a view nobody has changed yet. */
  onOpening?:(metric:string,channel:string|null)=>void;
  /** False while the workspace shows the images: the results view is mounted but not on screen. */
  shown?:boolean;
  /** Counts the researcher's own measurements (the 「測定」 action), not previews. */
  measured?:number;
  /** A next step's request to compare the groups (MV-09): the analysis is the group comparison, whatever the saved specification held. */
  compareRequest?:number;
  /** The opening result's region, applied once the statistics view is shown (DM-04); defaults to onAnalysisTargetChange. */
  onOpeningTarget?:(target:ReviewTarget)=>void;
  onPrepareMissing?:()=>Promise<unknown>;
  /** The declared experiment design; its derived metadata replaces per-field typing (E-08). */
  experiment?:ExperimentDesign|null;
  /** Hash of the saved stratified design, from the API; a stratum's cohort is bound to it. */
  experimentSha256?:string|null;
  onEditExperiment?:()=>void;
  /** Opens 画像, where the fields a result waits for are measured and adopted (genellect/cytellect#257 decision 11). */
  onImages?:()=>void;
  /** Opens 統計, where a condition without a result is calculated (from グラフ). */
  onStatistics?:()=>void;
  /** The recorded stain name of a channel (「5-EU」), for the name of a measure. */
  stainName?:(channelId:string)=>string;
  /** In the demo, the statistics its tour recorded for the scene; null elsewhere (every choice can be calculated). */
  recorded?:RecordedStatistic[]|null;
  /** The primary measure declared before results (#257 RP-04); results show 主要 or 探索 only when one exists. */
  primary?:PrimaryOutcome|null;
}
interface SavedSource {field_id:string;region_set?:{region_set_id:string};metadata?:{condition?:string}}
interface SavedChannel {channel_id:string;label?:string;stain?:string|null}
interface SavedRegion {region_set_id?:string;label?:string}
interface SavedSelection {metric?:string;channel_id?:string|null;source?:string;region_set_id?:string}
interface ResultPayload {stratum?:{label:string;levels:Array<{factor:string;level:string}>;declared_stratum_count?:number;field_ids:string[];analysed_field_ids:string[];excluded_fields:Array<{field_id:string;reason:string|null}>};selection?:{channel_gate?:{channel?:{channel_id:string;label?:string;stain?:string|null}}};revision_id:string;analysis_kind?:string;source_kind?:string;source_job_id?:string;source_fields?:SavedSource[];x_source?:{source_fields?:SavedSource[];metric?:string;channel?:SavedChannel|null;region?:SavedRegion|null};y_source?:{source_fields?:SavedSource[];metric?:string;channel?:SavedChannel|null;region?:SavedRegion|null;plot_data?:Record<string,unknown>[]};figure:{source_files:string[];status?:string;forms?:FigureForm[];presentation?:Presentation;legend_gaps?:string[];style?:{width_mm?:number};compositions?:Composition[]};metric?:string;channel?:SavedChannel|null;region?:SavedRegion|null;spec?:{plot?:Record<string,unknown>;conditions?:string[];test?:string;design?:{kind?:string};selection?:{metric:string;channel_id?:string|null;source?:string;region_set_id?:string;positivity?:{channel_id?:string;gfp_channel_id?:string}|null};x_selection?:SavedSelection;y_selection?:SavedSelection};field_summary?:Record<string,unknown>[];comparisons?:Record<string,unknown>[];associations?:Record<string,unknown>[];counts?:unknown;omnibus?:Record<string,unknown>|null;warnings?:string[];plot_data?:Record<string,unknown>[];estimates?:ComparisonEstimates|null;unit?:string;source_field_ledger?:FieldLedgerRow[];compartment_missing?:MissingSummary|null;mask_corrections?:{fields:MaskCorrectionRow[]}|null}
type MissingSummary=components["schemas"]["CompartmentMissingSummary"];
/** A form the saved result supports (common-statistics figure 2.0.0), as the analysis package lists it (FQ-02). */
interface FigureForm {id:string;kind:RenderPlot["kind"];observations?:Observations}
type Observations="points"|"violin"|"box"|"none";
type FigureSize="panel"|"single-column"|"double-column"|"custom";
type Composition="quantification"|"images-quantification";
interface Presentation {version:"1.0.0";observations?:Observations|null;color_by?:"run"|"group"|null;annotation?:"value"|"stars"|"none";size?:FigureSize;composition?:Composition;image_fields?:Record<string,string>;outlines?:boolean}
/** Field-standard names for the forms and sizes (UC-01). */
const formNames:Record<string,string>={points:"全データ点",density:"分布（バイオリン）",box:"箱ひげ",bar:"平均の棒",
  "run-box":"実験回の箱ひげ","run-violin":"実験回のバイオリン","run-histogram":"実験回のヒストグラム","run-paired":"実験回の対応",scatter:"散布図"};
const sizeNames:Record<FigureSize,string>={panel:"パネル","single-column":"1段幅 · 89 mm","double-column":"2段幅 · 183 mm",custom:"カスタム"};
interface Saved {job:string;revision:string;result:ResultPayload;identity:string;requestIdentity:string;plot:RenderPlot;figureJob:string;figure:ResultPayload["figure"];operation:ResultOperation;sources?:Array<{field:string;label:string}>;historical?:boolean;target?:ReviewTarget;created?:number;
  /** Server time of the statistics (never of a re-drawn figure); null when not recorded. */
  calculated?:number|null}
/** Saved units are the analysis package's (English, for figures); the result text names them in Japanese. */
const unitLabels:Record<string,string>={"nuclei per field":"個／視野","nuclei per mm²":"個／mm²","positive nuclei per field":"個／視野","fraction of evaluable nuclei":"",dimensionless:"",count:""};
const unitLabel=(unit?:string|null)=>unit?unitLabels[unit]??unit:"";
const metricLabels:Record<string,string>={area_px:"面積 / px²",area_um2:"面積 / µm²",mean:"平均輝度",median:"中央値",integrated:"積算輝度",mean_corrected:"平均輝度（背景補正）",integrated_corrected:"積算輝度（背景補正）",nucleolar_count:"核小体数",nucleolar_area_fraction:"核小体面積割合",log2_nucleoplasm_over_nucleolus:"核質／核小体 log₂ 比",positive_count:"視野あたりの陽性核数",positive_fraction:"陽性率",nucleus_count:"視野あたりの核数",nucleus_density_per_mm2:"核の密度（mm² あたり）",nucleolar_area_px:"核小体の総面積 / px²",nucleolar_area_um2:"核小体の総面積 / µm²",nucleolar_eccentricity:"核小体の離心率",largest_nucleolus_fraction:"最大の核小体の割合",solidity:"核のソリディティ",axis_ratio:"核の長短軸比",eccentricity:"核の離心率"};
const regionNames:Record<string,string>={nuclei:"核",nucleoli:"核小体",nucleoplasm:"核質",cell:"細胞ROI"};
/** The region a metric is checked on: a per-nucleus value of the nucleoli comes from the nucleoplasm set
 * but reads 「核小体（核ごとの値）」, as the image shows it (V-04, X-01). */
/** The region a saved result measured: its selection's region set, else its sources'. */
function savedRegion(result:ResultPayload):ReviewTarget|undefined{const id=result.spec?.selection?.region_set_id||resultSources(result)[0]?.region_set?.region_set_id||"";return id in regionNames?id as ReviewTarget:undefined;}
/** A per-region metric names its region and channel (「核小体の平均輝度（eu5）」); summaries name their own. */
/** One name for a saved result's measure (#257 B-3), by its recorded stain; a channel recorded without one is named by `stain`. */
function resultMetricLabel(result:ResultPayload,metric:string,stain:(id:string)=>string=id=>id){
  const operation=result.analysis_kind==="region-association"?"association":"comparison";
  const named=(channel:SavedChannel|null|undefined)=>channel&&!channel.stain?{...channel,stain:stain(channel.channel_id)}:channel;
  const value={...result,channel:named(result.channel),y_source:result.y_source&&{...result.y_source,channel:named(result.y_source.channel)}} as SavedResultLike;
  return savedCondition(operation,value)?savedMeasureLabel(operation,value):metricLabels[metric]||metric;
}
const analysisNames:Record<ResultOperation,string>={comparison:"群間比較",association:"相関",distribution:"分布"};
/** A saved figure by what it shows (FU-09): the measure, the analysis, the form and when it was drawn. */
/** A measure by its region and stain when it is measured per region (「核質の平均輝度（5-EU）」); a summary
 *  (「核小体の離心率」, 核数) names itself, as resultMetricLabel does. */
function measureName(selection:SavedSelection|undefined,channel:SavedChannel|null|undefined,metric:string){
  const label=metricLabels[metric]||metric;
  if(selection?.source!=="region")return label;
  const region=regionNames[selection.region_set_id||""],stain=channel?.stain||channel?.label||channel?.channel_id||selection.channel_id;
  return `${region?`${region}の`:""}${label}${stain?`（${stain}）`:""}`;
}
function savedFigureName(entry:Saved){
  const metric=entry.result.spec?.selection?.metric??entry.result.estimates?.metric??entry.result.metric??"";
  // Each measure by its region, metric and stain (the channel's stain, not its identifier).
  const spec=entry.result.spec;
  const axes:Array<[SavedSelection|undefined,{metric?:string;channel?:SavedChannel|null}|undefined]>=[[spec?.x_selection,entry.result.x_source],[spec?.y_selection,entry.result.y_source]];
  const measure=entry.operation==="association"?axes.map(([selection,source])=>measureName(selection,source?.channel,selection?.metric??source?.metric??"")).join(" × ")
    :nucleusPositivity(metric)?resultMetricLabel(entry.result,metric):measureName(spec?.selection,entry.result.channel,metric);
  const observations=entry.plot.presentation?.observations??entry.figure.presentation?.observations??"points";
  const form=(entry.figure.forms||[]).find(value=>value.kind===entry.plot.kind&&(value.kind!=="superplot"||(value.observations??"points")===observations));
  const when=entry.created?new Date(entry.created*1000).toLocaleString("ja-JP",{month:"numeric",day:"numeric",hour:"2-digit",minute:"2-digit"}):"";
  return [measure,analysisNames[entry.operation],form&&entry.operation==="comparison"?formNames[form.id]:"",when].filter(Boolean).join(" · ");
}
const resultSources=(result:ResultPayload):SavedSource[]=>result.source_fields||result.x_source?.source_fields||result.y_source?.source_fields||[];
const fail=(error:unknown)=>error instanceof ApiError?errorMessage(error):error instanceof Error?errorCodeMessage(error.message):"処理を完了できませんでした。";

/** Source-bound statistics and saved-result rendering. No statistical values are computed in React. */
export function ConnectedResults(props:ConnectedResultsProps) {
  return <WorkspaceResults key={props.workspace} {...props}/>;
}

function WorkspaceResults({adapter,workspace,selection,items:allItems,target,metric,channel,mode,shown=true,measured=0,compareRequest=0,onOpening,onOpeningTarget,onSource,beforePrepare,disabled=false,gfp=null,channelGate=null,initialSpec,onSaveDraft,onMetricChange,onAnalysisTargetChange,onPrepareMissing,experiment=null,experimentSha256=null,onEditExperiment,onImages,onStatistics,reclassifyRequest=0,stainName=(id:string)=>id,recorded:recordedStatistics=null,primary=null}:ConnectedResultsProps) {
  const showcaseUi=useShowcaseUi(),demo=showcaseUi.enabled,showcaseDataset=showcaseUi.dataset,openedSaved=useRef(false);
  const derived=useMemo(()=>experiment?fieldMetadata(experiment):{},[experiment]);
  // A stratified design (1.1.0) is read one declared stratum at a time: only that stratum's fields enter,
  // and the API refuses a cohort, description or comparison that pools strata.
  const strata=useMemo(()=>strataOf(experiment),[experiment]);
  const [stratumChoice,setStratumChoice]=useState("");
  const stratum=strata.find(value=>value.id===stratumChoice)??null;
  const stratifiedDesign=isStratified(experiment);
  const items=stratifiedDesign?allItems.filter(item=>!!stratum?.fieldIds.includes(item.fieldId)):allItems;
  const stratumRequestRef=useRef<CohortStratum|null>(null);
  // A field without a stratum is assigned or excluded with a reason before any stratum is analysed (the API refuses otherwise).
  const unstratified=unassignedFieldCount(experiment,allItems);
  const stratumRequest:CohortStratum|null=stratum?stratumRequestFor(experiment,experimentSha256,stratum.id):null;
  useLayoutEffect(()=>{stratumRequestRef.current=stratumRequest;});
  const comparison=useMemo(()=>createComparisonAdapter(),[]);
  const [csv,setCsv]=useState(false);
  const [operation,setOperation]=useState<ResultOperation>("distribution");
  const [proposedIndex,setProposedIndex]=useState(0);
  const proposals=[initialSpec?.statistics?.method,...(initialSpec?.additional_analyses??[])].filter((value):value is NonNullable<typeof value>=>!!value);
  const invalidMethod=(value:typeof proposals[number]|undefined)=>!!value&&value.kind==="association"&&!!(value.x||value.y)&&(!value.x?.region||!value.y?.region||value.x.region!==value.y.region);
  const invalidSaved=proposals.some(invalidMethod);
  const selectedProposal=proposals[proposedIndex];
  const unsupportedAxes=operation==="association"&&invalidMethod(selectedProposal);
  const displayMetric=(value:string)=>({area:"area_px",mean_raw:"mean",integral_raw:"integrated",integral_corrected:"integrated_corrected",ncl_log2_nucleoplasm_over_nucleoli:"log2_nucleoplasm_over_nucleolus"}[value]??value);
  function selectProposal(index:number){const method=proposals[index];if(!method)return;setProposedIndex(index);compareWanted.current=false;setOperation(method.kind==="descriptive"?"distribution":method.kind);setRank(["mann-whitney-u","wilcoxon"].includes(method.test||"")||method.association==="spearman");setPaired(["paired-t","wilcoxon"].includes(method.test||""));setTypedConfirmed(false);
    const figure=initialSpec?.figure_proposals?.find(value=>value.analysis_index===index),axis=method.y??figure;
    if(axis){onMetricChange?.(displayMetric(axis.metric),axis.channel??null);const region=axis.region;onAnalysisTargetChange?.(region==="nucleus"?"nuclei":region==="supplied"?"cell":region==="nucleoli"||region==="nucleoplasm"?region:target);}
    if(method.x){setXMetric(displayMetric(method.x.metric));setXChannel(method.x.channel??null);}
  }
  const [metadata,setMetadata]=useState<Record<string,Metadata>>({});
  const [paired,setPaired]=useState(false),[rank,setRank]=useState(false),[unit,setUnit]=useState(""),[pairing,setPairing]=useState("");
  // A workspace without a declared design keeps the confirmation of its typed groups, units and acquisition in 統計
  // (owner decision on #273, 2026-11-21); a declared design is confirmed in 実験 (decision 11).
  const [typedConfirmed,setTypedConfirmed]=useState(false);
  const [contrasts,setContrasts]=useState<string[][]>([]);
  const [xMetric,setXMetric]=useState("area_px"),[xChannel,setXChannel]=useState<string|null>(channel);
  // A size left unchosen follows the page: a distribution keeps 183 × 100 mm, a publication figure's custom size starts at 89 × 60 mm.
  const [chosenWidth,setWidth]=useState<number|null>(null),[chosenHeight,setHeight]=useState<number|null>(null),[font,setFont]=useState(7);
  // The publication figure's presentation; a choice left empty follows the saved result (plan FS, FQ, FA).
  const [size,setSize]=useState<FigureSize>("panel"),[annotation,setAnnotation]=useState<NonNullable<Presentation["annotation"]>>("value");
  const [observations,setObservations]=useState<Observations|null>(null),[colorBy,setColorBy]=useState<"run"|"group"|null>(null);
  const [composition,setComposition]=useState<Composition>("quantification"),[imageFields,setImageFields]=useState<Record<string,string>>({}),[outlines,setOutlines]=useState(true);
  // A figure saved without a presentation (before the publication figure) keeps its own width and height.
  function restorePresentation(value:unknown){const p=(value||{}) as Presentation;setSize(p.size||(value?"panel":"custom"));setAnnotation(p.annotation||"value");setObservations(p.observations??null);setColorBy(p.color_by??null);setComposition(p.composition||"quantification");setImageFields(p.image_fields||{});setOutlines(p.outlines??true);}
  const [xLabel,setXLabel]=useState(""),[yLabel,setYLabel]=useState(""),[yMin,setYMin]=useState(""),[yMax,setYMax]=useState("");
  const [xAxis,setXAxis]=useState<AxisState>(emptyAxis),[yAxis,setYAxis]=useState<AxisState>(emptyAxis);
  const outputRef=useRef<HTMLDivElement>(null),scrollPositions=useRef<Record<string,number>>({});
  useLayoutEffect(()=>{const element=outputRef.current,positions=scrollPositions.current;if(!element)return;element.scrollTop=positions[mode]??0;return()=>{positions[mode]=element.scrollTop;};},[mode,csv]);
  const [figureKind,setFigureKind]=useState<RenderPlot["kind"]>("distribution");
  const [part,setPart]=useState<FigurePart>("figure"),[colors,setColors]=useState<Record<string,string>>({}),[legend,setLegend]=useState(true),[pointSize,setPointSize]=useState<number|null>(null),[order,setOrder]=useState<string[]>([]);
  const [history,setHistory]=useState<Saved[]>([]),[historyLoaded,setHistoryLoaded]=useState(false);
  // One entry per saved result, with its latest figure: a setting redrawn on its own is not another saved figure.
  const savedResults=history.filter((entry,index)=>history.findIndex(other=>other.job===entry.job)===index);
  const receivedSpec=useRef(""),savedDraft=useRef(""),skipOwnSpec=useRef(false);
  const [selectedSeries,setSelectedSeries]=useState("");
  const [pointSource,setPointSource]=useState<{job:string;source:FigureSource}|null>(null);
  const [saved,setSaved]=useState<Saved|null>(null),[busy,setBusy]=useState(""),[error,setError]=useState("");
  const pageSize=(page:ResultOperation)=>page==="distribution"?{width:183,height:100}:{width:89,height:60};
  const width=chosenWidth??pageSize(saved?saved.operation:operation).width,height=chosenHeight??pageSize(saved?saved.operation:operation).height;
  const [recordedGate,setRecordedGate]=useState<{identity:string;revision:string;filter:ChannelGateFilter;result:ChannelGateResult}|null>(null);
  const [rawExport,setRawExport]=useState<{revision:string;included:boolean}|null>(null);
  const includeRaw=!!saved&&rawExport?.revision===saved.revision&&rawExport.included;
  const lock=useRef(false),renderCache=useRef(new Map<string,{job:string;figure:ResultPayload["figure"]}>()),renderIds=useRef(new Map<string,string>());
  useEffect(()=>{if(!workspace)return;let live=true;void request<Job[]>(`/v1/workspaces/${workspace}/jobs`).then(async jobs=>{
    // Newest first, one entry per result: a result redrawn many times does not push the others out.
    const completed=jobs.filter(job=>job.state==="succeeded"&&(job.kind==="statistics"||job.kind==="figure-render")).sort((a,b)=>b.created-a.created).slice(0,200);
    const load=async(job:Job):Promise<Saved|null>=>{try{const result=await request<ResultPayload>(`/v1/jobs/${job.id}/result`);if(result.source_kind!=="region-2d"||!result.figure)return null;const entry:Saved={job:result.source_job_id||job.id,revision:result.revision_id,result,identity:"history",requestIdentity:"history",plot:{...checkedPlot(183,100,7,"","","",""),...result.spec?.plot} as RenderPlot,figureJob:job.id,figure:result.figure,operation:result.analysis_kind==="region-comparison"?"comparison":result.analysis_kind==="region-association"?"association":"distribution",sources:resultSources(result).map(field=>({field:field.field_id,label:field.field_id})),historical:true,target:savedRegion(result),created:job.created,calculated:job.calculated_at??null};return entry;}catch{return null;}};
    const records:Saved[]=[];
    for(let start=0;start<completed.length&&records.length<40&&live;start+=20){
      for(const entry of await Promise.all(completed.slice(start,start+20).map(load)))if(entry&&records.length<40&&!records.some(value=>value.job===entry.job))records.push(entry);
    }
    if(live){setHistory(previous=>[...previous,...records.filter(value=>!previous.some(old=>old.figureJob===value.figureJob||old.job===value.job))]);setHistoryLoaded(true);}
  }).catch(()=>{if(live)setHistoryLoaded(true);});return()=>{live=false;};},[workspace]);
  const sources:ComparisonSource[]=items.flatMap(item=>item.result&&!item.excluded?[{field:item.fieldId,revision:item.result.revision,label:item.label,result:item.result,metadata:derived[item.fieldId]??metadata[item.fieldId]??item.metadata??emptyMetadata}]:[]);
  const fields=Object.fromEntries(sources.map(source=>[source.field,source.metadata]));
  const regionSet=sources[0]?.result.regionSet||target;
  // Every identity carries the saved design hash and the chosen stratum: a new stratum, a changed
  // assignment or another design makes the earlier classification, cohort and result stale.
  const gateIdentity=scopedIdentity(channelGateInputSignature(workspace,target,sources,fields,channelGate),stratumRequest);
  const gateCurrent=useRef(gateIdentity);
  useLayoutEffect(()=>{gateCurrent.current=gateIdentity;return()=>{gateCurrent.current="";};},[gateIdentity]);
  const currentGate=recordedGate?.identity===gateIdentity?recordedGate:null;
  const positivityMissing=metric.startsWith("positive_")&&!channelGate;
  // Nuclei whose nucleolus could not be established (Q-05) stay as missing instead of stopping the statistics: the
  // ledger read here is sent as it is with the calculation, and the result counts them in its n (decision 11).
  const compartment=regionSet==="nucleoli"||regionSet==="nucleoplasm";
  const ledgerKey=compartment?JSON.stringify(sources.map(source=>[source.field,source.revision])):"";
  const [ledger,setLedger]=useState<{key:string;fields:Record<string,CompartmentLedgerEntry>;error:string}|null>(null);
  useEffect(()=>{if(!ledgerKey)return;let live=true;
    void Promise.all(sources.map(source=>comparison.compartmentLedger(source.revision,source.field)))
      .then(values=>{if(live)setLedger({key:ledgerKey,fields:Object.assign({},...values),error:""});})
      .catch(cause=>{if(live)setLedger({key:ledgerKey,fields:{},error:fail(cause)});});
    return()=>{live=false;};},[ledgerKey]);// eslint-disable-line react-hooks/exhaustive-deps
  const currentLedger=ledger?.key===ledgerKey?ledger:null;
  const unresolvedFields=Object.fromEntries(Object.entries(currentLedger?.fields??{}).filter(([,entry])=>Object.keys(entry.missing).length>0).map(([fid,entry])=>[fid,entry.missing]));
  const unresolved=Object.keys(unresolvedFields).length>0;
  const ledgerReady=!compartment||(!!currentLedger&&!currentLedger.error);
  // A result answers the measurements and metadata it was calculated from; the adoption record's own version is not
  // part of it (calculating another region writes that record again).
  const resultIdentity=(chosen:typeof sources,metadata:typeof fields,scope:typeof stratumRequest)=>scopedIdentity(JSON.stringify([chosen.map(source=>[source.field,source.revision]),metadata]),scope);
  const identity=resultIdentity(sources,fields,stratumRequest);
  const conditions=[...new Set(Object.entries(fields).filter(([fid])=>!(channelGate?.control_field_ids??[]).includes(fid)).map(([,value])=>value.condition?.trim()).filter((value):value is string=>!!value))];
  const declared=experiment?.layout==="pair"&&experiment.control_group_id?comparisonDefaults(experiment):null;
  // The declared pair reads treatment − control; other pairs keep the order the groups appear in.
  const pairs=conditions.flatMap((a,index)=>conditions.slice(index+1).map(b=>declared&&new Set([a,b,declared.control,declared.treatment]).size===2?declared.contrasts[0]:[a,b]));
  const channels=[...new Set(sources.flatMap(source=>source.result.rows.map(row=>row.channel_id)))];
  // Only choices the calculation accepts are offered: an association needs two different region measurements.
  // Groups with saturated brightness are not analysed. With a GFP filter the analysed nuclei are not
  // known here, so the API decides.
  const saturatedIn=(value:string,stain:string|null)=>gfp||channelGate?new Set<string>():saturatedGroups(sources,fields,value,stain);
  const saturatedSet=saturatedIn(metric,channel),saturatedKey=[...saturatedSet].sort().join("\n");
  const unsaturatedPair=(pair:string[])=>pair.every(value=>!saturatedSet.has(value));
  const saturated=saturatedSet.size>0&&!pairs.some(unsaturatedPair);
  // The horizontal axis needs a stain for brightness; one without saturated pixels is offered first.
  const xStain=channels.find(value=>value===xChannel&&!saturatedIn("mean",value).size)??channels.find(value=>!saturatedIn("mean",value).size)??null;
  const xAxes=associationAxes(metric,channel,xStain).filter(value=>value.startsWith("area_")||!!xStain);
  const canAssociate=associationSupported({regionSet,metric,channel,gfp,channelGate})&&!saturatedSet.size&&xAxes.length>0;
  // Unconfirmed independence (E-05): no association test; a comparison stays descriptive (test "none").
  const unconfirmed=!!experiment&&!experiment.independence_confirmed;
  // A threshold without a negative control is exploratory: positive counts and fractions are described, not tested.
  const exploratory=exploratoryPositivity(metric,channelGate);
  // An analysis the measure or the design cannot have is changed, and the researcher reads why (SR-04). Two or more
  // groups are compared: the distribution is the analysis of a design without a comparison (owner decision 15).
  const comparable=conditions.length>=2;
  const measureKey=JSON.stringify([regionSet,metric,channel]);
  const [switched,setSwitched]=useState<{reason:string;key:string}|null>(null);
  useEffect(()=>{
    // An analysis can change twice (相関 → 分布 → 群間比較): the view goes to the last one and says the first reason.
    let next=operation,reason="";
    for(let step=0;step<3;step++){const change=automaticOperation({operation:next,comparable,canAssociate,unconfirmed,saturated,saturatedAny:saturatedSet.size>0,descriptive:descriptiveSupported(metric)});
      if(!change)break;next=change.operation;reason||=change.reason;}
    if(next===operation)return;setOperation(next);setSwitched(reason?{reason,key:measureKey}:null);},[operation,comparable,canAssociate,saturated,unconfirmed,metric]);// eslint-disable-line react-hooks/exhaustive-deps
  useEffect(()=>{if(saturatedKey&&contrasts.some(pair=>!unsaturatedPair(pair)))setContrasts(previous=>previous.filter(unsaturatedPair));},[saturatedKey,contrasts]);// eslint-disable-line react-hooks/exhaustive-deps
  useEffect(()=>{if(xAxes.length&&!xAxes.includes(xMetric))setXMetric(xAxes[0]);},[xAxes.join(),xMetric]);// eslint-disable-line react-hooks/exhaustive-deps
  useEffect(()=>{if(xStain!==xChannel)setXChannel(xStain);},[xStain,xChannel]);
  // Fields included in the comparison without an adopted measurement of this region (画像's work, not done yet).
  const missing=items.filter(item=>!item.excluded&&!item.result).length;
  // 統計 asks for no confirmation (genellect/cytellect#257 decision 11): what a request states comes from 画像 and 実験.
  const stated=statisticsDeclarations({demo,experiment,unmeasured:missing,typedConfirmed});
  // A comparison or an association states its design: declared in 実験, or confirmed here for typed groups.
  const designStated=demo||operation==="distribution"||!!experiment||typedConfirmed;
  const remaining=remainingWork({demo,experiment,unmeasured:missing,operation});
  const openRemaining=(work:RemainingWork)=>{(work.screen==="image"?onImages:onEditExperiment)?.();};
  // A described comparison of a design that can be tested waits for 計算 (D-5); its basis says so, not "unconfirmed".
  const testable=!demo&&operation==="comparison"&&(experiment?!!experiment.independence_confirmed:typedConfirmed)&&!exploratory;
  const design:ResultDesign={operation,metric,channel,regionSet,paired,rank,unit,pairing,independence:stated.independence,acquisition:stated.acquisition,sampling:stated.sampling,missingness:stated.missingness,contrasts,xMetric,xChannel,gfp,channelGate:currentGate?.filter??channelGate,estimates:!!experiment&&experiment.layout==="pair",inference:!unconfirmed&&!exploratory};
  // A declared two-group design compares the same runs as pairs, treatment − control (T-01).
  const designDefaults=declared;
  const independenceMissing=unconfirmed&&operation==="association";
  const needsDates=operation!=="distribution"&&(metricUsesChannel(metric)||(operation==="association"&&metricUsesChannel(xMetric))||(!!channelGate&&channelGate.method!=="manual")||metric.startsWith("positive_"));
  const datesMissing=!!experiment&&needsDates&&sources.some(source=>source.field in derived&&!source.metadata.acquisition_date?.trim());
  // A changed control (a new declared contrast) replaces the earlier contrast, so the direction shown is the one computed (S-04).
  const declaredContrast=useRef(designDefaults?.contrasts.join("\n"));
  useEffect(()=>{if(operation!=="comparison"||!designDefaults)return;const changed=declaredContrast.current!==designDefaults.contrasts.join("\n");declaredContrast.current=designDefaults.contrasts.join("\n");if(contrasts.length&&!changed)return;setPaired(true);setContrasts(designDefaults.contrasts);
    if(!unit.trim())setUnit("独立に行った実験回（別々に播種・処理・染色した実験日）");if(!pairing.trim())setPairing("同じ実験回の対照と処理");},[operation,designDefaults?.contrasts.join("\n")]);// eslint-disable-line react-hooks/exhaustive-deps
  useEffect(()=>{
    if(!initialSpec)return;const key=JSON.stringify(initialSpec);if(receivedSpec.current===key)return;receivedSpec.current=key;
    if(skipOwnSpec.current){skipOwnSpec.current=false;return;}
    const stat=initialSpec.statistics,figure=initialSpec.figure;
    // A saved specification changes for many reasons (settings, measurement policy): only a changed statistics part
    // replaces the analysis, so a measurement or a background setting never brings back an earlier metric (DM-04).
    const statKey=JSON.stringify(stat??null),statChanged=receivedStatistics.current!==statKey,firstLook=receivedStatistics.current===null;receivedStatistics.current=statKey;
    // The specification the workspace opens with sets the opening metric, under the same first-look rule as the opening
    // result (DM-04): it is not applied after a measurement, and a later measurement of another region replaces it.
    const chooseMetric=(value:string,stain:string|null)=>{if(!firstLook)onMetricChange?.(value,stain);else if(!measured)onOpening?.(value,stain);};
    if(stat?.method&&statChanged){const compare=compareWanted.current;compareWanted.current=false;appliedStatistics.current=true;setOperation(compare?"comparison":stat.method.kind==="descriptive"?"distribution":stat.method.kind);setPaired(stat.design==="paired");setRank(["mann-whitney-u","wilcoxon"].includes(stat.method.test||"")||stat.method.association==="spearman");setUnit(stat.unit_definition);setPairing(stat.pairing_basis);setContrasts(stat.comparisons||[]);setMetadata(stat.field_metadata||{});setTypedConfirmed(false);
      const restored=restoredMetric(stat);if(restored)chooseMetric(restored,stat.channel_id??null);
      const sx=stat as typeof stat & {x_metric?:string|null;x_channel_id?:string|null};if(stat.method.y)chooseMetric(displayMetric(stat.method.y.metric),stat.method.y.channel??null);if(stat.method.x){setXMetric(displayMetric(stat.method.x.metric));setXChannel(stat.method.x.channel??null);}else if(sx.x_metric){setXMetric(sx.x_metric);setXChannel(sx.x_channel_id??null);}
    }
    const proposed=initialSpec.figure_presentation;
    if(proposed&&!(figure?.plot as {presentation?:Presentation}|undefined)?.presentation?.composition)setComposition(proposed.composition);
    if(figure?.plot){const p=figure.plot as typeof figure.plot & {style?:RenderPlot["style"];axes?:RenderPlot["axes"]};setFigureKind(p.kind);setWidth(p.width_inches*25.4);setHeight(p.height_inches*25.4);setFont(p.font_size);setXLabel(p.x_label);setYLabel(p.y_label);setYMin(p.y_min==null?"":String(p.y_min));setYMax(p.y_max==null?"":String(p.y_max));setColors(p.style?.series_colors||{});setLegend(p.style?.show_legend??true);setPointSize(p.point_size??null);restorePresentation((p as {presentation?:unknown}).presentation);setOrder(p.group_order||[]);setXAxis({min:p.axes?.x_min==null?"":String(p.axes.x_min),max:p.axes?.x_max==null?"":String(p.axes.x_max),step:p.axes?.x_tick_step==null?"":String(p.axes.x_tick_step),scale:p.axes?.x_scale||"linear"});setYAxis({min:"",max:"",step:p.y_tick_step==null?"":String(p.y_tick_step),scale:p.axes?.y_scale||"linear"});}
  },[initialSpec,onMetricChange]);// eslint-disable-line react-hooks/exhaustive-deps -- measured and onOpening are read for the first look only
  // The request parts that change a result: the horizontal axis only for an association, and not the declarations (a
  // result calculated once they were given stays an answer when one is withdrawn). A description and a test of the same
  // choice answer it alike (the test is 計算 on the described result, D-5), but a tested result no longer answers a
  // design that cannot be tested (independence withdrawn, an exploratory threshold).
  const requestIdentity=JSON.stringify({...design,independence:undefined,acquisition:undefined,sampling:undefined,missingness:undefined,inference:undefined,...(operation==="association"?{}:{xMetric:undefined,xChannel:undefined})});
  // An association is always a test; a comparison is one unless it was described (test "none").
  const tested=(entry:Saved)=>entry.operation==="association"||entry.operation==="comparison"&&!!entry.result.spec?.test&&entry.result.spec.test!=="none";
  const stale=!!saved&&!saved.historical&&(saved.identity!==identity||saved.requestIdentity!==requestIdentity||(design.inference===false&&tested(saved)));
  const excludedCount=items.filter(item=>item.excluded).length;
  const ready=(!stratifiedDesign||!!stratumRequest&&!unstratified)&&!!sources.length&&!missing&&!disabled&&!busy&&stated.regions&&!remaining&&designStated&&ledgerReady&&!unsupportedAxes&&!independenceMissing&&!datesMissing&&!positivityMissing&&(!channelGate||!!currentGate);
  // The fields behind a comparison (fields.svg) are a check inside the result, not a figure of its own (owner decisions 15, 19).
  const svgFiles=saved?.figure.source_files.filter(name=>name.endsWith(".svg")&&name!=="fields.svg")||[];
  const fieldCheck=!!saved?.figure.source_files.includes("fields.svg");
  // Publication figures list their forms; the saved presentation tells which one is drawn.
  const forms=saved?.figure.forms||[],publication=forms.length>0;
  const drawnObservations=observations??saved?.figure.presentation?.observations??"points";
  const currentForm=forms.find(form=>form.kind===figureKind&&(form.kind!=="superplot"||(form.observations??"points")===drawnObservations))??forms.find(form=>form.kind===figureKind);
  const descriptiveResult=!!saved&&(saved.result.spec?.test==="none"||!!saved.result.warnings?.includes("descriptive_comparison_no_test_or_interval"));
  const pairedRuns=saved?.result.spec?.design?.kind==="paired";
  // The run hierarchy is drawn as a publication figure; a run-value form keeps its own drawing.
  const layered=figureKind==="superplot"||figureKind==="unit-mean-bar";
  const canRender=!!saved&&!stale&&!disabled&&!busy;
  const pointRows=saved&&pointSource?.job===saved.figureJob?(saved.result.plot_data||saved.result.y_source?.plot_data||[]).filter(row=>["condition","sample","experimental_unit"].every(key=>!(key in pointSource.source)||row[key]===pointSource.source[key as keyof FigureSource])):[];
  function openPoint(source:FigureSource){if(!saved)return;if(source.field_id){if(!resultSources(saved.result).some(field=>field.field_id===source.field_id))return;onSource(source.field_id,source.region_id??source.nucleus_id,saved.revision,saved.target,savedChannel,savedStructure);}else if(source.experimental_unit){setPointSource({job:saved.figureJob,source});}}
  const series=saved?.historical?(saved.operation==="distribution"?(saved.sources||[]).map(source=>source.field):saved.result.spec?.conditions||[]):resultSeries(operation,sources.map(source=>source.field),conditions,contrasts);
  const plot=():RenderPlot=>({...checkedPlot(width,height,font,xLabel,yLabel,yMin,yMax),...axisPlotOptions(xAxis,{...yAxis,min:yMin,max:yMax,...(layered&&(saved?.historical?saved.operation:operation)==="comparison"?{scale:"linear" as const}:{})},(saved?.historical?saved.operation:operation)==="association"),...(pointSize?{point_size:pointSize}:{}),group_order:seriesOrder(order,series),style:{version:"1.0.0",series_colors:colors,show_legend:legend},
    // Distribution pages have their own layout; comparisons and associations draw the publication figure.
    ...((saved?.historical?saved.operation:operation)==="distribution"?{}:{presentation:{version:"1.0.0" as const,annotation,size,...(observations?{observations}:{}),...(colorBy?{color_by:colorBy}:{}),
      composition,...(Object.keys(imageFields).length?{image_fields:imageFields}:{}),outlines}})});
  async function repairUnsupported(){if(!onSaveDraft)return;const additional=initialSpec?.additional_analyses??[],indexes=new Map<number,number>();let next=1;indexes.set(0,0);additional.forEach((value,index)=>{if(!invalidMethod(value))indexes.set(index+1,next++);});
    const primaryInvalid=invalidMethod(initialSpec?.statistics?.method??undefined);
    const statistics=primaryInvalid?{...initialSpec?.statistics,method:{kind:"descriptive",test:null,omnibus:null,association:null,x:null,y:null},x_metric:null,x_channel_id:null}:initialSpec?.statistics;
    await onSaveDraft({statistics,additional_analyses:additional.filter(value=>!invalidMethod(value)),figure_proposals:(initialSpec?.figure_proposals??[]).filter(value=>indexes.has(value.analysis_index)&&!(primaryInvalid&&value.analysis_index===0)).map(value=>({...value,analysis_index:indexes.get(value.analysis_index)!}))});setProposedIndex(0);if(primaryInvalid)setOperation("distribution");setError("");
  }
  async function persist(){if(unsupportedAxes)throw new Error("保存した相関案の横軸と縦軸には同じ測定領域を指定してください。解析案を作り直してください。");if(!onSaveDraft)return;const display={...plot(),kind:operation==="association"?"scatter" as const:figureKind};
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
  async function classifyForResults(){
    if(lock.current||disabled||busy||!channelGate||!sources.length||missing||!ledgerReady)return;
    lock.current=true;setBusy("分類記録を確認中…");setError("");const requested=gateIdentity;
    try{
      await persist();
      let adopted=beforePrepare?await beforePrepare():selection;
      if(!beforePrepare){for(const source of sources)await adapter.selectRevision(workspace,source.revision,source.field);adopted=adapter.selection();}
      const revision=await comparison.cohort(workspace,sources,fields,adopted,compartment&&unresolved?MISSING_POLICY:null,true,stratumRequest);
      const result=await adapter.channelGate(workspace,channelGateRequest({...channelGate,reference_sha256:null},sources.map(source=>({fieldId:source.field,label:source.label,revisionId:revision}))));
      if(gateCurrent.current!==requested)return;
      // The compared fields' decision stays with this comparison (and its saved result). The workspace keeps the decision
      // made on the image's own fields, so the image is coloured again after a reload (MV-10).
      const filter=recordedChannelGate(result);
      if(gateCurrent.current===requested)setRecordedGate({identity:requested,revision,filter,result});
    }catch(cause){if(gateCurrent.current===requested)setError(fail(cause));}
    finally{lock.current=false;setBusy("");}
  }
  // The image's next step asked to judge the compared fields again (MV-09); it runs once the cohort is ready.
  const pendingReclassify=useRef(0);
  useEffect(()=>{if(reclassifyRequest)pendingReclassify.current=reclassifyRequest;},[reclassifyRequest]);
  // A next step's group comparison outlasts only the saved specification that had not arrived yet: once a
  // specification's statistics have been applied, a later one (an adopted AI proposal) sets its own analysis.
  const compareWanted=useRef(false),appliedStatistics=useRef(false);
  const receivedStatistics=useRef<string|null>(null);
  useEffect(()=>{if(!compareRequest)return;compareWanted.current=!appliedStatistics.current;setOperation("comparison");setTypedConfirmed(false);},[compareRequest]);
  const runPendingReclassify=useEffectEvent(()=>{pendingReclassify.current=0;void classifyForResults();});
  // The request answers that one click: it lapses when the decision is already current or the researcher moves on,
  // so a later change of the experiment or exclusions never judges again unasked.
  useEffect(()=>{
    if(!pendingReclassify.current)return;
    if(mode!=="statistics"||!metric.startsWith("positive_")||!channelGate){pendingReclassify.current=0;return;}
    if(busy||disabled||!sources.length||missing||!ledgerReady)return;
    if(currentGate){pendingReclassify.current=0;return;}
    runPendingReclassify();
  },[reclassifyRequest,currentGate,channelGate,busy,disabled,sources.length,missing,ledgerReady,mode,metric]);
  async function calculate(automatic=false){
    if(lock.current||!ready)return;lock.current=true;setBusy("解析中…");setError("");setUnrecorded("");const startedFor=choiceNow.current;
    try{
      // The public demo calculates with the default figure (recorded for every result); a width the
      // visitor chose beforehand is drawn right after (below).
      // The figure follows the analysis being calculated, not the saved result on screen: a distribution page
      // has no publication presentation (its request refuses one).
      const {presentation:shownPresentation,...shownPlot}=plot();
      const pagePlot={...shownPlot,...(chosenWidth===null?{width_inches:pageSize(operation).width/25.4}:{}),...(chosenHeight===null?{height_inches:pageSize(operation).height/25.4}:{})};
      const drawn=operation==="distribution"?pagePlot:{...pagePlot,...(shownPresentation?{presentation:shownPresentation}:{})};
      const display=demo?(operation==="distribution"?{...pagePlot,width_inches:183/25.4}:{...pagePlot,presentation:{version:"1.0.0" as const,annotation:"value" as const,size:"panel" as const,composition:"quantification" as const,outlines:true}}):drawn;
      // Chosen without 計算, a comparison is described, never tested (D-5); the recorded demo replays its own requests.
      const base=resultRequest(automatic&&!demo&&operation==="comparison"?{...design,inference:false}:design,fields,display);
      // A new comparison opens on its publication figure; the bar stays when the researcher chose it.
      const chosenKind=operation==="association"?"scatter":operation==="distribution"?"distribution":!demo&&figureKind==="unit-mean-bar"?"unit-mean-bar":comparisonKind();
      const spec={...base,plot:{...base.plot,kind:chosenKind}};
      await persist();
      if(sources.some(source=>(source.result.regionSet||target)!==regionSet))throw new Error("同じ領域の測定結果を選択してください。");
      let adopted=beforePrepare?await beforePrepare():selection;
      if(!beforePrepare){for(const source of sources)await adapter.selectRevision(workspace,source.revision,source.field);adopted=adapter.selection();}
      const keepMissing=compartment&&unresolved;
      // A stratified design always reads a stratum cohort, one field included, so the stratum, the design
      // hash and the exclusion ledger reach the result; an undivided design keeps the single-field path.
      const requestedStratum=stratumRequest;
      const revision=currentGate?.revision??(sources.length===1&&!requestedStratum?sources[0].revision:await comparison.cohort(workspace,sources,fields,adopted,keepMissing?MISSING_POLICY:null,sources.length===1,requestedStratum));
      // For inferential requests the cohort persists the entered experimental metadata.
      if(operation!=="distribution"&&sources.length<2)throw new Error("統計解析には複数視野の測定結果と実験情報が必要です。");
      await comparison.review(revision,stated.regions,keepMissing?unresolvedFields:null);
      const accepted=await post<{job_id:string}>(`/v1/revisions/${revision}/${operation==="distribution"?"descriptive":"common-statistics"}`,spec);
      const calculatedJob=await waitJob(accepted.job_id);
      const result=await request<ResultPayload>(`/v1/jobs/${accepted.job_id}/${operation==="distribution"?"result":"common-statistics"}`);
      if(result.revision_id!==revision)throw new Error("結果の解析版が一致しません。");
      const current=choiceNow.current===startedFor;
      if(current){setFigureKind(chosenKind);if(demo){restorePresentation((display as RenderPlot).presentation);}
        if(observations&&!(result.figure.forms||[]).some(form=>form.observations===observations))setObservations(null);}
      // A design, stratum or source changed while this ran: its result is not shown as current.
      if(requestedStratum&&scopedIdentity("",requestedStratum)!==scopedIdentity("",stratumRequestRef.current))throw new Error("層または実験デザインが計算中に変わりました。もう一度計算してください。");
      const created:Saved={job:accepted.job_id,revision,result,identity:resultIdentity(sources,fields,requestedStratum),requestIdentity,plot:{...display,kind:chosenKind},figureJob:accepted.job_id,figure:result.figure,operation,sources:sources.map(source=>({field:source.field,label:source.label})),target:["nuclei","nucleoli","nucleoplasm","cell"].includes(regionSet)?regionSet as ReviewTarget:target,created:Date.now()/1000,calculated:calculatedJob.calculated_at??null};
      if(current)setSaved(created);setHistory(previous=>[created,...previous.filter(value=>value.job!==created.job)]);
    // In the demo, a choice the recording cannot answer (after an AI example changed the detection, say) is told as
    // the demo's limit on the condition's card, not as an error.
    }catch(cause){if(automatic&&demo)setUnrecorded(startedFor);else setError(fail(cause));}finally{lock.current=false;setBusy("");}
  }
  async function render(downloadZip=false){
    if(lock.current||!saved||!canRender)return;lock.current=true;setBusy("図を更新中…");setError("");setSavedNote("");
    try{if(!saved.historical)await persist();const display={...plot(),kind:figureKind};const key=JSON.stringify([saved.job,display]);let rendered=renderCache.current.get(key);
      if(!rendered){let requestId=renderIds.current.get(key);if(!requestId){requestId=crypto.randomUUID();renderIds.current.set(key,requestId);}
        const accepted=await post<{job_id:string}>(`/v1/jobs/${saved.job}/figure-render`,{request_id:requestId,plot:{...display,y_min:display.y_min??null,y_max:display.y_max??null}});await waitJob(accepted.job_id);
        const output=await request<{source_job_id:string;figure:ResultPayload["figure"]}>(`/v1/jobs/${accepted.job_id}/figure-render`);
        if(output.source_job_id!==saved.job)throw new Error("図の元データが一致しません。");rendered={job:accepted.job_id,figure:output.figure};renderCache.current.set(key,rendered);}
      baseline.current={job:rendered.job,signature:JSON.stringify(display)};failedSignature.current="";
      const updated={...saved,plot:display,figureJob:rendered.job,figure:rendered.figure,created:Date.now()/1000};setSaved(updated);setHistory(previous=>[updated,...previous.filter(value=>value.figureJob!==updated.figureJob)]);
      if(downloadZip){setBusy("保存ファイルを作成中…");try{const exported=await post<{job_id:string}>(`/v1/revisions/${saved.revision}/export${includeRaw?"?include_raw=true":""}`,{});await waitJob(exported.job_id);const packaged=await post<{job_id:string}>(`/v1/jobs/${rendered.job}/publication-package`,{analysis_job_id:exported.job_id,request_id:crypto.randomUUID()});await waitJob(packaged.job_id);await download(`/v1/jobs/${packaged.job_id}/files/publication.zip`,"Cytellect-publication.zip");}catch(cause){
        // The public demo records the publication package for the guided result only; any other
        // result saves the figure it shows, which is recorded.
        if(!demo||!(cause instanceof ApiError)||cause.code!=="showcase_action_not_recorded")throw cause;
        const file=rendered.figure.source_files.find(name=>name.endsWith(".svg"))||"figure-001.svg";await download(`/v1/jobs/${rendered.job}/files/${encodeURIComponent(file)}`,"Cytellect-figure.svg");setSavedNote("図（SVG）を保存しました。論文用パッケージ（ZIP）の作成には、Windows 版とお手元の画像が必要です。");}}
    }catch(cause){failedSignature.current=signature;setError(fail(cause));}finally{lock.current=false;setBusy("");}
  }
  /** The drawn figure as an image on the clipboard, for a slide (FU-08). */
  async function copyPng(){if(!saved)return;try{const blob=await fetchBlob(`/v1/jobs/${saved.figureJob}/files/figure.png`);await navigator.clipboard.write([new ClipboardItem({"image/png":blob.type==="image/png"?blob:new Blob([blob],{type:"image/png"})})]);setSavedNote("PNG をコピーしました。");}catch(cause){setError(fail(cause));}}
  function editMetadata(id:string,key:keyof Metadata,value:string){setMetadata(previous=>({...previous,[id]:{...fields[id],[key]:value||null}}));setTypedConfirmed(false);}
  function restoreFigure(selected:Saved){setSaved(selected);setOperation(selected.operation);setFigureKind(selected.plot.kind);setWidth(selected.plot.width_inches*25.4);setHeight(selected.plot.height_inches*25.4);setFont(selected.plot.font_size);setXLabel(selected.plot.x_label);setYLabel(selected.plot.y_label);setYMin(selected.plot.y_min==null?"":String(selected.plot.y_min));setYMax(selected.plot.y_max==null?"":String(selected.plot.y_max));setPointSize(selected.plot.point_size??null);restorePresentation(selected.plot.presentation);setColors(selected.plot.style?.series_colors||{});setLegend(selected.plot.style?.show_legend??true);setOrder(selected.plot.group_order);setXAxis({min:selected.plot.axes?.x_min==null?"":String(selected.plot.axes.x_min),max:selected.plot.axes?.x_max==null?"":String(selected.plot.axes.x_max),step:selected.plot.axes?.x_tick_step==null?"":String(selected.plot.axes.x_tick_step),scale:selected.plot.axes?.x_scale||"linear"});setYAxis({min:"",max:"",step:selected.plot.y_tick_step==null?"":String(selected.plot.y_tick_step),scale:selected.plot.axes?.y_scale||"linear"});}
  // Statistics and figures open on the latest saved result (as the researcher's last session left it), not an empty view.
  // Saved comparisons are one click apart (in the demo, the opening comparison and the source's other recorded
  // changes, goals C7): the newest figure of each, newest first.
  const recorded:Saved[]=[];
  if(mode==="statistics")for(const entry of history)if(entry.operation==="comparison"&&entry.result.estimates&&!recorded.some(value=>value.job===entry.job))recorded.push(entry);
  function showRecorded(entry:Saved){
    restoreFigure(entry);
    // The analysis settings follow the chosen result too, so its test is shown under its own method.
    const method=savedMethod(entry.operation,entry.result.spec);if(method.paired!==undefined)setPaired(method.paired);if(method.rank!==undefined)setRank(method.rank);
    // The side panel follows, so the shown result is the chosen metric's and not a "previous" one.
    const metric=entry.result.spec?.selection?.metric??entry.result.estimates?.metric??entry.result.metric;
    if(entry.target)onAnalysisTargetChange?.(metricStructure(metric??"",entry.target));
    if(metric)onMetricChange?.(metric,entry.result.spec?.selection?.channel_id??null);
  }
  const [savedNote,setSavedNote]=useState("");
  // The demo choice whose recorded result could not be replayed.
  const [unrecorded,setUnrecorded]=useState("");
  // A changed setting redraws the figure (FU-04); the drawn figure stays until the new one is ready.
  const signature=(()=>{try{return saved&&mode==="figure"?JSON.stringify({...plot(),kind:figureKind}):"";}catch{return "";}})();
  const baseline=useRef<{job:string;signature:string}|null>(null);
  // The settings whose redraw failed: they are not drawn again until one of them changes.
  const failedSignature=useRef("");
  useEffect(()=>{if(!saved){baseline.current=null;return;}
    if(baseline.current?.job!==saved.figureJob){if(signature)baseline.current={job:saved.figureJob,signature};return;}
    if(!signature||signature===baseline.current.signature||signature===failedSignature.current||busy||stale||disabled)return;
    const timer=setTimeout(()=>void render(),350);return()=>clearTimeout(timer);},[signature,saved?.figureJob,busy,stale,disabled]);// eslint-disable-line react-hooks/exhaustive-deps
  const openingTarget=useRef<ReviewTarget|null>(null),openingCommit=useRef(false);
  const openLatestSaved=useEffectEvent((entry:Saved)=>{if(saved)return;restoreFigure(entry);
    // The opening comparison (metric, channel, region) is for the first look only (DM-04): once the researcher has
    // measured, it is not applied, even when the saved results load after the measurement.
    if(measured)return;const metric=entry.result.spec?.selection?.metric??entry.result.metric;if(metric)onOpening?.(metric,entry.result.spec?.selection?.channel_id??null);
    // The opening result's region too, once the statistics view is shown (DM-04); the image view keeps its own
    // opening region until then (DM-03).
    if(!metric||!entry.target)return;const opening=metricStructure(metric,entry.target);
    // A deep link (step=statistics) shows the view before the saved results load: apply the region at once.
    if(shown&&(mode==="statistics"||mode==="figure"))(onOpeningTarget??onAnalysisTargetChange)?.(opening);else openingTarget.current=opening;});
  useEffect(()=>{if(measured)openingTarget.current=null;if(!shown||(mode!=="statistics"&&mode!=="figure")||!openingTarget.current)return;(onOpeningTarget??onAnalysisTargetChange)?.(openingTarget.current);openingTarget.current=null;openingCommit.current=true;},[shown,mode,history]);// eslint-disable-line react-hooks/exhaustive-deps
  // The researcher measured before the statistics view was first shown: their new measurement is what they compare
  // next, so the opening region is no longer applied (DM-04 applies to the first look only).
  useEffect(()=>{if(measured)openingTarget.current=null;},[measured]);
  useEffect(()=>{if(openedSaved.current||!history[0])return;openedSaved.current=true;openingCommit.current=true;openLatestSaved(history[0]);},[history]);
  // What the side panel chooses now, and the saved result that answers it (genellect/cytellect#257 D-1, owner decision
  // 2026-11-21): a newly chosen condition shows its own result at once, never the previous condition's.
  const gateNow=currentGate?.filter??channelGate;
  const condition:ResultCondition={operation,regionSet,metric,channel:conditionChannel(metric,channel,gateNow?.channel_id??null),filter:choiceFilter(metric,gfp,gateNow),
    x:operation==="association"?{metric:xMetric,channel:conditionChannel(xMetric,xChannel,null)}:null,stratum:stratifiedDesign?stratum?.label??null:null};
  const choiceKey=conditionKey(condition);
  const shownCondition=saved?savedCondition(saved.operation,saved.result):null;
  // A saved result that records no condition (an older format) is shown as it was. A result calculated here from other
  // measurements or settings than the chosen ones (stale) does not answer the choice either.
  // Both 統計 and グラフ follow the side panel's choice (SR-04): neither shows another condition's result.
  const resultMode=mode==="statistics"||mode==="figure";
  // A result calculated here answers the same measurements and request; one saved earlier (reopened) answers when it was
  // calculated with the test and pairing now chosen. A description answers a choice that could be tested (計算 tests it).
  const chosenMethod={paired,rank,inference:design.inference!==false};
  const pending=resultMode&&(!saved||stale||(!!saved.historical&&!sameMethod(saved.operation,saved.result.spec,chosenMethod))||(!!shownCondition&&conditionKey(shownCondition)!==choiceKey));
  const answers=(entry:Saved)=>entry.historical?sameMethod(entry.operation,entry.result.spec,chosenMethod):(entry.identity===identity&&entry.requestIdentity===requestIdentity&&!(design.inference===false&&tested(entry)));
  const available=savedFor(history.filter(answers),condition,sources.map(source=>({field:source.field,mask:source.result.masks?.metadata?.mask_revision_id??"",protocol:source.result.protocol,mode:source.result.measurement?.mode})));
  const stainOf=(id:string|null)=>id?stainName(id):null;
  const choiceLabel=measureLabel(metric,regionSet,stainOf(condition.channel));
  // In the demo, only what the tour recorded can be shown; elsewhere anything can be calculated.
  // The saved figures グラフ offers are the ones the side panel can show (SR-04): a design of two or more groups has no
  // distribution (decision 15), and a figure of another nucleus filter is chosen with that filter.
  const figureChoices=savedResults.filter(entry=>{const answered=savedCondition(entry.operation,entry.result);
    return !(comparable&&entry.operation==="distribution")&&(!answered||answered.filter===condition.filter);});
  const recordedChoice=(value:ResultCondition)=>!recordedStatistics||recordedStatistics.some(item=>item.analysis===value.operation&&item.region===value.regionSet&&item.metric===value.metric
    &&(nucleusPositivity(value.metric)?item.positivity===value.channel:!metricUsesChannel(value.metric)||item.channel===value.channel)
    &&(item.gate?`cg:${item.gate}`:"")===value.filter&&(value.operation!=="association"||(!!item.x&&item.x.metric===value.x?.metric&&item.x.channel===value.x?.channel)));
  const recordedOperation=(value:ResultOperation)=>recordedChoice({...condition,operation:value});
  // The current condition, read when a calculation ends: a result calculated for an earlier choice is kept, not shown.
  const choiceNow=useRef(choiceKey);
  useLayoutEffect(()=>{choiceNow.current=choiceKey;});
  const appliedChoice=useRef("");
  useEffect(()=>{
    const key=`${choiceKey}\n${available.current?.job??""}`;
    if(!shown||!resultMode||busy||openingCommit.current||!choiceKey||appliedChoice.current===key)return;
    appliedChoice.current=key;
    if(pending&&available.current)restoreFigure(available.current);
  },[choiceKey,available.current?.job,shown,busy,mode]);// eslint-disable-line react-hooks/exhaustive-deps
  // A chosen condition without a saved result is described at once (owner decisions D-5, 2026-11-21 and 11): in the demo
  // from its recording, elsewhere once 画像 and 実験 hold what it needs. A comparison is described (test "none") even
  // when it could be tested; a test, and an association, wait for 計算.
  const autoDescribed=useRef("");
  const autoEligible=resultMode&&shown&&!busy&&historyLoaded&&ready&&pending&&!available.current&&!!choiceKey&&recordedChoice(condition)
    &&(demo||operation==="distribution"||operation==="comparison"&&!!unit.trim());
  // Once per choice and per set of measurements and settings: measuring again describes the choice again.
  const autoKey=autoEligible?`${choiceKey}\n${identity}\n${requestIdentity}`:"";
  const autoNow=useRef(""),autoRun=useRef(()=>{});
  useLayoutEffect(()=>{autoNow.current=autoKey;autoRun.current=()=>void calculate(true);});
  // The effects that settle a choice (the analysis, the axis, the declared design) run in the same commit as the
  // choice: the calculation starts once the choice has stayed the same for a moment, never for a state in between.
  useEffect(()=>{if(!autoKey||autoDescribed.current===autoKey)return;
    const timer=setTimeout(()=>{if(autoNow.current!==autoKey||openingCommit.current||lock.current)return;autoDescribed.current=autoKey;autoRun.current();},300);
    return()=>clearTimeout(timer);},[autoKey]);
  // The opening steps' commit is over.
  useEffect(()=>{openingCommit.current=false;});
  const shownTarget=saved?.historical?saved.target:target;const shownMetric=saved?.historical?(saved.result.metric||saved.result.y_source?.metric||saved.result.spec?.selection?.metric||""):metric;const shownChannel=saved?.historical?(saved.result.channel?.channel_id||saved.result.y_source?.channel?.channel_id||saved.result.spec?.selection?.channel_id||null):channel;
  const savedChannel=saved?.result.channel?.channel_id??saved?.result.y_source?.channel?.channel_id??saved?.result.spec?.selection?.channel_id??saved?.result.selection?.channel_gate?.channel?.channel_id??saved?.result.spec?.selection?.positivity?.channel_id??null;
  const savedStructure=saved?.target?metricStructure(saved.result.spec?.selection?.metric??saved.result.estimates?.metric??saved.result.metric??"",saved.target):undefined;
  const tableRows=saved?.operation==="comparison"?saved.result.comparisons:saved?.operation==="association"?saved.result.associations:saved?.result.field_summary&&withMaskCorrections(saved.result.field_summary,saved.result.mask_corrections);
  const fieldLabels=Object.fromEntries([...(saved?.sources||[]).map((source,index)=>[source.field,source.label!==source.field?source.label:`視野 ${index+1}`]),...items.map(item=>[item.fieldId,item.label])]);

  // 主要 or 探索 only when a primary measure is declared (#257 RP-04): a saved result by the server time of its
  // statistics, never of a re-drawn figure; the chosen condition before it is calculated by its measure alone.
  // A declaration made after a result of the same measure was seen marks every result of that measure 探索.
  const postHoc=declaredAfterResults(primary,history.map(entry=>({condition:savedCondition(entry.operation,entry.result as SavedResultLike),calculatedAt:entry.calculated??null})));
  const roleOf=(entry:Saved):OutcomeRole=>outcomeRole(primary,savedCondition(entry.operation,entry.result as SavedResultLike),entry.calculated??null,postHoc);
  // The mark follows the label it stands beside: グラフ names the saved result even while another choice is pending.
  const shownRole:OutcomeRole=saved&&(!pending||mode==="figure")?roleOf(saved):outcomeRole(primary,{metric,regionSet,channel:condition.channel},undefined,postHoc);
  const roleMark=(role:OutcomeRole)=>role&&<span className={styles.outcomeRole} data-outcome-role={role}>{OUTCOME_ROLE_LABELS[role]}</span>;
  const savedChips=<div className={styles.recorded} role="group" aria-label="保存した比較">{recorded.map(entry=><button key={entry.job} aria-pressed={!pending&&saved?.job===entry.job} onClick={()=>showRecorded(entry)}>{resultMetricLabel(entry.result,entry.result.estimates?.metric??"",stainName)}{roleMark(roleOf(entry))}</button>)}</div>;
  if(csv)return <ConnectedCsvResults workspace={workspace} mode={mode} onImages={()=>setCsv(false)}/>;
  return <section className={styles.root} aria-label={mode==="figure"?"図の作成・保存":"測定結果の統計解析"}>
    <div className={styles.settings} onBlur={event=>{if(event.currentTarget.contains(event.relatedTarget)||(event.relatedTarget as HTMLElement|null)?.dataset?.calculate)return;if(!busy&&!saved?.historical)void persist().catch(cause=>setError(fail(cause)));}}>
      <header><h2>{mode==="figure"?"グラフ":"統計解析"}</h2><span>{sources.length} 視野{excludedCount?` · 除外 ${excludedCount}`:""}</span></header>
      {stratifiedDesign&&<div className={styles.stratumPick}>
        <label>比べる層<select aria-label="比べる層" value={stratumChoice} disabled={!!busy} onChange={event=>setStratumChoice(event.target.value)}>
          <option value="">層を選ぶ…</option>{strata.map(value=><option key={value.id} value={value.id}>{value.label}（{value.fieldIds.length} 視野）</option>)}</select></label>
        <p role="status">{stratum?`層「${stratum.label}」の視野だけで計算します（${sources.length} 視野${excludedCount?`、除外 ${excludedCount}`:""}${missing?`、未測定 ${missing}`:""}）。層の統合・層間の比較はしません。`
          :"計算には層の選択が必要です。選んだ層の 2 群を比較し、層の統合・層間の比較はしません。"}{strata.length>1?` 宣言した層：${strata.length}。層ごとに検定し、層の数に対する多重性の補正はしません。`:""}</p>
        {!!unstratified&&<p role="alert">層が決まっていない視野：{unstratified} 件。計算には、「実験」での層の割り当てか、理由を付けた除外が必要です。</p>}
      </div>}
      <button type="button" onClick={()=>setCsv(true)}>CSV の数値表を解析</button>
      <p className={styles.current}>{mode==="figure"&&saved?(saved.historical?resultMetricLabel(saved.result,shownMetric,stainName):measureLabel(shownMetric,shownTarget,stainOf(shownChannel))):choiceLabel}{roleMark(shownRole)}</p>
      {positivityMissing&&<p role="status">陽性核数・陽性率には核の分類が必要です。「画像」で色分けを「陽性・陰性」にし、染色を選んで分類してください。</p>}
      {channelGate&&<div><p>{currentGate?`${channelGateName(currentGate.result)}の分類記録：確認済み。` :"集計対象・実験情報の変更後は、分類記録の確認が必要です。"}</p>
        <button type="button" disabled={disabled||!!busy||!sources.length||!!missing||!ledgerReady} onClick={()=>void classifyForResults()}>現在の実験情報で再分類</button>
        <small>計算には判定記録の確認が必要です。陽性率の分母は、選別前に判定できた核です。</small>
        {currentGate&&<><table aria-label="核の分類の内訳"><thead><tr><th>視野</th><th>陽性</th><th>陰性</th><th>未判定</th><th>除外</th><th>対照</th></tr></thead>
          <tbody>{Object.entries(currentGate.result.field_counts).map(([fid,row])=><tr key={fid}><th scope="row">{sources.find(source=>source.field===fid)?.label||fid}</th>{(["positive","negative","unclassified","excluded","control"] as const).map(key=><td key={key}>{row.nuclei===null?"—":row[key]}</td>)}</tr>)}</tbody></table>
          {channelGateThresholds(currentGate.result).map(row=><small key={row.date}>{row.date} · {row.threshold===null?errorCodeMessage(row.reason||"channel_threshold_missing"):`しきい値 ${row.threshold.toPrecision(5)}`}</small>)}</>}
      </div>}
      {mode==="statistics"?<>
        {invalidSaved&&<button disabled={!!busy||disabled} onClick={()=>void repairUnsupported().catch(cause=>setError(fail(cause)))}>未対応の相関案を解除</button>}
        {unsupportedAxes&&<p role="alert">保存した相関案の横軸と縦軸の測定領域が一致していません。同じ領域を指定して解析案を作り直してください。</p>}
        {proposals.length>1&&<label>AIの解析案<select value={proposedIndex} disabled={!!busy} onChange={event=>selectProposal(Number(event.target.value))}>{proposals.map((value,index)=><option key={index} value={index}>{index+1} · {value.kind==="association"?"相関":value.kind==="comparison"?"群間比較":"分布"}</option>)}</select></label>}
        <label>解析<select value={operation} disabled={!!busy} onChange={event=>{compareWanted.current=false;setSwitched(null);setOperation(event.target.value as ResultOperation);setTypedConfirmed(false);}}>{(!comparable||saturated)&&<option value="distribution" disabled={!descriptiveSupported(metric)||!recordedOperation("distribution")}>{descriptiveSupported(metric)?"分布":"分布（この指標は群間比較のみ）"}</option>}<option value="comparison" disabled={saturated||!recordedOperation("comparison")}>{saturated?"群間比較（飽和画素を含む）":"群間比較"}</option><option value="association" disabled={!canAssociate||unconfirmed||!recordedOperation("association")}>{unconfirmed?"相関（独立性：未確認）":canAssociate?"相関":saturatedSet.size?"相関（飽和画素を含む）":"相関（面積・輝度のみ）"}</option></select></label>
        {switched?.key===measureKey&&<p className={styles.switched} role="status">{switched.reason}</p>}
        {operation!=="distribution"&&<>
          <div className={styles.row}>{operation==="comparison"&&(unconfirmed||exploratory)?<div className={styles.methodNone}><label>方法<select value="none" disabled><option value="none">記述統計</option></select></label><details><summary>検定の条件</summary><p>{exploratory?"検定には、陰性対照に基づくしきい値が必要です。":"検定には、実験回の独立性の確認が必要です。"}{!exploratory&&onEditExperiment&&<> <button type="button" onClick={onEditExperiment}>実験デザインを編集</button></>}</p></details></div>:<label>方法<select value={rank?"rank":"parametric"} onChange={event=>setRank(event.target.value==="rank")}><option value="parametric">{operation==="association"?"Pearson":"t 検定 / Welch ANOVA"}</option><option value="rank">{operation==="association"?"Spearman":"順位に基づく検定"}</option></select></label>}{operation==="comparison"&&<label>対応<select value={paired?"paired":"independent"} disabled={demo} onChange={event=>{setPaired(event.target.value==="paired");setTypedConfirmed(false);}}><option value="independent">対応なし</option><option value="paired">対応あり</option></select></label>}</div>
          {operation==="association"&&<div className={styles.row}><label>横軸<select value={xMetric} onChange={event=>setXMetric(event.target.value)}>{xAxes.map(value=><option key={value} value={value}>{metricLabels[value]}</option>)}</select></label><label>横軸チャンネル<select value={xChannel||""} onChange={event=>setXChannel(event.target.value||null)}><option value="">選択</option>{channels.map(value=><option key={value}>{value}</option>)}</select></label></div>}

          {declared?<p className={styles.designLine}><span>実験回 {experiment?.runs?.length??0}</span><span>{paired?"対応あり":"対応なし"}</span>{onEditExperiment&&<button type="button" onClick={onEditExperiment}>実験 ↗</button>}</p>:<>
          <label>独立実験単位<input value={unit} maxLength={200} placeholder="例：別の日に独立に調製した培養" onChange={event=>{setUnit(event.target.value);setTypedConfirmed(false);}}/></label>
          {paired&&operation==="comparison"&&<label>対応の根拠<input value={pairing} maxLength={200} onChange={event=>{setPairing(event.target.value);setTypedConfirmed(false);}}/></label>}</>}
          {operation==="comparison"&&<fieldset><legend>比較する群</legend>{pairs.length?pairs.map(pair=><label className={styles.check} key={JSON.stringify(pair)}><input type="checkbox" disabled={demo||!unsaturatedPair(pair)} checked={contrasts.some(value=>JSON.stringify(value)===JSON.stringify(pair))} onChange={event=>setContrasts(previous=>event.target.checked?[...previous,pair]:previous.filter(value=>JSON.stringify(value)!==JSON.stringify(pair)))}/>{declared&&JSON.stringify(pair)===JSON.stringify(declared.contrasts[0])?`${pair[0]} − ${pair[1]}（処理 − 対照）`:pair.join(" / ")}{unsaturatedPair(pair)?"":"（飽和画素を含む）"}</label>):<p>実験情報に群名を入力してください。</p>}</fieldset>}
          {!demo&&!experiment&&<label className={styles.check}><input type="checkbox" checked={typedConfirmed} disabled={disabled} onChange={event=>setTypedConfirmed(event.target.checked)}/>独立実験単位、撮影・画素条件、採否と欠測の扱いを確認済み</label>}
        </>}
        {compartment&&currentLedger?.error&&<p role="alert">{currentLedger.error}</p>}
        {datesMissing&&<p role="status">輝度の比較には撮影日が必要です（推定による補完はしません）。{onEditExperiment&&<button type="button" onClick={onEditExperiment}>撮影日を入力</button>}</p>}
        {independenceMissing&&<p role="status">相関には、実験回の独立性の確認が必要です。{onEditExperiment&&<button type="button" onClick={onEditExperiment}>実験デザインを編集</button>}</p>}
        {/* Without a result, 計算 is on the condition's card; with one, here (to test or calculate again). Work left in an
            earlier screen takes its place (decision 11). */}
        {!demo&&!pending&&(remaining&&!busy?<RemainingLine work={remaining} onOpen={openRemaining}/>:<button className={styles.primary} disabled={!ready} onClick={()=>void calculate()}>{busy||"計算"}</button>)}
      </>:pending?null:<>
        <nav className={styles.figureParts} aria-label="図の設定対象">{([["figure","図"],["x","横軸"],["y","縦軸"],["series","系列"]] as const).map(([key,label])=><button key={key} aria-pressed={part===key} onClick={()=>setPart(key)}>{label}</button>)}</nav>
        {part==="figure"&&<>
          {/* Composition first, then the form and the size (FU-02); each change redraws the figure (FU-04). */}
          {publication&&layered&&saved?.operation==="comparison"&&(saved.figure.compositions||[]).length>1&&<label>構成<select value={composition} onChange={event=>setComposition(event.target.value as Composition)}><option value="quantification">定量のみ</option><option value="images-quantification">代表画像と定量</option></select></label>}
          {publication&&layered&&composition==="images-quantification"&&(saved?.result.spec?.conditions||[]).map(group=><label key={group}>代表画像（{group}）<select value={imageFields[group]||""} onChange={event=>setImageFields(previous=>{const next={...previous};if(event.target.value)next[group]=event.target.value;else delete next[group];return next;})}><option value="">自動（実験回の平均に近い視野）</option>{resultSources(saved!.result).filter(field=>field.metadata?.condition===group).map(field=><option key={field.field_id} value={field.field_id}>{fieldLabels[field.field_id]||field.field_id}</option>)}</select></label>)}
          {publication&&layered&&composition==="images-quantification"&&<label className={styles.check}><input type="checkbox" checked={outlines} onChange={event=>setOutlines(event.target.checked)}/>測定した領域の輪郭</label>}
          {publication&&forms.length>1&&<label>形<select value={currentForm?.id||""} onChange={event=>{const chosen=forms.find(value=>value.id===event.target.value);if(chosen){setFigureKind(chosen.kind);setObservations(chosen.observations??null);}}}>{!currentForm&&<option value="" disabled>保存した形</option>}{forms.map(value=><option key={value.id} value={value.id}>{formNames[value.id]||value.id}</option>)}</select></label>}
          {publication?<label>大きさ<select value={size} onChange={event=>setSize(event.target.value as FigureSize)}>{(Object.keys(sizeNames) as FigureSize[]).map(value=><option key={value} value={value}>{sizeNames[value]}</option>)}</select></label>
            :<label>図の幅<select value={width===89?"89":width===183?"183":"custom"} onChange={event=>{if(event.target.value!=="custom"){setWidth(Number(event.target.value));setHeight(Math.min(height,170));setFont(previous=>Math.min(previous,7));}}}><option value="89">1段幅 · 89 mm</option><option value="183">2段幅 · 183 mm</option><option value="custom">カスタム</option></select></label>}
          {publication&&layered&&saved?.operation==="comparison"&&<label>注釈<select value={annotation} onChange={event=>setAnnotation(event.target.value as typeof annotation)}><option value="value">{descriptiveResult?"実験回ごとの変化":"効果と P 値"}</option>{!descriptiveResult&&<option value="stars">P 値（アスタリスク）</option>}<option value="none">なし</option></select></label>}
          {publication&&layered&&saved?.operation==="comparison"&&pairedRuns&&<label>色分け<select value={colorBy||"run"} onChange={event=>setColorBy(event.target.value as "run"|"group")}><option value="run">実験回</option><option value="group">群</option></select></label>}
          {(!publication||size==="custom")&&<div className={styles.row}><label>幅 / mm<input type="number" min={30} max={406.4} value={width} onChange={event=>setWidth(Number(event.target.value))}/></label><label>高さ / mm<input type="number" min={25.4} max={170} value={height} onChange={event=>setHeight(Number(event.target.value))}/></label></div>}
          <label>文字 / pt<input type="number" min={5} max={24} value={font} onChange={event=>setFont(Number(event.target.value))}/></label>
          <label className={styles.check}><input type="checkbox" checked={legend} onChange={event=>setLegend(event.target.checked)}/>凡例を表示</label>
          {saved?.operation==="comparison"&&<p className={styles.figureHint}>{descriptiveResult?"記述統計のため、信頼区間は描きません。":"群の平均に 95% 信頼区間を付けます。"}</p>}
        </>}
        {part==="x"&&<fieldset className={styles.plain}><label>横軸ラベル<input value={xLabel} maxLength={120} onChange={event=>setXLabel(event.target.value)}/></label><AxisControls axis="x" value={xAxis} onChange={setXAxis} numeric={(saved?.operation||operation)==="association"}/></fieldset>}
        {part==="y"&&<fieldset className={styles.plain}><label>縦軸ラベル<input value={yLabel} maxLength={120} onChange={event=>setYLabel(event.target.value)}/></label><AxisControls axis="y" value={{...yAxis,min:yMin,max:yMax}} onChange={value=>{setYAxis(value);setYMin(value.min);setYMax(value.max);}} scale={!(layered&&saved?.operation==="comparison")}/></fieldset>}
        {part==="series"&&<><fieldset className={styles.plain}><label>系列<select value={selectedSeries||series[0]||""} onChange={event=>setSelectedSeries(event.target.value)}>{(order.length?seriesOrder(order,series):series).map(key=><option key={key} value={key}>{sources.find(source=>source.field===key)?.label||key}</option>)}</select></label><label>色<input type="color" value={colors[selectedSeries||series[0]]||"#0072b2"} onChange={event=>setColors(previous=>({...previous,[selectedSeries||series[0]]:event.target.value}))}/></label><label>点の大きさ<input type="number" min={1} max={400} value={pointSize??""} placeholder="自動" onChange={event=>setPointSize(event.target.value?Number(event.target.value):null)}/></label><div className={styles.row}>{[-1,1].map(direction=><button key={direction} onClick={()=>{const current=order.length?seriesOrder(order,series):[...series];const index=current.indexOf(selectedSeries||series[0]);if(index+direction<0||index+direction>=current.length)return;[current[index],current[index+direction]]=[current[index+direction],current[index]];setOrder(current);}}>{direction<0?"前へ":"後へ"}</button>)}</div></fieldset>{operation==="distribution"&&<button onClick={()=>onSource(selectedSeries||series[0],undefined,saved?.revision,saved?.target,savedChannel,savedStructure)}>元の視野を表示</button>}</>}
        {busy&&<p role="status" className={styles.figureHint}>{busy}</p>}
        {!saved&&<p>図の編集には、統計での計算結果が必要です。</p>}
      </>}
      {savedNote&&<p role="status" className={styles.demoNote}>{savedNote}</p>}
      {missing>0&&<><p role="status">{missing} 視野の測定が未完了です。</p>{onPrepareMissing&&<button disabled={!!busy||disabled} onClick={()=>{setBusy("必要な測定値を計算中…");void onPrepareMissing().catch(cause=>setError(fail(cause))).finally(()=>setBusy(""));}}>必要な測定値を計算</button>}</>}
      {stale&&!pending&&<p role="status">測定結果または解析条件が変わりました。再計算してください。</p>}
      {error&&<ErrorText text={error}/>}
      {saved&&!pending&&<div className={styles.downloads}>{mode==="figure"&&<label className={styles.check}><input type="checkbox" checked={includeRaw} disabled={!!busy||stale} onChange={event=>setRawExport({revision:saved.revision,included:event.target.checked})}/>元画像を含める</label>}<button disabled={!!busy||stale} onClick={()=>void render(true)}>保存</button>{mode==="figure"&&saved.figure.source_files.includes("figure.png")&&<button disabled={!!busy} onClick={()=>void copyPng()}>PNG をコピー</button>}</div>}
    </div>
    <div className={styles.output} ref={outputRef}>
      {mode==="figure"&&figureChoices.length>0&&<label className={styles.figureHistory}>保存した図<select value={pending?"":saved?.job||""} onChange={event=>{const selected=savedResults.find(value=>value.job===event.target.value);if(selected)showRecorded(selected);}}><option value="" disabled>結果を選ぶ</option>{figureChoices.map(entry=><option key={entry.job} value={entry.job}>{savedFigureName(entry)}</option>)}</select></label>}
      {mode==="statistics"&&operation!=="distribution"&&(<details className={styles.metadata} open={!saved&&!experiment}><summary>実験情報</summary>{experiment&&<p className={styles.derivedNote}>群・試料・独立実験単位・撮影日・対応ペアは、実験デザインから決まります。{onEditExperiment&&<button type="button" onClick={onEditExperiment}>実験デザインを編集</button>}</p>}<div className={styles.tableScroll} tabIndex={0}><table><thead><tr><th>視野</th>{["群","試料","独立実験単位","撮影日",...(paired&&operation==="comparison"?["対応ペア"]:[])].map(value=><th key={value}>{value}</th>)}</tr></thead><tbody>{sources.map(source=><tr key={source.field}><th><button onClick={()=>onSource(source.field)}>{source.label}</button></th>{(["condition","sample","experimental_unit","acquisition_date",...(paired&&operation==="comparison"?["pair"]:[])] as Array<keyof Metadata>).map(key=><td key={key}><input maxLength={80} readOnly={demo||source.field in derived} aria-label={`${source.label} ${key}`} value={String(fields[source.field][key]??"")} onChange={event=>editMetadata(source.field,key,event.target.value)}/></td>)}</tr>)}</tbody></table></div></details>)}
      {pending?<>
        {recorded.length>0&&savedChips}
        {/* A condition without a result keeps the result's card and figure frame in place: its name and 計算 (plan 4.1). */}
        <div className={styles.resultGrid} data-columns={2}>
          <section className={`${styles.summary} ${styles.pendingCard}`} aria-label="選択中の条件" aria-busy={!!busy}><h3>{choiceLabel}</h3>
            {busy?<p role="status">{busy}</p>:demo?(unrecorded===choiceKey||!recordedChoice(condition))&&<p role="status">{showcaseNotices.showcase_action_not_recorded}</p>:remaining?<RemainingLine work={remaining} onOpen={openRemaining}/>:mode==="statistics"||ready?
              // 計算 saves the settings itself. Pressing it leaves the settings without the save on leaving them, which
              // would hold the workspace busy (and the button disabled) while the click lands.
              <button className={styles.primary} data-calculate="" disabled={!ready} onMouseDown={event=>event.preventDefault()} onClick={()=>void calculate()}>計算</button>:onStatistics&&<button type="button" onClick={onStatistics}>統計で計算</button>}</section>
          <div className={styles.pendingFrame} aria-hidden="true"/>
        </div>
      </>:saved?<>
        {saved.result.stratum&&<p className={styles.current}>層：{saved.result.stratum.label}（{saved.result.stratum.levels.map(value=>`${value.factor}：${value.level}`).join("、")}）· 割り当て {saved.result.stratum.field_ids.length} 視野のうち解析 {saved.result.stratum.analysed_field_ids.length}{saved.result.stratum.excluded_fields.length?`、除外 ${saved.result.stratum.excluded_fields.length}`:""}。ほかの層は含みません。{saved.result.stratum.declared_stratum_count&&saved.result.stratum.declared_stratum_count>1?`宣言した層：${saved.result.stratum.declared_stratum_count}。層ごとに検定し、層の数に対する多重性の補正はしていません。`:""}</p>}
        {mode==="statistics"?<div className={styles.resultGrid} data-columns={(!!saved.result.estimates||saved.operation==="distribution"&&!!experiment)&&svgFiles.length>0?2:1}>
          <div>
            {recorded.length>1&&savedChips}
            {mode==="statistics"&&saved.result.estimates&&<ResultSummaryCard estimates={saved.result.estimates} comparison={(saved.result.comparisons?.[0]??{}) as SavedComparison} metricLabel={resultMetricLabel(saved.result,saved.result.estimates.metric,stainName)} unit={unitLabel(saved.result.unit)} warnings={saved.result.warnings||[]} onEditExperiment={onEditExperiment} testable={testable}
          reported={showcaseDataset?.reported??null}
          counts={breakdown(Array.isArray(saved.result.counts)?saved.result.counts as CountRow[]:[],saved.result.source_field_ledger??[],saved.result.spec?.selection?.source==="field-summary"?null:saved.target==="nuclei"||saved.target==="nucleoplasm"?"核":saved.target==="nucleoli"?"核小体":"領域",
            saved.result.compartment_missing?{rows:saved.result.compartment_missing.rows,perNucleus:saved.result.spec?.selection?.source==="compartment-summary"}:null)}
          missing={saved.result.compartment_missing??null}/>}
            {/* The discussion is a separate, AI-made (or demo example) frame under the computed result (AC-01). */}
            {/* The discussion belongs to the shown result, also a saved one (AC-06, AC-08). */}{mode==="statistics"&&saved.result.estimates&&<DiscussionPanel key={saved.job} adapter={adapter} job={saved.job} demo={demo} workspace={workspace}
              summary={shownSummary(saved.result.estimates,(saved.result.comparisons?.[0]??{}) as SavedComparison,resultMetricLabel(saved.result,saved.result.estimates.metric,stainName),unitLabel(saved.result.unit),saved.result.warnings||[],saved.result.compartment_missing??null,testable)}/>}
            {mode==="statistics"&&saved.operation==="distribution"&&experiment&&<RunMedians onEditExperiment={onEditExperiment} design={experiment} summary={saved.result.field_summary??[]} metricLabel={resultMetricLabel(saved.result,saved.result.metric||"",stainName)} unit={unitLabel(saved.result.unit)} reported={showcaseDataset?.reported??null} missing={saved.result.compartment_missing??null}/>}
            {/* Without a summary card the denominators still stand beside the result (Q-05). */}
            {mode==="statistics"&&saved.result.compartment_missing&&!saved.result.estimates&&!(saved.operation==="distribution"&&experiment)&&<><MissingLead summary={saved.result.compartment_missing}/><MissingNucleoli summary={saved.result.compartment_missing}/></>}
          </div>
          <div>{svgFiles.map(file=><VectorFigure key={`${saved.figureJob}:${file}`} widthMm={saved.figure.style?.width_mm} path={`/v1/jobs/${saved.figureJob}/files/${encodeURIComponent(file)}`}/>)}
            {fieldCheck&&<details className={styles.fieldCheck}><summary>視野ごとの分布</summary><VectorFigure key={`${saved.figureJob}:fields`} alt="視野ごとの測定値と中央値" path={`/v1/jobs/${saved.figureJob}/files/fields.svg`}/></details>}</div>
        </div>:svgFiles.map(file=>mode==="figure"?<div key={`${saved.figureJob}:${file}`} className={styles.figureFrame} style={saved.figure.style?.width_mm?{maxWidth:`${Math.round(saved.figure.style.width_mm*8)}px`}:undefined}><EditableFigure path={`/v1/jobs/${saved.figureJob}/files/${encodeURIComponent(file)}`} onSelect={setPart} onSource={openPoint}/></div>:<VectorFigure key={`${saved.figureJob}:${file}`} widthMm={saved.figure.style?.width_mm} path={`/v1/jobs/${saved.figureJob}/files/${encodeURIComponent(file)}`}/>)}
        {mode==="figure"&&saved.figure.source_files.includes("figure-legend.md")&&<FigureLegend key={saved.job} path={`/v1/jobs/${saved.figureJob}/files/figure-legend.md`} gaps={saved.figure.legend_gaps||[]} terms={initialSpec?.figure_presentation?.legend_terms??null}/>}
        {pointSource?.job===saved.figureJob&&pointRows.length>0&&<section aria-label="選択した点の試料・視野"><strong>この点の元データ</strong><button onClick={()=>setPointSource(null)} aria-label="点の元データを閉じる">×</button><SavedTable rows={pointRows} fieldLabels={fieldLabels} onSource={(field,region)=>onSource(field,region,saved.revision,saved.target,savedChannel,savedStructure)}/></section>}
        {!svgFiles.length&&<p>この設定では図を表示できません。測定表と出力条件を確認してください。</p>}
        {mode==="statistics"&&tableRows&&(saved.result.estimates
          ?<Folded summary="検定の詳細">{()=><SavedTable rows={tableRows} fieldLabels={fieldLabels} onSource={(field,region)=>onSource(field,region,saved.revision,saved.target,savedChannel,savedStructure)}/>}</Folded>
          :<SavedTable rows={tableRows} fieldLabels={fieldLabels} onSource={(field,region)=>onSource(field,region,saved.revision,saved.target,savedChannel,savedStructure)}/>)}
        {mode==="statistics"&&saved.result.omnibus&&<p>全体検定 {String(saved.result.omnibus.method)} · p = {formatValue(saved.result.omnibus.p_value)}</p>}
        {/* With a result summary (it states n and its breakdown) the full count table is one click away;
            without one (associations, several groups, descriptions) it stays open, so n is always in view (S-03, S-07). */}
        {mode==="statistics"&&Array.isArray(saved.result.counts)&&(saved.result.estimates
          ?<Folded summary="数の内訳（観測・視野・独立実験単位）">{()=><SavedTable rows={saved.result.counts as Record<string,unknown>[]} fieldLabels={fieldLabels} onSource={(field,region)=>onSource(field,region,saved.revision,saved.target,savedChannel,savedStructure)}/>}</Folded>
          :<SavedTable rows={saved.result.counts as Record<string,unknown>[]} fieldLabels={fieldLabels} onSource={(field,region)=>onSource(field,region,saved.revision,saved.target,savedChannel,savedStructure)}/>)}
        {!!saved.result.warnings?.length&&<details><summary>解析上の注意</summary><ul>{saved.result.warnings.map(value=><li key={value}>{comparisonWarnings[value]||commonWarnings[value]||descriptiveWarning(value)}</li>)}</ul></details>}
        {!!saved.result.plot_data?.length&&<Folded summary="図の元データ">{()=><SavedTable rows={saved.result.plot_data!} fieldLabels={fieldLabels} onSource={(field,region)=>onSource(field,region,saved.revision,saved.target,savedChannel,savedStructure)}/>}</Folded>}
        <details><summary>元の視野{saved.historical?"（保存時の解析版）":""}</summary>{(saved.sources||[]).map(source=><button key={source.field} onClick={()=>onSource(source.field,undefined,saved.revision,saved.target,savedChannel,savedStructure)}>{items.find(item=>item.fieldId===source.field)?.label||source.label}</button>)}</details>
      </>:<p className={styles.empty}>計算した結果とグラフをここに表示します。</p>}
    </div>
  </section>;
}

/** A figure at the proportions of its printed size: a 50 mm panel is not stretched to a page width (FU-05). */
function VectorFigure({path,widthMm,alt="保存された解析結果のグラフ"}:{path:string;widthMm?:number;alt?:string}){const url=usePrivateImage(path);return url?<img className={styles.figure} style={widthMm?{maxWidth:`${Math.round(widthMm*6)}px`}:undefined} src={url} alt={alt}/>:<p role="status">図を読み込み中…</p>;}
/** The paper's figure legend, drafted from the saved result (FL-03). Bracketed gaps are facts the workspace does not
 * record (FL-05); the researcher fills them here before copying. The draft is Markdown (a bold title); the box and
 * the copy hold plain text, as a manuscript takes it. */
type LegendTerms={cell_line?:string|null;treatment?:string|null;stains?:string|null};
/** The gap each proposed term fills; numbers in the legend always come from the saved result (FM-01, FM-02). */
const termGaps:Array<[keyof LegendTerms,string]>=[["cell_line","[Cell line]"],["treatment","[treatment and duration]"],["stains","[antibody or dye for each stain]"]];
function FigureLegend({path,gaps,terms}:{path:string;gaps:string[];terms?:LegendTerms|null}){
  const [text,setText]=useState(""),[note,setNote]=useState(""),[filled,setFilled]=useState<string[]>([]);
  // A redraw of the same result brings a new draft. What the researcher wrote stays; the new draft waits
  // until they take it.
  const edited=useRef(false),taken=useRef(""),[pending,setPending]=useState<{draft:string;used:string[]}|null>(null);
  function take(draft:string,used:string[]){taken.current=draft;edited.current=false;setText(draft);setFilled(used);setPending(null);}
  const proposed=JSON.stringify(terms??null);
  useEffect(()=>{let live=true;void fetchBlob(path).then(blob=>blob.text()).then(value=>{if(!live)return;let draft=plainFigureLegend(value);const used:string[]=[];
    for(const [key,gap] of termGaps){const term=terms?.[key];if(term&&draft.includes(gap)){draft=draft.replaceAll(gap,term);used.push(gapNames[gap]);}}
    if(edited.current)setPending(draft===taken.current?null:{draft,used});else take(draft,used);}).catch(()=>{if(live&&!edited.current)setText("");});return()=>{live=false;};},[path,proposed]);// eslint-disable-line react-hooks/exhaustive-deps -- terms is read by its content
  if(!text)return null;
  const open=gaps.filter(gap=>text.includes(gap));
  return <section className={styles.legendDraft} aria-label="Figure legend の下書き">
    <div className={styles.legendHead}><strong>Figure legend</strong><button type="button" onClick={()=>void navigator.clipboard.writeText(text).then(()=>setNote("コピーしました")).catch(()=>setNote("コピーできませんでした"))}>コピー</button>{note&&<span role="status">{note}</span>}</div>
    {filled.length>0&&<p className={styles.figureHint}>AI の提案から記入：{filled.join("、")}。内容を確認してください</p>}
    {open.length>0&&<p className={styles.figureHint}>未記入：{open.map(gap=>gapNames[gap]||gap).join("、")}</p>}
    {pending&&<p role="status" className={styles.figureHint}>図を描き直したため、Figure legend の下書きが変わりました。記入した内容はそのまま残しています。<button type="button" onClick={()=>take(pending.draft,pending.used)}>新しい下書きに置き換える</button></p>}
    <textarea aria-label="Figure legend" value={text} rows={Math.min(12,Math.max(5,Math.ceil(text.length/90)))} onChange={event=>{edited.current=true;setText(event.target.value);}}/>
  </section>;
}
const gapNames:Record<string,string>={"[Cell line]":"細胞株","[treatment and duration]":"処理と時間","[antibody or dye for each stain]":"抗体・色素"};
/** The columns a researcher reads first (N-06): the field to open, its run and group, the region and the value. */
const leadingKeys=["field_id","pair","condition","experimental_unit","region_id","nucleus_id","value"];
/** What one saved observation (a region's value) is read by; the run and group already name its unit. */
const observationKeys=["field_id","pair","condition","region_id","nucleus_id","value"];
/** Saved versions and internal identifiers: kept with every row, read on request. */
const recordKey=(key:string)=>key==="observation_id"||key==="region_set_id"||key.endsWith("_revision_id");
function SavedTable({rows,fieldLabels,onSource}:{rows:Record<string,unknown>[];fieldLabels:Record<string,string>;onSource:(fieldId:string,regionId?:number)=>void}) {
  const all=[...new Set(rows.flatMap(row=>Object.keys(row)))];
  // Observation rows show where each value is and the value; their bookkeeping is folded with the identifiers.
  const observations=all.includes("observation_id"),folded=(key:string)=>recordKey(key)||observations&&!observationKeys.includes(key);
  const keys=[...leadingKeys.filter(key=>all.includes(key)&&!folded(key)),...all.filter(key=>!leadingKeys.includes(key)&&!folded(key))],records=all.filter(folded);
  const names:Record<string,string>={pair:"実験回",experimental_unit:"実験単位",sample:"試料",acquisition_date:"撮影日",exclusion_reason:"除外理由",gate_selected:"選別で採用",selection_status:"採用",channel_id:"染色",observation_id:"観測",region_set_id:"領域の種類",mask_revision_id:"輪郭の版",analysis_revision_id:"解析版",field_id:"視野",region_id:"領域番号",nucleus_id:"親核番号",value:"測定値",condition:"群",input_rows:"入力観測数",excluded:"除外観測数",manual_edits:"手作業の修正",gate_unselected:"選別の対象外数",missing_metric_selected:"採用対象の測定値欠測数",selected_rows:"採用観測数",mean:"平均値",median:"中央値",q1:"第1四分位",q3:"第3四分位",minimum:"最小値",maximum:"最大値",p_value:"p 値",p_adjusted:"補正 p 値",p_holm:"Holm補正 p 値",estimate:"推定値",coefficient:"相関係数",ci_low:"95% CI 下限",ci_high:"95% CI 上限",n:"対象数",missing_reason:"欠測理由",reason:"理由",group_a:"群 A",group_b:"群 B",observations:"採用観測数",input_fields:"入力視野数",selected_fields:"採用視野数",excluded_failed_fields:"除外した失敗視野数",samples:"試料数",input_units:"入力独立実験単位数",experimental_units:"採用独立実験単位数",explicitly_excluded_units:"除外独立実験単位数",complete_pairs:"完全ペア数",effect:"効果量",effect_name:"効果量の種類",method:"方法",scope:"対象",status:"状態",
    // Channel-neutral positivity (channel gate): the judged channel is named in the result, not here.
    channel_mean:"判定チャンネルの平均輝度",channel_positive:"陽性と判定",channel_excluded:"判定から除外",channel_saturated:"判定チャンネルの飽和",channel_gate_status:"判定の状態",channel_gate_reason:"判定の理由",channel_gate_threshold:"判定のしきい値",channel_control_field:"対照視野",channel_missing_reason:"判定値の欠測理由",gfp_positive:"GFP陽性と判定",positive_count:"陽性数",negative_count:"陰性数",unclassified_count:"未判定数",evaluable_count:"判定できた数",positive_fraction:"陽性の割合"};
  const statuses:Record<string,string>={selected:"採用",no_regions:"領域なし",no_selected_values:"採用できる測定値なし",excluded:"除外",missing:"欠測",
    // Channel-neutral positivity: each nucleus's judgement and its reason (values and keys are unchanged).
    positive:"陽性",negative:"陰性",unclassified:"未判定",control:"対照",failed:"解析に失敗",measured:"測定済み",
    channel_negative_control:"陰性対照",gfp_negative_control:"陰性対照（GFP）",negative_control:"陰性対照",
    above_threshold:"しきい値より高い",at_or_below_threshold:"しきい値以下",nucleus_excluded:"除外した核",field_excluded:"除外した視野",
    channel_intensity_missing:"判定チャンネルの値なし",channel_threshold_missing:"しきい値を決定できない"};
  const statusKeys=new Set(["status","selection_status","channel_gate_status","channel_gate_reason"]);
  const cell=(row:Record<string,unknown>,key:string,index:number)=>key==="field_id"&&typeof row[key]==="string"?<button style={{maxWidth:"14em",whiteSpace:"normal",overflowWrap:"anywhere"}} onClick={()=>onSource(row[key] as string,typeof row.region_id==="number"?row.region_id:undefined)}>{fieldLabels[row[key]]||`視野 ${index+1}`}</button>:statusKeys.has(key)&&typeof row[key]==="string"?statuses[row[key]]||row[key]:typeof row[key]==="boolean"?(row[key]?"はい":"いいえ"):row[key]!==null&&typeof row[key]==="object"?<span style={{whiteSpace:"normal",overflowWrap:"anywhere"}}>{JSON.stringify(row[key])}</span>:formatValue(row[key]);
  // On an observation row `excluded` is that region's flag, not a count.
  const head=(key:string)=><th key={key} scope="col" className={key==="field_id"?styles.stickyColumn:undefined} style={{whiteSpace:"normal",overflowWrap:"anywhere",maxWidth:"8em"}}>{observations&&key==="excluded"?"除外":names[key]||key}</th>;
  const body=(columns:string[])=><tbody>{rows.map((row,index)=><tr key={index}>{columns.map(key=><td key={key} className={key==="field_id"?styles.stickyColumn:undefined}>{cell(row,key,index)}</td>)}</tr>)}</tbody>;
  const fieldColumn=all.includes("field_id")?["field_id"]:[];
  return <><div className={styles.tableScroll} tabIndex={0}><table><thead><tr>{keys.map(head)}</tr></thead>{body(keys)}</table></div>
    {records.length>0&&<Folded summary="記録の詳細" className={styles.recordDetails}>{()=><div className={styles.tableScroll} tabIndex={0}><table><thead><tr>{[...fieldColumn,...records].map(head)}</tr></thead>{body([...fieldColumn,...records])}</table></div>}</Folded>}</>;
}

/** A folded section draws its content once opened: a saved table can hold every observation, and thousands of
 * hidden rows would slow the page for everyone who never opens it (N-03). */
function Folded({summary,className,children}:{summary:string;className?:string;children:()=>ReactNode}){
  const [open,setOpen]=useState(false);
  return <details className={className} onToggle={event=>setOpen(event.currentTarget.open)}><summary>{summary}</summary>{open&&children()}</details>;
}

/** A distribution of a two-group design read by run: each saved field median in its run and group.
 * No value is combined and nothing is tested, so it stays available before independence is confirmed. */
function RunMedians({design,summary,metricLabel,unit,reported,missing,onEditExperiment}:{design:ExperimentDesign;summary:Array<Record<string,unknown>>;metricLabel:string;unit:string;reported:ShowcaseDataset["reported"];missing:MissingSummary|null;onEditExperiment?:()=>void}){
  const table=runTable(design,summary);
  if(!table)return missing?<><MissingLead summary={missing}/><MissingNucleoli summary={missing}/></>:null;
  // The same layout as a comparison (RS-08): a heading, the values, and the basis line that states the premise once.
  const unresolved=missing?missing.rows.reduce((sum,row)=>sum+row.missing,0):0,nuclei=missing?missing.rows.reduce((sum,row)=>sum+row.nuclei,0):0;
  const basis:ResultBasis={label:tidy([design.independence_confirmed?"分布":"記述統計",`n = ${table.runs.length} 回`,missing&&unresolved?`核小体を確定できない核 ${unresolved} / ${nuclei} は欠測`:""].filter(Boolean).join(" · ")),
    reason:design.independence_confirmed?null:"実験回の独立性が未確認のため、検定と信頼区間は算出していません。",
    action:design.independence_confirmed?null:"experiment"};
  return <section className={styles.summary} aria-label="実験回と群ごとの値">
    <h3 className={styles.headline}>{tidy(`${metricLabel}：視野ごとの中央値${unit?`（${unit}）`:""}`)}</h3>
    <ResultBasisLine basis={basis} onEditExperiment={onEditExperiment}/>
    {missing?.warnings.map(warning=><p key={String(warning.run)} role="status" className={styles.missingWarning}>{warning.run?`実験回 ${warning.run} で、`:""}群の間の欠測の割合が {formatNumber(warning.difference_points)} ポイント違います（基準 {missing.warning_points} ポイント）。処理に関わる選別の偏りが残っている可能性があります。</p>)}
    <table><thead><tr><th scope="col">実験回</th>{table.groups.map(group=><th key={group.id} scope="col">{group.label}{group.id===design.control_group_id?"（対照）":""}</th>)}</tr></thead>
      <tbody>{table.runs.map(run=><tr key={run.id}><th scope="row">{run.label}</th>{run.cells.map((cell,index)=><td key={table.groups[index].id}>{cell.length?cell.map(value=>formatValue(value)).join("、"):"—"}</td>)}</tr>)}</tbody></table>
    {missing&&<details><summary>核小体を確定できない核の内訳</summary><MissingNucleoli summary={missing}/></details>}
    {reported&&<ReportedSource reported={reported}/>}
  </section>;
}

/** A run table value as the sentence writes it; differences carry their sign. */
const runValue=(value:number|null|undefined,signed=false)=>value==null?"—":`${value<0?"−":signed&&value>0?"+":""}${formatNumber(Math.abs(value))}`;

/** What the image source reports and how this demo measures, read after the result and folded (N-06). */
function ReportedSource({reported}:{reported:NonNullable<ShowcaseDataset["reported"]>}){
  return <><p className={styles.reportedLine}><strong>出典の報告</strong>{reported.comparison}：{reported.direction}</p>
    <details className={styles.reported}><summary>出典の報告と、このデモでの測定</summary>
    <p><strong>出典の報告</strong>{reported.comparison}：{reported.direction}。{reported.quantity}（{reported.source}）</p>
    <p><strong>このデモでの測定</strong>以下は、この公開画像を Cytellect で測った値です。{reported.scope}</p>
    {reported.independence&&<p><strong>実験回の独立性</strong>{reported.independence}</p>}</details></>;
}

/** The comparison stated in words first (S-01–S-07); every number is the saved result's. */
/** API warnings that change how this result is read, shown under the points; the rest stay in 「解析上の注意」 (NT-05). */
const READ_WARNINGS=new Set(["channel_gate_saturated_nuclei_present","channel_gate_selection_and_outcome_share_channel",
  "few_independent_units_model_assumptions_and_power_require_review","acquisition_batches_partially_unbalanced_no_batch_adjustment",
  "explicitly_excluded_failed_fields_have_unknown_observation_counts"]);
const EXPLORATORY_WARNING="channel_gate_exploratory_threshold_without_negative_control";

/** The comparison as a heading, up to four points and one basis line (RS-01–RS-07); the premises are stated once,
 * in the basis line (NT-01, NT-02). Every number is the saved result's. */
/** The summary of a saved comparison as the card shows it; the discussion is sent the same heading and points. */
export function shownSummary(estimates:ComparisonEstimates,comparison:SavedComparison,metricLabel:string,unit:string,warnings:string[],missing:MissingSummary|null,testable=false){
  const unresolved=missing?missing.rows.reduce((sum,row)=>sum+row.missing,0):0,nuclei=missing?missing.rows.reduce((sum,row)=>sum+row.nuclei,0):0;
  return summarize(estimates,comparison,metricLabel,unit,{exploratory:warnings.includes(EXPLORATORY_WARNING),
    missing:missing&&unresolved?`核小体を確定できない核 ${unresolved} / ${nuclei} は欠測`:null,testable});
}

function ResultSummaryCard({estimates,comparison,metricLabel,unit,warnings,counts,reported,missing,onEditExperiment,testable=false}:{estimates:ComparisonEstimates;comparison:SavedComparison;metricLabel:string;unit:string;warnings:string[];counts:ReturnType<typeof breakdown>;reported:ShowcaseDataset["reported"];missing:MissingSummary|null;onEditExperiment?:()=>void;testable?:boolean}){
  const summary=shownSummary(estimates,comparison,metricLabel,unit,warnings,missing,testable);
  const cautions=[...summary.cautions,...warnings.filter(code=>READ_WARNINGS.has(code)).map(code=>comparisonWarnings[code]||commonWarnings[code]).filter((value):value is string=>!!value)];
  // The demo says what the measured value means, for visitors who are not biologists (DM-11).
  const hint=useShowcaseUi().enabled?METRIC_HINTS[estimates.metric]:undefined;
  return <section className={styles.summary} aria-label="結果のまとめ">
    <h3 className={styles.headline}>{summary.heading}</h3>
    {hint&&<p className={styles.hint} data-term-hint>{hint}</p>}
    {summary.points.length>0&&<ul className={styles.points}>{summary.points.map(value=><li key={value}>{value}</li>)}</ul>}
    <ResultBasisLine basis={summary.basis} onEditExperiment={onEditExperiment}/>
    {missing?.warnings.map(warning=><p key={String(warning.run)} role="status" className={styles.missingWarning}>{warning.run?`実験回 ${warning.run} で、`:""}群の間の欠測の割合が {formatNumber(warning.difference_points)} ポイント違います（基準 {missing.warning_points} ポイント）。処理に関わる選別の偏りが残っている可能性があります。</p>)}
    {cautions.length>0&&<ul className={styles.cautions}>{cautions.map(value=><li key={value}>{value}</li>)}</ul>}
    {/* With few runs the run values carry the result, so they are shown open (S-07). */}
    {estimates.runs.length>0&&<details open={estimates.runs.length<5}><summary>実験回ごとの値</summary><table><thead><tr><th>実験回</th><th>{estimates.control}</th><th>{estimates.treatment}</th><th>差（{estimates.treatment} − {estimates.control}）{estimates.scale==="fraction"?" / ポイント":""}</th></tr></thead>
      <tbody>{estimates.runs.map(run=><tr key={run.pair}><th>{run.pair}</th><td>{runValue(run.control)}</td><td>{runValue(run.treatment)}</td><td>{runValue(run.difference,true)}</td></tr>)}</tbody></table></details>}
    <details><summary>n の内訳と除外</summary><ul>{counts.groups.map(value=><li key={value}>{value}</li>)}</ul>
      <p>{counts.exclusions.length?"除外・欠測（実験回ごと）":"除外・欠測：なし"}</p>{counts.exclusions.length>0&&<ul>{counts.exclusions.map(value=><li key={value}>{value}</li>)}</ul>}
      {missing&&<MissingNucleoli summary={missing}/>}
      <ul className={styles.cautions}>{summary.notes.map(value=><li key={value}>{value}</li>)}</ul></details>
    {reported&&<ReportedSource reported={reported}/>}
  </section>;
}

/** The method, n and p in one line; for a descriptive result it opens to why, with the one place to fix it (RS-04, NT-01). */
function ResultBasisLine({basis,onEditExperiment}:{basis:ResultBasis;onEditExperiment?:()=>void}){
  if(!basis.reason)return <p className={styles.basis}>{basis.label}</p>;
  return <details className={styles.basis}><summary>{basis.label}</summary><p>{basis.reason}{basis.action==="experiment"&&onEditExperiment&&<> <button type="button" onClick={onEditExperiment}>実験デザインを編集</button></>}</p></details>;
}

const missingReasons:Record<string,string>={no_candidate:"核小体が見つからない",indeterminate:"判定できない",empty_after_subtraction:"核質が残らない"};
const reasonText=(reasons:Record<string,number>)=>Object.entries(reasons).map(([reason,count])=>`${missingReasons[reason]||reason} ${count}`).join("、");
const percent=(part:number,whole:number)=>whole?`${(part/whole*100).toLocaleString(undefined,{maximumFractionDigits:1})}%`:"—";

/** The one piece of earlier work a result waits for (genellect/cytellect#257 decision 11), in one line that opens that
 * screen: 「画像：未測定 3 視野 →」. The arrow is a mark, not part of the name read aloud. */
function RemainingLine({work,onOpen}:{work:RemainingWork;onOpen:(work:RemainingWork)=>void}){
  return <button type="button" className={styles.remaining} onClick={()=>onOpen(work)}>{work.label}<span aria-hidden="true"> →</span></button>;
}

/** Right under the result sentence (Q-05): what the values describe, the missing nuclei over all nuclei
 * and the within-run warning. A missing warning does not mean that no selection bias remains. */
function MissingLead({summary}:{summary:MissingSummary}){
  const missing=summary.rows.reduce((sum,row)=>sum+row.missing,0),nuclei=summary.rows.reduce((sum,row)=>sum+row.nuclei,0);
  return <div className={styles.missingLead}>
    <p><strong>核小体を確定できた核の値です。</strong>確定できない核 {missing} / {nuclei}（{percent(missing,nuclei)}）は欠測として残しています。</p>
    {summary.warnings.map(warning=><p key={String(warning.run)} role="status" className={styles.missingWarning}>{warning.run?`実験回 ${warning.run} で、`:""}群の間の欠測の割合が {formatNumber(warning.difference_points)} ポイント違います（基準 {summary.warning_points} ポイント）。処理に関わる選別の偏りが残っている可能性があります。</p>)}
  </div>;
}

/** Every group and unit's missing nuclei over all nuclei, always shown with the result (Q-05). */
function MissingNucleoli({summary}:{summary:MissingSummary}){
  // Indeterminate nuclei by group and unit, only when there are any (an always-zero column says nothing).
  const indeterminate=summary.rows.some(row=>(row.reasons.indeterminate??0)>0);
  return <div className={styles.missing} role="group" aria-label="核小体を確定できない核の内訳">
    <p>核小体を確定できない核の内訳（分母：全核）</p>
    <div className={styles.tableScroll} tabIndex={0}><table><thead><tr><th scope="col">群</th><th scope="col">実験単位</th><th scope="col">欠測 / 全核</th>{indeterminate&&<th scope="col">うち判定不能</th>}<th scope="col">除外</th></tr></thead>
      <tbody>{summary.rows.map(row=><tr key={`${row.condition}:${row.experimental_unit}`}><th scope="row">{row.condition}</th><td>{row.experimental_unit}</td><td title={reasonText(row.reasons)}>{row.missing} / {row.nuclei}（{percent(row.missing,row.nuclei)}）</td>{indeterminate&&<td>{row.reasons.indeterminate??0}</td>}<td>{row.excluded}</td></tr>)}</tbody></table></div>
  </div>;
}
