import {comparisonRequest, comparisonSelection, type ComparisonChoices, type Metadata, type RegionComparisonMetric, type CompartmentComparisonMetric, type GfpSelectionChoice} from "../../../lib/workspace/comparison-adapter";
import {defaultFigureEdits} from "../../../lib/figure-controls";
import type {AssociationRequest} from "../../../lib/common-statistics";

export type ResultOperation = "distribution" | "comparison" | "association";
export const emptyMetadata: Metadata = {condition:null,sample:null,experimental_unit:null,pair:null,acquisition_date:null,repeat_length:null};
/** The numeric renderer names its explicitly declared formats figure.<format>. */
export function numericFigureFiles(figure:{source_files?:string[];formats?:string[]}):string[]{
  return [...new Set([...(figure.source_files||[]),...(figure.formats||[]).filter(format=>["svg","pdf","png"].includes(format)).map(format=>`figure.${format}`)])];
}
export interface ResultDesign {
  operation: ResultOperation; metric: string; channel: string | null; regionSet: string;
  paired: boolean; rank: boolean; unit: string; pairing: string; confirmed: boolean;
  contrasts: string[][]; xMetric: string; xChannel: string | null;
  gfp?: GfpSelectionChoice | null;
}
export type RenderPlot = ReturnType<typeof defaultFigureEdits> & {
  kind: "distribution" | "paired" | "box" | "violin" | "scatter" | "histogram";
  preset: "custom"; language: "en"; y_min?: number; y_max?: number;point_size?:number;
  style?:{version:"1.0.0";series_colors:Record<string,string>;show_legend:boolean};
  y_tick_step?:number|null;
  axes?:{version:"1.0.0";x_scale:"linear"|"log10"|"log2";y_scale:"linear"|"log10"|"log2";x_min:number|null;x_max:number|null;x_tick_step:number|null};
};
const metrics = new Set(["area_px","area_um2","mean","median","integrated","mean_corrected","median_corrected","integrated_corrected","nucleolar_count","nucleolar_area_fraction","log2_nucleoplasm_over_nucleolus"]);
export function resultSelection(design: Pick<ResultDesign,"regionSet"|"metric"|"channel"|"gfp">) {
  if (!metrics.has(design.metric)) throw new Error("対応する測定項目を選択してください。");
  return comparisonSelection(design.regionSet, design.metric as RegionComparisonMetric | CompartmentComparisonMetric,
    design.metric.startsWith("area_") || ["nucleolar_count","nucleolar_area_fraction"].includes(design.metric) ? null : design.channel,design.gfp??null);
}
export function resultRequest(design: ResultDesign, fields: Record<string, Metadata>, plot: RenderPlot) {
  const selection = resultSelection(design);
  if (design.operation === "distribution") return {mode:"descriptive",selection,group_by:"field",figure_policy:{version:"2.0.0",layout:"field-pages"},plot:{...plot,kind:"distribution"}};
  const conditions = [...new Set(Object.values(fields).map(value=>value.condition?.trim()).filter((value):value is string=>!!value))];
  if (!design.confirmed || !design.unit.trim()) throw new Error("独立実験単位と解析条件を確認してください。");
  if (Object.values(fields).some(value=>!value.condition?.trim() || !value.sample?.trim() || !value.experimental_unit?.trim()
    || ((!design.metric.startsWith("area_") || (design.operation === "association" && !design.xMetric.startsWith("area_"))) && !value.acquisition_date?.trim())
    || (design.operation === "comparison" && design.paired && !value.pair?.trim()))) throw new Error("視野の群・試料・独立実験単位と、必要な撮影日・対応ペアを入力してください。");
  if (design.operation === "comparison") {
    const choices: ComparisonChoices = {metric:design.metric as RegionComparisonMetric | CompartmentComparisonMetric,channel:design.channel,regionSet:design.regionSet,
      design:design.paired?"paired":"independent",method:design.rank?"rank":"parametric",unitDefinition:design.unit,pairingBasis:design.pairing,
      contrasts:design.contrasts,independence:design.confirmed,acquisition:design.confirmed,sampling:design.confirmed,missingness:design.confirmed,
      kind:design.paired?"paired":"distribution",width:plot.width_inches*25.4,height:plot.height_inches*25.4,yLabel:plot.y_label,gfp:design.gfp};
    const request = comparisonRequest(choices);
    return {...request,plot:{...request.plot,...plot,kind:design.paired?"paired":"distribution"}};
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
