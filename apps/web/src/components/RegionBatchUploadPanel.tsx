"use client";
import {useEffect,useState} from "react";
import {errorMessage,LOCAL_MODE,request} from "@/lib/api";
import {batchMetadata,emptyBatchMetadata,mapBatchFiles,metadataColumns,type MetadataDraft} from "@/lib/region-batch";
import {applyCommonMetadata,planCommonMetadata,undoCommonMetadata,type CommonMetadataChange,type CommonMetadataPlan} from "@/lib/batch-common-metadata";
import type {RegionChannel,RegionField} from "@/lib/region-types";
import styles from "./workspace.module.css";

type Channel={id:string;label:string;stain:string;suffix:string;files:File[];confirmed:boolean};
type Progress={status:"pending"|"uploading"|"succeeded"|"failed";id:string;error?:string;field?:RegionField};
type Props={wid:string;channels?:RegionChannel[];maskSource?:"manual"|"imported";hasFields:boolean;run:(fn:()=>Promise<void>)=>void;onDone:(field:RegionField)=>void;onInspect:()=>void};
const blankChannel=(i:number):Channel=>({id:`channel-${i+1}`,label:"",stain:"",suffix:"",files:[],confirmed:false});

export default function RegionBatchUploadPanel({wid,channels,maskSource,hasFields,run,onDone,onInspect}:Props){
 const [open,setOpen]=useState(false);
 const [columns,setColumns]=useState<Channel[]>(()=>channels?.map(channel=>({...blankChannel(0),id:channel.channel_id,label:channel.label,stain:channel.stain||""}))||[blankChannel(0)]);
 const [labels,setLabels]=useState<File[]>([]);const [labelSuffix,setLabelSuffix]=useState("");const [importLabels,setImportLabels]=useState(maskSource==="imported");
 const [common,setCommon]=useState<MetadataDraft>({...emptyBatchMetadata});const [metadata,setMetadata]=useState<Record<string,MetadataDraft>>({});
 const [commonReview,setCommonReview]=useState<CommonMetadataPlan|null>(null);const [commonUndo,setCommonUndo]=useState<CommonMetadataChange[]|null>(null);const [commonNotice,setCommonNotice]=useState("");
 const [confirmed,setConfirmed]=useState(false);const [sending,setSending]=useState(false);const [progress,setProgress]=useState<Record<string,Progress>>({});const [notice,setNotice]=useState("");const [round,setRound]=useState(0);
 const [pixelX,setPixelX]=useState("");const [pixelY,setPixelY]=useState("");const [calibrationConfirmed,setCalibrationConfirmed]=useState(false);
 const mapping=mapBatchFiles([...columns.map(channel=>({id:channel.id,suffix:channel.suffix,files:channel.files})),...(importLabels?[{id:"labels",suffix:labelSuffix,files:labels}]:[])]);
 const locked=Object.keys(progress).length>0;const successful=Object.values(progress).filter(row=>row.status==="succeeded").length;
 const commonPlan=planCommonMetadata(metadata,mapping.rows.map(row=>row.key),common);
 const reviewedCommon=commonReview&&JSON.stringify(commonReview)===JSON.stringify(commonPlan)?commonReview:null;
 useEffect(()=>{if(!locked)setImportLabels(maskSource==="imported");},[maskSource,locked]);
 useEffect(()=>{if(!locked&&hasFields&&channels){setColumns(current=>channels.map(channel=>({...blankChannel(0),id:channel.channel_id,label:channel.label,stain:channel.stain||"",suffix:current.find(item=>item.id===channel.channel_id)?.suffix||""})));setImportLabels(maskSource==="imported");setConfirmed(false);}},[channels,hasFields,maskSource,locked]);
 const ready=!reviewedCommon&&mapping.valid&&columns.every(channel=>channel.label.trim()&&channel.confirmed)&&confirmed&&(!pixelX&&!pixelY||(Number(pixelX)>0&&Number(pixelY)>0&&calibrationConfirmed));
 function update(index:number,value:Partial<Channel>){setColumns(current=>current.map((channel,i)=>i===index?{...channel,...value,confirmed:false}:channel));setConfirmed(false);setCalibrationConfirmed(false);}
 function setRow(key:string,name:keyof MetadataDraft,value:string){setMetadata(current=>({...current,[key]:{...(current[key]||emptyBatchMetadata),[name]:value}}));setCommonUndo(current=>{const remaining=current?.filter(change=>change.row!==key||change.column!==name);return remaining?.length?remaining:null;});setConfirmed(false);}
 function applyCommon(plan:CommonMetadataPlan){
  if(locked||sending||!plan.changes.length||JSON.stringify(plan)!==JSON.stringify(commonPlan))return;
  try{setMetadata(applyCommonMetadata(metadata,plan));setCommonUndo(plan.changes);setCommonReview(null);setConfirmed(false);setCommonNotice(`${new Set(plan.changes.map(change=>change.row)).size} 視野の実験情報を更新しました。空欄の共通項目は変更していません。`);}
  catch{setCommonReview(null);setCommonNotice("実験情報が変わりました。適用内容を確認し直してください。");}
 }
 function undoCommon(){
  if(locked||sending||!commonUndo)return;
  const undone=undoCommonMetadata(metadata,commonUndo);setMetadata(undone.metadata);setCommonUndo(null);setCommonReview(null);setConfirmed(false);
  setCommonNotice(`共通情報の適用を取り消しました。${undone.restored} セルを復元しました。${undone.kept?`その後に変更した ${undone.kept} セルは保持しました。`:""}`);
 }
 async function upload(){
  if(!ready||sending)return;setNotice("");
  // Validate the entire table before sending its first row. Keep request identities for retries.
  const validated=Object.fromEntries(mapping.rows.map(row=>[row.key,batchMetadata(metadata[row.key]||emptyBatchMetadata)]));
  const states=Object.fromEntries(mapping.rows.map(row=>[row.key,progress[row.key]||{status:"pending" as const,id:crypto.randomUUID()}]));setProgress(states);setSending(true);setCommonReview(null);setCommonUndo(null);setCommonNotice("");
  try{for(const row of mapping.rows){
   if(states[row.key].status==="succeeded")continue;
   const state=states[row.key];setProgress(current=>({...current,[row.key]:{...state,status:"uploading"}}));
   const data=new FormData();data.set("specification",JSON.stringify({version:"1.0.0",client_upload_id:state.id,channels:columns.map(channel=>({channel_id:channel.id,label:channel.label.trim(),stain:channel.stain.trim()||null,identity_confirmed:true,acquisition_saturation_value:null,acquisition_saturation_confirmed:false})),metadata:validated[row.key],calibration:pixelX&&pixelY?{pixel_size_x_um:Number(pixelX),pixel_size_y_um:Number(pixelY),confirmed:calibrationConfirmed}:null}));
   columns.forEach((channel,i)=>data.set(`ch${i}`,row.files[channel.id]!));if(importLabels)data.set("labels",row.files.labels!);
   try{const field=await request<RegionField>(`/v1/workspaces/${wid}/region-fields`,{method:"POST",body:data});states[row.key]={...state,status:"succeeded",field};onDone(field);}
   catch(error){states[row.key]={...state,status:"failed",error:errorMessage(error)};}
   setProgress(current=>({...current,[row.key]:states[row.key]}));
  }setNotice(Object.values(states).every(row=>row.status==="succeeded")?"全視野を登録しました。代表視野を選び、背景と領域を確認してください。":"登録できなかった視野が残っています。成功した視野は再送しません。");}finally{setSending(false);}
 }
 return <details className={styles.upload} open={open} onToggle={event=>setOpen(event.currentTarget.open)}><summary>＋ 複数視野をまとめて登録</summary><div className={styles.batchContent}>
  <p>チャンネルごとに画像を選び、同じ視野の対応を確認します。ファイル名は組み合わせにだけ使い、染色や実験単位は推定しません。</p>
  <div className={styles.regionChannels}>{columns.map((channel,index)=><fieldset className={styles.regionChannel} key={`${channel.id}-${round}`} disabled={locked||sending}><legend>チャンネル {index+1}</legend><div className={styles.formGrid}>
   <label>表示名<input aria-label={`一括 チャンネル ${index+1} の表示名`} value={channel.label} maxLength={120} readOnly={hasFields} onChange={event=>update(index,{label:event.target.value})}/></label>
   <label>染色・標識（任意）<input aria-label={`一括 チャンネル ${index+1} の染色`} value={channel.stain} maxLength={120} readOnly={hasFields} onChange={event=>update(index,{stain:event.target.value})}/></label>
   <label>画像 TIFF（複数可）<input aria-label={`一括 チャンネル ${index+1} の画像`} type="file" accept=".tif,.tiff" multiple onChange={event=>update(index,{files:Array.from(event.target.files||[])})}/></label>
   <label>取り除く末尾文字<input aria-label={`一括 チャンネル ${index+1} の末尾文字`} value={channel.suffix} placeholder="例：_ch1（拡張子を除く）" onChange={event=>update(index,{suffix:event.target.value})}/></label>
  </div><label className={styles.checkbox}><input type="checkbox" checked={channel.confirmed} onChange={event=>setColumns(current=>current.map((value,i)=>i===index?{...value,confirmed:event.target.checked}:value))}/>チャンネル {index+1} の全画像と表示名の対応を確認しました。</label></fieldset>)}</div>
  {!hasFields&&<div className={styles.actionRow}><button className={styles.secondary} disabled={locked||columns.length<=1} onClick={()=>{setColumns(current=>current.slice(0,-1));setConfirmed(false);setCalibrationConfirmed(false);}}>一括の最後のチャンネルを外す</button><button className={styles.secondary} disabled={locked||columns.length>=3} onClick={()=>{setColumns(current=>[...current,blankChannel(current.length)]);setConfirmed(false);setCalibrationConfirmed(false);}}>一括のチャンネルを追加</button></div>}
  <details className={styles.metadataHelp}><summary>共通の実験情報</summary><p>入力した項目だけを全行へ適用します。空欄の項目は各行の値を残し、入力済みの値が変わる場合は先に確認します。実験単位は記録に沿って入力してください。</p><div className={styles.formGrid}>{metadataColumns.map(([key,label])=><label key={key}>{label}<input aria-label={`一括 共通の${label}`} disabled={locked} value={common[key]} maxLength={80} type={key==="repeat_length"?"number":"text"} min={key==="repeat_length"?0:undefined} onChange={event=>{setCommon(current=>({...current,[key]:event.target.value}));setCommonReview(null);}}/></label>)}</div><button className={styles.secondary} disabled={locked||sending||!commonPlan.changes.length} onClick={()=>{setCommonNotice("");if(commonPlan.columns.some(column=>column.replace>0))setCommonReview(commonPlan);else applyCommon(commonPlan);}}>共通情報を全行へ適用</button>
   {reviewedCommon&&!locked&&<div className={styles.notice} role="group" aria-label="共通情報の変更確認"><p>次の項目を適用します。「置き換える行」は入力済みの値が変わります。</p><div className={styles.tableWrap}><table><thead><tr><th>項目</th><th>適用する値</th><th>空欄に入れる行</th><th>置き換える行</th></tr></thead><tbody>{reviewedCommon.columns.filter(column=>column.empty+column.replace>0).map(column=><tr key={column.key}><td>{column.label}</td><td>{column.value}</td><td>{column.empty}</td><td>{column.replace}</td></tr>)}</tbody></table></div><button className={styles.primary} onClick={()=>applyCommon(reviewedCommon)}>変更を確認して適用</button><button className={styles.secondary} onClick={()=>setCommonReview(null)}>適用せず戻る</button></div>}
   {commonNotice&&<p className={styles.small} role="status">{commonNotice}</p>}
   {commonUndo&&!locked&&<><button className={styles.secondary} disabled={sending} onClick={undoCommon}>直前の共通情報適用を取り消す</button><p className={styles.small}>後から入力した値や追加した視野、画像の対応、画素サイズは保持します。</p></>}
  </details>
  <details className={styles.metadataHelp}><summary>画素サイズ・領域マスク</summary><p>全視野が同じ画素サイズの場合だけ指定します。不明なら空欄のまま測定します。</p><div className={styles.formGrid}><label>X µm/px<input aria-label="一括 X方向 µm/px" type="number" min={.000001} step="any" disabled={locked} value={pixelX} onChange={event=>{setPixelX(event.target.value);setCalibrationConfirmed(false);}}/></label><label>Y µm/px<input aria-label="一括 Y方向 µm/px" type="number" min={.000001} step="any" disabled={locked} value={pixelY} onChange={event=>{setPixelY(event.target.value);setCalibrationConfirmed(false);}}/></label></div>{(pixelX||pixelY)&&<label className={styles.checkbox}><input type="checkbox" disabled={locked} checked={calibrationConfirmed} onChange={event=>setCalibrationConfirmed(event.target.checked)}/>全視野のX・Y画素サイズを撮影記録で確認しました。</label>}<label className={styles.checkbox}><input type="checkbox" disabled={locked||hasFields} checked={importLabels} onChange={event=>{setImportLabels(event.target.checked);setConfirmed(false);}}/>各視野の整数ラベルマスクを取り込む</label>{importLabels&&<div className={styles.formGrid}><label>マスク TIFF（複数可）<input key={round} aria-label="一括 マスク画像" type="file" accept=".tif,.tiff" multiple disabled={locked} onChange={event=>{setLabels(Array.from(event.target.files||[]));setConfirmed(false);setCalibrationConfirmed(false);}}/></label><label>マスクの末尾文字<input aria-label="一括 マスクの末尾文字" disabled={locked} value={labelSuffix} onChange={event=>{setLabelSuffix(event.target.value);setConfirmed(false);setCalibrationConfirmed(false);}}/></label></div>}</details>
  <h3>登録する視野を確認</h3><p className={styles.small}>末尾文字を除いた名前で対応させます。同名・不足がある行は登録できません。名前はこの画面内だけで扱い、保存先のパスには使いません。</p>
  {mapping.errors.map((error,i)=><p key={i} className={styles.error}>{error}</p>)}
  <div className={`${styles.tableWrap} ${styles.batchTable}`}><table><thead><tr><th>視野</th>{columns.map(channel=><th key={channel.id}>{channel.label||channel.id}</th>)}{importLabels&&<th>マスク</th>}<th>状態</th></tr></thead><tbody>{mapping.rows.map(row=><tr key={row.key}><th>{row.key}</th>{columns.map(channel=><td key={channel.id}>{row.files[channel.id]?.name||"不足"}</td>)}{importLabels&&<td>{row.files.labels?.name||"不足"}</td>}<td>{row.errors.length?row.errors.join(" / "):progress[row.key]?.status==="succeeded"?"登録済み":progress[row.key]?.status==="uploading"?"登録中":progress[row.key]?.status==="failed"?progress[row.key].error:"未登録"}</td></tr>)}</tbody></table></div>
  {!!mapping.rows.length&&<details className={styles.metadataHelp}><summary>行ごとの実験情報を確認・修正</summary><div className={`${styles.tableWrap} ${styles.metadataTable}`}><table><thead><tr><th>視野</th>{metadataColumns.map(([key,label])=><th key={key}>{label}</th>)}</tr></thead><tbody>{mapping.rows.map((row,i)=><tr key={row.key}><th>{row.key}</th>{metadataColumns.map(([key,label])=><td key={key}><input aria-label={`一括 視野 ${i+1} の${label}`} disabled={locked} value={(metadata[row.key]||emptyBatchMetadata)[key]} maxLength={80} type={key==="repeat_length"?"number":"text"} min={key==="repeat_length"?0:undefined} onChange={event=>setRow(row.key,key,event.target.value)}/></td>)}</tr>)}</tbody></table></div></details>}
  <label className={styles.checkbox}><input type="checkbox" disabled={locked} checked={confirmed} onChange={event=>setConfirmed(event.target.checked)}/>全視野の画像対応と実験情報を確認しました。</label>
  <div className={styles.actionRow}><button className={styles.primary} disabled={!ready||sending||successful===mapping.rows.length} onClick={()=>run(upload)}>{locked?"未登録の視野を再試行":"確認した視野を登録"} · {mapping.rows.length} 視野</button>{locked&&!sending&&<button className={styles.secondary} onClick={()=>{setColumns(current=>current.map(column=>({...column,files:[],confirmed:false})));setLabels([]);setMetadata({});setProgress({});setRound(value=>value+1);setConfirmed(false);setCalibrationConfirmed(false);setNotice("");setCommonReview(null);setCommonUndo(null);setCommonNotice("");}}>次の一括登録を準備</button>}</div>
  {(sending||notice)&&<p role="status" className={styles.notice}>{sending?`${successful} / ${mapping.rows.length} 視野を登録済み`:notice}</p>}
  {!!mapping.rows.length&&successful===mapping.rows.length&&!sending&&<button className={styles.primary} onClick={()=>{setOpen(false);requestAnimationFrame(onInspect);}}>登録した画像を確認 →</button>}
  <p className={styles.small}>{LOCAL_MODE?"画像はローカルに保存します。":"画像は非公開APIへ直接送信します。"}保存期限は最終操作から24時間です。{LOCAL_MODE&&"終了中に期限を迎えたデータは次回起動時に削除します。"}入力内容はこの画面を閉じると失われます。</p>
 </div></details>;
}
