"use client";
import {figureOrder,validFigureEdits,type FigureEdits} from "@/lib/figure-controls";
import styles from "./workspace.module.css";
type Props={prefix:string;preset:string;value:FigureEdits;onChange:(value:FigureEdits)=>void;groups:{id:string;label:string}[]};
export default function FigureControls({prefix,preset,value,onChange,groups}:Props){
 const change=(patch:Partial<FigureEdits>)=>onChange({...value,...patch});
 const order=figureOrder(value.group_order,groups.map(group=>group.id));
 function move(index:number,offset:number){const next=[...order];[next[index],next[index+offset]]=[next[index+offset],next[index]];change({group_order:next});}
 return <details><summary>軸ラベル・寸法・表示順</summary>
  <label>横軸ラベル<input aria-label={`${prefix}の横軸ラベル`} maxLength={120} value={value.x_label} onChange={event=>change({x_label:event.target.value})} placeholder="空欄で標準のラベル"/></label>
  <label>縦軸ラベル<input aria-label={`${prefix}の縦軸ラベル`} maxLength={120} value={value.y_label} onChange={event=>change({y_label:event.target.value})} placeholder="例：Mean fluorescence (a.u.)"/></label>
  <div className={styles.formGrid}>{preset==="custom"&&<label>幅 / inch<input aria-label={`${prefix}の幅 / inch`} type="number" min={3} max={16} step="0.1" value={value.width_inches} onChange={event=>change({width_inches:Number(event.target.value)})}/></label>}
   <label>高さ / inch<input aria-label={`${prefix}の高さ / inch`} type="number" min={1} max={preset==="custom"?16:170/25.4} step="0.1" value={value.height_inches} onChange={event=>change({height_inches:Number(event.target.value)})}/></label>
   <label>文字サイズ / pt<input aria-label={`${prefix}の文字サイズ / pt`} type="number" min={5} max={preset==="custom"?24:7} step="0.5" value={value.font_size} onChange={event=>change({font_size:Number(event.target.value)})}/></label>
  </div>
  {!validFigureEdits(value,preset)&&<p role="alert">寸法と文字サイズを入力範囲内に設定してください。</p>}
  {!!groups.length&&<fieldset><legend>{prefix}の表示順</legend>{order.map((id,index)=><div className={styles.actionRow} key={id}><span>{groups.find(group=>group.id===id)?.label}</span><button type="button" className={styles.secondary} aria-label={`${prefix} ${groups.find(group=>group.id===id)?.label} を前へ`} disabled={index===0} onClick={()=>move(index,-1)}>前へ</button><button type="button" className={styles.secondary} aria-label={`${prefix} ${groups.find(group=>group.id===id)?.label} を後へ`} disabled={index===order.length-1} onClick={()=>move(index,1)}>後へ</button></div>)}</fieldset>}
 </details>;
}
