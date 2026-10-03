"use client";
import { useEffect,useState } from "react";
import type {PlanResolution} from "@/lib/analysis-plan";
import {plannedSelection,selectionChangedFromPlan} from "@/lib/planned-selection";
import { useQuery } from "@tanstack/react-query";
import { download, errorCodeMessage, errorMessage, post, request } from "@/lib/api";
import { formatValue, type Job } from "@/lib/types";
import { descriptiveFieldNumber, descriptiveFieldStatus, descriptiveJobs, descriptiveWarning, sameDescriptiveSettings, savedDescriptiveLabel, selectedDescriptiveJob, type DescriptiveResult, type DescriptiveSelection } from "@/lib/descriptive-view";
import { usePrivateImage } from "@/lib/usePrivateImage";
import type {RegionTraceTarget} from "@/lib/region-trace";
import RegionTraceTable from "./RegionTraceTable";
import styles from "./workspace.module.css";

export type DescriptiveOption = {id:string;label:string;selection:DescriptiveSelection};
type Props = {revisionId?:string;reviewed:boolean;options:DescriptiveOption[];jobs:Job[];blocked:boolean;dirty:boolean;run:(fn:()=>Promise<void>)=>void;fieldLabels?:Record<string,string>;revisionLabels?:Record<string,string>;onInspectField?:(fieldId:string,revisionId:string)=>void;onInspectRegion?:(target:RegionTraceTarget)=>void;traceBlocked?:boolean;planSelection?:PlanResolution|null;backgroundRequired?:boolean};
const files:Record<string,string>={"figure.svg":"SVG","figure.pdf":"PDF","figure.png":"PNG","plot-data.csv":"図の元データ","field-summary.csv":"視野別の要約","selection.csv":"採用・除外の記録","missingness.csv":"欠測の記録","figure-caption.md":"図の説明","figure-data.json":"条件と出典","methods.md":"Methods"};
const jobStatuses:Record<string,string>={queued:"図の生成を待っています。",running:"図と元データを生成しています。",failed:"図を生成できませんでした。",cancelled:"図の生成を中止しました。"};

export default function DescriptivePanel({revisionId,reviewed,options,jobs,blocked,dirty,run,fieldLabels={},revisionLabels={},onInspectField,onInspectRegion,traceBlocked=false,planSelection,backgroundRequired=true}:Props){
 const [choice,setChoice]=useState("");
 const [language,setLanguage]=useState("en");
 const [preset,setPreset]=useState("nature-double");
 const [selectedJob,setSelectedJob]=useState("");
 const [submitting,setSubmitting]=useState(false);
 useEffect(()=>setChoice(""),[revisionId]);
 const option=plannedSelection(options,choice,planSelection);
 const available=descriptiveJobs(jobs);
 const job=selectedDescriptiveJob(jobs,selectedJob,revisionId);
 const succeeded=job?.state==="succeeded";
 const result=useQuery({queryKey:["descriptive",job?.id],queryFn:()=>request<DescriptiveResult>(`/v1/jobs/${job!.id}/result`),enabled:succeeded});
 const data=!submitting&&succeeded&&result.data?.revision_id===job?.revision_id?result.data:undefined;
 const image=usePrivateImage(data&&job?`/v1/jobs/${job.id}/files/figure.png`:null);
 const settingsMatch=data&&sameDescriptiveSettings(data,option?.selection,language,preset);

 return <section className={styles.statistics} aria-label="測定値と分布">
  <div className={`${styles.statsControls} ${styles.descriptiveControls}`}>
   <h2>測定値と分布を見る</h2>
   <p className={styles.small}>領域ごとの値と、視野内の中央値を表示します。1視野から作成できます。群間の検定や独立反復数の推定は行いません。</p>
   <label>表示する測定値<select aria-label="表示する測定値" value={option?.id||""} onChange={e=>setChoice(e.target.value)}><option value="">測定値を選択してください</option>{options.map(o=><option key={o.id} value={o.id}>{o.label}</option>)}</select></label>
   {planSelection&&!option&&<p className={styles.notice}>採用計画の指標・チャンネルをこの解析版で利用できません。表示する測定値を確認して選択してください。</p>}{selectionChangedFromPlan(option,planSelection)&&<p className={styles.notice}>採用計画から指標またはチャンネルを変更しています。この選択を図の条件として保存します。</p>}
   <div className={styles.formGrid}>
    <label>図の言語<select aria-label="記述図の言語" value={language} onChange={e=>setLanguage(e.target.value)}><option value="en">English</option><option value="ja">日本語</option></select></label>
    <label>図の幅<select aria-label="記述図の幅" value={preset} onChange={e=>setPreset(e.target.value)}><option value="nature-single">89 mm</option><option value="nature-double">183 mm</option></select></label>
   </div>
   <p className={styles.small}>SVG・PDFは編集可能な文字で出力します。撮影条件や領域定義の妥当性は、画像と解析記録で確認してください。</p>
    {!reviewed&&<p className={styles.notice}>{backgroundRequired?"領域・背景・失敗や除外の理由を確認してから、図を作成できます。":"領域・面積・失敗や除外の理由を確認してから、図を作成できます。"}</p>}
   {dirty&&<p className={styles.notice}>未反映の変更があります。再測定して品質確認を完了してください。</p>}
   <button className={styles.primary} disabled={submitting||blocked||dirty||!reviewed||!revisionId||!option} onClick={()=>run(async()=>{
    if(!option)return;
    setSubmitting(true);
    try {
     const created=await post<{job_id:string}>(`/v1/revisions/${revisionId}/descriptive`,{mode:"descriptive",selection:option.selection,group_by:"field",plot:{preset,kind:"distribution",language,width_inches:7,height_inches:3,font_size:7,x_label:"",y_label:"",group_order:[]}});
     setSelectedJob(created.job_id);
    } finally { setSubmitting(false); }
   })}>分布図を作成</button>
  </div>
  <div className={styles.statsResults}>
   {submitting?<div className={styles.card} role="status">図の生成を受け付けています。</div>:job&&!succeeded?<div className={styles.card} role={job.state==="failed"?"alert":"status"}>
    <h3>{jobStatuses[job.state]??"処理状態を確認しています。"}</h3>
    {job.error&&<p>{errorCodeMessage(job.error)}</p>}
    {["failed","cancelled"].includes(job.state)&&<p>条件を確認して「分布図を作成」から再実行できます。以前の図は履歴から選べます。</p>}
   </div>:selectedJob&&!job?<div className={styles.card} role="status">選択した処理の状態を確認しています。</div>
   :result.error?<div className={styles.card} role="alert"><p>{errorMessage(result.error)}</p><button className={styles.secondary} onClick={()=>void result.refetch()}>再読み込み</button></div>
   :succeeded&&result.isPending?<div className={styles.card} role="status">保存済みの図と条件を読み込んでいます。</div>
   :succeeded&&result.data&&!data?<div className={styles.card} role="alert">結果の解析版が一致しません。この図は表示できません。</div>
   :!data?<div className={styles.card}><h3>図と元データをまとめて保存</h3><p>測定値を選ぶと、視野ごとの分布と採用・欠測の記録を出力できます。</p></div>
   :<>
    <div className={styles.card} aria-label="保存済みの記述図">
     <div className={styles.sectionHeader}><h3>測定値の分布</h3><span>{data.revision_id===revisionId?"採用中の解析版":"旧版の結果"}</span></div>
     <p aria-label="保存済みの測定値"><b>{savedDescriptiveLabel(data)}</b></p>
     <p className={styles.small}>単位: {data.unit} · {revisionLabels[data.revision_id]||"保存済みの解析版"}<br/>図の言語: {data.spec.plot.language==="ja"?"日本語":"English"} · {data.spec.plot.preset==="nature-single"?"89 mm":data.spec.plot.preset==="nature-double"?"183 mm":"カスタム"}</p>
     {!settingsMatch&&<p className={styles.notice}>表示中は保存済みの条件で作成した図です。現在選択した指標・表示設定を反映するには「分布図を作成」を実行してください。</p>}
     <p>{data.counts.observations} 観測 · 採用値のある視野 {data.counts.selected_fields} / 入力 {data.counts.input_fields} 視野</p>
     <p className={styles.small}>観測数・視野数は、独立した実験反復数ではありません。</p>
     {image&&<img src={image} alt="領域の測定値と視野内中央値の分布図" style={{maxWidth:"100%",height:"auto"}}/>}
     <div className={styles.actionRow}>{data.figure.source_files.filter(name=>files[name]).map(name=><button className={styles.secondary} key={name} onClick={()=>run(()=>download(`/v1/jobs/${job!.id}/files/${name}`,name))}>{files[name]} ↓</button>)}</div>
     {onInspectRegion&&data.spec.selection.source==="region"&&<RegionTraceTable key={job!.id} result={data} disabled={blocked||dirty||traceBlocked} onInspect={onInspectRegion}/>}
    </div>
    <div className={styles.card}>
     <h3>採用と欠測</h3>
     <p>領域・観測の入力 {data.selection.input_rows} · 明示除外 {data.selection.excluded} · 選別外 {data.selection.gate_unselected} · 指標欠測 {data.selection.missing_metric_selected}</p>
     <p>失敗を確認して除外した視野: {data.counts.excluded_failed_fields} / 入力 {data.counts.input_fields} 視野。これらの視野の観測数は不明で、領域・観測の入力数には含みません。</p>
     {!!data.excluded_failed_fields.length&&<ul>{data.excluded_failed_fields.map(row=><li key={row.field_id}>{fieldLabels[row.field_id]||"現在の一覧にない視野"} — {row.reason}</li>)}</ul>}
     <div className={styles.tableWrap}><table>
      <thead><tr><th>図と画像の対応</th><th>状態</th><th>採用観測数</th><th>中央値</th><th>第1四分位</th><th>第3四分位</th></tr></thead>
      <tbody>{data.field_summary.map(row=><tr key={row.field_id}><td>図の視野 {descriptiveFieldNumber(data,row.field_id)??"—"}<br/><small>{fieldLabels[row.field_id]||"現在の一覧にない視野"}</small>{onInspectField&&fieldLabels[row.field_id]&&<><br/><button className={styles.linkButton} disabled={blocked||dirty||traceBlocked} onClick={()=>onInspectField(row.field_id,data.revision_id)}>この解析版の画像を確認</button></>}</td><td>{descriptiveFieldStatus(row.status)}</td><td>{row.selected_rows}</td><td>{formatValue(row.median)}</td><td>{formatValue(row.q1)}</td><td>{formatValue(row.q3)}</td></tr>)}</tbody>
     </table></div>
     <p className={styles.small}>四分位数は観測値の広がりを表し、信頼区間ではありません。図の番号と画像一覧の番号は異なる場合があります。元画像を確認すると、この図を作成した解析版を開きます。</p>
     <details><summary>出典の識別情報</summary><p>解析版: <code>{data.revision_id}</code></p>{data.spec.selection.source==="region"&&<p>領域定義: <code>{data.spec.selection.region_set_id}</code> · チャンネル: <code>{data.spec.selection.channel_id??"面積測定"}</code></p>}<ul>{data.field_summary.map(row=><li key={row.field_id}>図の視野 {descriptiveFieldNumber(data,row.field_id)??"—"}: <code>{row.field_id}</code></li>)}{data.excluded_failed_fields.map(row=><li key={row.field_id}>失敗を確認して除外: <code>{row.field_id}</code></li>)}</ul></details>
     {!!data.warnings.length&&<details><summary>解釈上の注意</summary><ul>{data.warnings.map(warning=><li key={warning}>{descriptiveWarning(warning)}</li>)}</ul></details>}
    </div>
   </>}
   {!!available.length&&<details className={styles.card}><summary>記述図の履歴</summary>{available.map(j=><button className={styles.linkButton} key={j.id} onClick={()=>setSelectedJob(j.id)}>{new Date(j.created*1000).toLocaleString("ja-JP")} · {j.revision_id===revisionId?"採用中の版":"旧版"} · {j.state==="succeeded"?"作成済み":j.state==="failed"?"失敗":j.state==="cancelled"?"中止":j.state==="running"?"実行中":"待機中"}</button>)}</details>}
  </div>
 </section>;
}
