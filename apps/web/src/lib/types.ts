import recipeDefaults from "./recipe-defaults.json";
import type { components } from "./generated";
import type {AdoptedPlan,PlanResolution} from "./analysis-plan";
export type Point = [number,number];
export type Session = {authenticated:boolean;retention_hours:number;demo:boolean};
export type Workspace = {id:string;title:string;active_revision:string|null;expires:number;bytes:number;analysis_plan?:AdoptedPlan|null};
export type Metadata = Required<components["schemas"]["FieldMetadata"]>;
export type Field = {id:string;metadata:Metadata;image_info:{shape:[number,number];dtype:string;legacy:boolean;channel_roles?:string[]};synthetic:boolean};
export type Background = Required<components["schemas"]["Background"]>;
export type Recipe = Required<components["schemas"]["Recipe"]>;
export type Exclusion = Required<components["schemas"]["Exclusion"]>;
export type Config = {recipe:Recipe;backgrounds:Record<string,Background>;exclusions:Exclusion[];field_ids?:string[];plan_resolution?:PlanResolution|null};
export type Revision = {id:string;parent_id:string|null;state:string;reviewed:boolean;created:number;config:Config};
export type Job = {id:string;revision_id:string;kind:string;state:string;created:number;error:string|null;attempts:number;analysis_mode?:components["schemas"]["JobView"]["analysis_mode"];analysis_version?:string|null};
export type Cell = Record<string,string|number|boolean|null> & {field_id:string;nucleus_id:number;condition:string;excluded:boolean;gfp_positive:boolean};
export type Measurements = {cells:Cell[];nucleoli:Cell[];manual_rois?:Cell[];field_failures:Array<{field_id:string;reason:string;category?:string}>;invalidated_nucleoli?:string[];engine_provenance?:Record<string,{engine:string}>;nucleolar_failures?:Array<{field_id:string;nucleus_id:number}>;field_status?:Record<string,string>};
export type Contour = {id:number;points:Point[]};
export type Masks = Record<"nuclei"|"nucleoli"|"manual",Contour[]>;
export type Layer = "nuclei"|"nucleoli"|"manual";
export type Operation = "select"|"background"|"add"|"replace"|"delete"|"merge"|"split";
export type Edit = {field_id:string;layer:Layer;operation:Exclude<Operation,"select"|"background">;ids:number[];polygon:Point[];parent_id:number|null};
export const defaultRecipe = recipeDefaults as Recipe;
const measures:Record<string,string>={mean:"平均（原値）",median:"中央値（原値）",integrated:"積算（原値）",mean_corrected:"平均（背景補正）",median_corrected:"中央値（背景補正）",integrated_corrected:"積算（背景補正）"};
export const metricLabels: Record<string,string> = {
 ncl_log2_nucleoplasm_over_nucleoli:"NCL log₂ 核質 / 核小体",ncl_nucleoplasm_over_nucleoli:"NCL 核質 / 核小体",ncl_legacy_release:"NCL 互換指標（核全体 / 高輝度）",
 ...Object.fromEntries(Object.entries({nucleus:"核全体",nucleoli:"核小体",nucleoplasm:"核質"}).flatMap(([compartment,label])=>Object.entries(measures).map(([measure,name])=>[`ncl_${compartment}_${measure}`,`${label}NCL${name}`]))),
 ...Object.fromEntries(Object.entries(measures).map(([measure,name])=>[`gfp_${measure}`,`核内GFP${name}`])),
 nucleus_area_px:"核面積 / px²",nucleus_area_um2:"核面積 / µm²",nucleolar_area_px:"核小体総面積 / px²",nucleolar_area_um2:"核小体総面積 / µm²",nucleoplasm_area_px:"核質面積 / px²",nucleoplasm_area_um2:"核質面積 / µm²",nucleolar_count:"核小体候補数",nucleolar_area_fraction:"核小体 / 核の面積割合",
};
export function availableMetricIds({hasGfp,hasNcl,legacy,calibrated}:{hasGfp:boolean;hasNcl:boolean;legacy:boolean;calibrated:boolean}){return Object.keys(metricLabels).filter(key=>{
 if(key.endsWith("_um2")&&!calibrated)return false;
 if(key.startsWith("gfp_"))return hasGfp;
 if(key.startsWith("nucleus_area_"))return true;
 if(!hasNcl)return false;
 if(key==="ncl_legacy_release")return legacy;
 if(["ncl_nucleoplasm_over_nucleoli","ncl_log2_nucleoplasm_over_nucleoli"].includes(key))return !legacy;
 return true;
});}
export function formatValue(value:unknown):string {
 if(value===null||value===undefined)return "—";
 if(typeof value!=="number")return String(value);
 if(!Number.isFinite(value))return "—";
 const rounded=Number(value.toPrecision(5));
 // Preserve small nonzero measurements and p values rather than displaying zero.
 if(rounded!==0&&Math.abs(rounded)<0.0001)return rounded.toExponential();
 return rounded.toLocaleString("en-US",{maximumSignificantDigits:5});
}

export const fieldRoles = (field?:Field):string[] => field?.image_info.channel_roles ?? ["dapi","ncl","gfp"];

const qualityReasons:Record<string,string>={processing_failed:"核小体処理失敗",nucleolar_processing_failed:"核小体処理失敗",no_candidate:"核小体候補なし",indeterminate:"核小体判定困難",unclassified:"核小体未判定",review_required:"核小体再確認",none_after_edit:"核小体候補なし",ncl_not_measured_recipe:"NCL対象外",no_compartment:"比の領域不足",nonpositive_signal:"補正値≤0",native_ratio_not_defined_in_legacy:"比は対象外"};
export const qualityReasonLabel=(reason:unknown):string=>typeof reason==="string"?(qualityReasons[reason]??reason):"";
