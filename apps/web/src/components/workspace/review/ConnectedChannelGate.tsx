"use client";

import {useLayoutEffect,useRef,useState} from "react";
import {ApiError,errorCodeMessage,errorMessage} from "@/lib/api";
import type {ApiAdapter} from "@/lib/workspace/api-adapter";
import {channelGateName,channelGateRequest,channelGateThresholds,recordedChannelGate,type ChannelGateFilter,type ChannelGateResult,type GateField} from "@/lib/workspace/channel-gate";
import {ErrorText} from "./showcase-ui";
import {GATE_STATUS_LABELS,GATE_STATUS_ORDER,gateExploratory,gateHistogram,gateMethodLabel,type GateStatus} from "@/lib/workspace/color-by";

/** `recorded`: the public demo, which answers from its recording. It offers every method as production does and
 * opens on the one it recorded (each acquisition date's Otsu threshold, positive or negative nuclei kept); a method
 * or value it did not record is answered with the demo's notice.
 * `decision`: the decision the image is coloured by; its values and thresholds are shown for judging the threshold,
 * with the selected nucleus's own value (MV-04). Production offers the negative control first (M22). */
export function ConnectedChannelGate({adapter,workspace,fields,channels,disabled=false,recorded=false,initialChannel="",decision,selected,onClassified}:{
  adapter:ApiAdapter;workspace:string;fields:GateField[];channels:Array<{id:string;stain:string|null}>;disabled?:boolean;recorded?:boolean;
  initialChannel?:string;decision?:{result:ChannelGateResult;filter:ChannelGateFilter}|null;selected?:{fieldId:string;regionId:number}|null;
  onClassified:(result:ChannelGateResult,filter:ChannelGateFilter)=>void|Promise<void>;
}){
  const [channel,setChannel]=useState(()=>channels.some(item=>item.id===initialChannel)?initialChannel:channels.length===1?channels[0].id:"");
  const [method,setMethod]=useState<ChannelGateFilter["method"]>(recorded?"batch_otsu":"negative_control");
  const [threshold,setThreshold]=useState(""),[percentile,setPercentile]=useState("99");
  const [values,setValues]=useState<"raw"|"corrected">("raw"),[keep,setKeep]=useState<"positive"|"negative">("positive");
  const [controls,setControls]=useState<string[]>([]),[busy,setBusy]=useState(false),[error,setError]=useState("");
  const [saved,setSaved]=useState<{identity:string;result:ChannelGateResult}|null>(null);
  const identity=JSON.stringify([workspace,fields,channels,channel,method,threshold,percentile,values,keep,controls]);
  const current=useRef(identity),lock=useRef(false);
  useLayoutEffect(()=>{current.current=identity;return()=>{current.current="";};},[identity]);
  const valid=fields.length>0&&channels.some(item=>item.id===channel)
    &&(method!=="manual"||(threshold.trim()!==""&&Number.isFinite(Number(threshold))))
    &&(method!=="negative_control"||(controls.length>0&&Number(percentile)>=50&&Number(percentile)<100));
  const result=saved?.identity===identity?saved.result:null;
  const totals=result?Object.values(result.field_counts).reduce((sum,row)=>({positive:sum.positive+row.positive,negative:sum.negative+row.negative,
    unclassified:sum.unclassified+row.unclassified,excluded:sum.excluded+row.excluded,control:sum.control+row.control}),{positive:0,negative:0,unclassified:0,excluded:0,control:0}):null;
  async function classify(){
    if(lock.current||disabled||!valid)return;
    lock.current=true;setBusy(true);setError("");const requested=identity;
    const filter:ChannelGateFilter={version:"1.0.0",gate_protocol:"channel-gate/1.0.0",channel_id:channel,method,values,keep,
      threshold:method==="manual"?Number(threshold):null,percentile:method==="negative_control"?Number(percentile):99,
      control_field_ids:method==="negative_control"?controls:[]};
    try{
      const response=await adapter.channelGate(workspace,channelGateRequest(filter,fields));
      if(current.current!==requested)return;
      await onClassified(response,recordedChannelGate(response));
      if(current.current===requested)setSaved({identity:requested,result:response});
    }catch(cause){if(current.current===requested)setError(cause instanceof ApiError?errorMessage(cause):cause instanceof Error?errorCodeMessage(cause.message):"分類を完了できませんでした。");}
    finally{lock.current=false;setBusy(false);}
  }
  return <section aria-label="チャンネルによる核の分類" style={{display:"grid",gap:12}}>
    <label>判定するチャンネル<select value={channel} onChange={event=>setChannel(event.target.value)} disabled={disabled||busy}>
      <option value="">選択</option>{channels.map(item=><option key={item.id} value={item.id}>{item.stain||item.id} · {item.id}</option>)}</select></label>
    <label>判定方法<select value={method} onChange={event=>setMethod(event.target.value as typeof method)} disabled={disabled||busy}>
      <option value="negative_control">撮影日ごとの陰性対照</option><option value="batch_otsu">撮影日ごとのOtsu（探索的）</option><option value="manual">しきい値を指定（探索的）</option></select></label>
    {gateExploratory(method)&&<small>陰性対照によらないしきい値での分類は探索的です。陽性率の比較は記述統計のみで、検定はしません。</small>}
    {recorded&&<small>公開デモには、撮影日ごとの Otsu による分類だけを記録しています。陰性対照としきい値の指定は、お手元の画像で使えます。</small>}
    <label>測定値<select value={values} onChange={event=>setValues(event.target.value as typeof values)} disabled={disabled||busy}>
      <option value="raw">原値</option><option value="corrected">背景補正値</option></select></label>
    {method==="manual"&&<label>核内平均輝度のしきい値<input type="number" step="any" value={threshold} onChange={event=>setThreshold(event.target.value)} disabled={disabled||busy}/></label>}
    {method==="negative_control"&&<><label>陰性対照のパーセンタイル<input type="number" min="50" max="99.999" step="any" value={percentile} onChange={event=>setPercentile(event.target.value)} disabled={disabled||busy}/></label>
      <fieldset><legend>陰性対照の視野（各撮影日に20核以上）</legend>{fields.map(field=><label key={field.fieldId} style={{display:"block"}}><input type="checkbox" disabled={disabled||busy} checked={controls.includes(field.fieldId)} onChange={event=>setControls(previous=>event.target.checked?[...previous,field.fieldId]:previous.filter(id=>id!==field.fieldId))}/>{field.label}</label>)}</fieldset></>}
    <label>測定値の集計対象<select value={keep} onChange={event=>setKeep(event.target.value as typeof keep)} disabled={disabled||busy}><option value="positive">陽性核</option><option value="negative">陰性核</option></select></label>
    <small>陽性率の分母：選別前の陽性核と陰性核。補正値の欠測は原値で補完しません。</small>
    <button type="button" disabled={disabled||busy||!valid} onClick={()=>void classify()}>{busy?"分類中…":"チャンネルで分類"}</button>
    {!fields.length&&<p>分類には、核の検出と採用が必要です。</p>}
    {totals&&result&&<output aria-live="polite">{channelGateName(result)} · 陽性 {totals.positive} · 陰性 {totals.negative} · 未判定 {totals.unclassified} · 除外 {totals.excluded} · 対照 {totals.control}</output>}
    {result&&channelGateThresholds(result).map(row=><small key={row.date}>{row.date} · {row.threshold===null?errorCodeMessage(row.reason||"channel_threshold_missing"):`しきい値 ${row.threshold.toPrecision(5)}`}</small>)}
    {error&&<ErrorText text={error}/>}
    {decision&&<GateReview result={decision.result} filter={decision.filter} selected={selected??null}/>}
  </section>;
}

const tones:Record<GateStatus,string>={positive:"#2f9e5b",negative:"#9aa3ad",unclassified:"#d99a2b",excluded:"#d9534f",control:"#4a8fd8"};
/** The saved decision's judged values on each acquisition date with that date's threshold, and the selected nucleus's
 * value, so the researcher can judge whether the threshold separates the nuclei (MV-04). Values are the saved ones. */
function GateReview({result,filter,selected}:{result:ChannelGateResult;filter:ChannelGateFilter;selected:{fieldId:string;regionId:number}|null}){
  const dates=[...new Set(result.nuclei.map(item=>item.acquisition_date??""))].sort();
  const nucleus=selected?result.nuclei.find(item=>item.field_id===selected.fieldId&&item.region_id===selected.regionId):undefined;
  const format=(value:number|null)=>value===null?"—":value.toLocaleString("ja-JP",{maximumFractionDigits:1});
  return <div aria-label="判定値の分布としきい値" role="group" style={{display:"grid",gap:8}}>
    <strong style={{fontSize:14}}>判定値の分布（{channelGateName(result)}、{filter.values==="corrected"?"背景補正値":"原値"}、{gateMethodLabel(filter.method)}）</strong>
    {dates.map(date=>{const chart=gateHistogram(result.nuclei,date);if(!chart.total)return null;
      const max=Math.max(1,...chart.counts.map(bin=>GATE_STATUS_ORDER.reduce((sum,status)=>sum+bin[status],0)));
      const x=(value:number)=>chart.high===chart.low?120:8+(value-chart.low)/(chart.high-chart.low)*224;
      return <figure key={date} style={{margin:0}}>
        <svg viewBox="0 0 240 70" width="100%" role="img" aria-label={`${date||"撮影日未設定"}の判定値の分布。しきい値 ${format(chart.threshold)}`}>
          {chart.counts.map((bin,index)=>{let y=60;return GATE_STATUS_ORDER.map(status=>{const h=bin[status]/max*52;y-=h;return h>0?<rect key={`${index}-${status}`} x={8+index*224/chart.counts.length} y={y} width={224/chart.counts.length-1} height={h} fill={tones[status]}/>:null;});})}
          <line x1="8" x2="232" y1="60" y2="60" stroke="#8a929c"/>
          {chart.threshold!==null&&<line x1={x(chart.threshold)} x2={x(chart.threshold)} y1="4" y2="62" stroke="#111" strokeDasharray="3 2"/>}
          {nucleus&&(nucleus.acquisition_date??"")===date&&nucleus.channel_mean!==null&&<path d={`M${x(nucleus.channel_mean)} 62 l-4 7 h8 z`} fill="#e0a800"/>}
        </svg>
        <figcaption style={{fontSize:12}}>{date||"撮影日未設定"} · しきい値 {format(chart.threshold)} · 核 {chart.total}</figcaption>
      </figure>;})}
    <small>{GATE_STATUS_ORDER.map(status=><span key={status} style={{marginRight:8,whiteSpace:"nowrap"}}><span aria-hidden="true" style={{display:"inline-block",width:9,height:9,marginRight:3,background:tones[status]}}/>{GATE_STATUS_LABELS[status]}</span>)}</small>
    {nucleus?<p style={{margin:0}}>選んだ核 {nucleus.region_id}：判定値 {format(nucleus.channel_mean)}、しきい値 {format(nucleus.threshold)} → {GATE_STATUS_LABELS[nucleus.status as GateStatus]}</p>
      :<small>選んだ核：未選択</small>}
  </div>;
}
