"use client";

import {useId, useRef, useState} from "react";
import type {components} from "@/lib/generated";
import styles from "./connected-partition.module.css";

export type PartitionTableData = components["schemas"]["RegionPartitionTable"];
export interface PartitionSourceOption {revisionId:string; label:string; detail?:string}
export interface PartitionChannelOption {id:string; label:string; stain?:string|null}
export interface PartitionRequest {
  fieldId:string; nuclearRevisionId:string; targetRevisionId:string; referenceRevisionId:string; channelId:string;
}
export interface ConnectedPartitionProps {
  fieldId:string; fieldLabel:string; nuclearRevisionId?:string; nuclearLabel?:string;
  sources:PartitionSourceOption[]; channels:PartitionChannelOption[];
  load:(request:PartitionRequest)=>Promise<PartitionTableData>;
  exportCsv:(request:PartitionRequest)=>Promise<void>;
  selectedNucleus?:number; onSelectNucleus?:(id:number)=>void;
}

const reasonLabels:Record<string,string> = {
  empty_target:"対象領域がありません", empty_reference:"参照領域がありません",
  background_not_confirmed:"測定用の背景ROIが未確認です", source_excluded:"保存された除外があります",
  nonpositive_target_mean:"対象の平均値が0以下です", nonpositive_reference_mean:"参照の平均値が0以下です",
  ratio_out_of_range:"比が計算できる数値範囲を超えています",
  target_review_required:"対象領域の確認が必要です", reference_review_required:"参照領域の確認が必要です",
  target_no_candidate:"対象領域が確定していません", reference_no_candidate:"参照領域が確定していません",
  target_indeterminate:"対象領域を判定できません", reference_indeterminate:"参照領域を判定できません",
  target_unclassified:"対象領域の状態が未確定です", reference_unclassified:"参照領域の状態が未確定です",
};
function reasonText(reason:string){return reasonLabels[reason]??reason;}
function valueText(value:number|null|undefined){return value==null?"欠測":new Intl.NumberFormat("ja-JP",{maximumSignificantDigits:6}).format(value);}
function requestKey(request:PartitionRequest){return JSON.stringify(request);}

/** Explicit source selection; every scientific value, including CSV, comes from the API. */
export function ConnectedPartition({fieldId,fieldLabel,nuclearRevisionId,nuclearLabel,sources,channels,load,exportCsv,
  selectedNucleus,onSelectNucleus}:ConnectedPartitionProps){
  const controlId=useId();
  const scope=`${fieldId}|${nuclearRevisionId??""}`;
  const [selection,setSelection]=useState({scope:"",target:"",reference:"",channel:""});
  const [basis,setBasis]=useState<"raw"|"corrected">("raw");
  const [state,setState]=useState<{key:string;table?:PartitionTableData;loading?:boolean;error?:string}>({key:""});
  const [exporting,setExporting]=useState(false);
  const serial=useRef(0);
  const chosen=selection.scope===scope?selection:{scope,target:"",reference:"",channel:""};
  const request:PartitionRequest={fieldId,nuclearRevisionId:nuclearRevisionId??"",targetRevisionId:chosen.target,
    referenceRevisionId:chosen.reference,channelId:chosen.channel};
  const key=requestKey(request);
  const current=state.key===key?state:undefined;
  const table=current?.table;
  const valid=!!nuclearRevisionId&&sources.some(item=>item.revisionId===chosen.target)
    &&sources.some(item=>item.revisionId===chosen.reference)&&channels.some(item=>item.id===chosen.channel)
    &&chosen.target!==chosen.reference;
  function choose(name:"target"|"reference"|"channel",value:string){setSelection({...chosen,[name]:value});}
  async function show(){
    if(!valid)return;
    const attempt=++serial.current;
    setState({key,loading:true});
    try{
      const result=await load(request);
      if(result.field_id!==request.fieldId||result.nuclear_source.revision_id!==request.nuclearRevisionId
        ||result.target_source.revision_id!==request.targetRevisionId||result.reference_source.revision_id!==request.referenceRevisionId
        ||result.pixel_source.channel.channel_id!==request.channelId)throw new Error("選択した入力と結果の対応を確認できません。");
      if(serial.current===attempt)setState({key,table:result});
    }catch(error){if(serial.current===attempt)setState({key,error:error instanceof Error?error.message:"分配表を取得できませんでした。"});}
  }
  async function download(){
    if(!table)return;
    setExporting(true);
    try{await exportCsv(request);}catch(error){setState({key,table,error:error instanceof Error?error.message:"CSVを保存できませんでした。"});}
    finally{setExporting(false);}
  }
  return <section className={styles.panel} aria-label="区画への分配">
    <div><h3>区画への分配</h3><p className={styles.intro}>{fieldLabel}の同じ核で、対象と参照に含まれる信号を比較します。</p></div>
    {!nuclearRevisionId?<p>この視野の核領域を採用すると、対象・参照・測定チャンネルを選べます。</p>:<>
      <p className={styles.source}>親核：{nuclearLabel??"採用した核領域"}</p>
      <fieldset className={styles.choices} disabled={current?.loading||exporting}>
        <legend>測定する入力</legend>
        <label htmlFor={`${controlId}-target`}>対象領域<select id={`${controlId}-target`} value={chosen.target} onChange={event=>choose("target",event.target.value)}>
          <option value="">対象を選択</option>{sources.map(source=><option key={source.revisionId} value={source.revisionId}>{source.label}{source.detail?`（${source.detail}）`:""}</option>)}
        </select></label>
        <label htmlFor={`${controlId}-reference`}>参照領域<select id={`${controlId}-reference`} value={chosen.reference} onChange={event=>choose("reference",event.target.value)}>
          <option value="">参照を選択</option>{sources.map(source=><option key={source.revisionId} value={source.revisionId}>{source.label}{source.detail?`（${source.detail}）`:""}</option>)}
        </select></label>
        <label htmlFor={`${controlId}-channel`}>測定チャンネル<select id={`${controlId}-channel`} value={chosen.channel} onChange={event=>choose("channel",event.target.value)}>
          <option value="">チャンネルを選択</option>{channels.map(channel=><option key={channel.id} value={channel.id}>{channel.label}{channel.stain?`（${channel.stain}）`:""}</option>)}
        </select></label>
      </fieldset>
      <p className={styles.hint}>対象と参照は、同じ核の中で重ならない領域を選びます。参照は自動で補いません。</p>
      {chosen.target&&chosen.target===chosen.reference&&<p role="status">対象と参照に異なる領域を選んでください。</p>}
      <button type="button" disabled={!valid||current?.loading||exporting} onClick={()=>void show()}>{current?.loading?"分配表を読み込み中…":"分配表を表示"}</button>
    </>}
    {current?.error&&<p role="alert">{current.error}</p>}
    {table&&<>
      <div className={styles.toolbar}><label htmlFor={`${controlId}-basis`}>表示する輝度<select id={`${controlId}-basis`} value={basis} onChange={event=>setBasis(event.target.value as "raw"|"corrected")}>
        <option value="raw">原値</option><option value="corrected">背景補正値</option>
      </select></label><button type="button" disabled={exporting} onClick={()=>void download()}>{exporting?"CSVを保存中…":"原値・補正値をCSV保存"}</button></div>
      <p className={styles.definition}>K = 対象の平均輝度 ÷ 参照の平均輝度。同じ測定チャンネルの対象／参照を表します。</p>
      <p role="status">{table.background.status==="confirmed"?"保存済みの確認済み背景ROIを用いて補正しています。":"測定用の背景ROIが未確認のため、補正値は欠測です。"}</p>
      <div className={styles.tableScroll} tabIndex={0} role="region" aria-label="核ごとの分配表を横にスクロール">
        <table><caption>{fieldLabel}の分配表 · {basis==="raw"?"原値":"背景補正値"}</caption><thead><tr>
          <th scope="col">核</th><th scope="col">対象面積<br/>px</th><th scope="col">参照面積<br/>px</th>
          <th scope="col">対象平均<br/>元の輝度単位</th><th scope="col">参照平均<br/>元の輝度単位</th>
          <th scope="col">対象積算<br/>輝度 × px</th><th scope="col">参照積算<br/>輝度 × px</th>
          <th scope="col">K</th><th scope="col">log2K</th><th scope="col">状態・欠測理由</th>
        </tr></thead><tbody>{table.rows.map(row=>{
          const reasons=row[basis].missing_reasons.map(reasonText);
          const mean=basis==="raw"?"raw_mean":"corrected_mean";
          const integrated=basis==="raw"?"raw_integrated":"corrected_integrated";
          return <tr key={row.nucleus_id} aria-selected={selectedNucleus===row.nucleus_id} data-excluded={row.excluded||undefined}>
            <th scope="row">{onSelectNucleus?<button type="button" onClick={()=>onSelectNucleus(row.nucleus_id)} aria-label={`画像の核${row.nucleus_id}を選択`}>{row.nucleus_id}</button>:row.nucleus_id}</th>
            <td>{valueText(row.target.area_px)}</td><td>{valueText(row.reference.area_px)}</td>
            <td>{valueText(row.target[mean])}</td><td>{valueText(row.reference[mean])}</td>
            <td>{valueText(row.target[integrated])}</td><td>{valueText(row.reference[integrated])}</td>
            <td>{valueText(row[basis].k)}</td><td>{valueText(row[basis].log2_k)}</td>
            <td>{reasons.length?reasons.join("、"):"測定済み"}{row.exclusions.map((item,index)=><div key={index}>{item.source==="nuclear"?"核":item.source==="target"?"対象":"参照"}の除外：{item.reason}</div>)}</td>
          </tr>;
        })}</tbody></table>
      </div>
      {!table.rows.length&&<p>保存された核領域がありません。核の測定値は作成されていません。</p>}
      <details className={styles.provenance}><summary>採用した入力と測定の定義を確認</summary>
        <dl><dt>核</dt><dd>{table.nuclear_source.label} / {table.nuclear_source.revision_id}</dd>
          <dt>対象</dt><dd>{table.target_source.label} / {table.target_source.revision_id}</dd>
          <dt>参照</dt><dd>{table.reference_source.label} / {table.reference_source.revision_id}</dd>
          <dt>測定チャンネル</dt><dd>{table.pixel_source.channel.label}（{table.pixel_source.channel.stain??"染色未設定"}）</dd>
          <dt>画素寸法</dt><dd>{table.calibration?`${table.calibration.pixel_size_x_um} × ${table.calibration.pixel_size_y_um} µm`:"未校正。面積はpxで表示"}</dd></dl>
        <p>原値と補正値、欠測・除外理由、マスクと元画素の識別情報はCSVに含まれます。</p>
        <p lang="en">{table.methods}</p>
      </details>
    </>}
  </section>;
}
