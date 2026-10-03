import type {RegionConfig,RegionMeasurementPolicy} from "./region-types";

// UI choices only; scientific policy and report types come from OpenAPI.
export type RegionMeasurementMode="area_and_intensity"|"area_only";
export function isAreaOnly(measurement?:RegionMeasurementPolicy|null){
 return measurement?.version==="1.0.0"&&measurement.mode==="area_only";
}
export function measurementMode(measurement?:RegionMeasurementPolicy|null):RegionMeasurementMode{
 return isAreaOnly(measurement)?"area_only":"area_and_intensity";
}
export function changeRegionMeasurement(config:RegionConfig,mode:RegionMeasurementMode):RegionConfig{
 if(measurementMode(config.measurement)===mode)return config;
 const measurement=mode==="area_only"?{version:"1.0.0" as const,mode:"area_only" as const}:null;
 const next={...config,backgrounds:{},...(config.plan_resolution?{plan_resolution:{...config.plan_resolution,version:"1.1.0" as const,measurement,changes_acknowledged:false}}:{})};
 if(mode==="area_only")next.measurement={version:"1.0.0",mode:"area_only"};
 else delete next.measurement;
 return next;
}
export function loadedRegionConfig(saved:RegionConfig,current:RegionConfig):RegionConfig{
 // Never resurrect previously confirmed backgrounds across a measurement-mode change.
 return {...saved,backgrounds:isAreaOnly(saved.measurement)?{}:{...(!isAreaOnly(current.measurement)?current.backgrounds:{}),...saved.backgrounds}};
}
