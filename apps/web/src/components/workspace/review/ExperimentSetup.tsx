"use client";
import {useEffect,useRef,useState} from "react";
import {LABEL_LIMIT,addRun,assignFields,emptyDesign,expandToPair,fieldsIn,issueText,labelProblem,readiness,removeRun,renameGroup,unassignField,updateRun,type ExperimentDesign} from "@/lib/workspace/experiment-design";
import styles from "./experiment-setup.module.css";

export interface SetupField {id:string;label:string;preview?:string}
export interface AddTarget {groupId:string;runId:string;sample:string|null}
interface Props {
  design:ExperimentDesign|null;
  fields:SetupField[];
  busy:boolean;
  readOnly:boolean;
  onSave:(design:ExperimentDesign)=>Promise<void>;
  onAdd:(target:AddTarget,files:FileList,design:ExperimentDesign)=>Promise<unknown>;
  /** Images added before the form was chosen: one screen takes them at once, two screens ask for their group.
   * Registering them without a form keeps typing groups and independent units per field in the statistics view. */
  pending?:{count:number;onPlace:(target:AddTarget,design:ExperimentDesign)=>Promise<void>;onWithoutForm:()=>void;onDiscard:()=>void};
  onOpenField:(fieldId:string)=>void;
  onCsv?:()=>void;
}

const today=()=>new Date().toISOString().slice(0,10);
/** A second independent experiment on the same day gets its own name: "2026-10-01 b". */
function uniqueRunLabel(date:string,taken:string[]){const used=new Set(taken.map(value=>value.toLowerCase()));if(!used.has(date.toLowerCase()))return date;for(const suffix of "bcdefghijklmnopqrstuvwxyz"){const label=`${date} ${suffix}`;if(!used.has(label))return label;}return `${date} z2`;}

/** Chooses one screen (describe one group) or two screens (compare two groups), then
 * groups, independent runs and samples before images are added (requirements E-01–E-08). */
export function ExperimentSetup({design,fields,busy,readOnly,onSave,onAdd,pending,onOpenField,onCsv}:Props){
  const [draft,setDraft]=useState<ExperimentDesign|null>(design);
  const [labels,setLabels]=useState<Record<string,string>>({});
  const [runDate,setRunDate]=useState(today());
  const [samples,setSamples]=useState<Record<string,string>>({});
  const [error,setError]=useState("");
  const [pendingTarget,setPendingTarget]=useState("");
  const fileInput=useRef<HTMLInputElement>(null),folderInput=useRef<HTMLInputElement>(null);
  const target=useRef<AddTarget|null>(null);
  useEffect(()=>{setDraft(design);},[design]);
  useEffect(()=>{folderInput.current?.setAttribute("webkitdirectory","");},[]);
  const fieldLabel=(id:string)=>fields.find(value=>value.id===id)?.label??id;

  async function save(next:ExperimentDesign){setError("");setDraft(next);try{await onSave(next);return true;}catch(cause){setError(cause instanceof Error?cause.message:"保存できませんでした。");return false;}}
  async function place(target:AddTarget,next:ExperimentDesign){setError("");try{await pending?.onPlace(target,next);}catch(cause){setError(cause instanceof Error?cause.message:"画像を登録できませんでした。");}}
  async function choose(layout:"single"|"pair"){
    const next=addRun(emptyDesign(layout),{label:runDate,performed_on:runDate});
    // One screen has one group and one run, so images that waited for the choice go there; two screens ask which group.
    if(await save(next)&&pending&&layout==="single")await place({groupId:next.groups[0].id,runId:next.runs![0].id,sample:null},next);
  }
  function pick(add:AddTarget,folder:boolean){target.current=add;(folder?folderInput:fileInput).current?.click();}
  async function received(list:FileList|null){
    if(!list?.length||!target.current||!draft)return;
    const chosen=target.current;target.current=null;setError("");
    try{await onAdd(chosen,list,draft);}catch(cause){setError(cause instanceof Error?cause.message:"画像を登録できませんでした。");}
  }

  if(!draft)return <section className={styles.choice} aria-label="解析の形を選ぶ">
    <h1>解析の形を選ぶ</h1>
    <p>実験の形に合わせて、画面の数を選びます。あとから 1 画面を 2 画面に広げられます。</p>
    {pending&&<p className={styles.pending} role="status">画像 {pending.count} 件を受け取りました。1 画面か 2 画面かを選ぶと登録します。
      <button className={styles.link} disabled={busy} title="群・試料・独立実験単位を、統計の画面で視野ごとに入力します" onClick={pending.onWithoutForm}>形を決めずに登録（群は統計で入力）</button>
      <button className={styles.link} disabled={busy} onClick={pending.onDiscard}>取り消す</button></p>}
    <div className={styles.choices}>
      <button className={styles.choiceCard} disabled={busy||readOnly} onClick={()=>choose("single")}><strong>1 画面</strong><span>1 つの群を記述する</span><small>核の大きさや数の分布を、実験回ごとに確かめます。検定はしません。</small></button>
      <button className={styles.choiceCard} disabled={busy||readOnly} onClick={()=>choose("pair")}><strong>2 画面</strong><span>2 つの群を比べる</span><small>対照と処理（例：WT と変異体、溶媒と薬剤）を並べ、同じ実験回の 2 群を対にして比べます。</small></button>
    </div>
    <label className={styles.inline}>最初の実験回の実施日<input type="date" value={runDate} onChange={event=>setRunDate(event.target.value)}/></label>
    {onCsv&&<button className={styles.link} onClick={onCsv}>測定済みの数値（CSV）を使う</button>}
  </section>;

  // One group is described, never tested: independence matters only once the design compares groups (E-01, T-05).
  const issues=readiness(draft,fields.map(value=>value.id)).filter(issue=>draft.layout==="pair"||issue.code!=="experiment_design_independence_unconfirmed");
  const assigned=new Set(Object.keys(draft.fields??{}));
  const unassigned=fields.filter(value=>!assigned.has(value.id));
  const runs=draft.runs??[];
  const locked=busy||readOnly;
  const labelOf=(key:string,fallback:string)=>labels[key]??fallback;
  function commitLabel(key:string,current:string,apply:(label:string)=>ExperimentDesign){
    const value=labels[key];if(value===undefined||value===current)return;
    const problem=labelProblem(value);if(problem){setError(problem);return;}
    setLabels(previous=>{const next={...previous};delete next[key];return next;});void save(apply(value));
  }

  return <section className={styles.setup} aria-label="実験の形">
    <header className={styles.setupHeader}>
      <h1>{draft.layout==="pair"?"2 画面：2 つの群を比べる":"1 画面：1 つの群を記述する"}</h1>
      {draft.layout==="single"&&!readOnly&&<button disabled={locked} onClick={()=>void save(expandToPair(draft))}>2 画面に広げる</button>}
    </header>
    <p className={styles.lead}>{draft.layout==="pair"
      ?"同じ実験回（実験日）に行った対照と処理を対にして比べます。n は実験回の数で、細胞や視野の数ではありません。"
      :"1 つの群の値の分布を、実験回ごとに示します。"}</p>
    {pending&&!readOnly&&<section className={styles.pendingPlace} aria-label="受け取った画像の追加先">
      <p>受け取った画像 {pending.count} 件を追加する実験回と群を選んでください。群ごとに分かれた画像は「取り消す」を押し、各群の「画像を追加」から追加します。</p>
      <select aria-label="追加先" disabled={locked} value={pendingTarget} onChange={event=>setPendingTarget(event.target.value)}>
        <option value="">追加先を選ぶ…</option>
        {runs.flatMap(run=>draft.groups.map(group=><option key={`${run.id}:${group.id}`} value={`${run.id}\u0000${group.id}`}>{run.label} · {group.label}</option>))}
      </select>
      <button disabled={locked||!pendingTarget} onClick={()=>{const [runId,groupId]=pendingTarget.split("\u0000");setPendingTarget("");void place({groupId,runId,sample:null},draft);}}>追加</button>
      <button className={styles.link} disabled={locked} onClick={pending.onDiscard}>取り消す</button>
    </section>}
    <div className={styles.grid} style={{gridTemplateColumns:`minmax(200px,270px) repeat(${draft.groups.length},minmax(0,1fr))`}} role="table" aria-label="群と実験回">
      <div role="row" className={styles.row}>
        <div role="columnheader" className={styles.corner}>実験回</div>
        {draft.groups.map(group=><div role="columnheader" key={group.id} className={styles.groupHead}>
          <label>群の名前<input value={labelOf(`group:${group.id}`,group.label)} maxLength={LABEL_LIMIT} disabled={locked}
            onChange={event=>setLabels(previous=>({...previous,[`group:${group.id}`]:event.target.value}))}
            onBlur={()=>commitLabel(`group:${group.id}`,group.label,label=>renameGroup(draft,group.id,label))}/></label>
          {draft.layout==="pair"&&<label className={styles.check}><input type="radio" name="control" checked={draft.control_group_id===group.id} disabled={locked} onChange={()=>void save({...draft,control_group_id:group.id})}/>対照</label>}
        </div>)}
      </div>
      {runs.map(run=><div role="row" key={run.id} className={styles.row}>
        <div role="rowheader" className={styles.runHead}>
          <label>名前<input value={labelOf(`run:${run.id}`,run.label)} maxLength={LABEL_LIMIT} disabled={locked}
            onChange={event=>setLabels(previous=>({...previous,[`run:${run.id}`]:event.target.value}))}
            onBlur={()=>commitLabel(`run:${run.id}`,run.label,label=>updateRun(draft,run.id,{label}))}/></label>
          <label>実施日<input type="date" value={run.performed_on??""} disabled={locked} onChange={event=>void save(updateRun(draft,run.id,{performed_on:event.target.value||null}))}/></label>
          <label>撮影日<input type="date" value={run.acquired_on??""} disabled={locked} onChange={event=>void save(updateRun(draft,run.id,{acquired_on:event.target.value||null}))}/></label>
          {!readOnly&&!Object.values(draft.fields??{}).some(value=>value.run_id===run.id)&&<button className={styles.link} disabled={locked} onClick={()=>void save(removeRun(draft,run.id))}>この回を削除</button>}
        </div>
        {draft.groups.map(group=>{
          const cell=fieldsIn(draft,group.id,run.id),key=`${run.id}:${group.id}`;
          return <div role="cell" key={group.id} className={styles.cell} data-empty={!cell.length}>
            <p className={styles.count}><span className={styles.cellGroup}>{group.label} · </span>{cell.length?`${cell.length} 視野`:"画像なし"}</p>
            <ul className={styles.fieldList}>{cell.map(([id,value])=><li key={id}>
              <button className={styles.fieldButton} onClick={()=>onOpenField(id)} title={fieldLabel(id)}>
                {fields.find(item=>item.id===id)?.preview&&<img src={fields.find(item=>item.id===id)!.preview} alt=""/>}
                <span>{fieldLabel(id)}</span>{value.sample&&<small>{value.sample}</small>}
              </button>
              {!readOnly&&<button className={styles.remove} aria-label={`${fieldLabel(id)} の割り当てを外す`} disabled={locked} onClick={()=>void save(unassignField(draft,id))}>×</button>}
            </li>)}</ul>
            {!readOnly&&<div className={styles.addRow}>
              <label className={styles.sample}>試料（任意）<input value={samples[key]??""} maxLength={LABEL_LIMIT} placeholder="例：カバーガラス 1" onChange={event=>setSamples(previous=>({...previous,[key]:event.target.value}))}/></label>
              <button disabled={locked} onClick={()=>pick({groupId:group.id,runId:run.id,sample:samples[key]?.trim()||null},false)}>画像を追加</button>
              <button disabled={locked} onClick={()=>pick({groupId:group.id,runId:run.id,sample:samples[key]?.trim()||null},true)}>フォルダ</button>
            </div>}
          </div>;
        })}
      </div>)}
    </div>
    {!readOnly&&<div className={styles.addRun}>
      <label>実験回を追加（実施日）<input type="date" value={runDate} onChange={event=>setRunDate(event.target.value)}/></label>
      <button disabled={locked||!runDate} onClick={()=>void save(addRun(draft,{label:uniqueRunLabel(runDate,runs.map(run=>run.label)),performed_on:runDate}))}>追加</button>
      {runs.some(run=>run.performed_on===runDate)&&<small>同じ日の別の独立な実験は「{uniqueRunLabel(runDate,runs.map(run=>run.label))}」として追加します。</small>}
    </div>}
    <label className={styles.independence}><input type="checkbox" checked={draft.independence_confirmed??false} disabled={locked} onChange={event=>void save({...draft,independence_confirmed:event.target.checked})}/>
      <span><strong>各実験回は独立に行った</strong>（別々に播種・処理・染色した）。日付やプレートが違うだけでは独立とは限りません。確認できない場合は、分布の記述まで行えます。</span></label>
    {unassigned.length>0&&<section className={styles.unassigned} aria-label="群と実験回が決まっていない視野">
      <h2>群と実験回が決まっていない視野</h2>
      <ul>{unassigned.map(field=><li key={field.id}><button className={styles.link} onClick={()=>onOpenField(field.id)}>{field.label}</button>
        <select aria-label={`${field.label} の割り当て`} disabled={locked||!runs.length} value="" onChange={event=>{const [runId,groupId]=event.target.value.split("\u0000");if(runId&&groupId)void save(assignFields(draft,[field.id],{group_id:groupId,run_id:runId}));}}>
          <option value="">割り当てる…</option>
          {runs.flatMap(run=>draft.groups.map(group=><option key={`${run.id}:${group.id}`} value={`${run.id}\u0000${group.id}`}>{run.label} · {group.label}</option>))}
        </select></li>)}</ul>
    </section>}
    {(issues.length>0||error)&&<ul className={styles.issues} aria-label="統計の前に確かめること">
      {error&&<li role="alert">{error}</li>}
      {issues.map((issue,index)=><li key={index}>{issueText(draft,issue,fieldLabel)}</li>)}
    </ul>}
    <input ref={fileInput} hidden type="file" multiple accept=".tif,.tiff,image/tiff" onChange={event=>{void received(event.target.files);event.target.value="";}}/>
    <input ref={folderInput} hidden type="file" multiple onChange={event=>{void received(event.target.files);event.target.value="";}}/>
  </section>;
}
