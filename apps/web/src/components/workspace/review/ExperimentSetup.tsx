"use client";
import {useEffect,useRef,useState} from "react";
import {LABEL_LIMIT,savePlan,addRun,assignFields,assignStratum,emptyDesign,expandToPair,fieldsIn,isStratified,issueText,labelProblem,readiness,removeRun,renameGroup,unassignField,updateRun,type ExperimentDesign} from "@/lib/workspace/experiment-design";
import {StrataEditor} from "./StrataEditor";
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
  /** The one next step (ED-02): check the detections on the images, or compare in statistics once every field is measured. */
  next?:{label:string;onClick:()=>void}|null;
}

const today=()=>new Date().toISOString().slice(0,10);
/** A second independent experiment on the same day gets its own name: "2026-10-01 b". */
function uniqueRunLabel(date:string,taken:string[]){const used=new Set(taken.map(value=>value.toLowerCase()));if(!used.has(date.toLowerCase()))return date;for(const suffix of "bcdefghijklmnopqrstuvwxyz"){const label=`${date} ${suffix}`;if(!used.has(label))return label;}return `${date} z2`;}

/** Chooses one screen (describe one group) or two screens (compare two groups), then
 * groups, independent runs and samples before images are added (requirements E-01–E-08). */
export function ExperimentSetup({design,fields,busy,readOnly,onSave,onAdd,pending,onOpenField,onCsv,next}:Props){
  const [draft,setDraft]=useState<ExperimentDesign|null>(design);
  const [labels,setLabels]=useState<Record<string,string>>({});
  const [runDate,setRunDate]=useState(today());
  const [samples,setSamples]=useState<Record<string,string>>({});
  const [error,setError]=useState("");
  const [pendingTarget,setPendingTarget]=useState("");
  const fileInput=useRef<HTMLInputElement>(null),folderInput=useRef<HTMLInputElement>(null);
  const target=useRef<AddTarget|null>(null);
  // The last plan the API stored: a refused save returns the editor to it instead of keeping the refused edit.
  const stored=useRef<ExperimentDesign|null>(design);
  useEffect(()=>{stored.current=design;setDraft(design);},[design]);
  useEffect(()=>{folderInput.current?.setAttribute("webkitdirectory","");},[]);
  const fieldLabel=(id:string)=>fields.find(value=>value.id===id)?.label??id;

  async function save(next:ExperimentDesign){
    setError("");setDraft(next);
    const outcome=await savePlan(stored.current,next,onSave);
    stored.current=outcome.stored;setDraft(outcome.shown);setError(outcome.error);
    return outcome.ok;
  }
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

  if(!draft)return <section className={styles.choice} aria-label="実験デザイン">
    <h1>実験デザイン</h1>
    <p>比べ方を選びます。1 群の記述は、後から対照との比較に広げられます。</p>
    {pending&&<p className={styles.pending} role="status">受け取った画像：{pending.count} 件。1 画面か 2 画面かの選択後に登録します。
      <button className={styles.link} disabled={busy} title="群・試料・実験回は、統計の画面で視野ごとに入力します" onClick={pending.onWithoutForm}>実験デザインなしで登録</button>
      <button className={styles.link} disabled={busy} onClick={pending.onDiscard}>取り消す</button></p>}
    <div className={styles.choices}>
      <button className={styles.choiceCard} disabled={busy||readOnly} onClick={()=>choose("single")}><strong>1 群を記述する</strong><span>1 画面</span><small>核の大きさや数の分布を実験回ごとに示します。検定はしません。</small></button>
      <button className={styles.choiceCard} disabled={busy||readOnly} onClick={()=>choose("pair")}><strong>対照と処理を比べる</strong><span>2 画面</span><small>対照と処理（例：WT と変異体、溶媒と薬剤）を、同じ実験回で対にして比較します。</small></button>
    </div>
    <label className={styles.inline}>最初の実験回の実施日<input type="date" value={runDate} onChange={event=>setRunDate(event.target.value)}/></label>
    {onCsv&&<button className={styles.link} onClick={onCsv}>測定済みの CSV を使用</button>}
  </section>;

  // One group is described, never tested: independence matters only once the design compares groups (E-01, T-05).
  // The demo states its unconfirmed independence as the record it is, beside the reason (ED-03), not as a task.
  const issues=readiness(draft,fields.map(value=>value.id)).filter(issue=>(draft.layout==="pair"&&!readOnly)||issue.code!=="experiment_design_independence_unconfirmed");
  const assigned=new Set(Object.keys(draft.fields??{}));
  const unassigned=fields.filter(value=>!assigned.has(value.id));
  const runs=draft.runs??[];
  const locked=busy||readOnly;
  const pair=draft.layout==="pair";
  const registered=new Set(fields.map(value=>value.id));
  const placed=Object.keys(draft.fields??{}).filter(id=>registered.has(id)).length;
  const independent=draft.independence_confirmed??false;
  // One line of what is in place (ED-02): runs, groups, fields, and what the comparison will be.
  const status=[`${runs.length} 実験回 × ${draft.groups.length} 群、${placed} 視野を割り当て済み。`,
    pair?(independent?"実験回は独立と記録済みのため、検定と信頼区間まで示します。":"独立性が未確認のため、検定なしの記述（実験回ごとの値と差）です。"):"1 群の記述です（検定なし）。",
    issues.length?`統計の前の確認：${issues.length} 件（下）。`:""].filter(Boolean).join("");
  const labelOf=(key:string,fallback:string)=>labels[key]??fallback;
  function commitLabel(key:string,current:string,apply:(label:string)=>ExperimentDesign){
    const value=labels[key];if(value===undefined||value===current)return;
    const problem=labelProblem(value);if(problem){setError(problem);return;}
    setLabels(previous=>{const next={...previous};delete next[key];return next;});void save(apply(value));
  }

  return <section className={styles.setup} aria-label="実験デザイン">
    <header className={styles.setupHeader}>
      <h1>{pair?"対照と処理を、実験回ごとに対にして比べる":"1 群の値を、実験回ごとに示す"}<small>{pair?"2 画面":"1 画面"}</small></h1>
      <div className={styles.headerActions}>
        {draft.layout==="single"&&!readOnly&&<button disabled={locked} onClick={()=>void save(expandToPair(draft))}>対照との比較に広げる（2 画面）</button>}
        {next&&<button className={styles.next} disabled={busy} onClick={next.onClick}>{next.label}</button>}
      </div>
    </header>
    {/* What a run is, why runs are kept apart, and how the values are combined, in the first view (C-1, ED-01). */}
    <section className={styles.explain} aria-label="実験回とまとめ方">
      <p>実験回は、播種・処理・染色・撮影を独立に行った 1 回の実験です。同じ回の核や視野は互いに独立ではないため、回ごとに分けて記録します。{pair?"同じ実験回の対照と処理を対にし、回ごとの差を比べます。":""}n は核や視野の数ではなく、実験回の数です（図では Run）。</p>
      <ol className={styles.flow} aria-label="値のまとめ方"><li>核ごとの値</li><li>視野の中央値</li><li>試料の平均</li><li>実験回の値</li>{pair&&<li>回ごとの差（処理 − 対照）</li>}</ol>
    </section>
    <p className={styles.status} role="status">{status}</p>
    {readOnly&&<p className={styles.record}>公開データの実験デザインです（変更できません）。{pair&&!independent&&"出典に、実験回が独立に行われたかの記載がないため、独立性は未確認として記録しています。群間比較は検定なしの記述になります。"}</p>}
    {pending&&!readOnly&&<section className={styles.pendingPlace} aria-label="受け取った画像の追加先">
      <p>受け取った画像 {pending.count} 件の追加先を選んでください。群ごとに分かれた画像は「取り消す」の後、各群の「画像を追加」から追加します。</p>
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
          {readOnly?<p className={styles.recorded}><strong>{group.label}</strong>{pair&&draft.control_group_id===group.id&&<span className={styles.badge}>対照</span>}</p>:<><label>群の名前<input value={labelOf(`group:${group.id}`,group.label)} maxLength={LABEL_LIMIT} disabled={locked}
            onChange={event=>setLabels(previous=>({...previous,[`group:${group.id}`]:event.target.value}))}
            onBlur={()=>commitLabel(`group:${group.id}`,group.label,label=>renameGroup(draft,group.id,label))}/></label>
          {draft.layout==="pair"&&<label className={styles.check}><input type="radio" name="control" checked={draft.control_group_id===group.id} disabled={locked} onChange={()=>void save({...draft,control_group_id:group.id})}/>対照</label>}</>}
        </div>)}
      </div>
      {runs.map(run=><div role="row" key={run.id} className={styles.row}>
        <div role="rowheader" className={styles.runHead}>
          {readOnly?<p className={styles.recorded}><strong>{run.label}</strong>{run.performed_on&&<span>実施日 {run.performed_on}</span>}{run.acquired_on&&<span>撮影日 {run.acquired_on}</span>}</p>:<><label>名前<input value={labelOf(`run:${run.id}`,run.label)} maxLength={LABEL_LIMIT} disabled={locked}
            onChange={event=>setLabels(previous=>({...previous,[`run:${run.id}`]:event.target.value}))}
            onBlur={()=>commitLabel(`run:${run.id}`,run.label,label=>updateRun(draft,run.id,{label}))}/></label>
          <label>実施日<input type="date" value={run.performed_on??""} disabled={locked} onChange={event=>void save(updateRun(draft,run.id,{performed_on:event.target.value||null}))}/></label>
          <label>撮影日<input type="date" value={run.acquired_on??""} disabled={locked} onChange={event=>void save(updateRun(draft,run.id,{acquired_on:event.target.value||null}))}/></label>
          {!Object.values(draft.fields??{}).some(value=>value.run_id===run.id)&&<button className={styles.link} disabled={locked} onClick={()=>void save(removeRun(draft,run.id))}>この回を削除</button>}</>}
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
              {isStratified(draft)&&readOnly&&<small className={styles.stratum}>{draft.strata.find(stratum=>stratum.id===value.stratum_id)?.label??"層：未割り当て"}</small>}
              {isStratified(draft)&&!readOnly&&<select className={styles.stratum} aria-label={`${fieldLabel(id)} の層`} disabled={locked} value={value.stratum_id??""}
                onChange={event=>void save(assignStratum(draft,[id],event.target.value||null))}>
                <option value="">層を選ぶ…</option>{draft.strata.map(stratum=><option key={stratum.id} value={stratum.id}>{stratum.label}</option>)}</select>}
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
    {!readOnly&&<label className={styles.independence}><input type="checkbox" checked={draft.independence_confirmed??false} disabled={locked} onChange={event=>void save({...draft,independence_confirmed:event.target.checked})}/>
      <span><strong>各実験回は独立に行った</strong>（別々に播種・処理・染色）。日付やプレートの違いだけでは独立とは限りません。未確認の場合、群間比較は記述統計のみです。</span></label>}
    <StrataEditor design={draft} locked={locked} readOnly={readOnly} onSave={save}/>
    {unassigned.length>0&&<section className={styles.unassigned} aria-label="群・実験回が未割り当ての視野">
      <h2>群・実験回が未割り当ての視野</h2>
      <ul>{unassigned.map(field=><li key={field.id}><button className={styles.link} onClick={()=>onOpenField(field.id)}>{field.label}</button>
        {!readOnly&&<select aria-label={`${field.label} の割り当て`} disabled={locked||!runs.length} value="" onChange={event=>{const [runId,groupId]=event.target.value.split("\u0000");if(runId&&groupId)void save(assignFields(draft,[field.id],{group_id:groupId,run_id:runId}));}}>
          <option value="">割り当てる…</option>
          {runs.flatMap(run=>draft.groups.map(group=><option key={`${run.id}:${group.id}`} value={`${run.id}\u0000${group.id}`}>{run.label} · {group.label}</option>))}
        </select>}</li>)}</ul>
    </section>}
    {(issues.length>0||error)&&<ul className={styles.issues} aria-label="統計の前の確認事項">
      {error&&<li role="alert">{error}</li>}
      {issues.map((issue,index)=><li key={index}>{issueText(draft,issue,fieldLabel)}</li>)}
    </ul>}
    <input ref={fileInput} hidden type="file" multiple accept=".tif,.tiff,image/tiff" onChange={event=>{void received(event.target.files);event.target.value="";}}/>
    <input ref={folderInput} hidden type="file" multiple onChange={event=>{void received(event.target.files);event.target.value="";}}/>
  </section>;
}
