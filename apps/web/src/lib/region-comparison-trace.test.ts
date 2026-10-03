import {describe,expect,it} from "vitest";
import {regionComparisonHierarchy} from "./region-comparison-trace";
import type {RegionComparisonTraceInput} from "./region-comparison-view";
import type {components} from "./generated";

type Row=Record<string,unknown>;
const hash="a".repeat(64),fingerprint="b".repeat(64);
const channel={channel_id:"actin",label:"Actin",stain:"phalloidin",identity_confirmed:true,acquisition_saturation_confirmed:false} satisfies components["schemas"]["ChannelSpec"];
// Hand-set practice references, not a second implementation of aggregation.
const fieldReferences:[string,string,string,string,number][]=[
 ["f01","A","1","A1-s1",2],["f02","A","1","A1-s1",4],["f03","A","1","A1-s2",10],
 ["f04","A","2","A2-s1",5],["f05","A","2","A2-s1",5],["f06","A","3","A3-s1",7],
 ["f07","B","1","B1-s1",5],["f08","B","1","B1-s1",7],["f09","B","1","B1-s2",13],
 ["f10","B","2","B2-s1",4],["f11","B","2","B2-s1",4],["f12","B","3","B3-s1",9],
];
const sampleValues:Record<string,number>={"A1-s1":3,"A1-s2":10,"A2-s1":5,"A3-s1":7,"B1-s1":6,"B1-s2":13,"B2-s1":4,"B3-s1":9};
const unitReferences:[string,string,number,number][]=[["A","1",6.5,6],["A","2",5,4],["A","3",7,2],["B","1",9.5,6],["B","2",4,4],["B","3",9,2]];
function source(field:Row):Row {
 const fieldId=String(field.field_id);
 return {field_id:fieldId,analysis_revision_id:"saved-r1",hash_format:"cytellect-array-v1",mask_sha256:hash,
  metadata:Object.fromEntries(["condition","sample","experimental_unit","pair","acquisition_date"].map(name=>[name,field[name]])),
  region_set:{region_set_id:"regions",label:"Measured regions",mask_revision_id:`mask-${fieldId}`,source:"imported"},
  image_info:{shape:[80,80],channels:[channel]},channel_provenance:[{channel}]};
}
function observation(field:Row,rid:number,value:number|null,status="selected"):Row {
 return {...(source(field).metadata as Row),field_id:field.field_id,observation_id:JSON.stringify([field.field_id,"regions",rid]),
  region_id:rid,region_set_id:"regions",mask_revision_id:`mask-${field.field_id}`,analysis_revision_id:"saved-r1",channel_id:"actin",
  value,excluded:status==="excluded",exclusion_reason:status==="excluded"?"reviewed artifact":null,
  missing_reason:status==="missing"?"metric_unavailable":null,selection_status:status};
}
function fixture(paired=false):RegionComparisonTraceInput {
 const unitId=(condition:string,id:string)=>paired?`M-${id}`:`U-${condition}${id}`;
 const ledger:Row[]=fieldReferences.map(([field_id,condition,id,sample])=>({field_id,condition,sample,experimental_unit:unitId(condition,id),
  pair:paired?`P-${id}`:null,acquisition_date:"generated-batch",in_scope:true,explicitly_excluded:false,exclusion_reason:null,
  status:"selected",input_observations:2,selected_observations:2,excluded_observations:0,missing_observations:0}));
 const fields=ledger.map((row,i)=>({condition:row.condition,experimental_unit:row.experimental_unit,sample:row.sample,field_id:row.field_id,value:fieldReferences[i][4]}));
 const sample_summary=Object.entries(sampleValues).map(([sample,value])=>{
  const field=ledger.find(row=>row.sample===sample)!;return {condition:field.condition,experimental_unit:field.experimental_unit,sample,value};
 });
 const unit_summary=unitReferences.map(([condition,id,value])=>({condition,experimental_unit:unitId(condition,id),...(paired?{pair:`P-${id}`} :{}),value}));
 const unit_ledger=unitReferences.map(([condition,id,,selected_observations])=>({condition,experimental_unit:unitId(condition,id),pair:paired?`P-${id}`:null,
  field_ids:ledger.filter(row=>row.condition===condition&&row.experimental_unit===unitId(condition,id)).map(row=>row.field_id),
  excluded_fields:[],selected_observations,status:"selected"}));
 return {revision_id:"saved-r1",source_fingerprint:fingerprint,
  spec:{selection:{source:"region",region_set_id:"regions",channel_id:"actin",metric:"mean_corrected"},design:{kind:paired?"paired":"independent"},conditions:["A","B"]},
  metric:"mean_corrected",region:{region_set_id:"regions",label:"Measured regions"},channel,
  source_fields:ledger.map(source),source_field_ledger:ledger,observation_ledger:ledger.flatMap((row,i)=>[observation(row,1,fieldReferences[i][4]-1),observation(row,2,fieldReferences[i][4]+1)]),
  field_summary:fields,sample_summary,unit_summary,unit_ledger,
  pair_ledger:paired?[1,2,3].map(id=>({pair:`P-${id}`,status:"selected",units:{A:`M-${id}`,B:`M-${id}`}})):[],
  missingness:[],excluded_failed_fields:[],
 } as unknown as RegionComparisonTraceInput;
}
function valid(result:RegionComparisonTraceInput){const value=regionComparisonHierarchy(result);expect(value.ok).toBe(true);if(!value.ok)throw Error(value.reason);return value;}
function extraField(result:RegionComparisonTraceInput,status:"excluded"|"no_regions"|"no_selected_values",failed=false){
 const row:Row={...result.source_field_ledger[0],field_id:"extra",status,explicitly_excluded:status==="excluded",exclusion_reason:status==="excluded"?"reviewed artifact":null,
  input_observations:status==="no_regions"||failed?0:2,selected_observations:0,excluded_observations:status==="excluded"&&!failed?2:0,missing_observations:status==="no_selected_values"?2:0};
 result.source_field_ledger.push(row);(result.unit_ledger[0].field_ids as string[]).push("extra");
 if(status==="excluded")(result.unit_ledger[0].excluded_fields as string[]).push("extra");
 if(failed)result.excluded_failed_fields.push({field_id:"extra",reason:"reviewed artifact",error:"input_hash_mismatch"});
 else {result.source_fields.push(source(row));if(status!=="no_regions")for(const id of [1,2]){
  const obs=observation(row,id,status==="excluded"?0:null,status==="excluded"?"excluded":"missing");result.observation_ledger.push(obs);
  if(status==="no_selected_values")result.missingness.push({field_id:"extra",observation_id:obs.observation_id,reason:"metric_unavailable"});
 }}
}

describe("saved comparison aggregation provenance",()=>{
 it("shows hand-set unit 6.5 from saved sample means 3/10 and field medians 2/4/10",()=>{
  const result=fixture(),before=structuredClone(result),tree=valid(result),unit=tree.units[0];
  expect(unit).toMatchObject({condition:"A",experimentalUnit:"U-A1",value:6.5,selectedObservations:6});
  expect(unit.samples.map(sample=>sample.value)).toEqual([3,10]);
  expect(unit.samples.flatMap(sample=>sample.fields.map(field=>field.value))).toEqual([2,4,10]);
  expect(unit.samples.flatMap(sample=>sample.fields.map(field=>field.fieldNumber))).toEqual([1,2,3]);
  expect(tree.units).toHaveLength(6);expect(result).toEqual(before);
 });
 it("copies saved aggregate cells instead of deriving new values in the browser",()=>{
  const result=fixture();result.unit_summary[0].value=6.500000000000001;result.sample_summary[0].value=3.0000000000000004;
  const unit=valid(result).units[0];expect(unit.value).toBe(6.500000000000001);expect(unit.samples[0].value).toBe(3.0000000000000004);
 });
 it("pairs through the saved mapping and keeps the same unit ID separate across conditions",()=>{
  const result=fixture(true);result.unit_ledger.reverse();result.unit_summary.reverse();
  const pair=valid(result).pairs[0];
  expect(pair.pair).toBe("P-1");expect(pair.units.map(unit=>[unit.condition,unit.experimentalUnit,unit.value])).toEqual([["A","M-1",6.5],["B","M-1",9.5]]);
  expect(pair.units[0].key).not.toBe(pair.units[1].key);
 });
 it("keeps a fully excluded declared pair without an invented aggregate or complete-pair count",()=>{
  const result=fixture(true);
  for(const condition of ["A","B"]){
   const row={...result.source_field_ledger[0],field_id:`failed-${condition}`,condition,sample:`${condition}4-s1`,experimental_unit:"M-4",pair:"P-4",
    status:"excluded",explicitly_excluded:true,exclusion_reason:"failed field reviewed",input_observations:0,selected_observations:0,excluded_observations:0,missing_observations:0};
   result.source_field_ledger.push(row);result.excluded_failed_fields.push({field_id:row.field_id,reason:row.exclusion_reason,error:"input_hash_mismatch"});
   result.unit_ledger.push({condition,experimental_unit:"M-4",pair:"P-4",field_ids:[row.field_id],excluded_fields:[row.field_id],selected_observations:0,status:"excluded"});
  }
  result.pair_ledger.push({pair:"P-4",status:"excluded",units:{A:"M-4",B:"M-4"}});
  const pair=valid(result).pairs[3];expect(pair.status).toBe("excluded");expect(pair.units.map(unit=>unit.value)).toEqual([null,null]);
  expect(pair.units[0].samples[0].value).toBeNull();expect(pair).not.toHaveProperty("completePairs");
 });
 it("treats delimiter and prototype-like identifiers as literal identities",()=>{
  const result=fixture();
  for(const collection of [result.source_field_ledger,result.field_summary,result.sample_summary,result.unit_summary,result.unit_ledger,result.observation_ledger]){
   for(const row of collection){if(row.experimental_unit==="U-A1")row.experimental_unit="__proto__|日本語";if(row.sample==="A1-s1")row.sample='sample|["x"]';}
  }
  for(const row of result.source_fields){const md=row.metadata as Row;if(md.experimental_unit==="U-A1")md.experimental_unit="__proto__|日本語";if(md.sample==="A1-s1")md.sample='sample|["x"]';}
  const unit=valid(result).units[0];expect(unit.experimentalUnit).toBe("__proto__|日本語");expect(unit.samples[0].sample).toBe('sample|["x"]');expect(unit.value).toBe(6.5);
 });
 it("preserves missing/excluded notes and distinguishes an empty field from a zero value",()=>{
  for(const status of ["excluded","no_regions","no_selected_values"] as const){
   const result=fixture();extraField(result,status);const field=valid(result).units[0].samples[0].fields.at(-1)!;
   expect(field.status).toBe(status);expect(field.value).toBeNull();expect(field.target).not.toBeNull();
   expect(field.observationNotes).toHaveLength(status==="no_regions"?0:2);
   if(status==="no_selected_values")expect(field).toMatchObject({missingObservations:2,observationNotes:[{reason:"metric_unavailable"},{reason:"metric_unavailable"}]});
  }
 });
 it("keeps failed excluded field counts unknown even when its server ledger contains zero",()=>{
  const result=fixture();extraField(result,"excluded",true);const field=valid(result).units[0].samples[0].fields.at(-1)!;
  expect(field).toMatchObject({value:null,inputObservations:null,selectedObservations:null,excludedObservations:null,missingObservations:null,
   exclusionReason:"reviewed artifact",failureReason:"input_hash_mismatch",target:null});
 });
 it("preserves finite negative and zero saved values",()=>{
  const result=fixture();result.field_summary[0].value=-2;result.sample_summary[0].value=0;result.unit_summary[0].value=-0.5;
  const unit=valid(result).units[0];expect(unit.value).toBe(-0.5);expect(unit.samples[0].value).toBe(0);expect(unit.samples[0].fields[0].value).toBe(-2);
 });
 it("keeps out-of-scope metadata unknown without manufacturing a unit",()=>{
  const result=fixture(),field={...result.source_field_ledger[0],field_id:"outside",condition:"C",sample:null,experimental_unit:null,pair:null,
   in_scope:false,status:"out_of_scope",input_observations:0,selected_observations:0};
  result.source_field_ledger.push(field);result.source_fields.push(source(field));
  const tree=valid(result);expect(tree.units).toHaveLength(6);expect(tree.outOfScopeFields[0]).toMatchObject({fieldId:"outside",sample:null,experimentalUnit:null,value:null,fieldNumber:13});
 });
 it("creates an exact historical field target with the recorded actual stain and no fabricated region ID",()=>{
  const field=valid(fixture()).units[0].samples[0].fields[0];
  expect(field.target).toEqual({revisionId:"saved-r1",fieldId:"f01",regionSetId:"regions",maskRevisionId:"mask-f01",maskSha256:hash,
   maskSource:"imported",shape:[80,80],channelId:"actin",channelLabel:"Actin",channelStain:"phalloidin",regionLabel:"Measured regions"});
  expect(field.target).not.toHaveProperty("regionId");expect(field.target).not.toHaveProperty("observationId");
 });
 it("keeps area targets channel-neutral",()=>{
  const result=fixture();result.metric="area_px";result.spec.selection.metric="area_px";result.spec.selection.channel_id=null;result.channel=null;
  for(const row of result.observation_ledger)row.channel_id=null;
  expect(valid(result).units[0].samples[0].fields[0].target).toMatchObject({channelId:null,channelLabel:null,channelStain:null});
 });
 it.each([
  ["missing source",(r:RegionComparisonTraceInput)=>{r.source_fields.shift();}],
  ["historical metadata mismatch",(r:RegionComparisonTraceInput)=>{(r.source_fields[0].metadata as Row).sample="new-sample";}],
  ["wrong mask revision",(r:RegionComparisonTraceInput)=>{(r.source_fields[0].region_set as Row).mask_revision_id="new-mask";}],
  ["wrong saved revision",(r:RegionComparisonTraceInput)=>{r.source_fields[0].analysis_revision_id="new-revision";}],
  ["malformed hash",(r:RegionComparisonTraceInput)=>{r.source_fields[0].mask_sha256="not-a-hash";}],
  ["unconfirmed channel",(r:RegionComparisonTraceInput)=>{r.source_fields[0].channel_provenance=[{channel:{...channel,identity_confirmed:false}}];}],
  ["wrong stain",(r:RegionComparisonTraceInput)=>{r.source_fields[0].channel_provenance=[{channel:{...channel,stain:"NCL"}}];}],
  ["duplicate channel",(r:RegionComparisonTraceInput)=>{r.source_fields[0].channel_provenance=[{channel},{channel}];}],
 ] as const)("disables only the source link for %s",(_,mutate)=>{
  const result=fixture();mutate(result);const field=valid(result).units[0].samples[0].fields[0];expect(field.value).toBe(2);expect(field.target).toBeNull();
 });
 it.each([
  ["duplicate field summary",(r:RegionComparisonTraceInput)=>{r.field_summary.push({...r.field_summary[0]});}],
  ["orphan summary",(r:RegionComparisonTraceInput)=>{r.sample_summary[0].sample="unknown";}],
  ["missing unit summary",(r:RegionComparisonTraceInput)=>{r.unit_summary.shift();}],
  ["missing metadata",(r:RegionComparisonTraceInput)=>{r.source_field_ledger[0].experimental_unit=null;}],
  ["duplicate field ID",(r:RegionComparisonTraceInput)=>{r.source_field_ledger.push({...r.source_field_ledger[0]});}],
  ["missing unit field membership",(r:RegionComparisonTraceInput)=>{(r.unit_ledger[0].field_ids as string[]).pop();}],
  ["invalid saved number",(r:RegionComparisonTraceInput)=>{r.unit_summary[0].value=Number.NaN;}],
  ["string saved number",(r:RegionComparisonTraceInput)=>{r.sample_summary[0].value="3";}],
  ["observation from another revision",(r:RegionComparisonTraceInput)=>{r.observation_ledger[0].analysis_revision_id="new";}],
  ["duplicate observation",(r:RegionComparisonTraceInput)=>{r.observation_ledger.push({...r.observation_ledger[0]});}],
  ["wrong observation metadata",(r:RegionComparisonTraceInput)=>{r.observation_ledger[0].sample="another";}],
  ["duplicate source field",(r:RegionComparisonTraceInput)=>{r.source_fields.push({...r.source_fields[0]});}],
 ] as const)("rejects ambiguous or malformed saved joins: %s",(_,mutate)=>{
  const result=fixture();mutate(result);expect(regionComparisonHierarchy(result)).toEqual({ok:false,reason:"saved_comparison_hierarchy_inconsistent"});
 });
 it.each([
  ["missing pair",(r:RegionComparisonTraceInput)=>{r.pair_ledger.pop();}],
  ["duplicate pair",(r:RegionComparisonTraceInput)=>{r.pair_ledger.push({...r.pair_ledger[0]});}],
  ["wrong mapping",(r:RegionComparisonTraceInput)=>{(r.pair_ledger[0].units as Row).B="M-2";}],
  ["summary pair differs",(r:RegionComparisonTraceInput)=>{r.unit_summary[0].pair="P-2";}],
 ] as const)("does not infer paired membership: %s",(_,mutate)=>{
  const result=fixture(true);mutate(result);expect(regionComparisonHierarchy(result).ok).toBe(false);
 });
});
