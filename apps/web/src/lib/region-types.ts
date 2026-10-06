import type { Contour, Point } from "./types";
import type { components } from "./generated";
import type {PlanResolution} from "./analysis-plan";

// OpenAPI is authoritative. Tuple/required refinements describe validated JSON responses.
type Schema=components["schemas"];
export type RegionChannel=Required<Schema["ChannelSpec"]>;
export type RegionCalibration=Schema["Calibration2D"];
export type RegionMetadata=Required<Schema["RegionFieldMetadata"]>;
export type RegionField=Omit<Schema["RegionFieldView"],"metadata"|"image_info">&{metadata:RegionMetadata;image_info:Omit<Required<Schema["RegionImageInfo"]>,"shape"|"channels">&{shape:[number,number];channels:RegionChannel[]}};
export type RegionNuclearRecipe=Omit<Required<Schema["RegionNuclearRecipe"]>,"detector">&{detector:Required<Schema["NuclearDetectorSpec"]>};
export type RegionRecipe=Required<Schema["RegionRecipe"]>|RegionNuclearRecipe;
export type RegionBackground=Omit<Schema["RegionBackground"],"polygon">&{polygon:Point[]};
export type RegionExclusion=Required<Schema["RegionExclusion"]>;
export type RegionConfig=Omit<Schema["RegionAnalysisRequest"],"recipe"|"backgrounds"|"exclusions">&{recipe:RegionRecipe;backgrounds:Record<string,Record<string,RegionBackground>>;exclusions:RegionExclusion[];analysis_kind?:"region-2d";field_snapshot?:Record<string,{metadata:RegionMetadata}>;plan_resolution?:PlanResolution|null};
export type RegionRevision={id:string;parent_id:string|null;state:string;reviewed:boolean;created:number;config:RegionConfig};
export type RegionMaskMetadata=Schema["RegionFieldMask"];
export type RegionMasks={regions:Contour[];metadata:RegionMaskMetadata};
export type RegionRow=Schema["RegionMeasurementRow"]|Schema["RegionMeasurementRowV2"];
export type RegionTable=Schema["RegionMeasurementTable"]|Schema["RegionMeasurementTableV2"];
export type RegionReport=Schema["RegionReport"]|Schema["RegionReportV2"];
export type RegionMeasurementPolicy=Schema["RegionMeasurementPolicy"]|Schema["RawIntensityPolicy"]|Schema["AutomaticBackgroundPolicy"];
export const regionRecipe:Required<Schema["RegionRecipe"]>={id:"region-2d",version:"1.0.0",region_set_id:"regions",label:"測定領域",source:"manual",defining_channel_id:null};
export const regionMetricLabels={area_px:"面積 / px²",area_um2:"面積 / µm²",mean:"平均（原値）",median:"中央値（原値）",integrated:"積算（原値）",mean_corrected:"平均（背景補正）",median_corrected:"中央値（背景補正）",integrated_corrected:"積算（背景補正）"};
export type RegionMetric=keyof typeof regionMetricLabels;
export type RegionComparisonRequest=Schema["RegionComparisonRequest"];

export function regionFigureOptions(recipe:RegionRecipe,fields:RegionField[],measurement?:RegionMeasurementPolicy|null){
 const channels=new Map<string,RegionChannel>();fields.forEach(field=>field.image_info.channels.forEach(channel=>channels.set(channel.channel_id,channel)));
 const selections=Object.entries(regionMetricLabels).flatMap(([key,label])=>{
  const metric=key as RegionMetric;
  if(measurement?.mode==="area_only"&&!metric.startsWith("area_"))return [];
  if(measurement?.mode==="raw_intensity"&&metric.endsWith("_corrected"))return [];
  if(metric==="area_um2"&&!fields.every(field=>field.image_info.calibration))return [];
  if(metric.startsWith("area_"))return [{id:metric,label:`${recipe.label} · ${label}`,selection:{source:"region" as const,region_set_id:recipe.region_set_id,channel_id:null as string|null,metric}}];
  return [...channels.values()].map(channel=>({id:`${channel.channel_id}-${metric}`,label:`${recipe.label} · ${channel.label} · ${label}`,selection:{source:"region" as const,region_set_id:recipe.region_set_id,channel_id:channel.channel_id as string|null,metric}}));
 });
 return selections;
}
