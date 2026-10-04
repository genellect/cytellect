"use client";
import {useEffect,useState} from "react";
import type {AdoptedPlan,PlanResolution} from "@/lib/analysis-plan";
import type {RegionMeasurementPolicy} from "@/lib/region-types";
import {isAreaOnly} from "@/lib/region-measurement";
import styles from "./workspace.module.css";
export type PlanMetricOption={id:string;label:string;metric:string;channel_id:string|null};
type RecipeView={id:string;source?:string;gfp_gate?:string;gfp_maximum?:number|null;nucleolar_method?:string};
export function planChanges(plan:AdoptedPlan,recipe:RecipeView,metric?:string,measurement?:RegionMeasurementPolicy|null){
 const candidate=plan.decision.candidates.find(item=>item.id===plan.selected_candidate_id);if(!candidate)return [];
 const changes:string[]=[];if(recipe.id!==candidate.recipe_id)changes.push("レシピ");if(candidate.workflow==="regions"&&recipe.source!==candidate.source)changes.push("領域の作成方法");if(candidate.workflow==="nuclear"&&recipe.id==="ncl-native-2d"&&recipe.nucleolar_method!=="ncl-otsu")changes.push("核小体の定義");if(metric&&!candidate.allowed_metrics.some(value=>value===metric))changes.push("測定する指標");if(isAreaOnly(candidate.measurement)!==isAreaOnly(measurement))changes.push("測定する量");const actual=recipe.gfp_gate||"none",expected=plan.input.answers.gating;if(!(actual===expected||(expected==="exploratory"&&["manual","otsu-batch"].includes(actual)))||recipe.gfp_maximum!=null)changes.push("GFP選別");return changes;
}
export default function PlanResolutionPanel({plan,recipe,options,value,blocked,saved=false,measurement,onChange}:{plan?:AdoptedPlan|null;recipe:RecipeView;options:PlanMetricOption[];value?:PlanResolution|null;blocked:boolean;saved?:boolean;measurement?:RegionMeasurementPolicy|null;onChange:(value:PlanResolution)=>void}){
 const [expanded,setExpanded]=useState(!saved);useEffect(()=>setExpanded(!saved),[saved]);
 if(!plan)return null;const candidate=plan.decision.candidates.find(item=>item.id===plan.selected_candidate_id);if(!candidate)return null;
 const selected=options.find(option=>option.metric===value?.metric&&option.channel_id===value.channel_id);const changes=planChanges(plan,recipe,selected?.metric,measurement);
 function choose(id:string){const option=options.find(item=>item.id===id),explicitMeasurement=value?.version==="1.1.0"||measurement||plan!.input.version==="2.1.0";if(option)onChange({version:explicitMeasurement?"1.1.0":"1.0.0",...(explicitMeasurement?{measurement:measurement??null}:{}),plan_sha256:plan!.sha256,candidate_id:plan!.selected_candidate_id,metric:option.metric,channel_id:option.channel_id,changes_acknowledged:false});}
 return <details className={styles.planResolution} aria-label="計画と実画像の対応" open={expanded} onToggle={event=>setExpanded(event.currentTarget.open)}><summary className={styles.planSummary}>解析計画{saved&&selected?` · ${selected.label}`:" · 実画像との対応を確認"}</summary><div className={styles.sectionHeader}><h2>解析計画の適用</h2><span className={styles.statusPill}>{selected?"指標を選択済み":"実画像で確認"}</span></div><p>計画：{candidate.label}</p><p className={styles.small}>{isAreaOnly(measurement)?"登録した画像に合わせて、面積の単位を選びます。領域と画素サイズは画像・撮影記録で確認してください。":"登録した画像に合わせて、測るチャンネルと指標を選びます。背景と領域は画像上で確認してください。"}</p>
  <label>{isAreaOnly(measurement)?"測定する面積の単位":"今回測定するチャンネル・指標"}<select aria-label={isAreaOnly(measurement)?"計画に対応する面積の単位":"計画に対応する実チャンネルと指標"} disabled={blocked||!options.length} value={selected?.id||""} onChange={event=>choose(event.target.value)}><option value="">実画像から選択してください</option><optgroup label="計画の指標">{options.filter(option=>candidate.allowed_metrics.some(value=>value===option.metric)).map(option=><option key={option.id} value={option.id}>{option.label}</option>)}</optgroup><optgroup label="計画から変更する指標">{options.filter(option=>!candidate.allowed_metrics.some(value=>value===option.metric)).map(option=><option key={option.id} value={option.id}>{option.label}</option>)}</optgroup></select></label>
  {!!changes.length&&<div className={styles.notice}><p>計画から変更：{changes.join("、")}</p><label className={styles.checkbox}><input type="checkbox" disabled={blocked||!selected} checked={!!value?.changes_acknowledged} onChange={event=>{if(value)onChange({...value,changes_acknowledged:event.target.checked});}}/>変更した内容を確認し、この条件で進めます。</label></div>}
  <details><summary>採用した計画と確認事項</summary>{plan.decision.questions.map(question=><p className={styles.small} key={question.id}><b>{question.title}</b> {question.detail}</p>)}<p className={styles.small}>指標は解析版へ保存します。統計・図の条件は結果画面で別途指定します。</p><p className={styles.small}>計画 {plan.input.version} · <code>{plan.sha256}</code></p></details>
 </details>;
}
