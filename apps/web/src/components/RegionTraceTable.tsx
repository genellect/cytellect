"use client";
import {useState} from "react";
import {descriptiveFieldNumber,savedDescriptiveLabel,type DescriptiveResult} from "@/lib/descriptive-view";
import {regionTraceRows,type RegionTraceTarget} from "@/lib/region-trace";
import {formatValue} from "@/lib/types";
import styles from "./workspace.module.css";

type Props={result:DescriptiveResult;disabled:boolean;onInspect:(target:RegionTraceTarget)=>void};
export default function RegionTraceTable({result,disabled,onInspect}:Props){
 const [field,setField]=useState("");const [page,setPage]=useState(0);
 const all=regionTraceRows(result);const rows=field?all.filter(row=>row.fieldId===field):all;
 const totalPages=Math.max(1,Math.ceil(rows.length/20));const current=Math.min(page,totalPages-1);const visible=rows.slice(current*20,(current+1)*20);
 return <details className={styles.regionTrace}>
  <summary>図に使った測定値 · {all.length} 件</summary>
  <p className={styles.small}>{savedDescriptiveLabel(result)} · 単位: {result.unit}<br/>測定値から、この図を作成した解析版の領域を開きます。</p>
  {result.spec.selection.source==="region"&&result.spec.selection.channel_id===null&&<p className={styles.small}>面積測定にはチャンネルを使用していません。画像は現在の表示チャンネル、またはその視野の最初のチャンネルで確認します。</p>}
  {disabled&&<p className={styles.notice}>処理中、または未保存の領域・設定があるため、画像への切り替えを停止しています。</p>}
  <label>図の視野で絞り込む<select aria-label="図の視野で絞り込む" value={field} onChange={event=>{setField(event.target.value);setPage(0);}}><option value="">すべての視野</option>{result.field_summary.map(row=><option key={row.field_id} value={row.field_id}>図の視野 {descriptiveFieldNumber(result,row.field_id)??"—"}</option>)}</select></label>
  <div className={styles.tableWrap}><table aria-label="図に使った領域ごとの測定値"><thead><tr><th>図の視野</th><th>領域ID</th><th>測定値</th><th>元画像</th></tr></thead><tbody>{visible.map((row,index)=><tr key={`${row.observationId}-${index}`}><td>{descriptiveFieldNumber(result,row.fieldId)??"—"}</td><td>{row.regionId??"—"}</td><td>{formatValue(row.value)}</td><td>{row.target?<button className={styles.linkButton} disabled={disabled} aria-label={`図の視野 ${descriptiveFieldNumber(result,row.fieldId)??"—"} 領域 ${row.regionId} を画像で確認`} onClick={()=>onInspect(row.target!)}>画像で確認</button>:<span>出典を確認できません</span>}</td></tr>)}</tbody></table></div>
  {!all.length&&<p className={styles.small}>この結果には、画面で確認できる領域の測定値がありません。保存済みの元データをご確認ください。</p>}
  <div className={styles.tracePages}><span>{rows.length?`${current*20+1}–${Math.min((current+1)*20,rows.length)} / ${rows.length} 件`:"0 件"}</span><button className={styles.secondary} disabled={current===0} onClick={()=>setPage(current-1)}>前の20件</button><button className={styles.secondary} disabled={current+1>=totalPages} onClick={()=>setPage(current+1)}>次の20件</button></div>
 </details>;
}
