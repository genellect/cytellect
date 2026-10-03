import {describe,it,expect} from "vitest";
import {regionTraceRows,regionTraceMismatch,regionFieldTraceMismatch,traceDisplayChannel,type RegionFieldTraceTarget} from "./region-trace";
import type {DescriptiveResult} from "./descriptive-view";
import type {RegionField,RegionMasks} from "./region-types";

const digest="a".repeat(64);
const saved:DescriptiveResult={analysis_kind:"descriptive",revision_id:"analysis-new",metric:"mean_corrected",unit:"a.u.",
 spec:{selection:{source:"region",region_set_id:"regions",channel_id:"actin",metric:"mean_corrected"},plot:{language:"en",preset:"nature-double"}},
 counts:{observations:1,input_fields:1,selected_fields:1,excluded_failed_fields:0,experimental_units:null},selection:{input_rows:1,excluded:0,gate_unselected:0,missing_metric_selected:0},
 field_summary:[{field_id:"field",selected_rows:1,median:-2,q1:-2,q3:-2,status:"selected"}],
 source_fields:[{field_id:"field",analysis_revision_id:"analysis-new",mask_sha256:digest,hash_format:"cytellect-array-v1",image_info:{shape:[20,30]},region_set:{label:"Regions",region_set_id:"regions",mask_revision_id:"mask-old",source:"imported"},channel_provenance:[{channel:{channel_id:"actin",label:"Actin",stain:"Phalloidin"}},{channel:{channel_id:"dna",label:"DNA",stain:null}}]}],
 plot_data:[{observation_id:'["field","regions",3]',field_id:"field",region_id:3,region_set_id:"regions",mask_revision_id:"mask-old",analysis_revision_id:"analysis-new",channel_id:"actin",value:-2}],excluded_failed_fields:[],figure:{source_files:[]},warnings:[]};
const field={id:"field",image_info:{shape:[20,30],channels:[{channel_id:"dna",label:"DNA",stain:null},{channel_id:"actin",label:"Actin",stain:"Phalloidin"}]}} as RegionField;
const masks:RegionMasks={regions:[{id:3,points:[[1,1],[3,1],[3,3]]}],metadata:{region_set_id:"regions",mask_revision_id:"mask-old",mask_sha256:digest,source:"imported",shape:[20,30],file:{bytes:2528,sha256:"b".repeat(64)}}};

describe("saved descriptive region tracing",()=>{
 it("accepts reused canonical masks without equating their revision with the analysis revision",()=>{
  const target=regionTraceRows(saved)[0].target!;expect(target.maskRevisionId).not.toBe(target.revisionId);expect(regionTraceMismatch(target,field,masks)).toBeNull();
  expect(traceDisplayChannel(target,field,"dna")?.channel_id).toBe("actin");
 });
 it.each([0,-2])("retains the saved signed value %s",value=>{const row=regionTraceRows({...saved,plot_data:[{...saved.plot_data![0],value}]})[0];expect(row.value).toBe(value);expect(row.target).not.toBeNull();});
 it("keeps area channel null and treats the current channel only as display",()=>{
  const result={...saved,spec:{...saved.spec,selection:{source:"region" as const,region_set_id:"regions",channel_id:null,metric:"area_px"}},plot_data:[{...saved.plot_data![0],channel_id:null,value:9}]};
  const target=regionTraceRows(result)[0].target!;expect(target.channelId).toBeNull();expect(traceDisplayChannel(target,field,"actin")?.channel_id).toBe("actin");expect(traceDisplayChannel(target,field,"missing")?.channel_id).toBe("dna");
 });
 it.each([{region_id:0},{region_id:1.5},{analysis_revision_id:"another"},{mask_revision_id:"wrong"},{region_set_id:"other"},{channel_id:"dna"},{observation_id:"wrong"},{value:null},{value:Infinity}])("rejects an untraceable saved observation %j",patch=>{expect(regionTraceRows({...saved,plot_data:[{...saved.plot_data![0],...patch}]})[0].target).toBeNull();});
 it("rejects saved source identity mismatches",()=>{
  for(const patch of [{analysis_revision_id:"wrong"},{mask_sha256:"invalid"},{hash_format:"file-sha256"},{image_info:{shape:[20]}}])expect(regionTraceRows({...saved,source_fields:[{...saved.source_fields[0],...patch}]})[0].target).toBeNull();
 });
 it("checks array hash, mask revision, shape and actual ID before selecting, never file hash",()=>{
  const target=regionTraceRows(saved)[0].target!;
  expect(regionTraceMismatch(target,field,{...masks,metadata:{...masks.metadata,file:{...masks.metadata.file,sha256:"c".repeat(64)}}})).toBeNull();
  for(const patch of [{mask_sha256:"c".repeat(64)},{mask_revision_id:"wrong"},{region_set_id:"wrong"},{shape:[20,31]},{source:"manual" as const}])expect(regionTraceMismatch(target,field,{...masks,metadata:{...masks.metadata,...patch}})).not.toBeNull();
  expect(regionTraceMismatch(target,field,{...masks,regions:[]})).toContain("領域を確認できません");
  expect(regionTraceMismatch(target,{...field,id:"other"},masks)).not.toBeNull();
 });
 it("rejects channel identity drift instead of falling back to another stain",()=>{
  const target=regionTraceRows(saved)[0].target!;expect(traceDisplayChannel(target,{...field,image_info:{...field.image_info,channels:field.image_info.channels.map(ch=>({...ch,label:"changed"}))}},"dna")).toBeNull();
 });
 it("does not fabricate trace rows for older missing data or native-cell results",()=>{
  expect(regionTraceRows({...saved,plot_data:undefined})).toEqual([]);
  expect(regionTraceRows({...saved,spec:{...saved.spec,selection:{source:"legacy-cell",metric:"gfp_mean"}}})).toEqual([]);
 });
});

describe("saved comparison field tracing",()=>{
 const regionTarget=regionTraceRows(saved)[0].target!;
 const target:RegionFieldTraceTarget={revisionId:regionTarget.revisionId,fieldId:regionTarget.fieldId,regionSetId:regionTarget.regionSetId,maskRevisionId:regionTarget.maskRevisionId,maskSha256:regionTarget.maskSha256,maskSource:regionTarget.maskSource,shape:regionTarget.shape,channelId:regionTarget.channelId,channelLabel:regionTarget.channelLabel,channelStain:regionTarget.channelStain,regionLabel:regionTarget.regionLabel};
 it("opens the saved field without fabricating one aggregate region ID",()=>{
  expect(regionFieldTraceMismatch(target,field,{...masks,regions:[]})).toBeNull();
  expect(target).not.toHaveProperty("regionId");expect(target).not.toHaveProperty("observationId");
  expect(traceDisplayChannel(target,field,"dna")?.channel_id).toBe("actin");
 });
 it("requires exact field, canonical mask, dimensions and source",()=>{
  for(const patch of [{mask_sha256:"c".repeat(64)},{mask_revision_id:"other"},{region_set_id:"other"},{source:"manual" as const},{shape:[20,30,1]}])expect(regionFieldTraceMismatch(target,field,{...masks,metadata:{...masks.metadata,...patch}})).not.toBeNull();
  expect(regionFieldTraceMismatch({...target,shape:[20]},field,masks)).not.toBeNull();
  expect(regionFieldTraceMismatch(target,{...field,id:"other"},masks)).not.toBeNull();
  const invalidDimensions={...field,image_info:{...field.image_info,shape:[20,30,1]}} as unknown as RegionField;
  expect(regionFieldTraceMismatch(target,invalidDimensions,masks)).not.toBeNull();
 });
 it("does not give an area comparison a measurement channel",()=>{
  const area={...target,channelId:null,channelLabel:null,channelStain:null};
  expect(traceDisplayChannel(area,field,"dna")?.channel_id).toBe("dna");expect(area.channelId).toBeNull();
 });
});
