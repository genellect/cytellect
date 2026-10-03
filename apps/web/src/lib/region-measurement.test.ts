import {describe,expect,it} from "vitest";
import {regionRecipe,type RegionConfig} from "./region-types";
import {changeRegionMeasurement,isAreaOnly,loadedRegionConfig} from "./region-measurement";

const original:RegionConfig={recipe:{...regionRecipe},backgrounds:{first:{signal:{polygon:[[0,0],[3,0],[3,3],[0,3]],confirmed:true}}},exclusions:[],plan_resolution:{version:"1.0.0",plan_sha256:"a".repeat(64),candidate_id:"regions-manual",metric:"area_px",channel_id:null,changes_acknowledged:true}};

describe("measurement mode transitions preserve saved provenance",()=>{
 it("enters area-only without inherited background evidence or method-change approval",()=>{
  const next=changeRegionMeasurement(original,"area_only");
  expect(next.measurement).toEqual({version:"1.0.0",mode:"area_only"});
  expect(next.backgrounds).toEqual({});expect(next.plan_resolution?.changes_acknowledged).toBe(false);
  expect(original.backgrounds.first.signal.confirmed).toBe(true);expect(original.plan_resolution?.changes_acknowledged).toBe(true);
  expect(next.recipe).toBe(original.recipe);
 });
 it("returns to the unchanged v1 request shape and requires fresh background confirmation",()=>{
  const next=changeRegionMeasurement(changeRegionMeasurement(original,"area_only"),"area_and_intensity");
  expect(next).not.toHaveProperty("measurement");expect(next.backgrounds).toEqual({});
  expect(isAreaOnly(next.measurement)).toBe(false);
 });
 it("reopening area history clears current background drafts; v1 history restores only its actual records",()=>{
  const area=changeRegionMeasurement(original,"area_only");
  expect(loadedRegionConfig(area,original).backgrounds).toEqual({});
  expect(loadedRegionConfig(original,area).backgrounds).toEqual(original.backgrounds);
  const empty:RegionConfig={...original,backgrounds:{}};
  expect(loadedRegionConfig(empty,area).backgrounds).toEqual({});
 });
 it("preserves the existing v1 field-background merge and unchanged choices",()=>{
  expect(loadedRegionConfig({...original,backgrounds:{}},original).backgrounds).toEqual(original.backgrounds);
  expect(changeRegionMeasurement(original,"area_and_intensity")).toBe(original);
 });
});
