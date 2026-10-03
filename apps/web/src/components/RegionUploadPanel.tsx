"use client";
import { useEffect, useState, type FormEvent } from "react";
import { LOCAL_MODE, request } from "@/lib/api";
import type { RegionChannel, RegionField } from "@/lib/region-types";
import styles from "./workspace.module.css";

type ChannelDraft={id:string;label:string;stain:string;confirmed:boolean;saturation:string;saturationConfirmed:boolean};
const blankMetadata={condition:"",experimental_unit:"",sample:"",acquisition_date:"",pair:"",repeat_length:""};
const draft=(index:number):ChannelDraft=>({id:`channel-${index+1}`,label:"",stain:"",confirmed:false,saturation:"",saturationConfirmed:false});
type Props={wid:string;channels?:RegionChannel[];maskSource?:"manual"|"imported";hasFields:boolean;run:(fn:()=>Promise<void>)=>void;onDone:(field:RegionField)=>void};

export default function RegionUploadPanel({wid,channels,maskSource,hasFields,run,onDone}:Props){
 const [open,setOpen]=useState(!hasFields);
 const [drafts,setDrafts]=useState<ChannelDraft[]>(()=>channels?.map(channel=>({id:channel.channel_id,label:channel.label,stain:channel.stain||"",confirmed:false,saturation:channel.acquisition_saturation_value===null?"":String(channel.acquisition_saturation_value),saturationConfirmed:false}))||[draft(0)]);
 const [metadata,setMetadata]=useState(blankMetadata);const [importLabels,setImportLabels]=useState(maskSource==="imported");const [calibrated,setCalibrated]=useState(false);const [sending,setSending]=useState(false);
 useEffect(()=>setImportLabels(maskSource==="imported"),[maskSource]);
 useEffect(()=>{if(hasFields)setOpen(false);},[hasFields]);
 useEffect(()=>{if(hasFields&&channels){setDrafts(channels.map(channel=>({id:channel.channel_id,label:channel.label,stain:channel.stain||"",confirmed:false,saturation:channel.acquisition_saturation_value===null?"":String(channel.acquisition_saturation_value),saturationConfirmed:false})));setImportLabels(maskSource==="imported");}},[channels,hasFields,maskSource]);
 function update(index:number,value:Partial<ChannelDraft>){setDrafts(current=>current.map((channel,i)=>i===index?{...channel,...value}:channel));}
 async function upload(event:FormEvent<HTMLFormElement>){
  event.preventDefault();const form=event.currentTarget;const source=new FormData(form);const data=new FormData();
  const specification={version:"1.0.0",channels:drafts.map(channel=>({channel_id:channel.id,label:channel.label.trim(),stain:channel.stain.trim()||null,identity_confirmed:channel.confirmed,acquisition_saturation_value:channel.saturation?Number(channel.saturation):null,acquisition_saturation_confirmed:channel.saturation?channel.saturationConfirmed:false})),metadata:{...Object.fromEntries(Object.entries(metadata).map(([key,value])=>[key,key==="repeat_length"?(value===""?null:Number(value)):value.trim()||null]))},calibration:calibrated?{pixel_size_x_um:Number(source.get("pixel_size_x_um")),pixel_size_y_um:Number(source.get("pixel_size_y_um")),confirmed:source.get("calibration_confirmed")==="on"}:null};
  data.set("specification",JSON.stringify(specification));drafts.forEach((_,i)=>data.set(`ch${i}`,source.get(`ch${i}`)!));if(importLabels)data.set("labels",source.get("labels")!);
  setSending(true);try{const field=await request<RegionField>(`/v1/workspaces/${wid}/region-fields`,{method:"POST",body:data});form.querySelectorAll<HTMLInputElement>('input[type="file"]').forEach(input=>{input.value="";});const calibration=form.elements.namedItem("calibration_confirmed");if(calibration instanceof HTMLInputElement)calibration.checked=false;setDrafts(current=>current.map(channel=>({...channel,confirmed:false,saturationConfirmed:false})));setOpen(false);onDone(field);}finally{setSending(false);}
 }
 return <details className={styles.upload} open={open} onToggle={event=>setOpen(event.currentTarget.open)}>
  <summary>＋ 画像を登録</summary>
  <form onSubmit={event=>{event.preventDefault();run(()=>upload(event));}}>
   <p className={styles.small}>チャンネル別の8/16-bitグレースケール2D TIFFを登録します。表示名とファイルの対応を確認してください。染色が不明なら空欄のままにします。</p>
   <div className={styles.regionChannels}>{drafts.map((channel,index)=><fieldset className={styles.regionChannel} key={channel.id}>
    <legend>チャンネル {index+1}</legend>
    <div className={styles.formGrid}><label>表示名<input aria-label={`チャンネル ${index+1} の表示名`} value={channel.label} onChange={event=>update(index,{label:event.target.value,confirmed:false})} placeholder="例：Actin、核染色" maxLength={120} required readOnly={hasFields}/></label><label>実際の染色・標識（任意）<input aria-label={`チャンネル ${index+1} の染色`} value={channel.stain} onChange={event=>update(index,{stain:event.target.value,confirmed:false})} placeholder="不明なら空欄" maxLength={120} readOnly={hasFields}/></label><label>画像 TIFF<input aria-label={`チャンネル ${index+1} の画像`} name={`ch${index}`} type="file" accept=".tif,.tiff" required onChange={()=>update(index,{confirmed:false})}/></label></div>
    <label className={styles.checkbox}><input type="checkbox" checked={channel.confirmed} onChange={event=>update(index,{confirmed:event.target.checked})} required/>チャンネル {index+1} の画像と表示名の対応を確認しました。</label>
    <details className={styles.metadataHelp}><summary>取得時の飽和値（分かる場合のみ）</summary><label>取得時の最大画素値<input aria-label={`チャンネル ${index+1} の取得時最大値`} type="number" min={1} max={65535} step={1} value={channel.saturation} onChange={event=>update(index,{saturation:event.target.value,saturationConfirmed:false})}/></label>{channel.saturation&&<label className={styles.checkbox}><input type="checkbox" checked={channel.saturationConfirmed} onChange={event=>update(index,{saturationConfirmed:event.target.checked})} required/>撮影設定から、この最大値を確認しました。</label>}<p>保存形式の最大値とは区別します。分からない場合は未設定のままにしてください。</p></details>
   </fieldset>)}</div>
   {!hasFields&&<div className={styles.actionRow}><button type="button" className={styles.secondary} disabled={drafts.length<=1} onClick={()=>setDrafts(current=>current.slice(0,-1))}>最後のチャンネルを外す</button><button type="button" className={styles.secondary} disabled={drafts.length>=3} onClick={()=>setDrafts(current=>[...current,draft(current.length)])}>チャンネルを追加</button></div>}
   {hasFields&&<p className={styles.small}>チャンネル構成はこの作業で共通です。異なる構成の画像は別の作業に登録してください。</p>}
   <details className={styles.metadataHelp}><summary>実験情報（任意）</summary><p>処置を独立に割り付けた単位を記録し、その単位から得た複数視野には同じIDを使います。未確認の情報は空欄にでき、次の視野には入力した内容を引き継ぎます。</p><div className={styles.formGrid}>{([['condition','条件'],['experimental_unit','独立実験単位'],['sample','試料'],['acquisition_date','撮影日／バッチ'],['pair','対応ペア'],['repeat_length','リピート長']] as const).map(([name,label])=><label key={name}>{label}<input name={name} value={metadata[name]} type={name==="repeat_length"?"number":"text"} min={name==="repeat_length"?0:undefined} step={name==="repeat_length"?"any":undefined} maxLength={80} onChange={event=>setMetadata(current=>({...current,[name]:event.target.value}))}/></label>)}</div><button className={styles.linkButton} type="button" onClick={()=>setMetadata({...blankMetadata})}>実験情報をクリア</button></details>
   <details className={styles.metadataHelp} open={importLabels}><summary>画素サイズと領域マスク</summary><label className={styles.checkbox}><input type="checkbox" checked={calibrated} onChange={event=>setCalibrated(event.target.checked)}/>画素サイズが分かる</label>{calibrated&&<><div className={styles.formGrid}><label>X方向 µm/px<input name="pixel_size_x_um" type="number" min={.000001} step="any" required/></label><label>Y方向 µm/px<input name="pixel_size_y_um" type="number" min={.000001} step="any" required/></label></div><label className={styles.checkbox}><input name="calibration_confirmed" type="checkbox" required/>撮影情報からX・Yの画素サイズを確認しました。</label></>}<label className={styles.checkbox}><input type="checkbox" checked={importLabels} disabled={hasFields} onChange={event=>setImportLabels(event.target.checked)}/>領域マスクを取り込む</label>{importLabels&&<><label>整数ラベル TIFF<input name="labels" type="file" accept=".tif,.tiff" required/></label><p>原画像と同じ大きさのラベルTIFFを使います。領域外は0、各領域を異なる整数で塗り分けます。同じ値の画素は、離れていても1領域として測ります。輪郭の内側は自動で埋めません。</p></>}{hasFields&&<p>領域の入力方式はこの作業で共通です。</p>}</details>
   <p className={styles.small}>{LOCAL_MODE?"画像はローカルに保存されます。保存期限は最終操作から24時間です。終了中に期限を迎えたデータは次回起動時に削除します。":"画像は非公開の解析APIへ直接送信し、最終操作から24時間で失効します。"}</p>
   <button className={styles.primary} disabled={sending}>この視野を登録</button>
  </form>
 </details>;
}
