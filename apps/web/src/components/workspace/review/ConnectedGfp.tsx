"use client";

import {useLayoutEffect, useRef, useState} from "react";
import {ApiError, errorMessage} from "@/lib/api";
import type {ApiAdapter, GfpGateResult} from "@/lib/workspace/api-adapter";

export type WorkspaceGfpFilter = {
  version:"1.0.0";gate_protocol:"gfp-gate/2.0.0";gfp_channel_id:string;
  percentile:number;control_field_ids:string[];keep:"positive"|"negative";
} | {
  version:"1.1.0";gate_protocol:"gfp-gate/3.0.0";gfp_channel_id:string;
  method:"manual"|"batch_otsu";threshold:number|null;values:"raw"|"corrected";keep:"positive"|"negative";unit?:"nucleus"|"cell_roi";
};
export interface ConnectedGfpProps {
  adapter:ApiAdapter;workspace:string;
  fields:Array<{fieldId:string;label:string;revisionId:string}>;
  channels:Array<{id:string;stain:string|null}>;disabled?:boolean;
  unit?:"nucleus"|"cell_roi";
  onClassified:(result:GfpGateResult, filter:WorkspaceGfpFilter)=>void;
}

/** Classification uses saved nuclear means and identities; never positive pixel components. */
export function ConnectedGfp({adapter,workspace,fields,channels,disabled=false,onClassified,unit="nucleus"}:ConnectedGfpProps) {
  const known=channels.filter(item=>/^(e?gfp)$/i.test(item.stain??""));
  const [channel,setChannel]=useState(known.length===1?known[0].id:"");
  const [method,setMethod]=useState<"negative_control"|"manual"|"batch_otsu">("manual");
  const [threshold,setThreshold]=useState("");
  const [values,setValues]=useState<"raw"|"corrected">("raw");
  const [keep,setKeep]=useState<"positive"|"negative">("positive");
  const [controls,setControls]=useState<string[]>([]);
  const [busy,setBusy]=useState(false),[error,setError]=useState("");
  const [saved,setSaved]=useState<{identity:string;result:GfpGateResult}|null>(null);
  const lock=useRef(false);
  const identity=JSON.stringify([workspace,fields.map(field=>[field.fieldId,field.revisionId]),channel,method,threshold,values,keep,controls,unit]);
  const current=useRef(identity);
  useLayoutEffect(()=>{current.current=identity;return()=>{current.current="";};},[identity]);
  const validChannel=channels.some(item=>item.id===channel);
  const valid=validChannel&&fields.length>0&&(method!=="manual"||(threshold.trim()!==""&&Number.isFinite(Number(threshold))))
    &&(method!=="negative_control"||(unit==="nucleus"&&controls.some(id=>fields.some(field=>field.fieldId===id))));
  const result=saved?.identity===identity?saved.result:null;
  const totals=result?Object.values(result.field_counts).reduce((total,item)=>({positive:total.positive+item.positive,negative:total.negative+item.negative,pending:total.pending+item.unselected}),{positive:0,negative:0,pending:0}):null;
  async function classify(){
    if(lock.current||disabled||!valid)return;
    lock.current=true;setBusy(true);setError("");const requested=identity;
    const controlIds=controls.filter(id=>fields.some(field=>field.fieldId===id));
    const filter:WorkspaceGfpFilter=method==="negative_control"
      ?{version:"1.0.0",gate_protocol:"gfp-gate/2.0.0",gfp_channel_id:channel,percentile:99,control_field_ids:controlIds,keep}
      :{version:"1.1.0",gate_protocol:"gfp-gate/3.0.0",gfp_channel_id:channel,method,threshold:method==="manual"?Number(threshold):null,values,keep,...(unit==="cell_roi"?{unit}:{})};
    try {
      const response=await adapter.gfpGate(workspace,{gfp_channel_id:channel,percentile:99,method,unit,
        values:method==="negative_control"?"raw":values,...(method==="manual"?{threshold:Number(threshold)}:{}),
        fields:fields.map(field=>({field_id:field.fieldId,revision_id:field.revisionId,control:method==="negative_control"&&controlIds.includes(field.fieldId)}))});
      if(current.current!==requested)return;
      setSaved({identity:requested,result:response});onClassified(response,filter);
    } catch(caught){if(current.current===requested)setError(caught instanceof ApiError?errorMessage(caught):"GFPの分類を完了できませんでした。");}
    finally{lock.current=false;setBusy(false);}
  }
  return <section aria-label={unit==="cell_roi"?"細胞ROI内GFPによる分類":"核内GFPによる分類"} style={{display:"grid",gap:12}}>
    <strong>{unit==="cell_roi"?"細胞ROI内GFP":"核内GFP"}</strong>
    <label>チャンネル<select aria-label="GFPチャンネル" value={channel} onChange={event=>setChannel(event.target.value)} disabled={disabled||busy}>
      <option value="">選択</option>{channels.map(item=><option key={item.id} value={item.id}>{item.id}{item.stain?` · ${item.stain}`:""}</option>)}</select></label>
    <label>判定方法<select value={method} onChange={event=>setMethod(event.target.value as typeof method)} disabled={disabled||busy}>
      <option value="manual">しきい値を指定</option>{unit==="nucleus"&&<option value="negative_control">陰性対照の99パーセンタイル</option>}<option value="batch_otsu">撮影日ごとのOtsu（探索的）</option></select></label>
    {method==="manual"&&<label>平均輝度のしきい値<input type="number" step="any" value={threshold} onChange={event=>setThreshold(event.target.value)} disabled={disabled||busy}/></label>}
    {method!=="negative_control"&&<label>測定値<select value={values} onChange={event=>setValues(event.target.value as typeof values)} disabled={disabled||busy}><option value="raw">原値</option><option value="corrected">背景補正値</option></select></label>}
    {method==="negative_control"&&<fieldset><legend>陰性対照の視野</legend>{fields.map(field=><label key={field.fieldId} style={{display:"block"}}><input type="checkbox" checked={controls.includes(field.fieldId)} disabled={disabled||busy} onChange={event=>setControls(previous=>event.target.checked?[...previous,field.fieldId]:previous.filter(id=>id!==field.fieldId))}/>{field.label}</label>)}</fieldset>}
    <label>集計対象<select value={keep} onChange={event=>setKeep(event.target.value as typeof keep)} disabled={disabled||busy}><option value="positive">GFP陽性{unit==="nucleus"?"核":"細胞ROI"}</option><option value="negative">GFP陰性{unit==="nucleus"?"核":"細胞ROI"}</option></select></label>
    <button type="button" disabled={disabled||busy||!valid} onClick={()=>void classify()}>{busy?"分類中…":"GFPで分類"}</button>
    {!fields.length&&<p>{unit==="nucleus"?"核の検出後":"細胞ROIの保存後"}に分類できます。</p>}
    {totals&&<output aria-live="polite">陽性 {totals.positive} · 陰性 {totals.negative} · 未判定 {totals.pending}</output>}
    {result&&Object.entries(result.dates).map(([date,item])=><small key={date}>{date==="all"?"全視野":date||"撮影日未設定"} · {item.threshold===null?"しきい値未確定":`しきい値 ${item.threshold.toPrecision(5)}`}</small>)}
    {error&&<p role="alert">{error}</p>}
  </section>;
}
