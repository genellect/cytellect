import recipeDefaults from "./recipe-defaults.json";
import type { components } from "./generated";
export type Point = [number,number];
export type Session = {authenticated:boolean;retention_hours:number;demo:boolean};
export type Workspace = {id:string;title:string;active_revision:string|null;expires:number;bytes:number};
export type Metadata = Required<components["schemas"]["FieldMetadata"]>;
export type Field = {id:string;metadata:Metadata;image_info:{shape:[number,number];dtype:string;legacy:boolean;channel_roles?:string[]};synthetic:boolean};
export type Background = Required<components["schemas"]["Background"]>;
export type Recipe = Required<components["schemas"]["Recipe"]>;
export type Exclusion = Required<components["schemas"]["Exclusion"]>;
export type Config = {recipe:Recipe;backgrounds:Record<string,Background>;exclusions:Exclusion[];field_ids?:string[]};
export type Revision = {id:string;parent_id:string|null;state:string;reviewed:boolean;created:number;config:Config};
export type Job = {id:string;revision_id:string;kind:string;state:string;created:number;error:string|null;attempts:number};
export type Cell = Record<string,string|number|boolean|null> & {field_id:string;nucleus_id:number;condition:string;excluded:boolean;gfp_positive:boolean};
export type Measurements = {cells:Cell[];nucleoli:Cell[];manual_rois?:Cell[];field_failures:Array<{field_id:string;error:string}>;invalidated_nucleoli?:string[];engine_provenance?:Record<string,{engine:string}>;field_status?:Record<string,string>};
export type Contour = {id:number;points:Point[]};
export type Masks = Record<"nuclei"|"nucleoli"|"manual",Contour[]>;
export type Layer = "nuclei"|"nucleoli"|"manual";
export type Operation = "select"|"background"|"add"|"replace"|"delete"|"merge"|"split";
export type Edit = {field_id:string;layer:Layer;operation:Exclude<Operation,"select"|"background">;ids:number[];polygon:Point[];parent_id:number|null};
export const defaultRecipe = recipeDefaults as Recipe;
export const metricLabels: Record<string,string> = {ncl_log2_nucleoplasm_over_nucleoli:"NCL log₂ 核質 / 核小体",ncl_legacy_release:"NCL 互換指標（核全体 / 高輝度）",ncl_nucleus_mean_corrected:"核内NCL平均（背景補正）",gfp_mean_corrected:"核内GFP平均（背景補正）",nucleolar_area_fraction:"核小体 / 核の面積割合"};
export function formatValue(value:unknown):string { if(value === null || value === undefined) return "—"; if(typeof value==="number") return Number.isFinite(value) ? Number(value.toPrecision(5)).toLocaleString("en-US",{maximumFractionDigits:5}):"—"; return String(value); }

export const fieldRoles = (field?:Field):string[] => field?.image_info.channel_roles ?? ["dapi","ncl","gfp"];

const qualityReasons:Record<string,string>={ncl_not_measured_recipe:"NCL対象外",no_compartment:"比の領域不足",nonpositive_signal:"補正値≤0",native_ratio_not_defined_in_legacy:"比は対象外"};
export const qualityReasonLabel=(reason:unknown):string=>typeof reason==="string"?(qualityReasons[reason]??reason):"";
