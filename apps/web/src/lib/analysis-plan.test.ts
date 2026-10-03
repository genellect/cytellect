import {describe,expect,it} from "vitest";
import fixtures from "../../../../fixtures/planning/decisions-v2.json";
import currentFixtures from "../../../../fixtures/planning/decisions-v21.json";
import {buildPlan,emptyPlan,parsePlan,planReceipt} from "./analysis-plan";
describe("offline planning matches scientific decisions",()=>{
 for(const item of fixtures.cases){it(item.id,()=>{if(item.error)expect(()=>parsePlan(item.input)).toThrow();else {const input=parsePlan(item.input);expect(buildPlan(input.answers,input.version)).toEqual(item.decision);}});}
 for(const item of currentFixtures.cases){it(`2.1 ${item.id}`,()=>{if(item.error)expect(()=>parsePlan(item.input)).toThrow();else {const input=parsePlan(item.input);expect(input.version).toBe("2.1.0");expect(buildPlan(input.answers,input.version)).toEqual(item.decision);}});}
 it("exports intent only, with no actual confirmation or executable settings",()=>{const receipt=planReceipt(emptyPlan);expect(Object.keys(receipt).sort()).toEqual(["answers","format","version"]);expect(buildPlan(emptyPlan).status).toBe("planning-only-not-adopted");});
 it("rejects old, forged and invalid imported guidance",()=>{expect(()=>parsePlan({...planReceipt(emptyPlan),guidance:{candidates:["anything"]}})).toThrow();expect(()=>parsePlan({format:"cytellect-analysis-plan",version:"1.0.1",answers:{}})).toThrow();expect(()=>parsePlan({...planReceipt(emptyPlan),answers:{measurement:true}})).toThrow();expect(parsePlan({version:"2.0.0",answers:{}}).answers).toEqual(emptyPlan);});
});
