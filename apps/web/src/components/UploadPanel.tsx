"use client";
import { useState, type FormEvent } from "react";
import { LOCAL_MODE, request } from "@/lib/api";
import type { Recipe } from "@/lib/types";
import styles from "./workspace.module.css";
export default function UploadPanel({wid,onDone,run,demo}:{wid:string;onDone:(recipeId:Recipe["id"])=>void;run:(fn:()=>Promise<void>)=>void;demo:boolean}){
 const [open,setOpen]=useState(false);
 const [mode,setMode]=useState("channels");const [purpose,setPurpose]=useState("ncl");const [includeGfp,setIncludeGfp]=useState(false);const [sending,setSending]=useState(false);
 const roles=mode==="legacy"?["dapi","ncl","gfp"]:purpose==="gfp"?["dapi","gfp"]:includeGfp?["dapi","ncl","gfp"]:["dapi","ncl"];
 const names:Record<string,string>={dapi:"核染色（DAPI等）",ncl:"NCL",gfp:"GFP"};
 async function upload(e:FormEvent<HTMLFormElement>){
  e.preventDefault();const form=e.currentTarget;const source=new FormData(form);const data=new FormData();
  const optional=(key:string)=>source.get(key)?String(source.get(key)):null;
  data.set("metadata",JSON.stringify({condition:source.get("condition"),experimental_unit:source.get("experimental_unit"),sample:source.get("sample"),acquisition_date:source.get("acquisition_date"),pair:optional("pair"),repeat_length:optional("repeat_length")?Number(source.get("repeat_length")):null,pixel_size_um:optional("pixel_size_um")?Number(source.get("pixel_size_um")):null}));
  data.set("channel_roles",JSON.stringify(roles));
  if(mode==="ome"){data.set("ome",source.get("ome")!);data.set("mapping",JSON.stringify(roles.map(role=>Number(source.get(role+"_index")))));}else for(const role of roles)data.set(role,source.get(role)!);
  data.set("legacy",String(mode==="legacy"));
  setSending(true);try{await request(`/v1/workspaces/${wid}/fields`,{method:"POST",body:data});form.reset();setOpen(false);onDone(mode==="legacy"?"ncl-legacy-rgb":purpose==="gfp"?"gfp-nuclear-2d":"ncl-native-2d");}finally{setSending(false);}
 }
 return <details className={styles.upload} open={open} onToggle={e=>setOpen(e.currentTarget.open)}><summary>＋ 画像を登録</summary>{demo?<p className={styles.notice}>この環境は合成データ専用です。研究画像をアップロードできません。</p>:<form onSubmit={e=>{e.preventDefault();run(()=>upload(e));}}>
  <div className={styles.notice}>8/16-bitグレースケール2D TIFF、または単一シリーズ OME-TIFF（Z=1、T=1）。{LOCAL_MODE?"画像はローカルに保存されます。保存期限は最終操作から24時間です。終了中に期限を迎えたデータは次回起動時に削除します。":"原画像は非公開APIへ直接送信します。"}</div>
  <div className={styles.formGrid}><label>入力形式<select aria-label="入力形式" value={mode} onChange={e=>setMode(e.target.value)}><option value="channels">チャンネル別TIFF</option><option value="ome">OME-TIFF（2–3チャンネル）</option><option value="legacy">RGB表示TIFF・互換モード</option></select></label>{mode!=="legacy"&&<label>測定対象<select aria-label="測定対象" value={purpose} onChange={e=>setPurpose(e.target.value)}><option value="ncl">NCL · 核と核小体</option><option value="gfp">GFP · 核内輝度</option></select></label>}</div>
  {mode!=="legacy"&&purpose==="ncl"&&<label className={styles.checkbox}><input type="checkbox" checked={includeGfp} onChange={e=>setIncludeGfp(e.target.checked)}/>GFPチャンネルも登録する</label>}
  <div className={styles.formGrid}>{mode==="ome"?<><label>OME-TIFF<input name="ome" type="file" accept=".tif,.tiff" required/></label>{roles.map((role,i)=><label key={role}>{names[role]} のチャンネル（0始まり）<input name={role+"_index"} type="number" min={0} max={roles.length-1} defaultValue={i} required/></label>)}</>:roles.map(role=><label key={role}>{names[role]} TIFF<input name={role} type="file" accept=".tif,.tiff" required/></label>)}</div>
  <div className={styles.formGrid}><label>群<input name="condition" required maxLength={80}/></label><label>独立実験単位<input name="experimental_unit" required maxLength={80} placeholder="例：experiment-1"/></label><label>試料<input name="sample" required maxLength={80}/></label><label>撮影日／バッチ<input name="acquisition_date" required maxLength={40}/></label><label>対応ペア（任意）<input name="pair" maxLength={80}/></label><label>リピート長（任意）<input name="repeat_length" type="number" min={0} step="any"/></label><label>画素サイズ µm/px（任意）<input name="pixel_size_um" type="number" min={.000001} step="any"/></label></div>
  <label className={styles.checkbox}><input type="checkbox" required/>登録する画像の染色とチャンネル対応を確認しました。</label><button className={styles.primary} disabled={sending}>この視野を登録</button>
 </form>}</details>;
}
