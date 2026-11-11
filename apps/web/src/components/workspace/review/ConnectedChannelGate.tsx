"use client";

import {useLayoutEffect,useRef,useState} from "react";
import {ApiError,errorCodeMessage,errorMessage} from "@/lib/api";
import type {ApiAdapter} from "@/lib/workspace/api-adapter";
import {channelGateName,channelGateRequest,channelGateThresholds,recordedChannelGate,type ChannelGateFilter,type ChannelGateResult,type GateField} from "@/lib/workspace/channel-gate";

/** `recorded`: the public demo, which answers from its recording. It classifies only with the method that
 * needs no value typed in (each acquisition date's Otsu threshold), for every channel and measured value. */
export function ConnectedChannelGate({adapter,workspace,fields,channels,disabled=false,recorded=false,onClassified}:{
  adapter:ApiAdapter;workspace:string;fields:GateField[];channels:Array<{id:string;stain:string|null}>;disabled?:boolean;recorded?:boolean;
  onClassified:(result:ChannelGateResult,filter:ChannelGateFilter)=>void|Promise<void>;
}){
  const [channel,setChannel]=useState("");
  const [method,setMethod]=useState<ChannelGateFilter["method"]>(recorded?"batch_otsu":"manual");
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
      {!recorded&&<><option value="manual">しきい値を指定（探索的）</option><option value="negative_control">撮影日ごとの陰性対照</option></>}<option value="batch_otsu">撮影日ごとのOtsu（探索的）</option></select></label>
    {recorded&&<small>公開デモでは、値を入力しない判定方法（撮影日ごとの Otsu）で分類し、陽性核を集計します。分類の後に統計で比べられるのは、陽性率・陽性核数と、陽性核の面積・平均輝度です。しきい値の指定、陰性対照による判定、陰性核の集計は、お手元の画像で使えます。</small>}
    <label>測定値<select value={values} onChange={event=>setValues(event.target.value as typeof values)} disabled={disabled||busy}>
      <option value="raw">原値</option><option value="corrected">背景補正値</option></select></label>
    {method==="manual"&&<label>核内平均輝度のしきい値<input type="number" step="any" value={threshold} onChange={event=>setThreshold(event.target.value)} disabled={disabled||busy}/></label>}
    {method==="negative_control"&&<><label>陰性対照のパーセンタイル<input type="number" min="50" max="99.999" step="any" value={percentile} onChange={event=>setPercentile(event.target.value)} disabled={disabled||busy}/></label>
      <fieldset><legend>陰性対照の視野（各撮影日に20核以上）</legend>{fields.map(field=><label key={field.fieldId} style={{display:"block"}}><input type="checkbox" disabled={disabled||busy} checked={controls.includes(field.fieldId)} onChange={event=>setControls(previous=>event.target.checked?[...previous,field.fieldId]:previous.filter(id=>id!==field.fieldId))}/>{field.label}</label>)}</fieldset></>}
    <label>測定値の集計対象<select value={keep} onChange={event=>setKeep(event.target.value as typeof keep)} disabled={disabled||busy}><option value="positive">陽性核</option>{!recorded&&<option value="negative">陰性核</option>}</select></label>
    <small>陽性率では、選別前の陽性核と陰性核を分母にします。補正値の欠測は原値に置き換えません。</small>
    <button type="button" disabled={disabled||busy||!valid} onClick={()=>void classify()}>{busy?"分類中…":"チャンネルで分類"}</button>
    {!fields.length&&<p>核を検出して採用すると分類できます。</p>}
    {totals&&result&&<output aria-live="polite">{channelGateName(result)} · 陽性 {totals.positive} · 陰性 {totals.negative} · 未判定 {totals.unclassified} · 除外 {totals.excluded} · 対照 {totals.control}</output>}
    {result&&channelGateThresholds(result).map(row=><small key={row.date}>{row.date} · {row.threshold===null?errorCodeMessage(row.reason||"channel_threshold_missing"):`しきい値 ${row.threshold.toPrecision(5)}`}</small>)}
    {error&&<p role="alert">{error}</p>}
  </section>;
}
