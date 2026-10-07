"use client";

import {useState} from "react";
import type {Point} from "@/lib/types";

export type WorkspaceBackgrounds = Record<string,Record<string,{polygon:Point[];confirmed:true}>>;
export interface ConnectedBackgroundProps {
  fieldId:string;fieldLabel:string;channels:Array<{id:string;stain:string|null;role?:string}>;
  backgrounds:WorkspaceBackgrounds;confirmedChannelIds:string[];disabled?:boolean;drawing?:boolean;
  onDraw:(channels:string[])=>void;
  onRemove:(channels:string[])=>Promise<void>;
}

/** Background is a separate selection, never added to the measured object mask. */
export function ConnectedBackground({fieldId,fieldLabel,channels,backgrounds,confirmedChannelIds,disabled=false,drawing=false,onDraw,onRemove}:ConnectedBackgroundProps){
  const available=channels.filter(channel=>channel.role!=="unused");
  const [chosen,setChosen]=useState<string[]|null>(null),[error,setError]=useState("");
  const selected=(chosen??available.map(channel=>channel.id)).filter(id=>available.some(channel=>channel.id===id));
  const [busy,setBusy]=useState(false);
  const existing=selected.filter(id=>!!backgrounds[fieldId]?.[id]);
  async function remove(){setBusy(true);setError("");try{await onRemove(existing);}catch{setError("背景ROIを削除できませんでした。");}finally{setBusy(false);}}
  return <section aria-label="背景ROI" style={{display:"grid",gap:10}}>
    <strong>背景ROI · {fieldLabel}</strong>
    <fieldset disabled={disabled||drawing||busy}><legend>同じ背景領域を使うチャンネル</legend>
      {available.map(channel=><label key={channel.id} style={{display:"block"}}><input type="checkbox" checked={selected.includes(channel.id)} onChange={event=>setChosen(previous=>{const current=previous??available.map(item=>item.id);return event.target.checked?[...current,channel.id]:current.filter(id=>id!==channel.id);})}/>{channel.id} · {channel.stain??"染色未設定"}{backgrounds[fieldId]?.[channel.id]&&confirmedChannelIds.includes(channel.id)?" · 保存済み":""}</label>)}
    </fieldset>
    <button type="button" disabled={disabled||drawing||busy||!selected.length} onClick={()=>onDraw(selected)}>{drawing?"背景を描画中":"背景を描く"}</button>
    <small>細胞や検出領域を含まない場所を囲み、画像上で保存します。対象チャンネルも一緒に記録します。</small>
    {!!existing.length&&<button type="button" disabled={disabled||drawing||busy} onClick={()=>void remove()}>選択した背景ROIを削除</button>}
    {error&&<p role="alert">{error}</p>}
  </section>;
}
