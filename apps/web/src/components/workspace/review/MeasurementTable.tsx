"use client";
import {useEffect,useRef,useState} from "react";
import {ApiError,errorCodeMessage,errorMessage} from "@/lib/api";
import styles from "./connected-workspace.module.css";
import type {MeasurementRow,RegionFeatureTable} from "@/lib/workspace/api-adapter";

/** The saved measurements of one field, one row per region; a row selects its outline, and an
 * outline chosen on the image brings its row into view. Values are shown to one decimal (three below 10),
 * as in the nucleus table; the exact value is in the cell's title and in the CSV. */
/** One decimal for ordinary values; small values (|x| < 10, e.g. a corrected mean near zero) keep three
 * decimals so they never read as 0. */
const shown=(value:number)=>value.toLocaleString(undefined,{maximumFractionDigits:Math.abs(value)<10?3:1});

/** Column names of the region features (region-features/1.0.0), in the order the API lists them. */
const FEATURE_COLUMNS:Record<string,string>={solidity:"ソリディティ",axis_ratio:"長短軸比",eccentricity:"離心率",cv:"画素の CV",cv_corrected:"画素の CV（背景補正）",positive_area_fraction:"陽性面積率"};
/** Why a region has no feature value, in words (the code stays in the CSV and the API). */
const FEATURE_REASONS:Record<string,string>={below_minimum_area:"面積が最小面積より小さいため、形を測っていません",touches_border:"画像の端にかかるため、形を測っていません",
  degenerate:"形を定義できません",nonpositive_mean:"平均が 0 以下のため、CV を計算できません",threshold_not_established:"視野の画素が一様で、閾値を決められません",
  nucleus_excluded:"除外した領域です",automatic_background_insufficient_tiles:"背景を推定できなかった視野です",automatic_background_insufficient_coverage:"背景を推定できなかった視野です"};

export function MeasurementTable({rows,selected,onSelect,features}:{rows:MeasurementRow[];selected?:number;onSelect:(n:number)=>void;features?:RegionFeatureTable|null}){
  const body=useRef<HTMLTableSectionElement>(null);
  useEffect(()=>{if(selected!==undefined)body.current?.querySelector("tr[aria-selected=true]")?.scrollIntoView({block:"nearest"});},[selected]);
  const corrected=rows.some(row=>"mean_corrected" in row);
  const extra=features?.metrics.filter(metric=>metric in FEATURE_COLUMNS)??[];
  const byRegion=new Map((features?.rows??[]).map(row=>[row.region_id,row.values]));
  return <table><thead><tr><th>番号</th><th>面積 / px²</th><th>平均輝度</th><th>積算輝度</th>{corrected&&<><th>平均（背景補正）</th><th>積算（背景補正）</th></>}{extra.map(metric=><th key={metric}>{FEATURE_COLUMNS[metric]}</th>)}</tr></thead><tbody ref={body}>{rows.map(row=><tr key={row.region_id} aria-selected={row.region_id===selected}><td><button onClick={()=>onSelect(row.region_id)}>{row.region_id}</button></td>{[row.area_px,row.mean,row.integrated,...(corrected?[row.mean_corrected,row.integrated_corrected]:[])].map((value,i)=><td key={i} title={value==null?row.correction_missing_reason||row.intensity_missing_reason||row.area_missing_reason||undefined:String(value)}>{value==null?"—":shown(value)}</td>)}{extra.map(metric=>{const value=byRegion.get(row.region_id)?.[metric];return <td key={metric} title={value?.value==null?(value?.missing_reason?FEATURE_REASONS[value.missing_reason]??value.missing_reason:undefined):String(value.value)}>{value?.value==null?"—":shown(value.value)}</td>;})}</tr>)}</tbody></table>;
}

/** The table with its shape and pixel-signal columns, loaded from the API when asked (#257 A-4, region-features/1.0.0).
 * Asked for once, the columns follow the field, stain and revision in view (`loadKey`). A failure is shown with its
 * reason, and the button comes back to try again. Without `load` (a candidate or an earlier version) the measured
 * columns only. */
export function FeatureMeasurementTable({rows,selected,onSelect,load,loadKey}:{rows:MeasurementRow[];selected?:number;onSelect:(n:number)=>void;
  load?:()=>Promise<RegionFeatureTable>;loadKey:string}){
  const [wanted,setWanted]=useState(false);
  const [state,setState]=useState<{key:string;value:RegionFeatureTable|null;error?:string}>();
  useEffect(()=>{
    if(!wanted||!load)return;
    let live=true;
    load().then(value=>{if(live)setState({key:loadKey,value});},error=>{
      if(!live)return;
      setState({key:loadKey,value:null,error:error instanceof ApiError?errorMessage(error):error instanceof Error?errorCodeMessage(error.message):"形と信号の値を読み込めませんでした。"});
      setWanted(false);});
    return()=>{live=false;};
  },[wanted,loadKey]);// eslint-disable-line react-hooks/exhaustive-deps -- `load` is a new function each render; `loadKey` names what it loads
  const current=state?.key===loadKey?state:undefined;
  return <>
    <MeasurementTable rows={rows} selected={selected} onSelect={onSelect} features={current?.value??null}/>
    {current?.error&&<p role="alert">形と信号の値を読み込めませんでした：{current.error}</p>}
    {load&&!wanted&&<button type="button" className={styles.linkButton} onClick={()=>{setState(undefined);setWanted(true);}}>形と信号の値を表示</button>}
  </>;
}
