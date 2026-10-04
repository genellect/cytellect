import {describe,expect,it} from "vitest";
import type {components} from "./generated";
import type {RegionRevision} from "./region-types";
import {regionRecipe} from "./region-types";
import {regionQualityOverview} from "./region-quality-overview";

type Row=Record<string,unknown>;
type Fixture={report:Row;revision:RegionRevision};
const hash="a".repeat(64),policy={version:"1.0.0",mode:"area_only"};
const metadata={condition:null,sample:null,experimental_unit:null,pair:null,acquisition_date:null,repeat_length:null};
const channels=[
 {channel_id:"signal",label:"Recorded signal",stain:"example stain",identity_confirmed:true,acquisition_saturation_value:200,acquisition_saturation_confirmed:true},
 {channel_id:"other",label:"Second channel",stain:null,identity_confirmed:true,acquisition_saturation_value:null,acquisition_saturation_confirmed:false},
] satisfies Required<components["schemas"]["ChannelSpec"]>[];

// Saved values are hand set: three distinct labels across two channels are three
// objects, never six objects or independent experimental units. No image inference.
function makeTable(fieldId:string){
 const table={protocol_version:"1.0.0",status:"measured",field_id:fieldId,analysis_revision_id:"revision-new",
  region_set:{region_set_id:"regions",label:"Measured regions",source:"manual",defining_channel_id:null,mask_revision_id:"mask-parent"},
  shape_yx:[8,10],mask_sha256:hash,hash_format:"cytellect-array-v1",calibration:null,
  channel_provenance:channels.map(channel=>({channel:{...channel},dtype:"uint8" as const,pixel_sha256:hash,storage_maximum:255,
   background_mask_sha256:hash,background_revision_id:"background-parent",background_pixel_count:4,background_median:10})),
  rows:[1,7,12].flatMap(regionId=>channels.map(channel=>({field_id:fieldId,analysis_revision_id:"revision-new",region_set_id:"regions",
   mask_revision_id:"mask-parent",region_id:regionId,channel_id:channel.channel_id,area_px:4,area_um2:null,area_missing_reason:"calibration_unknown" as const,
   mean:2,median:2,integrated:8,mean_corrected:-8,median_corrected:-8,integrated_corrected:-32,
   storage_limit_fraction:regionId===7&&channel.channel_id==="signal"?0.25:0,
   acquisition_saturation_fraction:channel.channel_id==="signal"?(regionId===1?0.5:0):null,
   acquisition_saturation_missing_reason:channel.channel_id==="signal"?null:"acquisition_limit_unknown" as const,
   touches_border:regionId===1||regionId===7}))),
 } satisfies components["schemas"]["RegionMeasurementTable"];
 return table;
}
function fixture(area=false):Fixture{
 const table=makeTable("field-one"),recipe={...regionRecipe,label:"Measured regions"};
 const exclusions=[{field_id:"field-one",region_id:7,reason:"Reviewed excluded region"},{field_id:"field-one",region_id:12,reason:"Unflagged exclusion"}];
 const revision:RegionRevision={id:"revision-new",parent_id:"mask-parent",state:"succeeded",reviewed:false,created:1,
  config:{analysis_kind:"region-2d",field_ids:["field-one"],recipe,backgrounds:{},exclusions,
   field_snapshot:{"field-one":{metadata,image_info:{shape:[8,10],calibration:null,channels:structuredClone(channels)}}}} as RegionRevision["config"]};
 const report:Row={analysis_kind:"region-2d",protocol_version:"1.0.0",revision_id:revision.id,recipe,
  field_tables:{"field-one":table},field_masks:{"field-one":{mask_revision_id:"mask-parent",mask_sha256:hash,region_set_id:"regions",source:"manual",shape:[8,10],file:{path:"private/labels.npy",sha256:hash,bytes:1}}},
  field_outcomes:{"field-one":"measured"},field_failures:[],excluded_failed_fields:[],exclusions:structuredClone(exclusions)};
 const value={report,revision};
 if(area){
  revision.config.measurement={version:"1.0.0",mode:"area_only"};report.measurement={...policy};report.protocol_version="2.0.0";
  const current=firstTable(value);current.protocol_version="2.0.0";current.measurement={...policy};
  for(const provenance of current.channel_provenance as Row[]){for(const key of ["background_mask_sha256","background_revision_id","background_pixel_count","background_median"])delete provenance[key];provenance.background={status:"not_measured",reason:"not_required_for_area"};}
  for(const row of current.rows as Row[]){
   for(const key of ["mean","median","integrated","mean_corrected","median_corrected","integrated_corrected","storage_limit_fraction","acquisition_saturation_fraction"])row[key]=null;
   row.intensity_missing_reason="not_requested";row.storage_limit_missing_reason="not_requested";row.acquisition_saturation_missing_reason="not_requested";
  }
 }
 return value;
}
function firstTable(value:Fixture):Row{return (value.report.field_tables as Record<string,Row>)["field-one"];}
function firstRow(value:Fixture):Row{return (firstTable(value).rows as Row[])[0];}
function valid(value:Fixture){const result=regionQualityOverview(value.report,value.revision);expect(result.ok).toBe(true);if(!result.ok)throw Error(result.reason);return result;}
function addOutcome(value:Fixture,fieldId:string,outcome:"no_regions"|"failed"|"excluded_failed"){
 value.revision.config.field_ids!.push(fieldId);
 (value.report.field_outcomes as Row)[fieldId]=outcome;
 if(outcome==="no_regions"){
  const table=structuredClone(firstTable(value));table.field_id=fieldId;table.status=outcome;table.rows=[];
  (value.report.field_tables as Row)[fieldId]=table;
  (value.report.field_masks as Row)[fieldId]=structuredClone((value.report.field_masks as Row)["field-one"]);
  value.revision.config.field_snapshot![fieldId]={metadata,image_info:{shape:[8,10],calibration:null,channels:structuredClone(channels)}} as {metadata:typeof metadata};
 }else{
  // A valid leftover mask is not evidence of successfully measured regions.
  (value.report.field_masks as Row)[fieldId]=structuredClone((value.report.field_masks as Row)["field-one"]);
  if(outcome==="failed")(value.report.field_failures as Row[]).push({field_id:fieldId,reason:"region_unknown_excluded_object"});
  else {
   (value.report.excluded_failed_fields as Row[]).push({field_id:fieldId,error:"region_channel_or_background_mapping_mismatch",reason:"Reviewed failed field"});
   const exclusion={field_id:fieldId,region_id:null,reason:"Reviewed failed field"};
   value.revision.config.exclusions.push(exclusion);(value.report.exclusions as Row[]).push({...exclusion});
  }
 }
}

describe("saved all-field region quality overview",()=>{
 it("counts border labels once, keeps per-channel flags and excluded objects separate without mutation",()=>{
  const value=fixture(),before=structuredClone(value),result=valid(value),field=result.fields[0];
  expect(field).toMatchObject({regionCount:3,includedRegionCount:1,excludedRegionCount:2,calibration:"unknown"});
  expect(field.border).toMatchObject({status:"measured",includedCount:1,excludedCount:1});
  expect(field.border!.items.map(item=>item.regionId)).toEqual([1,7]);
  expect(field.channels[0].storageLimit).toMatchObject({status:"measured",includedCount:0,excludedCount:1});
  expect(field.channels[0].storageLimit.items[0]).toMatchObject({regionId:7,value:0.25,excluded:true});
  expect(field.channels[0].acquisitionSaturation).toMatchObject({status:"measured",includedCount:1,excludedCount:0});
  expect(field.channels[1].storageLimit).toMatchObject({status:"measured",includedCount:0,excludedCount:0});
  expect(field.excludedRegions.map(item=>[item.regionId,item.reasons])).toEqual([[7,["Reviewed excluded region"]],[12,["Unflagged exclusion"]]]);
  expect(value).toEqual(before);expect(result).not.toHaveProperty("reviewed");expect(field).not.toHaveProperty("independent_n");
 });
 it("binds field, channel and region navigation to the saved revision and reused mask identity",()=>{
  const field=valid(fixture()).fields[0];
  expect(field.target).toEqual({revisionId:"revision-new",fieldId:"field-one",regionSetId:"regions",maskRevisionId:"mask-parent",maskSha256:hash,
   maskSource:"manual",shape:[8,10],channelId:null,channelLabel:null,channelStain:null,regionLabel:"Measured regions"});
  expect(field.channels[0].storageLimit.items[0].target).toMatchObject({revisionId:"revision-new",maskRevisionId:"mask-parent",channelId:"signal",channelLabel:"Recorded signal",channelStain:"example stain",regionId:7,observationId:'["field-one","regions",7]'});
  expect(field.border!.items[0].target.channelId).toBeNull();expect(field.excludedRegions[1].target.regionId).toBe(12);
 });
 it("does not turn unknown acquisition limits into zero saturation or a quality verdict",()=>{
  const field=valid(fixture()).fields[0];
  expect(field.channels[1].acquisitionSaturation).toEqual({status:"unknown",reason:"acquisition_limit_unknown",includedCount:null,excludedCount:null,items:[]});
  expect(field).not.toHaveProperty("quality");
 });
 it("retains area-only border checks while recording both intensity diagnostics as not measured",()=>{
  const value=fixture(true),result=valid(value),field=result.fields[0];
  expect(result.mode).toBe("area_only");expect(field.border).toMatchObject({includedCount:1,excludedCount:1});
  for(const channel of field.channels){
   for(const diagnostic of [channel.storageLimit,channel.acquisitionSaturation])expect(diagnostic).toEqual({status:"not_measured",reason:"not_requested",includedCount:null,excludedCount:null,items:[]});
   expect(channel.target.channelId).toBeNull();
  }
 });
 it("keeps empty, failed and explicitly excluded failed fields even when masks remain",()=>{
  const value=fixture();addOutcome(value,"empty","no_regions");addOutcome(value,"failed","failed");addOutcome(value,"excluded-failed","excluded_failed");
  value.revision.config.field_ids!.reverse();
  const fields=valid(value).fields;expect(fields.map(field=>field.fieldId)).toEqual(["excluded-failed","failed","empty","field-one"]);
  expect(fields[0]).toMatchObject({outcome:"excluded_failed",regionCount:null,target:null,failureReason:"region_channel_or_background_mapping_mismatch",exclusionReasons:["Reviewed failed field"]});
  expect(fields[1]).toMatchObject({outcome:"failed",regionCount:null,border:null,target:null});
  expect(fields[2]).toMatchObject({outcome:"no_regions",regionCount:0,includedRegionCount:0,excludedRegionCount:0,border:{status:"no_regions"}});
  expect(fields[2].channels[0].acquisitionSaturation.status).toBe("no_regions");expect(fields[2].channels[1].acquisitionSaturation.status).toBe("unknown");
 });
 it("preserves a failed removed-region exclusion as a failure instead of hiding the field",()=>{
  const value=fixture();addOutcome(value,"failed","failed");
  const exclusion={field_id:"failed",region_id:99,reason:"Former selected region"};
  value.revision.config.exclusions.push(exclusion);(value.report.exclusions as Row[]).push({...exclusion});
  expect(valid(value).fields[1]).toMatchObject({outcome:"failed",regionCount:null,failureReason:"region_unknown_excluded_object"});
 });
 it("retains field exclusion and region-specific reasons without double counting an object",()=>{
  const value=fixture(),exclusion={field_id:"field-one",region_id:null,reason:"Field artifact"};
  value.revision.config.exclusions.push(exclusion);(value.report.exclusions as Row[]).push({...exclusion});
  const field=valid(value).fields[0];expect(field).toMatchObject({includedRegionCount:0,excludedRegionCount:3,exclusionReasons:["Field artifact"]});
  expect(field.excludedRegions[1].reasons).toEqual(["Reviewed excluded region","Field artifact"]);
 });
 it("accepts historical snapshot absence and known non-isotropic calibration without calculating area",()=>{
  const value=fixture();delete value.revision.config.field_snapshot;
  firstTable(value).calibration={pixel_size_x_um:0.2,pixel_size_y_um:0.3,confirmed:true};
  for(const row of firstTable(value).rows as Row[]){row.area_um2=0.24;row.area_missing_reason=null;}
  expect(valid(value).fields[0].calibration).toBe("known");
 });
 it("accepts metadata-only historical snapshots without inventing current channel information",()=>{
  const value=fixture();value.revision.config.field_snapshot={"field-one":{metadata}};
  expect(valid(value).fields[0].channels[0].label).toBe("Recorded signal");
 });
 const mutations:[string,(value:Fixture)=>void][]=[
  ["unknown report protocol",v=>{v.report.protocol_version="3.0.0";}],
  ["policy on v1 report",v=>{v.report.measurement=policy;}],
  ["missing outcome",v=>{delete (v.report.field_outcomes as Row)["field-one"];}],
  ["missing measured table",v=>{delete (v.report.field_tables as Row)["field-one"];}],
  ["missing mask provenance",v=>{delete (v.report.field_masks as Row)["field-one"];}],
  ["wrong analysis revision",v=>{firstTable(v).analysis_revision_id="other-revision";}],
  ["mismatched mask hash",v=>{firstTable(v).mask_sha256="b".repeat(64);}],
  ["mismatched snapshot shape",v=>{firstTable(v).shape_yx=[9,10];(v.report.field_masks as Record<string,Row>)["field-one"].shape=[9,10];}],
  ["missing channel row",v=>{(firstTable(v).rows as Row[]).pop();}],
  ["duplicate channel row",v=>{(firstTable(v).rows as Row[]).push({...firstRow(v)});}],
  ["disagreeing border flag",v=>{firstRow(v).touches_border=false;}],
  ["disagreeing duplicated area",v=>{firstRow(v).area_px=5;}],
  ["wrong observation identity",v=>{firstRow(v).field_id="another-field";}],
  ["unknown area treated as zero",v=>{firstRow(v).area_um2=0;}],
  ["out of range fraction",v=>{firstRow(v).storage_limit_fraction=1.1;}],
  ["non-finite fraction",v=>{firstRow(v).storage_limit_fraction=NaN;}],
  ["absent saturation missingness",v=>{(firstTable(v).rows as Row[])[1].acquisition_saturation_missing_reason=null;}],
  ["unconfirmed channel identity",v=>{((firstTable(v).channel_provenance as Row[])[0].channel as Row).identity_confirmed=false;}],
  ["unconfirmed acquisition limit",v=>{((firstTable(v).channel_provenance as Row[])[0].channel as Row).acquisition_saturation_confirmed=false;}],
  ["source channel label drift",v=>{((firstTable(v).channel_provenance as Row[])[0].channel as Row).label="Changed label";}],
  ["mismatched exclusions",v=>{(v.report.exclusions as Row[]).pop();}],
  ["unknown region in a successful table",v=>{(v.report.exclusions as Row[])[0].region_id=99;v.revision.config.exclusions[0].region_id=99;}],
  ["duplicate failure/outcome",v=>{(v.report.field_failures as Row[]).push({field_id:"field-one",reason:"failed"});}],
  ["failed field supplied as measured table",v=>{(v.report.field_outcomes as Row)["field-one"]="failed";(v.report.field_failures as Row[]).push({field_id:"field-one",reason:"failed"});}],
 ];
 it.each(mutations)("does not label inconsistent saved data clean: %s",(_,mutate)=>{
  const value=fixture();mutate(value);expect(regionQualityOverview(value.report,value.revision)).toEqual({ok:false,reason:"saved_region_quality_inconsistent"});
 });
 it.each(["mean","storage_limit_fraction","acquisition_saturation_fraction"])("rejects an invented area-only %s value",metric=>{
  const value=fixture(true);firstRow(value)[metric]=0;expect(regionQualityOverview(value.report,value.revision).ok).toBe(false);
 });
 it("rejects area-only table with missing explicit policy",()=>{
  const value=fixture(true);delete firstTable(value).measurement;expect(regionQualityOverview(value.report,value.revision).ok).toBe(false);
 });
});
