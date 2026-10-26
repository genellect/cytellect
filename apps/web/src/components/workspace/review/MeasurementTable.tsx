"use client";
import {useEffect,useRef} from "react";
import type {MeasurementRow} from "@/lib/workspace/api-adapter";

/** The saved measurements of one field, one row per region; a row selects its outline, and an
 * outline chosen on the image brings its row into view. */
export function MeasurementTable({rows,selected,onSelect}:{rows:MeasurementRow[];selected?:number;onSelect:(n:number)=>void}){
  const body=useRef<HTMLTableSectionElement>(null);
  useEffect(()=>{if(selected!==undefined)body.current?.querySelector("tr[aria-selected=true]")?.scrollIntoView({block:"nearest"});},[selected]);
  const corrected=rows.some(row=>"mean_corrected" in row);
  return <table><thead><tr><th>番号</th><th>面積 / px²</th><th>平均輝度</th><th>積算輝度</th>{corrected&&<><th>平均（背景補正）</th><th>積算（背景補正）</th></>}</tr></thead><tbody ref={body}>{rows.map(row=><tr key={row.region_id} aria-selected={row.region_id===selected}><td><button onClick={()=>onSelect(row.region_id)}>{row.region_id}</button></td>{[row.area_px,row.mean,row.integrated,...(corrected?[row.mean_corrected,row.integrated_corrected]:[])].map((value,i)=><td key={i} title={value==null?row.correction_missing_reason||row.intensity_missing_reason||row.area_missing_reason||undefined:undefined}>{value?.toLocaleString(undefined,{maximumFractionDigits:2})??"—"}</td>)}</tr>)}</tbody></table>;
}
