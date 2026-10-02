import { describe,expect,it } from "vitest";
import { availableMetricIds } from "./types";
describe("measured metric availability",()=>{
 it("does not invent NCL or calibrated area for GFP-only uncalibrated input",()=>{
  const ids=availableMetricIds({hasGfp:true,hasNcl:false,legacy:false,calibrated:false});
  expect(ids).toHaveLength(7);expect(ids).toContain("gfp_integrated_corrected");expect(ids).toContain("nucleus_area_px");
  expect(ids.some(x=>x.startsWith("ncl")||x.startsWith("nucleolar")||x.endsWith("um2"))).toBe(false);
 });
 it("separates legacy and native indicators while preserving measured compartments",()=>{
  const native=availableMetricIds({hasGfp:false,hasNcl:true,legacy:false,calibrated:true});
  expect(native).toContain("ncl_nucleoplasm_median_corrected");expect(native).toContain("ncl_nucleoli_integrated");expect(native).toContain("nucleoplasm_area_um2");expect(native).not.toContain("ncl_legacy_release");
  const legacy=availableMetricIds({hasGfp:true,hasNcl:true,legacy:true,calibrated:false});
  expect(legacy).toContain("ncl_legacy_release");expect(legacy).not.toContain("ncl_nucleoplasm_over_nucleoli");expect(legacy).not.toContain("ncl_log2_nucleoplasm_over_nucleoli");
 });
});
