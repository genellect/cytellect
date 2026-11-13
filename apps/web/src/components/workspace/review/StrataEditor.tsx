"use client";
import {useState} from "react";
import {LABEL_LIMIT,addFactor,addLevel,addStratum,addStratumCombination,combinationLabel,declareStrata,factorProblem,fieldsInStrata,isStratified,levelProblem,
  removeFactor,removeLevel,removeStrata,removeStrataById,strataNaming,strataOf,stratumProblem,type ExperimentDesign,type StratifiedExperimentDesign} from "@/lib/workspace/experiment-design";
import styles from "./experiment-setup.module.css";

/** Level names typed as a list; each is one level (nothing is derived from the images). */
const levels=(value:string)=>value.split(/[、,]/).map(item=>item.trim()).filter(Boolean);

/** Declares the conditions held fixed within each comparison (experiment design 1.1.0): 1–3 factors with
 * their levels, and each stratum as one level of every factor. Fields are assigned in the grid above;
 * removing a level, factor or stratum leaves its fields unassigned (asked first), never moved. Inputs are
 * checked before saving and kept until the plan is stored, so a refused edit can be corrected and saved again. */
export function StrataEditor({design,locked,readOnly,onSave}:{design:ExperimentDesign;locked:boolean;readOnly:boolean;onSave:(next:ExperimentDesign)=>Promise<boolean>}){
  const [factorLabel,setFactorLabel]=useState(""),[levelLabels,setLevelLabels]=useState("");
  const [newLevels,setNewLevels]=useState<Record<string,string>>({});
  const [combination,setCombination]=useState<Record<string,string>>({}),[comboLabel,setComboLabel]=useState("");
  // Removing strata leaves their fields without a stratum: the researcher confirms with the count first.
  const confirmUnassign=(plan:StratifiedExperimentDesign,strataIds:string[],sentence:(count:number)=>string)=>{
    const count=fieldsInStrata(plan,strataIds).length;
    return !strataIds.length||window.confirm(`${sentence(strataIds.length)}${count?`その ${count} 視野は層が未割り当てになり、選び直すまでどの層の比較にも入りません。`:""}保存した結果は再計算が必要になります。`);
  };
  // A typed factor is checked only once something was typed; the reason is shown next to the disabled button.
  const factorIssue=factorLabel||levelLabels?factorProblem(design,factorLabel,levels(levelLabels)):null;
  const factorForm=(apply:(label:string,values:string[])=>Promise<boolean>,button:string)=><div className={styles.addRun}>
    <label>因子<input value={factorLabel} maxLength={LABEL_LIMIT} placeholder="例：細胞株、時点" onChange={event=>setFactorLabel(event.target.value)}/></label>
    <label>水準（「、」区切り）<input value={levelLabels} placeholder="例：条件 A、条件 B" onChange={event=>setLevelLabels(event.target.value)}/></label>
    <button disabled={locked||!factorLabel||!levelLabels||!!factorIssue}
      onClick={()=>{void apply(factorLabel,levels(levelLabels)).then(saved=>{if(saved){setFactorLabel("");setLevelLabels("");}});}}>{button}</button>
    {factorIssue&&<small role="status">{factorIssue}</small>}
  </div>;

  // Most designs hold nothing else fixed: the option stays folded until the researcher opens it.
  if(!isStratified(design))return <section className={styles.strata} aria-label="層">
    <details><summary><h2 className={styles.inlineHeading}>層別（任意）</h2></summary>
      <p>層（細胞株、時点など）ごとに 2 群を比較します。層の統合・層間の比較はしません。</p>
      {!readOnly&&factorForm((label,values)=>onSave(declareStrata(design,label,values)),"層を宣言")}
    </details>
  </section>;

  const strata=strataOf(design);
  const choose=(factorId:string,levelId:string)=>{const next={...combination,[factorId]:levelId};setCombination(next);setComboLabel(combinationLabel(design,next));};
  // Only the current factors' choices count (a removed factor or level leaves nothing behind).
  const chosen=Object.fromEntries(design.factors.flatMap(factor=>factor.levels.some(level=>level.id===combination[factor.id])?[[factor.id,combination[factor.id]!]]:[]));
  const complete=Object.keys(chosen).length===design.factors.length;
  const comboIssue=complete?stratumProblem(design,chosen,comboLabel):null;
  return <section className={styles.strata} aria-label="層">
    <h2>層別</h2>
    <p>層ごとに 2 群を比較します。層の統合・層間の比較はしません。層は各因子の水準の組み合わせで宣言します。</p>
    <ul className={styles.factors} aria-label="因子と水準">{design.factors.map(factor=><li key={factor.id}>
      <strong>{factor.label}</strong>：{factor.levels.map(level=><span key={level.id} className={styles.level}>{level.label}
        {!readOnly&&factor.levels.length>1&&<button className={styles.remove} aria-label={`水準 ${level.label} を外す`} disabled={locked}
          onClick={()=>{const named=strataNaming(design,factor.id,level.id);if(confirmUnassign(design,named,count=>`水準「${level.label}」と、それを含む層 ${count} 件を外します。`))void onSave(removeLevel(design,factor.id,level.id));}}>×</button>}</span>)}
      {!readOnly&&<span className={styles.inlineAdd}>
        <input aria-label={`${factor.label} に加える水準`} value={newLevels[factor.id]??""} maxLength={LABEL_LIMIT} placeholder="水準を追加" onChange={event=>setNewLevels(previous=>({...previous,[factor.id]:event.target.value}))}/>
        <button disabled={locked||!newLevels[factor.id]||!!levelProblem(design,factor.id,newLevels[factor.id]!)} onClick={()=>{const label=newLevels[factor.id]!;
          void onSave(design.factors.length===1?addStratum(design,label):addLevel(design,factor.id,label)).then(saved=>{if(saved)setNewLevels(previous=>({...previous,[factor.id]:""}));});}}>追加</button>
        {newLevels[factor.id]&&levelProblem(design,factor.id,newLevels[factor.id]!)&&<small role="status">{levelProblem(design,factor.id,newLevels[factor.id]!)}</small>}
        <button className={styles.link} disabled={locked} onClick={()=>{const named=strataNaming(design,factor.id);if(confirmUnassign(design,named,count=>`因子「${factor.label}」と、層 ${count} 件を外します。`))void onSave(removeFactor(design,factor.id));}}>この因子を外す</button>
      </span>}
    </li>)}</ul>
    {!readOnly&&design.factors.length<3&&<details className={styles.addFactor}><summary>因子を追加（最大 3 つ）</summary>
      {factorForm(async(label,values)=>confirmUnassign(design,design.strata.map(value=>value.id),count=>`因子を加えると、今の層 ${count} 件はすべての因子の水準を持たなくなるため外れます。`)&&onSave(addFactor(design,label,values)),"因子を追加")}
      {design.strata.length>0&&<small>因子を加えると、今の層はすべての因子の水準を持たなくなるため外れます。層を宣言し直してください。</small>}
    </details>}
    <table className={styles.strataTable} aria-label="宣言した層"><thead><tr><th>層</th>{design.factors.map(factor=><th key={factor.id}>{factor.label}</th>)}<th>視野</th><th/></tr></thead>
      <tbody>{design.strata.map(stratum=><tr key={stratum.id}><td>{stratum.label}</td>
        {design.factors.map(factor=><td key={factor.id}>{factor.levels.find(level=>level.id===stratum.levels[factor.id])?.label}</td>)}
        <td>{strata.find(value=>value.id===stratum.id)?.fieldIds.length??0}</td>
        <td>{!readOnly&&<button className={styles.link} disabled={locked} onClick={()=>{if(confirmUnassign(design,[stratum.id],()=>`層「${stratum.label}」を外します。`))void onSave(removeStrataById(design,[stratum.id]));}}>外す</button>}</td></tr>)}
      </tbody></table>
    {design.strata.length===0&&<p role="status">層がまだありません。下で、各因子の水準を 1 つずつ選んで層を宣言してください。</p>}
    {!readOnly&&<div className={styles.addRun} aria-label="層を宣言">
      {design.factors.map(factor=><label key={factor.id}>{factor.label}<select value={combination[factor.id]??""} onChange={event=>choose(factor.id,event.target.value)}>
        <option value="">選ぶ…</option>{factor.levels.map(level=><option key={level.id} value={level.id}>{level.label}</option>)}</select></label>)}
      <label>層の名前<input value={comboLabel} maxLength={LABEL_LIMIT} onChange={event=>setComboLabel(event.target.value)}/></label>
      <button disabled={locked||!complete||!!comboIssue} onClick={()=>{void onSave(addStratumCombination(design,chosen,comboLabel)).then(saved=>{if(saved){setCombination({});setComboLabel("");}});}}>層を宣言</button>
      {comboIssue&&<small role="status">{comboIssue}</small>}
      <button className={styles.link} disabled={locked} onClick={()=>{if(confirmUnassign(design,design.strata.map(value=>value.id),count=>`層の設定（因子・水準と層 ${count} 件）を外します。`))void onSave(removeStrata(design));}}>層を使わない</button>
    </div>}
  </section>;
}
