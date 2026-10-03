export * from "./analysis-plan-v2";
import {buildPlan as buildPlan20,parsePlan as parsePlan20,type PlanAnswers,type PlanDecision,type PlanInput} from "./analysis-plan-v2";
import catalog21 from "./planning-catalog-v21.json";
import {LATEST_PLANNING_VERSION} from "./planning-runtime";

export const PLAN_VERSION=LATEST_PLANNING_VERSION;
export function parsePlan(value:unknown):PlanInput{
 if(value&&typeof value==="object"&&!Array.isArray(value)&&(value as Record<string,unknown>).version===PLAN_VERSION){
  const legacy=parsePlan20({...value,version:"2.0.0"});return {...legacy,version:PLAN_VERSION};
 }
 return parsePlan20(value);
}
export const planReceipt=(answers:PlanAnswers,version:PlanInput["version"]=PLAN_VERSION):PlanInput=>({format:"cytellect-analysis-plan",version,answers:{...answers}});
export function buildPlan(answers:PlanAnswers,version:PlanInput["version"]=PLAN_VERSION):PlanDecision{
 const original=buildPlan20(answers);if(version==="2.0.0")return original;
 const candidates=original.candidates.map(candidate=>candidate.workflow==="regions"&&candidate.allowed_metrics.every(metric=>metric==="area_px"||metric==="area_um2")?{...candidate,measurement:{version:"1.0.0" as const,mode:"area_only" as const},actual_review_required:candidate.actual_review_required.filter(task=>task!=="background-rois")}:candidate);
 const allArea=candidates.length>0&&candidates.every(candidate=>candidate.measurement?.mode==="area_only");
 const someArea=candidates.some(candidate=>candidate.measurement?.mode==="area_only");
 const findings=catalog21.findings as Record<string,PlanDecision["questions"][number]>;
 return {...original,version:PLAN_VERSION,candidates,
  questions:allArea?original.questions.filter(question=>question.id!=="background"):someArea?original.questions.map(question=>question.id==="background"?findings["background-candidate"]:question):original.questions,
  decisions:allArea?original.decisions.map(decision=>decision.id==="actual-adoption"?findings["actual-adoption-area"]:decision):original.decisions};
}
