"use client";
import FigureControls from "./FigureControls";
import {defaultFigureEdits,figureOrder,validFigureEdits} from "@/lib/figure-controls";
import { useEffect,useState } from "react";
import type {PlanResolution} from "@/lib/analysis-plan";
import {plannedSelection,selectionChangedFromPlan} from "@/lib/planned-selection";
import { useQuery } from "@tanstack/react-query";
import { download, errorCodeMessage, errorMessage, fetchBlob, post, request } from "@/lib/api";
import { formatValue, type Job } from "@/lib/types";
import { descriptiveFieldNumber, descriptiveFieldStatus, descriptiveFigureView, descriptiveJobs, descriptiveRecovery, descriptiveRequest, descriptiveTableFiles, descriptiveWarning, sameDescriptiveSettings, savedDescriptiveLabel, selectedDescriptiveJob, type DescriptiveResult, type DescriptiveSelection } from "@/lib/descriptive-view";
import type {RegionTraceTarget} from "@/lib/region-trace";
import RegionTraceTable from "./RegionTraceTable";
import styles from "./workspace.module.css";

export type DescriptiveOption = {id:string;label:string;selection:DescriptiveSelection};
type Props = {revisionId?:string;reviewed:boolean;options:DescriptiveOption[];jobs:Job[];blocked:boolean;dirty:boolean;run:(fn:()=>Promise<void>)=>void;fieldLabels?:Record<string,string>;revisionLabels?:Record<string,string>;onInspectField?:(fieldId:string,revisionId:string)=>void;onInspectRegion?:(target:RegionTraceTarget)=>void;traceBlocked?:boolean;planSelection?:PlanResolution|null;backgroundRequired?:boolean};
const jobStatuses:Record<string,string>={queued:"図の生成を待っています。",running:"図と元データを生成しています。",failed:"図を生成できませんでした。",cancelled:"図の生成を中止しました。"};

// Remount for every saved job/page. A pending or missing image can never reuse another page's blob.
function SavedPageImage({path}:{path:string}){
 const [image,setImage]=useState<string|null>(null);
 const [failed,setFailed]=useState(false);
 const [attempt,setAttempt]=useState(0);
 useEffect(()=>{
  const controller=new AbortController();let objectUrl:string|undefined;
  setImage(null);setFailed(false);
  void fetchBlob(path,controller.signal).then(blob=>{
   if(controller.signal.aborted)return;
   objectUrl=URL.createObjectURL(blob);setImage(objectUrl);
  }).catch(()=>{if(!controller.signal.aborted)setFailed(true);});
  return()=>{controller.abort();if(objectUrl)URL.revokeObjectURL(objectUrl);};
 },[path,attempt]);
 if(failed)return <div className={styles.notice} role="alert"><p>このページの図を読み込めません。測定表と出典は下で確認できます。</p><button className={styles.secondary} onClick={()=>{setImage(null);setFailed(false);setAttempt(value=>value+1);}}>このページを再読み込み</button></div>;
 return image?<img src={image} alt="領域の測定値と視野内中央値の分布図" style={{maxWidth:"100%",height:"auto"}} onError={()=>{setImage(null);setFailed(true);}}/>:<p className={styles.small} role="status">このページの図を読み込んでいます。</p>;
}

function SavedDescriptiveFigure({data,jobId,language,preset,disabled,run,onCreated}:{data:DescriptiveResult;jobId:string;language:string;preset:string;disabled:boolean;run:Props["run"];onCreated:(id:string)=>void}){
 const view=descriptiveFigureView(data);
 const [pageIndex,setPageIndex]=useState(0);
 const [retrying,setRetrying]=useState(false);
 const [retryError,setRetryError]=useState("");
 const page=view.kind==="ready"||view.kind==="legacy"?view.pages[pageIndex]:undefined;
 const savedPlotChanged=data.spec.plot.language!==language||data.spec.plot.preset!==preset;
 const tableFiles=Array.isArray(data.figure?.source_files)?data.figure.source_files.filter(name=>Object.hasOwn(descriptiveTableFiles,name)):[];
 return <div className={styles.descriptiveFigure}>
  {view.kind==="tables_only"?<div className={styles.notice} role="status">
   <p><b>測定表を保存しました。図は作成できませんでした。</b></p>
   <p>{errorCodeMessage(view.code)}{view.failedPage!==null&&`（${view.failedPage} ページ目）`}</p>
   <p>再作成する対象: {savedDescriptiveLabel(data)}。この結果と同じ解析版・測定値を使用します。</p>
   <p>再作成時の表示: {language==="ja"?"日本語":"English"} · {preset==="nature-single"?"89 mm":"183 mm"}{savedPlotChanged?"（保存時から変更）":"（保存時と同じ）"}。</p>
   <button className={styles.secondary} disabled={disabled||retrying} onClick={()=>run(async()=>{
    setRetrying(true);setRetryError("");
    try{const retry=descriptiveRecovery(data,language,preset);const created=await post<{job_id:string}>(retry.path,retry.body);onCreated(created.job_id);}
    catch(error){setRetryError(errorMessage(error));}
    finally{setRetrying(false);}
   })}>{retrying?"再作成を受け付けています…":"この解析版で図を再作成"}</button>
   {disabled&&<p>未反映の操作がある場合は、反映または取り消してから再作成してください。</p>}
   {retryError&&<p role="alert">{retryError} 保存済みの測定表は引き続き確認できます。</p>}
  </div>:view.kind==="invalid"?<p className={styles.notice} role="alert">図のページ情報を確認できません。保存済みの測定表と出典を確認してください。</p>:<>
   {view.kind==="ready"&&<>
    <div className={styles.descriptivePagination} aria-label="記述図のページ">
     <button className={styles.secondary} disabled={pageIndex===0} onClick={()=>setPageIndex(index=>index-1)}>前のページ</button>
     <label>ページ<select aria-label="記述図のページ番号" value={pageIndex} onChange={event=>setPageIndex(Number(event.target.value))}>{view.pages.map((item,index)=><option key={item.index} value={index}>{item.index} / {view.pages.length}</option>)}</select></label>
     <button className={styles.secondary} disabled={pageIndex===view.pages.length-1} onClick={()=>setPageIndex(index=>index+1)}>次のページ</button>
    </div>
    <p className={styles.small} aria-live="polite">{page?.index} / {view.pages.length} ページ · 図の視野 {page?.fieldNumbers.join("・")} · 全 {view.fieldCount} 視野</p>
    <p className={styles.small}>全ページで同じ縦軸範囲を使用しています（{formatValue(view.limits[0])}–{formatValue(view.limits[1])} {data.unit}）。ページ分割によるデータの除外はありません。</p>
   </>}
   {page?<>
    <SavedPageImage key={`${jobId}/${page.files.png}`} path={`/v1/jobs/${jobId}/files/${page.files.png}`}/>
    <div className={styles.actionRow} aria-label="表示中の図を保存">{(["svg","pdf","png"] as const).map(format=><button className={styles.secondary} key={format} onClick={()=>run(()=>download(`/v1/jobs/${jobId}/files/${page.files[format]}`,page.files[format]))}>{format.toUpperCase()} ↓</button>)}</div>
   </>:<p className={styles.notice} role="alert">選択したページを確認できません。別の図は代わりに表示しません。</p>}
  </>}
  <div className={styles.actionRow} aria-label="全視野の表と出典を保存">{tableFiles.map(name=><button className={styles.secondary} key={name} onClick={()=>run(()=>download(`/v1/jobs/${jobId}/files/${name}`,name))}>{descriptiveTableFiles[name]} ↓</button>)}</div>
 </div>;
}

export default function DescriptivePanel({revisionId,reviewed,options,jobs,blocked,dirty,run,fieldLabels={},revisionLabels={},onInspectField,onInspectRegion,traceBlocked=false,planSelection,backgroundRequired=true}:Props){
 const [choice,setChoice]=useState("");
 const [figure,setFigure]=useState(defaultFigureEdits);
 const [language,setLanguage]=useState("en");
 const [preset,setPreset]=useState("nature-double");
 const [selectedJob,setSelectedJob]=useState("");
 const [submitting,setSubmitting]=useState(false);
 useEffect(()=>{setChoice("");setFigure(defaultFigureEdits());},[revisionId]);
 const option=plannedSelection(options,choice,planSelection);
 const available=descriptiveJobs(jobs);
 const job=selectedDescriptiveJob(jobs,selectedJob,revisionId);
 const succeeded=job?.state==="succeeded";
 const result=useQuery({queryKey:["descriptive",job?.id],queryFn:()=>request<DescriptiveResult>(`/v1/jobs/${job!.id}/result`),enabled:succeeded});
 const data=!submitting&&succeeded&&result.data?.revision_id===job?.revision_id?result.data:undefined;
 const orderGroups=data&&data.revision_id===revisionId?data.field_summary.map(row=>({id:row.field_id,label:fieldLabels[row.field_id]||`図の視野 ${descriptiveFieldNumber(data,row.field_id)}`})):[];
 const edits={...figure,group_order:figure.group_order.length?figureOrder(figure.group_order,orderGroups.map(group=>group.id)):[]};
 const settingsMatch=data&&sameDescriptiveSettings(data,option?.selection,language,preset,edits);

 return <section className={styles.statistics} aria-label="測定値と分布">
  <div className={`${styles.statsControls} ${styles.descriptiveControls}`}>
   <h2>図の出力</h2>
   <p className={styles.small}>領域ごとの値と、視野内の中央値を表示します。1視野から作成できます。群間の検定や独立反復数の推定は行いません。</p>
   <label>表示する測定値<select aria-label="表示する測定値" value={option?.id||""} onChange={e=>setChoice(e.target.value)}><option value="">測定値を選択してください</option>{options.map(o=><option key={o.id} value={o.id}>{o.label}</option>)}</select></label>
   {planSelection&&!option&&<p className={styles.notice}>採用計画の指標・チャンネルをこの解析版で利用できません。表示する測定値を確認して選択してください。</p>}{selectionChangedFromPlan(option,planSelection)&&<p className={styles.notice}>採用計画から指標またはチャンネルを変更しています。この選択を図の条件として保存します。</p>}
   <div className={styles.formGrid}>
    <label>図の言語<select aria-label="記述図の言語" value={language} onChange={e=>setLanguage(e.target.value)}><option value="en">English</option><option value="ja">日本語</option></select></label>
    <label>図の幅<select aria-label="記述図の幅" value={preset} onChange={e=>setPreset(e.target.value)}><option value="nature-single">89 mm</option><option value="nature-double">183 mm</option></select></label>
   </div>
   <FigureControls prefix="記述図" preset={preset} value={edits} onChange={setFigure} groups={orderGroups}/>
   <p className={styles.small}>SVG・PDFは編集可能な文字で出力します。撮影条件や領域定義の妥当性は、画像と解析記録で確認してください。</p>
    {!reviewed&&<p className={styles.notice}>{backgroundRequired?"領域・背景・失敗や除外の理由を確認してから、図を作成できます。":"領域・面積・失敗や除外の理由を確認してから、図を作成できます。"}</p>}
   {dirty&&<p className={styles.notice}>未反映の変更があります。再測定して品質確認を完了してください。</p>}
   <button className={styles.primary} disabled={!validFigureEdits(edits,preset)||submitting||blocked||dirty||!reviewed||!revisionId||!option} onClick={()=>run(async()=>{
    if(!option)return;
    setSubmitting(true);
    try {
     const created=await post<{job_id:string}>(`/v1/revisions/${revisionId}/descriptive`,descriptiveRequest(option.selection,language,preset,edits));
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
   :!data?<div className={styles.card}><h3>図は未作成です</h3><p>測定値を選ぶと、視野ごとの分布と採用・欠測の記録を出力できます。</p></div>
   :<>
    <div className={styles.card} aria-label="保存済みの記述図">
     <div className={styles.sectionHeader}><h3>測定値の分布</h3><span>{data.revision_id===revisionId?"採用中の解析版":"旧版の結果"}</span></div>
     <p aria-label="保存済みの測定値"><b>{savedDescriptiveLabel(data)}</b></p>
     <p className={styles.small}>単位: {data.unit} · {revisionLabels[data.revision_id]||"保存済みの解析版"}<br/>図の言語: {data.spec.plot.language==="ja"?"日本語":"English"} · {data.spec.plot.preset==="nature-single"?"89 mm":data.spec.plot.preset==="nature-double"?"183 mm":"カスタム"}</p>
     {!settingsMatch&&<p className={styles.notice}>表示中は保存済みの条件による結果です。現在選択した指標・表示設定を反映するには「分布図を作成」を実行してください。</p>}
     <p>{data.counts.observations} 観測 · 採用値のある視野 {data.counts.selected_fields} / 入力 {data.counts.input_fields} 視野</p>
     <p className={styles.small}>観測数・視野数は、独立した実験反復数ではありません。</p>
     <SavedDescriptiveFigure key={`figure-${job!.id}`} data={data} jobId={job!.id} language={language} preset={preset} disabled={blocked||dirty||traceBlocked} run={run} onCreated={setSelectedJob}/>
     {onInspectRegion&&data.spec.selection.source==="region"&&<RegionTraceTable key={`trace-${job!.id}`} result={data} disabled={blocked||dirty||traceBlocked} onInspect={onInspectRegion}/>}
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
   {!!available.length&&<details className={styles.card}><summary>記述図の履歴</summary>{available.map(j=><button className={styles.linkButton} key={j.id} onClick={()=>setSelectedJob(j.id)}>{new Date(j.created*1000).toLocaleString("ja-JP")} · {j.revision_id===revisionId?"採用中の版":"旧版"} · {j.state==="succeeded"?"結果あり":j.state==="failed"?"失敗":j.state==="cancelled"?"中止":j.state==="running"?"実行中":"待機中"}</button>)}</details>}
  </div>
 </section>;
}
