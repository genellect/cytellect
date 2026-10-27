import {comparisonRequest, comparisonSelection, FIELD_SUMMARY_METRICS, type ComparisonChoices, type ComparisonMetric, type Metadata, type GfpSelectionChoice} from "../../../lib/workspace/comparison-adapter";
import {metricUsesChannel} from "../../../lib/workspace/metric-catalog";
import {defaultFigureEdits} from "../../../lib/figure-controls";
import type {AssociationRequest} from "../../../lib/common-statistics";
import type {MeasurementRow} from "../../../lib/workspace/api-adapter";

export type ResultOperation = "distribution" | "comparison" | "association";
export const emptyMetadata: Metadata = {condition:null,sample:null,experimental_unit:null,pair:null,acquisition_date:null,repeat_length:null};
/** The metric a saved statistics block names, in the selector's terms; null when none was named (a proposal with no metrics). */
export function restoredMetric(statistics:{metric?:string|null}):string|null{
  if(!statistics.metric)return null;
  return statistics.metric==="ncl_log2_nucleoplasm_over_nucleoli"?"log2_nucleoplasm_over_nucleolus":statistics.metric;
}
/** The numeric renderer names its explicitly declared formats figure.<format>. */
export function numericFigureFiles(figure:{source_files?:string[];formats?:string[]}):string[]{
  return [...new Set([...(figure.source_files||[]),...(figure.formats||[]).filter(format=>["svg","pdf","png"].includes(format)).map(format=>`figure.${format}`)])];
}
export interface ResultDesign {
  operation: ResultOperation; metric: string; channel: string | null; regionSet: string;
  paired: boolean; rank: boolean; unit: string; pairing: string; confirmed: boolean;
  contrasts: string[][]; xMetric: string; xChannel: string | null;
  gfp?: GfpSelectionChoice | null;
  /** Request treatment − control estimates (a declared two-group design). */
  estimates?: boolean;
  /** False while the runs' independence is unconfirmed: compare descriptively, without a test. */
  inference?: boolean;
}
export type RenderPlot = ReturnType<typeof defaultFigureEdits> & {
  kind: "distribution" | "paired" | "box" | "violin" | "scatter" | "histogram" | "superplot" | "unit-mean-bar";
  preset: "custom"; language: "en"; y_min?: number; y_max?: number;point_size?:number;
  style?:{version:"1.0.0";series_colors:Record<string,string>;show_legend:boolean};
  y_tick_step?:number|null;
  axes?:{version:"1.0.0";x_scale:"linear"|"log10"|"log2";y_scale:"linear"|"log10"|"log2";x_min:number|null;x_max:number|null;x_tick_step:number|null};
};
const metrics = new Set(["area_px","area_um2","mean","median","integrated","mean_corrected","median_corrected","integrated_corrected","nucleolar_count","nucleolar_area_fraction","log2_nucleoplasm_over_nucleolus","nucleolar_area_px","nucleolar_area_um2","nucleolar_eccentricity",...FIELD_SUMMARY_METRICS]);
export function resultSelection(design: Pick<ResultDesign,"regionSet"|"metric"|"channel"|"gfp">) {
  if (!metrics.has(design.metric)) throw new Error("対応する測定項目を選択してください。");
  return comparisonSelection(design.regionSet, design.metric as ComparisonMetric, metricUsesChannel(design.metric) ? design.channel : null, design.gfp??null);
}
/** An association plots two region measurements; per-nucleus nucleolar summaries cannot be an axis. */
export function associationSupported(design: Pick<ResultDesign,"regionSet"|"metric"|"channel"|"gfp">) {
  try {return resultSelection(design).source === "region";} catch {return false;}
}
/** Horizontal-axis measurements that differ from the vertical one. */
export function associationAxes(metric: string, channel: string|null, xChannel: string|null) {
  return ["area_px","mean","median","integrated"].filter(value=>value!==metric||(!value.startsWith("area_")&&xChannel!==channel));
}
/** The API refuses brightness when an analysed region holds saturated or storage-limit pixels in that
 * channel (region_comparison_saturated_signal). The groups whose adopted regions do; a comparison
 * analyses only the groups of its pairs, an association every group. */
export function saturatedGroups(sources: Array<{field: string; result?: {rows: MeasurementRow[]; exclusions?: Array<{region_id: number | null}>}}>, fields: Record<string, {condition?: string | null}>, metric: string, channel: string | null) {
  const groups = new Set<string>();
  if (!channel || !metricUsesChannel(metric)) return groups;
  for (const source of sources) {
    const group = fields[source.field]?.condition?.trim();
    const excluded = new Set((source.result?.exclusions ?? []).map(item => item.region_id));
    if (group && (source.result?.rows ?? []).some(row => row.channel_id === channel && !excluded.has(row.region_id)
      && ((row.storage_limit_fraction ?? 0) > 0 || (row.acquisition_saturation_fraction ?? 0) > 0))) groups.add(group);
  }
  return groups;
}
/** Figure series are exactly the analysed groups: fields for a distribution, the
 * checked groups for a comparison (as sent in the request), all groups for an association. */
export function resultSeries(operation: ResultOperation, sourceFields: string[], conditions: string[], contrasts: string[][]): string[] {
  if (operation === "distribution") return sourceFields;
  if (operation === "association") return conditions;
  const compared = new Set(contrasts.flat());
  return [...conditions.filter(value => compared.has(value)), ...[...compared].filter(value => !conditions.includes(value))];
}
/** An edited order never adds or keeps a series outside the analysed groups. */
export function seriesOrder(order: string[], series: string[]): string[] {
  return order.length ? [...new Set([...order.filter(key => series.includes(key)), ...series.filter(key => !order.includes(key))])] : [];
}
/** The first figure of a comparison: a declared two-group experiment is drawn by run (fields, run
 * values, lines per run, mean and 95% CI; requirements F-01); other comparisons keep their default. */
export function comparisonKind(design: Pick<ResultDesign, "paired" | "estimates">): "superplot" | "paired" | "distribution" {
  return design.estimates ? "superplot" : design.paired ? "paired" : "distribution";
}
export function resultRequest(design: ResultDesign, fields: Record<string, Metadata>, plot: RenderPlot) {
  const selection = resultSelection(design);
  if (design.operation === "distribution") return {mode:"descriptive",selection,group_by:"field",figure_policy:{version:"2.0.0",layout:"field-pages"},plot:{...plot,kind:"distribution"}};
  const conditions = [...new Set(Object.values(fields).map(value=>value.condition?.trim()).filter((value):value is string=>!!value))];
  if (!design.confirmed || !design.unit.trim()) throw new Error("独立実験単位と解析条件を確認してください。");
  if (Object.values(fields).some(value=>!value.condition?.trim() || !value.sample?.trim() || !value.experimental_unit?.trim()
    || ((metricUsesChannel(design.metric) || (design.operation === "association" && metricUsesChannel(design.xMetric))) && !value.acquisition_date?.trim())
    || (design.operation === "comparison" && design.paired && !value.pair?.trim()))) throw new Error("視野の群・試料・独立実験単位と、必要な撮影日・対応ペアを入力してください。");
  if (design.operation === "comparison") {
    const choices: ComparisonChoices = {metric:design.metric as ComparisonMetric,channel:design.channel,regionSet:design.regionSet,
      design:design.paired?"paired":"independent",method:design.rank?"rank":"parametric",unitDefinition:design.unit,pairingBasis:design.pairing,
      contrasts:design.contrasts,independence:design.confirmed,acquisition:design.confirmed,sampling:design.confirmed,missingness:design.confirmed,
      kind:comparisonKind(design),width:plot.width_inches*25.4,height:plot.height_inches*25.4,yLabel:plot.y_label,gfp:design.gfp,estimates:design.estimates,inference:design.inference};
    const request = comparisonRequest(choices);
    return {...request,plot:{...request.plot,...plot,kind:comparisonKind(design)}};
  }
  const x = resultSelection({...design,metric:design.xMetric,channel:design.xChannel});
  if (selection.source !== "region" || x.source !== "region") throw new Error("相関には同じ領域の面積・輝度を選択してください。");
  if (JSON.stringify(x) === JSON.stringify(selection)) throw new Error("横軸と縦軸に異なる測定項目を選択してください。");
  const request: AssociationRequest = {mode:"region-association",version:design.gfp?"1.1.0":"1.0.0",x_selection:x,y_selection:selection,
    design:{kind:"independent",confirmed:true,unit_definition:design.unit.trim(),pairing_basis:null},conditions,
    acquisition_review:{confirmed:true,basis:"same-settings",field_batches:{},spatial_sampling_confirmed:true},missingness_confirmed:true,
    method:design.rank?"spearman":"pearson",scope:"per-condition",pooling_confirmed:false,
    aggregation:"field-median_sample-mean_unit-mean-v1",missingness_policy:"require-matched-unexcluded-units-v1",plot:{...plot,kind:"scatter"}};
  return request;
}

export function checkedPlot(width:number,height:number,fontSize:number,xLabel:string,yLabel:string,yMin:string,yMax:string): RenderPlot {
  const min=yMin.trim()?Number(yMin):undefined, max=yMax.trim()?Number(yMax):undefined;
  if (![width,height,fontSize].every(Number.isFinite) || width<76.2 || width>406.4 || height<25.4 || height>170 || fontSize<5 || fontSize>24
    || (min!==undefined&&!Number.isFinite(min)) || (max!==undefined&&!Number.isFinite(max)) || (min!==undefined&&max!==undefined&&min>=max)) throw new Error("図の寸法・文字サイズ・縦軸の範囲を確認してください。");
  return {...defaultFigureEdits(),kind:"distribution",preset:"custom",language:"en",width_inches:width/25.4,height_inches:height/25.4,font_size:fontSize,x_label:xLabel,y_label:yLabel,
    ...(min!==undefined?{y_min:min}:{}),...(max!==undefined?{y_max:max}:{})};
}

/** Saved per-field medians laid out by independent run and group (control first). Presentation
 * only: no value is combined, so a design whose independence is unconfirmed can still be read. */
export interface RunTable {groups:Array<{id:string;label:string}>;runs:Array<{id:string;label:string;cells:Array<Array<number|null>>}>}
export function runTable(design:{groups:Array<{id:string;label:string}>;control_group_id?:string|null;runs?:Array<{id:string;label:string}>|null;fields?:Record<string,{group_id:string;run_id:string}>|null},
  summary:Array<Record<string,unknown>>):RunTable|null{
  const groups=[...design.groups].sort((a,b)=>Number(b.id===design.control_group_id)-Number(a.id===design.control_group_id));
  const assigned=design.fields??{};
  const runs=(design.runs??[]).map(run=>({id:run.id,label:run.label,cells:groups.map(group=>summary
    .filter(row=>typeof row.field_id==="string"&&assigned[row.field_id]?.run_id===run.id&&assigned[row.field_id]?.group_id===group.id)
    .map(row=>typeof row.median==="number"&&Number.isFinite(row.median)?row.median:null))})).filter(run=>run.cells.some(cell=>cell.length));
  return groups.length>1&&runs.length?{groups,runs}:null;
}
