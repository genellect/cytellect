/** Offline preview mirrors planning.py; the API recomputes every adopted plan. */
import catalog from "./planning-catalog.json";
import type {components} from "./generated";
type Schema=components["schemas"];
export const PLAN_VERSION="2.0.0" as const;
export const answerOptions={measurement:["unknown","area","mean","integrated","ncl-ratio"],region:["unknown","nucleus","nucleolus","nucleoplasm","custom"],definition:["unknown","manual","imported","nuclear-stain","ncl-enrichment"],signal:["unknown","ncl","gfp","other"],input:["unknown","grayscale-2d","rgb","zt"],nuclear_stain:["unknown","yes","no"],background:["unknown","yes","no"],acquisition:["unknown","matched","different"],comparison:["unknown","descriptive","independent","paired"],allocation:["unknown","biological","fields"],gating:["none","negative-control","exploratory"]} as const;
export type PlanAnswers=Required<Schema["PlanAnswers"]>;
export type PlanInput=Omit<Schema["PlanInput"],"answers">&{answers:PlanAnswers};
export type PlanCandidate=Schema["PlanCandidate"];
export type CandidateId=PlanCandidate["id"];
type Finding=Schema["PlanFinding"];
export type PlanDecision=Schema["PlanDecision"];
export type PlanSnapshot=Omit<Schema["PlanSnapshot"],"input">&{input:PlanInput};
export type AdoptedPlan=Omit<Schema["AdoptedPlan"],"input">&{input:PlanInput};
export type PlanResolution=Required<Omit<Schema["PlanResolution"],"measurement">>&Pick<Schema["PlanResolution"],"measurement">;
export const emptyPlan:PlanAnswers={measurement:"unknown",region:"unknown",definition:"unknown",signal:"unknown",input:"unknown",nuclear_stain:"unknown",background:"unknown",acquisition:"unknown",comparison:"unknown",allocation:"unknown",gating:"none"};
export const planReferences=catalog.references as PlanDecision["references"];
export function parsePlan(value:unknown):PlanInput{
 if(!value||typeof value!=="object"||Array.isArray(value))throw Error("計画ファイルの形式を確認してください。");const input=value as Record<string,unknown>;
 if(typeof input.version==="string"&&input.version.startsWith("1.0."))throw Error("以前の計画メモです。現在の計画ガイドで内容を確認し直してください。");
 if((input.format!==undefined&&input.format!=="cytellect-analysis-plan")||input.version!==PLAN_VERSION||Object.keys(input).some(key=>!["format","version","answers"].includes(key)))throw Error("対応していない計画ファイルです。");
 if(!input.answers||typeof input.answers!=="object"||Array.isArray(input.answers))throw Error("計画の回答がありません。");const answers=input.answers as Record<string,unknown>;
 if(Object.keys(answers).some(key=>!(key in answerOptions))||Object.entries(answerOptions).some(([key,values])=>answers[key]!==undefined&&!values.some(value=>value===answers[key])))throw Error("計画の回答を確認してください。");
 return {format:"cytellect-analysis-plan",version:PLAN_VERSION,answers:{...emptyPlan,...answers} as PlanAnswers};
}
export const planReceipt=(answers:PlanAnswers):PlanInput=>({format:"cytellect-analysis-plan",version:PLAN_VERSION,answers:{...answers}});
function candidate(a:PlanAnswers,id:CandidateId,metrics:string[]):PlanCandidate{
 const generic=id.startsWith("regions-"),automatic=["regions-nuclei","legacy-ncl","legacy-gfp-nuclear"].includes(id);const roles:PlanCandidate["required_channel_roles"]=[];
 if(automatic)roles.push("nuclear-stain");if(generic)roles.push(a.measurement==="area"?"image":"measurement");else{roles.push(id==="legacy-ncl"?"ncl":"gfp");if(id==="legacy-ncl"&&a.gating!=="none")roles.push("gfp");}
 const tasks:PlanCandidate["actual_review_required"]=["native-input","channel-mapping","background-rois","region-definition","metric-selection","mask-quality"];if(automatic)tasks.push("nuclear-stain");if(a.measurement==="area")tasks.push("calibration-for-physical-area");if(a.gating!=="none")tasks.push("gfp-gate");
 return {id,label:{"regions-manual":"手動領域の面積・輝度","regions-imported":"保存した領域の面積・輝度","regions-nuclei":"核染色からの核検出・測定","legacy-ncl":"核・核小体のNCL解析","legacy-gfp-nuclear":"核内GFP解析"}[id],workflow:generic?"regions":"nuclear",recipe_id:generic?"region-2d":id==="legacy-ncl"?"ncl-native-2d":"gfp-nuclear-2d",recipe_version:id==="regions-nuclei"?"1.1.0":"1.0.0",source:id==="regions-manual"?"manual":id==="regions-imported"?"imported":id==="regions-nuclei"?"stardist_nuclear":null,selection_source:generic?"region":"legacy-cell",allowed_metrics:metrics as PlanCandidate["allowed_metrics"],required_channel_roles:roles,actual_review_required:tasks};
}
export function buildPlan(a:PlanAnswers):PlanDecision{
 const r:PlanDecision={version:PLAN_VERSION,status:"planning-only-not-adopted",candidates:[],comparison_intent:"undetermined",descriptive_allowed:true,questions:[],decisions:[],limits:[],references:planReferences};const findings=catalog.findings as Record<string,Finding>;
 const add=(list:Finding[],id:string)=>{if(!findings[id])throw Error("Planning catalog mismatch");list.push(findings[id]);};
 if([a.measurement,a.region,a.definition].includes("unknown")||(a.measurement!=="area"&&a.signal==="unknown"))add(r.questions,"measurement");if(a.input!=="grayscale-2d")add(r.questions,"input");if(a.background!=="yes")add(r.questions,"background");if(a.acquisition!=="matched"&&["mean","integrated","ncl-ratio"].includes(a.measurement))add(r.questions,"acquisition");
 const automatic=["nuclear-stain","ncl-enrichment"].includes(a.definition);if(automatic&&a.nuclear_stain!=="yes")add(r.questions,"nuclear-stain");let ready=a.input==="grayscale-2d"&&![a.measurement,a.region,a.definition].includes("unknown")&&(a.measurement==="area"||a.signal!=="unknown")&&(!automatic||a.nuclear_stain==="yes");const metrics:Record<string,string[]>={area:["area_px","area_um2"],mean:["mean","mean_corrected"],integrated:["integrated","integrated_corrected"]};
 if(a.definition==="nuclear-stain"&&a.region!=="nucleus"){add(r.limits,"nuclear-model-scope");ready=false;}
 if(a.measurement==="ncl-ratio"&&(a.definition!=="ncl-enrichment"||a.signal!=="ncl"||!["nucleolus","nucleoplasm"].includes(a.region))){add(r.limits,"ratio-definition");ready=false;}
 if(a.definition==="ncl-enrichment"&&(!["nucleus","nucleolus","nucleoplasm"].includes(a.region)||(a.measurement!=="area"&&a.signal!=="ncl"))){add(r.limits,"ncl-definition-scope");ready=false;}
 if(a.definition==="ncl-enrichment")add(r.limits,"circularity");const legacyGfp=a.definition==="nuclear-stain"&&a.region==="nucleus"&&a.signal==="gfp",legacyNcl=a.definition==="ncl-enrichment";
 if(a.gating!=="none"){if(!(legacyGfp||legacyNcl)){add(r.limits,"gating-unsupported");ready=false;}add(r.limits,"selection");}
 if(ready){if(["manual","imported"].includes(a.definition)&&metrics[a.measurement])r.candidates.push(candidate(a,a.definition==="manual"?"regions-manual":"regions-imported",metrics[a.measurement]));else if(a.definition==="nuclear-stain"&&metrics[a.measurement]){if(a.gating==="none")r.candidates.push(candidate(a,"regions-nuclei",metrics[a.measurement]));if(legacyGfp)r.candidates.push(candidate(a,"legacy-gfp-nuclear",a.measurement==="area"?["nucleus_area_px","nucleus_area_um2"]:a.measurement==="mean"?["gfp_mean","gfp_mean_corrected"]:["gfp_integrated","gfp_integrated_corrected"]));}else if(legacyNcl){const prefix={nucleus:"nucleus",nucleolus:"nucleoli",nucleoplasm:"nucleoplasm"}[a.region as "nucleus"|"nucleolus"|"nucleoplasm"],areaPrefix=a.region==="nucleolus"?"nucleolar":prefix;r.candidates.push(candidate(a,"legacy-ncl",a.measurement==="ncl-ratio"?["ncl_nucleoplasm_over_nucleoli","ncl_log2_nucleoplasm_over_nucleoli"]:a.measurement==="area"?[`${areaPrefix}_area_px`,`${areaPrefix}_area_um2`]:[`ncl_${prefix}_${a.measurement}`,`ncl_${prefix}_${a.measurement}_corrected`]));}}
 if(a.comparison==="descriptive"){r.comparison_intent="descriptive";add(r.decisions,"descriptive");}else if(a.comparison==="unknown"||a.allocation!=="biological")add(r.questions,"independence");else{r.comparison_intent=a.comparison==="paired"?"paired-candidate":"independent-candidate";add(r.decisions,"units");add(r.limits,"sample-size");}
 if(a.measurement==="area")add(r.decisions,"area-calibration");if(a.measurement==="integrated")add(r.limits,"integrated-not-concentration");add(r.decisions,"actual-adoption");add(r.decisions,"traceability");return r;
}
