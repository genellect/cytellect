import {describe,expect,it} from "vitest";
import {regionRecipe,type RegionConfig,type RegionRevision} from "./region-types";
import {regionSubmission,sameRegionRecipe} from "./region-submission";

const config:RegionConfig={recipe:{id:"region-2d",version:"1.1.0",source:"stardist_nuclear",region_set_id:"regions",label:"測定領域",defining_channel_id:"dna",nuclear_stain_confirmed:true,detector:{engine:"fiji-stardist-2d",model:"Versatile (fluorescent nuclei)",probability:.5,nms:.3,percentile_low:1,percentile_high:99.8}},field_ids:["first"],backgrounds:{},exclusions:[]};
const active:RegionRevision={id:"corrected",parent_id:"initial",state:"succeeded",reviewed:true,created:1,config};
describe("generic detection scope preserves explicit edits",()=>{
 it("reuses corrected representative masks and adds only new fields with the identical recipe",()=>{
  expect(regionSubmission(config,active,["first","second"],"second","batch")).toMatchObject({field_ids:["first","second"],reuse_revision:"corrected",preservedCount:1,replacedCount:0,confirmationRequired:false});
  expect(regionSubmission(config,active,["first","second"],"second","add").field_ids).toEqual(["first","second"]);
 });
 it("requires replacement confirmation after a detector or defining channel change",()=>{
  if(config.recipe.source!=="stardist_nuclear")throw Error("fixture");
  for(const recipe of [{...config.recipe,defining_channel_id:"other"},{...config.recipe,detector:{...config.recipe.detector,probability:.6}}])expect(regionSubmission({...config,recipe},active,["first","second"],"first","batch")).toMatchObject({reuse_revision:null,replacedCount:1,confirmationRequired:true,recipeChanged:true});
 });
 it("re-detects only the requested field even when settings are unchanged",()=>{
  const spec=regionSubmission(config,active,["first","second"],"first","redetect");
  expect(spec).toMatchObject({field_ids:["first"],reuse_revision:null,replacedCount:1,confirmationRequired:true});
 });
 it("does not treat an unsucceeded revision or a changed method as reusable",()=>{
  expect(regionSubmission(config,{...active,state:"failed"},["first"],"first","batch").reuse_revision).toBeNull();
  expect(sameRegionRecipe(config.recipe,regionRecipe)).toBe(false);
 });
});
