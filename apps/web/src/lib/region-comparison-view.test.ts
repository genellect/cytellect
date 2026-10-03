import {describe,expect,it} from "vitest";
import {probabilityLabel,regionComparisonJobs,selectedRegionComparisonJob} from "./region-comparison-view";
import type {Job} from "./types";

const job=(id:string,revision_id:string,state:string,created:number,analysis_mode:Job["analysis_mode"]="region-experimental-unit"):Job=>({id,revision_id,state,created,analysis_mode,kind:"statistics",error:null,attempts:1});
describe("source-bound region comparison display",()=>{
 const jobs=[job("old","r1","succeeded",1),job("new","r2","running",2),job("distribution","r2","succeeded",3,"descriptive")];
 it("does not substitute descriptive or older-revision results for the current comparison",()=>{
  expect(regionComparisonJobs(jobs).map(item=>item.id)).toEqual(["new","old"]);
  expect(selectedRegionComparisonJob(jobs,"","r2")?.id).toBe("new");
  expect(selectedRegionComparisonJob(jobs,"","r3")).toBeUndefined();
 });
 it("keeps explicit pending, failed and missing selections instead of falling back to old success",()=>{
  expect(selectedRegionComparisonJob(jobs,"not-polled","r2")).toBeUndefined();
  expect(selectedRegionComparisonJob([...jobs,job("failed","r2","failed",4)],"failed","r2")?.state).toBe("failed");
  expect(selectedRegionComparisonJob(jobs,"old","r2")?.revision_id).toBe("r1");
 });
 it("does not round a small nonzero p-value to zero or invent missing values",()=>{
  expect(probabilityLabel(.0000000172)).toBe("1.72e-8");
  expect(probabilityLabel(null)).toBe("—");
  expect(probabilityLabel(.1256)).toBe("0.126");
 });
});
