"use client";
import {useMemo} from "react";
import {errorCodeMessage} from "@/lib/api";
import {formatValue} from "@/lib/types";
import {regionQualityOverview,type QualityDiagnostic,type RegionQualityField} from "@/lib/region-quality-overview";
import type {RegionReport,RegionRevision} from "@/lib/region-types";
import type {RegionFieldTraceTarget,RegionTraceTarget} from "@/lib/region-trace";
import styles from "./region-quality.module.css";

type Navigation={disabled:boolean;onInspectField:(target:RegionFieldTraceTarget)=>void;onInspectRegion:(target:RegionTraceTarget)=>void;onInspectInput:(fieldId:string)=>void};
type Props=Navigation&{report:RegionReport;revision:RegionRevision;revisionLabel:string;fieldLabels:Record<string,string>;fieldOrder:string[]};
const outcomeLabels={measured:"測定済み",no_regions:"領域なし",failed:"処理失敗",excluded_failed:"理由付き失敗除外"};

function Diagnostic({label,value,disabled,onInspectRegion}:{label:string;value:QualityDiagnostic|null}&Pick<Navigation,"disabled"|"onInspectRegion">){
 if(!value)return <p className={styles.diagnostic}>{label}：不明</p>;
 if(value.status!=="measured")return <p className={styles.diagnostic}>{label}：{value.status==="not_measured"?"未測定（面積のみ）":value.status==="no_regions"?"領域なし":label==="取得時飽和"?"取得上限不明":"不明"}</p>;
 const count=(value.includedCount??0)+(value.excludedCount??0);
 return <div className={styles.diagnostic}>
  <span className={count?styles.warning:undefined}>{label}：{count?`採用対象 ${value.includedCount} / 除外対象 ${value.excludedCount} 領域`:"この診断で該当なし"}</span>
  {!!value.items.length&&<details><summary>{label}の領域と値</summary><div className={styles.issues}>{value.items.map(issue=><div key={issue.regionId}>
   <span>領域 {issue.regionId} · {issue.excluded?"除外対象":"採用対象"}{typeof issue.value==="number"?` · 画素の割合 ${formatValue(issue.value)}`:""}</span>
   {!!issue.exclusionReasons.length&&<small>除外理由：{issue.exclusionReasons.join(" / ")}</small>}
   <button type="button" disabled={disabled} onClick={()=>onInspectRegion(issue.target)} aria-label={`${label}の領域 ${issue.regionId} を画像で確認`}>この領域を確認 →</button>
  </div>)}</div></details>}
 </div>;
}

function QualityField({field,label,name,areaOnly,...nav}:Navigation&{field:RegionQualityField;label:string;name:string;areaOnly:boolean}){
 return <tr aria-label={`品質一覧の${label}`}>
  <th scope="row"><b>{label}</b>{name&&<small>{name}</small>}<small>{outcomeLabels[field.outcome]}</small></th>
  <td><span>{field.regionCount===null?"領域数不明":`${field.regionCount} 領域`}</span>{field.regionCount!==null&&<small>採用対象 {field.includedRegionCount} / 除外対象 {field.excludedRegionCount}</small>}
   {field.calibration!==null&&<small>{field.calibration==="known"?"画素サイズ確認済み":"画素サイズ不明・px²"}</small>}
   {!!field.exclusionReasons.length&&<small>除外理由：{field.exclusionReasons.join(" / ")}</small>}
   {!!field.excludedRegions.length&&<details className={styles.diagnostic}><summary>除外対象の領域と理由</summary><div className={styles.issues}>{field.excludedRegions.map(region=><div key={region.regionId}><span>領域 {region.regionId}</span><small>{region.reasons.join(" / ")}</small><button type="button" disabled={nav.disabled} onClick={()=>nav.onInspectRegion(region.target)} aria-label={`${label} の除外領域 ${region.regionId} を確認`}>この領域を確認 →</button></div>)}</div></details>}
   {field.failureReason&&<p className={styles.warning}>{errorCodeMessage(field.failureReason)}</p>}
  </td>
  <td><Diagnostic label="画像端" value={field.border} disabled={nav.disabled} onInspectRegion={nav.onInspectRegion}/>
   {areaOnly&&<p className={styles.diagnostic}>輝度・保存形式上限・取得時飽和：未測定（面積のみ）</p>}
   {!areaOnly&&<div className={styles.channels}>{field.channels.map(channel=><div className={styles.channel} key={channel.channelId} aria-label={`${label} ${channel.label} の診断`}>
    <b>{channel.label}</b>{channel.stain&&<small>標識：{channel.stain}</small>}
    <Diagnostic label="保存形式上限" value={channel.storageLimit} disabled={nav.disabled} onInspectRegion={nav.onInspectRegion}/>
    <Diagnostic label="取得時飽和" value={channel.acquisitionSaturation} disabled={nav.disabled} onInspectRegion={nav.onInspectRegion}/>
    {channel.target&&<button type="button" disabled={nav.disabled} onClick={()=>nav.onInspectField(channel.target!)} aria-label={`${label} ${channel.label} を品質一覧から確認`}>このチャンネルを確認 →</button>}
   </div>)}</div>}
   {areaOnly&&field.target&&<button type="button" disabled={nav.disabled} onClick={()=>nav.onInspectField(field.target!)} aria-label={`${label} の領域を品質一覧から確認`}>領域を確認 →</button>}
   {(field.outcome==="failed"||field.outcome==="excluded_failed")&&<><p className={styles.diagnostic}>測定結果と領域の品質は確認できません。</p><button type="button" disabled={nav.disabled} onClick={()=>nav.onInspectInput(field.fieldId)} aria-label={`${label} の入力画像を確認`}>入力画像を確認 →</button></>}
  </td>
 </tr>;
}

export default function RegionQualityOverview({report,revision,revisionLabel,fieldLabels,fieldOrder,...nav}:Props){
 const {id:revisionId,config}=revision;
 const overview=useMemo(()=>regionQualityOverview(report,{id:revisionId,config}),[report,revisionId,config]);
 const order=new Map(fieldOrder.map((id,index)=>[id,index]));
 return <section className={styles.overview} aria-label="全視野の品質一覧">
  <div className={styles.heading}><h3>全視野の品質一覧</h3><span>{revisionLabel} · この解析版全体：{revision.reviewed?"品質確認済み":"品質確認前"}</span></div>
  <p>保存済みの測定にある診断です。警告の有無だけで、品質や採否は確定しません。</p>
  {nav.disabled&&<p className={styles.notice}>処理中、または未保存の領域・設定があります。画像を切り替える前に保存・反映してください。</p>}
  {!overview.ok?<p className={styles.notice} role="status">保存済みの品質情報と出典を確認できません。測定条件と処理履歴をご確認ください。</p>:<>
   {overview.mode==="area_only"&&<p>面積のみの測定です。画像のチャンネルは領域確認用で、輝度の測定対象ではありません。</p>}
   <div className={styles.tableWrap} tabIndex={0} role="region" aria-label="全視野の診断表"><table><thead><tr><th>視野・処理状態</th><th>領域と採否</th><th>既存の診断と画像</th></tr></thead><tbody>{overview.fields.toSorted((a,b)=>(order.get(a.fieldId)??Infinity)-(order.get(b.fieldId)??Infinity)).map(field=><QualityField key={field.fieldId} field={field} label={fieldLabels[field.fieldId]||"保存済みの視野"} name={[revision.config.field_snapshot?.[field.fieldId]?.metadata.condition,revision.config.field_snapshot?.[field.fieldId]?.metadata.sample].filter(Boolean).join(" · ")} areaOnly={overview.mode==="area_only"} {...nav}/>)}</tbody></table></div>
   <p className={styles.footnote}>同じ領域を複数チャンネルで測定しても、領域数を重複して数えません。閲覧による視野ごとの確認記録は作りません。</p>
  </>}
 </section>;
}
