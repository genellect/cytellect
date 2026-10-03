import {describe,expect,it} from "vitest";
import {planningVersion} from "./planning-runtime";
import {buildPlan,emptyPlan,parsePlan,planReceipt} from "./analysis-plan";

describe("published guide remains compatible with the advertised Windows package",()=>{
 const answers={...emptyPlan,measurement:"area" as const,region:"custom" as const,definition:"manual" as const,input:"grayscale-2d" as const};
 it("public API-unconfigured build preserves2.0 guidance and downloadable memo",()=>{
  const version=planningVersion(false,false);expect(version).toBe("2.0.0");
  const result=buildPlan(answers,version);expect(result.candidates[0]).not.toHaveProperty("measurement");
  expect(result.questions.some(question=>question.id==="background")).toBe(true);expect(planReceipt(answers,version).version).toBe("2.0.0");
 });
 it("local and explicitly configured backend builds offer2.1 without confirming scientific observations",()=>{
  for(const [local,configured] of [[true,false],[false,true]]){
   const version=planningVersion(local,configured);expect(version).toBe("2.1.0");const result=buildPlan(answers,version);
   expect(result.candidates[0].measurement).toEqual({version:"1.0.0",mode:"area_only"});expect(result.candidates[0].actual_review_required).not.toContain("background-rois");
   expect(result.candidates[0].actual_review_required).toContain("channel-mapping");expect(result.candidates[0].actual_review_required).toContain("mask-quality");
   expect(parsePlan(planReceipt(answers,version)).answers.background).toBe("unknown");
  }
 });
});
