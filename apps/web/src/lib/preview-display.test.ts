import { describe, expect, it } from "vitest";
import { readPreviewDisplay, type PreviewDisplay, type PreviewIdentity } from "./preview-display";

const identity:PreviewIdentity={fieldId:"field-a",channel:"signal",gain:2,composite:false};
const receipt:PreviewDisplay={version:"1.0.0",field_id:"field-a",requested_channel:"signal",composite:false,scope:"whole-plane",mode:"per-plane-percentile",low_percentile:0,high_percentile:100,gain:2,planes:[{channel_id:"signal",dtype:"uint16",value_basis:"native-grayscale",source_min:100,source_max:4100,percentile_low_value:100,percentile_high_value:4100,normalization_span:4000,display_black_value:100,display_white_value:2100,constant_plane:false}]};

describe("preview display receipt boundary",()=>{
 it("retains authoritative original-value range without recomputing it",()=>{
  expect(readPreviewDisplay(JSON.stringify(receipt),identity)).toEqual({status:"verified",value:receipt});
 });
 it.each(["fieldId","channel","gain","composite"] as const)("rejects stale %s after view changes",key=>{
  const changed={...identity,[key]:key==="gain"?1:key==="composite"?true:"other"};
  expect(readPreviewDisplay(JSON.stringify(receipt),changed)).toEqual({status:"invalid"});
 });
 it("distinguishes absent older API receipt from malformed metadata without inventing a range",()=>{
  expect(readPreviewDisplay(null,identity)).toEqual({status:"missing"});
  for(const header of ["", "null", "{}", "<error>", JSON.stringify({...receipt,version:"2.0.0"})])expect(readPreviewDisplay(header,identity)).toEqual({status:"invalid"});
 });
 it("accepts signed values and exact zero without a truthiness fallback",()=>{
  const value={...receipt,planes:[{...receipt.planes[0],dtype:"float64",value_basis:"legacy-imported",source_min:-1,source_max:1,percentile_low_value:-1,percentile_high_value:1,normalization_span:2,display_black_value:-1,display_white_value:0}]};
  expect(readPreviewDisplay(JSON.stringify(value),identity).status).toBe("verified");
 });
 it("rejects null/nonfinite range and contradictory constant flags",()=>{
  for(const patch of [{display_white_value:null},{display_white_value:Infinity},{constant_plane:true},{normalization_span:0},{channel_id:"other"}]) {
   const value={...receipt,planes:[{...receipt.planes[0],...patch}]};
   expect(readPreviewDisplay(JSON.stringify(value),identity).status).toBe("invalid");
  }
 });
 it("allows only actual unique native components in merge and named generic merge remains single",()=>{
  const merged={...receipt,composite:true,requested_channel:"merge",planes:[{...receipt.planes[0],channel_id:"gfp"}]};
  expect(readPreviewDisplay(JSON.stringify(merged),{...identity,channel:"merge",composite:true}).status).toBe("verified");
  expect(readPreviewDisplay(JSON.stringify({...merged,planes:[...merged.planes,...merged.planes]}),{...identity,channel:"merge",composite:true}).status).toBe("invalid");
  const single={...receipt,requested_channel:"merge",planes:[{...receipt.planes[0],channel_id:"merge"}]};
  expect(readPreviewDisplay(JSON.stringify(single),{...identity,channel:"merge"}).status).toBe("verified");
 });
});
