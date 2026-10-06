import { describe,expect,it } from "vitest";
import { regionFigureOptions,regionRecipe,type RegionField } from "./region-types";

function field(calibrated:boolean):RegionField{
 return {id:"field-1",workspace_id:"workspace-1",synthetic:false,metadata:{condition:null,experimental_unit:null,sample:null,acquisition_date:null,pair:null,repeat_length:null},image_info:{kind:"region-2d",input_mode:"native",axes:"YX",inputs:{},channel_arrays:{},shape:[64,64],channels:["Signal","Reference"].map((label,i)=>({channel_id:`channel-${i+1}`,label,stain:null,identity_confirmed:true,acquisition_saturation_value:null,acquisition_saturation_confirmed:false})),calibration:calibrated?{pixel_size_x_um:.2,pixel_size_y_um:.3,confirmed:true}:null,labels_array:null}};
}
describe("generic region figure choices",()=>{
 it("never offers corrected intensity when only raw pixels were measured",()=>{
  const options=regionFigureOptions(regionRecipe,[field(false)],{version:"1.1.0",mode:"raw_intensity"});
  expect(options.some(option=>option.selection.metric==="mean")).toBe(true);
  expect(options.some(option=>option.selection.metric.endsWith("_corrected"))).toBe(false);
 });
 it("offers area once, without a channel, and each intensity on its explicit channel",()=>{
  const options=regionFigureOptions(regionRecipe,[field(false)]);
  expect(options.filter(option=>option.selection.metric==="area_px")).toHaveLength(1);
  expect(options.find(option=>option.id==="area_px")?.selection.channel_id).toBeNull();
  expect(options.filter(option=>option.selection.metric==="mean").map(option=>option.selection.channel_id)).toEqual(["channel-1","channel-2"]);
  expect(options.some(option=>option.id==="area_um2")).toBe(false);
 });
 it("requires calibration on every included field before offering physical area",()=>{
  expect(regionFigureOptions(regionRecipe,[field(true)]).some(option=>option.id==="area_um2")).toBe(true);
  expect(regionFigureOptions(regionRecipe,[field(true),field(false)]).some(option=>option.id==="area_um2")).toBe(false);
 });
 it("offers only channel-neutral area metrics for the saved area-only policy",()=>{
  const measurement={version:"1.0.0",mode:"area_only"} as const;
  expect(regionFigureOptions(regionRecipe,[field(true)],measurement).map(option=>option.selection)).toEqual([
   {source:"region",region_set_id:"regions",channel_id:null,metric:"area_px"},
   {source:"region",region_set_id:"regions",channel_id:null,metric:"area_um2"},
  ]);
  expect(regionFigureOptions(regionRecipe,[field(false)],measurement).map(option=>option.id)).toEqual(["area_px"]);
  expect(regionFigureOptions(regionRecipe,[field(true)]).some(option=>option.selection.metric==="mean_corrected")).toBe(true);
 });
});
