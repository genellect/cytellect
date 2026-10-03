import { metricLabels, type Job } from "./types";
import { regionMetricLabels } from "./region-types";
import type {components} from "./generated";

type PagedOutput = components["schemas"]["PagedDescriptiveOutput"];
type FigurePolicy = components["schemas"]["DescriptiveFigurePolicy"];

export type DescriptiveSelection =
  | { source: "legacy-cell"; metric: string }
  | { source: "region"; region_set_id: string; channel_id: string | null; metric: string };

export type DescriptiveResult = {
  analysis_kind: "descriptive";
  revision_id: string;
  spec: { selection: DescriptiveSelection; figure_policy?:FigurePolicy; plot: { language: string; preset: string; group_order?:string[] } };
  metric: string;
  unit: string;
  counts: { observations: number; input_fields: number; selected_fields: number; excluded_failed_fields: number; experimental_units: null };
  selection: { input_rows: number; excluded: number; gate_unselected: number; missing_metric_selected: number };
  field_summary: Array<{ field_id: string; selected_rows: number; median: number | null; q1: number | null; q3: number | null; status: string }>;
  plot_data?: Array<Record<string, unknown>>;
  source_fields: Array<{ field_id: string; analysis_revision_id?:string; mask_sha256?:string; hash_format?:string; image_info?:{shape?:number[]}; region_set?: { label: string;region_set_id?:string;mask_revision_id?:string;source?:string }; channel_provenance?: Array<{ channel: { channel_id: string; label: string; stain: string | null } }> }>;
  excluded_failed_fields: Array<{ field_id: string; reason: string }>;
  figure: { source_files: string[]; descriptive_figure_version?:"1.0.0"|"1.0.1" } | PagedOutput;
  warnings: string[];
};

export const descriptiveTableFiles:Record<string,string>={"plot-data.csv":"全視野の元データ","field-summary.csv":"全視野の要約","selection.csv":"採用・除外の記録","missingness.csv":"欠測の記録","figure-caption.md":"図の説明","figure-data.json":"条件と出典","methods.md":"Methods"};
const presentationCodes = new Set(["figure_labels_overlap","figure_text_outside_canvas","japanese_font_not_installed","sans_serif_font_not_installed","figure_font_glyphs_unavailable"]);
type PageView = {index:number;fieldIds:string[];fieldNumbers:number[];files:{svg:string;pdf:string;png:string}};
export type DescriptiveFigureView =
 | {kind:"legacy";pages:PageView[]}
 | {kind:"ready";pages:PageView[];limits:number[];fieldCount:number}
 | {kind:"tables_only";code:string;failedPage:number|null;plannedPages:number;limits:number[]}
 | {kind:"invalid"};
const record=(value:unknown):value is Record<string,unknown>=>typeof value==="object"&&value!==null&&!Array.isArray(value);

// Validate saved display identities only. Values, limits and summaries are never recomputed here.
// An incomplete new manifest must not fall back to a previous single figure.
export function descriptiveFigureView(result:DescriptiveResult):DescriptiveFigureView{
 const raw:unknown=result.figure;
 if(!record(raw)||!Array.isArray(raw.source_files)||!raw.source_files.every(name=>typeof name==="string"))return {kind:"invalid"};
 const sourceFiles=raw.source_files as string[];
 if(!("figure_policy" in result.spec)&&(!("descriptive_figure_version" in raw)||raw.descriptive_figure_version==="1.0.0"||raw.descriptive_figure_version==="1.0.1")){
  if(!["figure.svg","figure.pdf","figure.png"].every(name=>sourceFiles.includes(name)))return {kind:"invalid"};
  return {kind:"legacy",pages:[{index:1,fieldIds:[],fieldNumbers:[],files:{svg:"figure.svg",pdf:"figure.pdf",png:"figure.png"}}]};
 }
 if(result.spec.figure_policy?.version!=="2.0.0"||result.spec.figure_policy.layout!=="field-pages"||raw.descriptive_figure_version!=="2.0.0"||
  !Array.isArray(raw.field_order)||!Array.isArray(raw.page_plan)||!raw.page_plan.length||!Array.isArray(raw.pages)||
  !Array.isArray(raw.y_limits)||raw.y_limits.length!==2||!raw.y_limits.every(value=>typeof value==="number"&&Number.isFinite(value))||!(raw.y_limits[0]<raw.y_limits[1])||
  !Array.isArray(raw.y_ticks)||!raw.y_ticks.every(value=>typeof value==="number"&&Number.isFinite(value))||
  typeof raw.source_result_sha256!=="string"||!/^[a-f0-9]{64}$/.test(raw.source_result_sha256)||!record(raw.files))return {kind:"invalid"};
 const expectedOrder=result.spec.plot.group_order?.length?result.spec.plot.group_order:result.field_summary.map(row=>row.field_id);
 const summaryIds=result.field_summary.map(row=>row.field_id);
 if(new Set(summaryIds).size!==summaryIds.length||expectedOrder.length!==summaryIds.length||new Set(expectedOrder).size!==expectedOrder.length||
  expectedOrder.some(id=>!summaryIds.includes(id))||raw.field_order.length!==expectedOrder.length||raw.field_order.some((id,index)=>id!==expectedOrder[index])||
  new Set(sourceFiles).size!==sourceFiles.length||Object.keys(raw.files).length!==sourceFiles.length)return {kind:"invalid"};
 for(const name of sourceFiles){
  const file=raw.files[name];
  if(!record(file)||typeof file.sha256!=="string"||!/^[a-f0-9]{64}$/.test(file.sha256)||!Number.isSafeInteger(file.bytes)||Number(file.bytes)<0||
   !Object.hasOwn(descriptiveTableFiles,name)&&!/^figure-[0-9]{3}\.(svg|pdf|png)$/.test(name))return {kind:"invalid"};
 }
 if(!["plot-data.csv","field-summary.csv","selection.csv","methods.md","figure-data.json","figure-caption.md"].every(name=>sourceFiles.includes(name)))return {kind:"invalid"};
 const plans:Array<{index:number;fieldIds:string[];fieldNumbers:number[]}>=[];
 let offset=0;
 for(const [index,plan] of raw.page_plan.entries()){
  if(!record(plan)||plan.page_index!==index+1||!Array.isArray(plan.field_ids)||!plan.field_ids.length||plan.field_ids.length>8||
   !Array.isArray(plan.field_numbers)||plan.field_ids.length!==plan.field_numbers.length||
   plan.field_ids.some((id,n)=>id!==expectedOrder[offset+n])||plan.field_numbers.some((number,n)=>number!==offset+n+1))return {kind:"invalid"};
  plans.push({index:index+1,fieldIds:plan.field_ids as string[],fieldNumbers:plan.field_numbers as number[]});offset+=plan.field_ids.length;
 }
 if(offset!==expectedOrder.length)return {kind:"invalid"};
 if(raw.status==="tables_only"){
  if(raw.pages.length||raw.font_metadata!==null||!record(raw.error)||typeof raw.error.code!=="string"||!presentationCodes.has(raw.error.code)||
   !(raw.error.page_index===null||Number.isInteger(raw.error.page_index)&&Number(raw.error.page_index)>=1&&Number(raw.error.page_index)<=plans.length)||sourceFiles.some(name=>name.startsWith("figure-")&&/\.(svg|pdf|png)$/.test(name)))return {kind:"invalid"};
  return {kind:"tables_only",code:raw.error.code,failedPage:raw.error.page_index as number|null,plannedPages:plans.length,limits:raw.y_limits as number[]};
 }
 if(raw.status!=="ready"||raw.error!==null||!record(raw.font_metadata)||raw.pages.length!==plans.length)return {kind:"invalid"};
 const pages:PageView[]=[];
 for(const [index,page] of raw.pages.entries()){
  if(!record(page)||page.page_index!==index+1||!record(page.files))return {kind:"invalid"};
  for(const suffix of ["svg","pdf","png"]){const name=`figure-${String(index+1).padStart(3,"0")}.${suffix}`;if(page.files[suffix]!==name||!sourceFiles.includes(name))return {kind:"invalid"};}
  pages.push({...plans[index],files:page.files as PageView["files"]});
 }
 if(sourceFiles.filter(name=>/^figure-[0-9]{3}\.(svg|pdf|png)$/.test(name)).length!==pages.length*3)return {kind:"invalid"};
 return {kind:"ready",pages,limits:raw.y_limits as number[],fieldCount:expectedOrder.length};
}

export function descriptiveRequest(selection:DescriptiveSelection,language:string,preset:string,savedPlot?:DescriptiveResult["spec"]["plot"]){
 return {mode:"descriptive",selection,group_by:"field",figure_policy:{version:"2.0.0",layout:"field-pages"},plot:{kind:"distribution",width_inches:7,height_inches:3,font_size:7,x_label:"",y_label:"",group_order:[],...savedPlot,preset,language}};
}

export function descriptiveRecovery(result:DescriptiveResult,language:string,preset:string){
 return {path:`/v1/revisions/${result.revision_id}/descriptive`,body:descriptiveRequest(result.spec.selection,language,preset,result.spec.plot)};
}

export function descriptiveJobs(jobs: Job[]) {
  return jobs.filter(job => job.kind === "statistics" && job.analysis_mode === "descriptive").toSorted((a, b) => b.created - a.created);
}

// An explicit selection remains selected while queued, failed, cancelled or not yet polled.
// In particular, a failed new figure must never silently resolve to a previous success.
export function selectedDescriptiveJob(jobs: Job[], selectedId: string, revisionId?: string) {
  const available = descriptiveJobs(jobs);
  if (selectedId) return available.find(job => job.id === selectedId);
  return available.find(job => job.revision_id === revisionId) ?? available[0];
}

export function sameDescriptiveSettings(result: DescriptiveResult, selection: DescriptiveSelection | undefined, language: string, preset: string) {
  const saved = result.spec.selection;
  if (!selection || saved.source !== selection.source || saved.metric !== selection.metric) return false;
  if (saved.source === "region" && selection.source === "region" && (saved.region_set_id !== selection.region_set_id || saved.channel_id !== selection.channel_id)) return false;
  return result.spec.plot.language === language && result.spec.plot.preset === preset;
}

export function savedDescriptiveLabel(result: DescriptiveResult) {
  const selection = result.spec.selection;
  if (selection.source === "legacy-cell") return metricLabels[selection.metric] ?? selection.metric;
  const field = result.source_fields[0];
  const region = field?.region_set?.label ?? selection.region_set_id;
  const metric = regionMetricLabels[selection.metric as keyof typeof regionMetricLabels] ?? selection.metric;
  if (selection.channel_id === null) return `${region} · ${metric}`;
  const channel = field?.channel_provenance?.find(item => item.channel.channel_id === selection.channel_id)?.channel;
  const label = channel ? `${channel.label}（標識: ${channel.stain ?? "未記録"}）` : "標識名未記録";
  return `${region} · ${label} · ${metric}`;
}

const statuses: Record<string, string> = { selected: "採用値あり", no_regions: "領域なし", no_selected_values: "採用可能な値なし" };
export function descriptiveFieldNumber(result:DescriptiveResult,fieldId:string){
  const order=result.spec.plot.group_order?.length?result.spec.plot.group_order:result.field_summary.map(row=>row.field_id);
  const index=order.indexOf(fieldId);
  return index<0?null:index+1;
}
export const descriptiveFieldStatus = (status: string) => statuses[status] ?? status;
const warnings: Record<string, string> = {
  descriptive_independence_not_assessed: "独立反復は評価していません。観測数・視野数を独立した実験反復数として扱わないでください。",
  acquisition_comparability_not_established: "撮影条件の比較可能性は未確認です。視野間の差を処置の効果と判断する前に、取得条件を確認してください。",
  missing_outcomes_excluded_inspect_fieldwise_missingness: "指標が欠測した観測は図に含まれません。視野ごとの欠測と理由を確認してください。",
  ncl_defined_regions_can_change_with_the_measured_ncl_distribution: "NCLから定義した領域は、測定対象であるNCLの分布とともに変化することがあります。",
  data_derived_or_manual_gfp_selection_requires_predeclared_or_independent_validation: "GFPの手動・データ由来の選別を含みます。事前に定めた条件または別データでの検証を確認してください。",
};
export const descriptiveWarning = (code: string) => warnings[code] ?? code;
