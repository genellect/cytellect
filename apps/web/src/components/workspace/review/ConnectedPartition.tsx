"use client";

import {useEffect, useId, useRef, useState} from "react";
import type {components} from "@/lib/generated";
import styles from "./connected-partition.module.css";

export type PartitionTableData = components["schemas"]["RegionPartitionTable"];
export interface PartitionSourceOption {revisionId:string; label:string; detail?:string}
export interface PartitionChannelOption {id:string; label:string; stain?:string|null}
export interface PartitionRequest {
  fieldId:string; nuclearRevisionId:string; targetRevisionId:string; referenceRevisionId:string; channelId:string;
}
export interface ConnectedPartitionProps {
  fieldId:string; fieldLabel:string; nuclearRevisionId?:string;
  /** The field's regions inside the nuclei, by name (核小体, 核質). */
  sources:Array<PartitionSourceOption&{name:string}>;
  /** Target and reference by name; the workspace keeps them so every pane and the heading read the same pair (MV-05). */
  pair:{target:string;reference:string}; onPair:(pair:{target:string;reference:string})=>void;
  /** The measured stain is the one chosen above the image. */
  channel:PartitionChannelOption;
  load:(request:PartitionRequest)=>Promise<PartitionTableData>;
  exportCsv:(request:PartitionRequest)=>Promise<void>;
  selectedNucleus?:number; onSelectNucleus?:(id:number)=>void;
}

const reasonLabels:Record<string,string> = {
  empty_target:"対象領域がありません", empty_reference:"参照領域がありません",
  background_not_confirmed:"測定用の背景ROIが未確認です", source_excluded:"保存された除外があります",
  nonpositive_target_mean:"対象の平均値が0以下です", nonpositive_reference_mean:"参照の平均値が0以下です",
  ratio_out_of_range:"比が計算可能な数値範囲を超えています",
  target_review_required:"対象領域の確認が必要です", reference_review_required:"参照領域の確認が必要です",
  target_no_candidate:"対象領域が確定していません", reference_no_candidate:"参照領域が確定していません",
  target_indeterminate:"対象領域を判定できません", reference_indeterminate:"参照領域を判定できません",
  target_unclassified:"対象領域の状態が未確定です", reference_unclassified:"参照領域の状態が未確定です",
};
function reasonText(reason:string){return reasonLabels[reason]??reason;}
function valueText(value:number|null|undefined){return value==null?"欠測":new Intl.NumberFormat("ja-JP",{maximumSignificantDigits:6}).format(value);}
function requestKey(request:PartitionRequest){return JSON.stringify(request);}

/** The partition table of one field in the nucleolus-and-nucleoplasm colour mode (MV-05, M23). It loads as soon as the
 * target, the reference and the stain are known, with no button; the request names all three, and the table names them.
 * Every scientific value, including the CSV, comes from the API. */
export function ConnectedPartition({fieldId,fieldLabel,nuclearRevisionId,sources,pair,onPair,channel,load,exportCsv,
  selectedNucleus,onSelectNucleus}:ConnectedPartitionProps){
  const controlId=useId();
  const [basis,setBasis]=useState<"raw"|"corrected">("raw");
  const [state,setState]=useState<{key:string;table?:PartitionTableData;error?:string}>({key:""});
  const [exporting,setExporting]=useState(false);
  const target=sources.find(item=>item.name===pair.target),reference=sources.find(item=>item.name===pair.reference);
  const request:PartitionRequest={fieldId,nuclearRevisionId:nuclearRevisionId??"",targetRevisionId:target?.revisionId??"",
    referenceRevisionId:reference?.revisionId??"",channelId:channel.id};
  const key=requestKey(request);
  const valid=!!nuclearRevisionId&&!!target&&!!reference&&target.revisionId!==reference.revisionId&&!!channel.id;
  const current=state.key===key?state:undefined;
  const table=current?.table;
  const areaKey=table?.calibration?"area_um2":"area_px";
  const areaUnit=table?.calibration?"µm²":"px²";
  // The loader may be a new function on every render; only the request decides a new load.
  const loader=useRef(load);
  useEffect(()=>{loader.current=load;},[load]);
  useEffect(()=>{
    if(!valid)return;
    let live=true;
    const asked:PartitionRequest=JSON.parse(key);
    loader.current(asked).then(result=>{
      if(result.field_id!==asked.fieldId||result.nuclear_source.revision_id!==asked.nuclearRevisionId
        ||result.target_source.revision_id!==asked.targetRevisionId||result.reference_source.revision_id!==asked.referenceRevisionId
        ||result.pixel_source.channel.channel_id!==asked.channelId)throw new Error("選択した入力と結果の対応を確認できません。");
      if(live)setState({key,table:result});
    }).catch(error=>{if(live)setState({key,error:error instanceof Error?error.message:"分配表を取得できませんでした。"});});
    return()=>{live=false;};
  },[key,valid]);
  const names=sources.map(item=>item.name);
  async function download(){
    if(!table)return;
    setExporting(true);
    try{await exportCsv(request);}catch(error){setState({key,table,error:error instanceof Error?error.message:"CSVを保存できませんでした。"});}
    finally{setExporting(false);}
  }
  return <section className={styles.panel} aria-label="区画への分配">
    {!nuclearRevisionId?<p>区画への分配の表示には、核領域の採用が必要です。</p>
    :sources.length<2?<p>分配の比較には、核内の 2 領域（例：核小体と核質）の測定が必要です。{sources.length?`測定済みの核内領域：${sources.length}`:"測定済みの核内領域：なし"}</p>:<>
      <div className={styles.choices}>
        <label htmlFor={`${controlId}-target`}>対象<select id={`${controlId}-target`} value={pair.target} onChange={event=>onPair({target:event.target.value,reference:event.target.value===pair.reference?pair.target:pair.reference})}>
          {sources.map(source=><option key={source.name} value={source.name}>{source.label}</option>)}</select></label>
        <span aria-hidden="true">÷</span>
        <label htmlFor={`${controlId}-reference`}>参照<select id={`${controlId}-reference`} value={pair.reference} onChange={event=>onPair({reference:event.target.value,target:event.target.value===pair.target?pair.reference:pair.target})}>
          {sources.map(source=><option key={source.name} value={source.name}>{source.label}</option>)}</select></label>
        <span>測定する染色：{channel.label}</span>
      </div>
      {!names.includes(pair.target)||!names.includes(pair.reference)?<p role="status">この視野には{!names.includes(pair.target)?"対象":"参照"}の領域がありません。</p>
      :!current?<p role="status">分配表を読み込み中…</p>:null}
    </>}
    {current?.error&&<p role="alert">{current.error}</p>}
    {table&&<>
      {table.review_status==="preview"&&<p role="status">確認用の計算表です。統計に使う前に、領域・欠測・除外を確認してください。</p>}
      <div className={styles.toolbar}><label htmlFor={`${controlId}-basis`}>表示する輝度<select id={`${controlId}-basis`} value={basis} onChange={event=>setBasis(event.target.value as "raw"|"corrected")}>
        <option value="raw">原値</option><option value="corrected">背景補正値</option>
      </select></label><button type="button" disabled={exporting} onClick={()=>void download()}>{exporting?"CSVを保存中…":"原値・補正値をCSV保存"}</button></div>
      <p className={styles.definition}>K = 対象の平均輝度 ÷ 参照の平均輝度（同じ染色）。統計の「核質／核小体 log₂ 比」と同じ向きは、対象：核質、参照：核小体です。</p>
      <p className={styles.definition}>区画内の飽和：未評価。飽和画素を含む核では、K が実際より小さく出ることがあります。</p>
      <p role="status">{table.background.status==="confirmed"?"背景補正：保存済みの確認済み背景ROI":"測定用の背景ROIが未確認のため、補正値は欠測です。"}</p>
      <div className={styles.tableScroll} tabIndex={0} role="region" aria-label="核ごとの分配表">
        <table><caption>{fieldLabel}の分配表 · {table.target_source.label} ÷ {table.reference_source.label} · {basis==="raw"?"原値":"背景補正値"}</caption><thead><tr>
          <th scope="col">核</th><th scope="col">K</th><th scope="col">log2K</th><th scope="col">状態・欠測理由</th>
          <th scope="col">対象面積<br/>{areaUnit}</th><th scope="col">参照面積<br/>{areaUnit}</th>
          <th scope="col">対象平均<br/>元の輝度単位</th><th scope="col">参照平均<br/>元の輝度単位</th>
          <th scope="col">対象積算<br/>輝度 × px</th><th scope="col">参照積算<br/>輝度 × px</th>
        </tr></thead><tbody>{table.rows.map(row=>{
          const reasons=row[basis].missing_reasons.map(reasonText);
          const mean=basis==="raw"?"raw_mean":"corrected_mean";
          const integrated=basis==="raw"?"raw_integrated":"corrected_integrated";
          return <tr key={row.nucleus_id} aria-selected={selectedNucleus===row.nucleus_id} data-excluded={row.excluded||undefined}>
            <th scope="row">{onSelectNucleus?<button type="button" onClick={()=>onSelectNucleus(row.nucleus_id)} aria-label={`画像の核${row.nucleus_id}を選択`}>{row.nucleus_id}</button>:row.nucleus_id}</th>
            <td>{valueText(row[basis].k)}</td><td>{valueText(row[basis].log2_k)}</td>
            <td>{reasons.length?reasons.join("、"):"測定済み"}{row.exclusions.map((item,index)=><div key={index}>{item.source==="nuclear"?"核":item.source==="target"?"対象":"参照"}の除外：{item.reason}</div>)}</td>
            <td>{valueText(row.target[areaKey])}</td><td>{valueText(row.reference[areaKey])}</td>
            <td>{valueText(row.target[mean])}</td><td>{valueText(row.reference[mean])}</td>
            <td>{valueText(row.target[integrated])}</td><td>{valueText(row.reference[integrated])}</td>
          </tr>;
        })}</tbody></table>
      </div>
      {!table.rows.length&&<p>保存済みの核領域がないため、核の測定値はありません。</p>}
      <details className={styles.provenance}><summary>採用した入力と測定の定義</summary>
        <dl><dt>核</dt><dd>{table.nuclear_source.label} / {table.nuclear_source.revision_id} · {table.nuclear_source.adopted?"現在の採用領域":"保存された領域"} · {table.nuclear_source.reviewed?"確認済み":"確認前"}</dd>
          <dt>対象</dt><dd>{table.target_source.label} / {table.target_source.revision_id} · {table.target_source.adopted?"現在の採用領域":"保存された領域"} · {table.target_source.reviewed?"確認済み":"確認前"}</dd>
          <dt>参照</dt><dd>{table.reference_source.label} / {table.reference_source.revision_id} · {table.reference_source.adopted?"現在の採用領域":"保存された領域"} · {table.reference_source.reviewed?"確認済み":"確認前"}</dd>
          <dt>測定チャンネル</dt><dd>{table.pixel_source.channel.label}（{table.pixel_source.channel.stain??"染色未設定"}）</dd>
          <dt>画素寸法</dt><dd>{table.calibration?`${table.calibration.pixel_size_x_um} × ${table.calibration.pixel_size_y_um} µm`:"未校正。面積はpxで表示"}</dd></dl>
        <p>原値と補正値、欠測・除外理由、マスクと元画素の識別情報はCSVに含まれます。</p>
        <p lang="en">{table.methods}</p>
      </details>
    </>}
  </section>;
}
