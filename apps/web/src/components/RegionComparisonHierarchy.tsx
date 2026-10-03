"use client";
import {useMemo,useState} from "react";
import {errorCodeMessage} from "@/lib/api";
import {comparisonLabel,type RegionComparisonResult} from "@/lib/region-comparison-view";
import {regionComparisonHierarchy,type ComparisonFieldNode,type ComparisonSampleNode,type ComparisonUnitNode} from "@/lib/region-comparison-trace";
import type {RegionFieldTraceTarget} from "@/lib/region-trace";
import {formatValue} from "@/lib/types";
import styles from "./comparison-hierarchy.module.css";

type Navigation={disabled:boolean;fieldLabels:Record<string,string>;onInspectSourceField?:(target:RegionFieldTraceTarget)=>void};
type Props=Navigation&{result:RegionComparisonResult;revisionLabel:string};
const statuses:Record<string,string>={selected:"集計に採用",excluded:"明示除外",out_of_scope:"比較対象外",no_regions:"領域なし",no_selected_values:"採用できる測定値なし",missing:"欠測"};
const savedValue=(value:number|null)=>value===null?"未集計":formatValue(value);
const savedCount=(value:number|null)=>value===null?"不明":formatValue(value);
const naturalOrder=new Intl.Collator("ja",{numeric:true});
const fixedOrder=(left:string,right:string)=>left<right?-1:left>right?1:0;
const compareLabels=(left:string,right:string,leftKey:string,rightKey:string)=>naturalOrder.compare(left,right)||fixedOrder(leftKey,rightKey);
const compareFields=(left:ComparisonFieldNode,right:ComparisonFieldNode,labels:Record<string,string>)=>compareLabels(labels[left.fieldId]||left.fieldId,labels[right.fieldId]||right.fieldId,left.fieldId,right.fieldId);

function Field({node,disabled,fieldLabels,onInspectSourceField}:Navigation&{node:ComparisonFieldNode}){
 const [recordsOpen,setRecordsOpen]=useState(false);
 const label=fieldLabels[node.fieldId]||"保存済みの視野";
 return <article className={styles.field} aria-label={`集計の${label}`}>
  <div className={styles.fieldHeading}><b>{label}</b><span>視野内の中央値 <strong>{savedValue(node.value)}</strong></span></div>
  <p className={styles.status}>{statuses[node.status]||node.status}</p>
  {node.exclusionReason&&<p className={styles.reason}>除外理由：{node.exclusionReason}</p>}
  {node.failureReason&&<p className={styles.reason}>処理失敗：{errorCodeMessage(node.failureReason)}。この視野の領域数は不明です。</p>}
  <dl className={styles.counts}><div><dt>入力領域</dt><dd>{savedCount(node.inputObservations)}</dd></div><div><dt>採用</dt><dd>{savedCount(node.selectedObservations)}</dd></div><div><dt>除外</dt><dd>{savedCount(node.excludedObservations)}</dd></div><div><dt>欠測</dt><dd>{savedCount(node.missingObservations)}</dd></div></dl>
  {node.target&&onInspectSourceField?<button type="button" className={styles.sourceButton} disabled={disabled} onClick={()=>onInspectSourceField(node.target!)} aria-label={`集計の${label} を保存済み画像で確認`}>この集計の視野を確認 →</button>:<p className={styles.unavailable}>保存済みの測定出典を画像で確認できません。集計表と出典ファイルをご確認ください。</p>}
  <details className={styles.sourceDetails} onToggle={event=>setRecordsOpen(event.currentTarget.open)}><summary>視野の記録と採否</summary>
   <dl><div><dt>条件</dt><dd>{node.condition}</dd></div><div><dt>実験単位</dt><dd>{node.experimentalUnit??"未記録"}</dd></div><div><dt>試料</dt><dd>{node.sample??"未記録"}</dd></div><div><dt>対応ペア</dt><dd>{node.pair??"未記録"}</dd></div><div><dt>視野ID</dt><dd><code>{node.fieldId}</code></dd></div></dl>
   {recordsOpen&&node.observationNotes.length>0&&<ul>{node.observationNotes.map(note=><li key={note.observationId}><span>{statuses[note.status]||note.status}{note.reason?`：${errorCodeMessage(note.reason)}`:""}</span><code>{note.observationId}</code></li>)}</ul>}
  </details>
 </article>;
}

function Sample({node,...navigation}:Navigation&{node:ComparisonSampleNode}){
 return <details className={styles.sample} aria-label={`${node.condition} 実験単位 ${node.experimentalUnit} 試料 ${node.sample}`}>
  <summary><span>試料 {node.sample}</span><span className={styles.value}>試料内の視野平均 <strong>{savedValue(node.value)}</strong></span></summary>
  <div className={styles.fields}>{node.fields.toSorted((left,right)=>compareFields(left,right,navigation.fieldLabels)).map(field=><Field key={field.key} node={field} {...navigation}/>)}</div>
 </details>;
}

function Unit({node,...navigation}:Navigation&{node:ComparisonUnitNode}){
 return <details className={styles.unit} aria-label={`${node.condition} 実験単位 ${node.experimentalUnit}`}>
  <summary><span className={styles.identity}>{node.condition} · 実験単位 {node.experimentalUnit}<small>{statuses[node.status]||node.status}</small></span><span className={styles.value}>実験単位の値 <strong>{savedValue(node.value)}</strong></span></summary>
  <p className={styles.unitNote}>集計に用いた領域：{formatValue(node.selectedObservations)}。領域や視野は、別の独立反復として数えません。</p>
  <div className={styles.samples}>{node.samples.toSorted((left,right)=>compareLabels(left.sample,right.sample,left.key,right.key)).map(sample=><Sample key={sample.key} node={sample} {...navigation}/>)}</div>
 </details>;
}

/** Render saved server cells and membership only; no aggregation or scientific n is derived here. */
export default function RegionComparisonHierarchy({result,revisionLabel,disabled,fieldLabels,onInspectSourceField}:Props){
 const hierarchy=useMemo(()=>regionComparisonHierarchy(result),[result]);
 return <section className={styles.hierarchy} aria-label="実験単位から視野への集計">
  <h3>実験単位の値をたどる</h3>
  <p className={styles.context}><b>{comparisonLabel(result)}</b><br/>{revisionLabel} · 単位 {result.unit}{result.channel?.stain?` · 標識 ${result.channel.stain}`:""}</p>
  <p>視野内の中央値 → 試料内の視野平均 → 実験単位内の試料平均。各段階を開くと、この結果に保存された値と採否を確認できます。</p>
  {result.spec.selection.channel_id===null&&<p>面積測定にはチャンネルを使用していません。元画像を開いた際の蛍光チャンネルは、領域を確認するための表示です。</p>}
  {disabled&&<p className={styles.notice}>処理中、または未保存の領域・設定・実験情報があるため、画像への切り替えを停止しています。保存済みの集計は展開して確認できます。</p>}
  {!hierarchy.ok?<p className={styles.notice} role="status">集計の対応関係を確認できません。この結果の集計表・採否・出典ファイルをご確認ください。保存済みの図とダウンロードは引き続き利用できます。</p>:<>
   <div className={styles.units}>{hierarchy.design==="paired"?hierarchy.pairs.map(pair=><details className={styles.pair} key={pair.key} aria-label={`対応ペア ${pair.pair}`}>
    <summary><span>対応ペア {pair.pair}</span><span className={styles.status}>{statuses[pair.status]||pair.status}</span></summary>
    <p className={styles.unitNote}>保存された対応関係に従って条件を並べています。条件ごとの行を別々のペアとして数えません。</p>
    <div className={styles.pairedUnits}>{pair.units.map(unit=><Unit key={unit.key} node={unit} disabled={disabled} fieldLabels={fieldLabels} onInspectSourceField={onInspectSourceField}/>)}</div>
   </details>):result.spec.conditions.map(condition=><section className={styles.conditionGroup} key={condition} aria-label={`条件 ${condition} の実験単位`}>
    <h4 className={styles.conditionHeading}>条件 {condition}</h4>
    {hierarchy.units.filter(unit=>unit.condition===condition).toSorted((left,right)=>compareLabels(left.experimentalUnit,right.experimentalUnit,left.key,right.key)).map(unit=><Unit key={unit.key} node={unit} disabled={disabled} fieldLabels={fieldLabels} onInspectSourceField={onInspectSourceField}/>)}
   </section>)}</div>
   {hierarchy.outOfScopeFields.length>0&&<details className={styles.outOfScope}><summary>比較対象外の視野</summary><p>この比較の集計には使われていません。未記録の試料・実験単位は推測して補っていません。</p><div className={styles.fields}>{hierarchy.outOfScopeFields.toSorted((left,right)=>compareFields(left,right,fieldLabels)).map(field=><Field key={field.key} node={field} disabled={disabled} fieldLabels={fieldLabels} onInspectSourceField={onInspectSourceField}/>)}</div></details>}
  </>}
 </section>;
}
