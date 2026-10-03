"use client";
import {useState} from "react";
import {useQuery} from "@tanstack/react-query";
import {download,errorCodeMessage,errorMessage,post,request} from "@/lib/api";
import {formatValue,type Job} from "@/lib/types";
import {type RegionComparisonRequest,type RegionField,type RegionMetadata,type RegionRevision} from "@/lib/region-types";
import {comparisonLabel,comparisonWarnings,probabilityLabel,regionComparisonJobs,selectedRegionComparisonJob,type RegionComparisonResult} from "@/lib/region-comparison-view";
import {usePrivateImage} from "@/lib/usePrivateImage";
import type {DescriptiveOption} from "./DescriptivePanel";
import styles from "./workspace.module.css";
import {plannedSelection,selectionChangedFromPlan} from "@/lib/planned-selection";
import RegionComparisonHierarchy from "./RegionComparisonHierarchy";
import type {RegionFieldTraceTarget} from "@/lib/region-trace";

type Props={revision?:RegionRevision;fields:RegionField[];options:DescriptiveOption[];jobs:Job[];blocked:boolean;dirty:boolean;traceBlocked?:boolean;fieldLabels?:Record<string,string>;run:(work:()=>Promise<void>)=>void;onReview:()=>void;onInspectField:(fieldId:string,revisionId:string)=>void;onInspectSourceField?:(target:RegionFieldTraceTarget)=>void;revisionLabels:Record<string,string>};
const fileLabels:Record<string,string>={"figure.svg":"SVG","figure.pdf":"PDF","figure.png":"PNG","plot-data.csv":"図の元データ","observations.csv":"観測・採否","source-fields.csv":"実験情報","field-summary.csv":"視野集計","sample-summary.csv":"試料集計","experimental-units.csv":"実験単位集計","unit-ledger.csv":"実験単位の採否","pair-ledger.csv":"対応ペア","comparisons.csv":"比較結果","missingness.csv":"欠測","excluded-failed-fields.csv":"失敗視野の除外","figure-caption.md":"図の説明","figure-data.json":"条件と出典","methods.md":"Methods"};
const metadataLabels=[['condition','条件'],['sample','試料'],['experimental_unit','独立実験単位'],['acquisition_date','撮影日／バッチ'],['pair','対応ペア'],['repeat_length','リピート長']] as const;
const asText=(value:unknown)=>value===null||value===undefined?"—":String(value);
function Records({rows,columns}:{rows:Record<string,unknown>[];columns:[string,string][]}){return <div className={styles.tableWrap}><table><thead><tr>{columns.map(([key,label])=><th key={key}>{label}</th>)}</tr></thead><tbody>{rows.map((row,i)=><tr key={i}>{columns.map(([key])=><td key={key}>{formatValue(row[key])}</td>)}</tr>)}</tbody></table></div>;}

export default function RegionComparisonPanel({revision,fields,options,jobs,blocked,dirty,traceBlocked=false,fieldLabels={},run,onReview,onInspectField,onInspectSourceField,revisionLabels}:Props){
 const [metadata,setMetadata]=useState<Record<string,RegionMetadata>>(()=>Object.fromEntries(fields.map(field=>[field.id,{...field.metadata}])));
 const [metadataDirty,setMetadataDirty]=useState(false);
 const [choice,setChoice]=useState("");const option=plannedSelection(options,choice,revision?.config.plan_resolution);
 const [design,setDesign]=useState<""|"independent"|"paired">("");const [unitDefinition,setUnitDefinition]=useState("");const [pairingBasis,setPairingBasis]=useState("");const [designConfirmed,setDesignConfirmed]=useState(false);
 const [conditions,setConditions]=useState<string[]>([]);const [familyKind,setFamilyKind]=useState<"control"|"planned">("control");const [control,setControl]=useState("");const [planned,setPlanned]=useState<string[]>([]);
 const [acquisitionConfirmed,setAcquisitionConfirmed]=useState(false);const [samplingConfirmed,setSamplingConfirmed]=useState(false);const [missingnessConfirmed,setMissingnessConfirmed]=useState(false);
 const [language,setLanguage]=useState<"en"|"ja">("en");const [preset,setPreset]=useState<"nature-single"|"nature-double">("nature-double");
 const [selectedJob,setSelectedJob]=useState("");const [submitting,setSubmitting]=useState(false);
 const available=regionComparisonJobs(jobs);const job=selectedRegionComparisonJob(jobs,selectedJob,revision?.id);
 const result=useQuery({queryKey:["region-comparison",job?.id],queryFn:()=>request<RegionComparisonResult>(`/v1/jobs/${job!.id}/region-comparison`),enabled:job?.state==="succeeded"});
 const data=!submitting&&job?.state==="succeeded"&&result.data?.revision_id===job.revision_id?result.data:undefined;
 const image=usePrivateImage(data&&job?`/v1/jobs/${job.id}/files/figure.png`:null);
 const knownConditions=[...new Set(fields.map(field=>field.metadata.condition).filter((value):value is string=>!!value))];
 const pairChoices=conditions.flatMap((a,i)=>conditions.slice(i+1).map(b=>[a,b] as [string,string]));
 const contrasts=familyKind==="control"?conditions.filter(value=>value!==control).map(value=>[control,value]):pairChoices.filter(pair=>planned.includes(JSON.stringify(pair)));
 const scopeMatches=conditions.length>=2&&contrasts.length>0&&new Set(contrasts.flat()).size===conditions.length&&contrasts.flat().every(value=>conditions.includes(value));
 const metric=option?.selection.metric||"";const area=metric.startsWith("area_");const needsSampling=metric==="area_px"||metric.includes("integrated");
 const missingMetadata=fields.some(field=>!field.metadata.condition||(conditions.includes(field.metadata.condition)&&(!field.metadata.sample||!field.metadata.experimental_unit||(design==="paired"&&!field.metadata.pair)||(!area&&!field.metadata.acquisition_date))));
 const disabled=blocked||dirty||metadataDirty||submitting||!revision?.reviewed||!option||!design||!designConfirmed||!unitDefinition.trim()||(design==="paired"&&!pairingBasis.trim())||!scopeMatches||missingMetadata||!acquisitionConfirmed||!missingnessConfirmed||(needsSampling&&!samplingConfirmed);
 function clearConfirmations(){setDesignConfirmed(false);setAcquisitionConfirmed(false);setMissingnessConfirmed(false);}
 const metadataUpdate=(fid:string,key:keyof RegionMetadata,value:string)=>{setMetadata(current=>({...current,[fid]:{...current[fid],[key]:key==="repeat_length"?(value===""?null:Number(value)):value||null}}));setMetadataDirty(true);clearConfirmations();};
 async function submit(){
  if(disabled||!revision||!option||option.selection.source!=="region"||!design)return;
  const selection={...option.selection,metric:option.selection.metric as RegionComparisonRequest["selection"]["metric"]};
  const spec:RegionComparisonRequest={mode:"region-experimental-unit",version:"1.0.0",selection,design:{kind:design,confirmed:true,unit_definition:unitDefinition.trim(),pairing_basis:design==="paired"?pairingBasis.trim():null},conditions,comparison_family:{family_id:"primary",kind:familyKind,control:familyKind==="control"?control:null,contrasts},acquisition_review:{confirmed:true,basis:metric==="area_um2"?"calibrated-area":"same-settings",field_batches:{},spatial_sampling_confirmed:samplingConfirmed},missingness_confirmed:true,aggregation:"field-median_sample-mean_unit-mean-v1",missingness_policy:"available-observations_require-unexcluded-units-v1",plot:{kind:design==="paired"?"paired":"distribution",preset,language,width_inches:7,height_inches:3,font_size:7,x_label:"",y_label:"",group_order:conditions}};
  setSubmitting(true);try{const created=await post<{job_id:string}>(`/v1/revisions/${revision.id}/region-comparisons`,spec);setSelectedJob(created.job_id);}finally{setSubmitting(false);}
 }
 return <section className={styles.regionComparison} aria-label="実験単位で比較">
  <div className={styles.card}><h2>実験情報を確認</h2><p>処置を独立に割り付けた単位を記録し、その単位から得た複数視野には同じIDを使います。領域数や視野数を独立反復数に置き換えません。</p>
   <details open={missingMetadata||metadataDirty}><summary>視野と実験単位の対応</summary><p className={styles.small}>比較する視野の条件・試料・独立実験単位を入力します。対応がある場合は同じペア名を使います。未確認の情報を推測して埋めないでください。</p>
    <div className={`${styles.tableWrap} ${styles.metadataTable}`}><table><thead><tr><th>視野</th>{metadataLabels.map(([key,label])=><th key={key}>{label}</th>)}</tr></thead><tbody>{fields.map((field,i)=><tr key={field.id}><th>視野 {i+1}</th>{metadataLabels.map(([key,label])=><td key={key}><input aria-label={`視野 ${i+1} の${label}`} value={metadata[field.id]?.[key]??""} type={key==="repeat_length"?"number":"text"} min={key==="repeat_length"?0:undefined} step={key==="repeat_length"?"any":undefined} maxLength={80} disabled={blocked} onChange={event=>metadataUpdate(field.id,key,event.target.value)}/></td>)}</tr>)}</tbody></table></div>
    <button className={styles.secondary} disabled={blocked||dirty||!metadataDirty||revision?.state!=="succeeded"} onClick={()=>run(async()=>{await post(`/v1/revisions/${revision!.id}/region-metadata`,{version:"1.0.0",fields:Object.fromEntries(Object.entries(metadata).map(([fid,values])=>[fid,Object.fromEntries(Object.entries(values).map(([key,value])=>[key,typeof value==="string"?value.trim()||null:value]))]))});})}>実験情報を新しい解析版に保存</button><p className={styles.small}>画像と修正領域を保持し、新しい解析版で再測定します。元の情報も旧版に残ります。</p>
   </details>
   {!revision?.reviewed&&<div className={styles.notice}>保存後は領域・背景と採否を確認してください。<button className={styles.secondary} onClick={onReview}>画像と品質確認へ</button></div>}
  </div>
  <div className={styles.statistics}><div className={`${styles.statsControls} ${styles.comparisonControls}`}><h2>実験単位で比較する</h2>
   <label>比較する測定値<select aria-label="比較する測定値" value={option?.id||""} onChange={event=>{setChoice(event.target.value);clearConfirmations();setSamplingConfirmed(false);}}>{options.map(item=><option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
   {revision?.config.plan_resolution&&!option&&<p className={styles.notice}>採用計画の指標・チャンネルをこの解析版で利用できません。測定値を確認して選択してください。</p>}{selectionChangedFromPlan(option,revision?.config.plan_resolution)&&<p className={styles.notice}>採用計画から指標またはチャンネルを変更しています。この選択を比較条件として保存します。</p>}
   <label>実験デザイン<select aria-label="実験デザイン" value={design} onChange={event=>{setDesign(event.target.value as typeof design);setDesignConfirmed(false);}}><option value="">選択してください</option><option value="independent">独立した実験単位の比較</option><option value="paired">同じ実験単位・対応する試料の比較</option></select></label>
   <label>独立実験単位の定義<input aria-label="独立実験単位の定義" value={unitDefinition} maxLength={200} placeholder="例：別々に培養した培養皿" onChange={event=>{setUnitDefinition(event.target.value);setDesignConfirmed(false);}}/></label>
   {design==="paired"&&<label>対応の根拠<input aria-label="対応の根拠" value={pairingBasis} maxLength={200} placeholder="どの試料同士が対応するか" onChange={event=>{setPairingBasis(event.target.value);setDesignConfirmed(false);}}/></label>}
   <label className={styles.checkbox}><input type="checkbox" checked={designConfirmed} onChange={event=>setDesignConfirmed(event.target.checked)}/>独立性と、必要な対応関係を実験記録で確認しました。</label>
   <fieldset className={styles.comparisonGroup}><legend>比較に含める条件</legend>{knownConditions.map(condition=><label className={styles.checkbox} key={condition}><input type="checkbox" checked={conditions.includes(condition)} onChange={event=>{setConditions(current=>event.target.checked?[...current,condition]:current.filter(value=>value!==condition));setPlanned([]);clearConfirmations();}}/>{condition}</label>)}{knownConditions.length<2&&<p className={styles.small}>比較には2条件以上が必要です。上の実験情報に、実際の条件を記録してください。</p>}</fieldset>
   <label>比較する組み合わせ<select aria-label="比較する組み合わせ" value={familyKind} onChange={event=>{setFamilyKind(event.target.value as typeof familyKind);setMissingnessConfirmed(false);}}><option value="control">対照群と各条件</option><option value="planned">事前に決めた組み合わせ</option></select></label>
   {familyKind==="control"?<label>対照群<select aria-label="対照群" value={control} onChange={event=>{setControl(event.target.value);setMissingnessConfirmed(false);}}><option value="">選択してください</option>{conditions.map(condition=><option key={condition}>{condition}</option>)}</select></label>:<fieldset className={styles.comparisonGroup}><legend>実施する比較</legend>{pairChoices.map(pair=>{const key=JSON.stringify(pair);return <label className={styles.checkbox} key={key}><input type="checkbox" checked={planned.includes(key)} onChange={event=>{setPlanned(current=>event.target.checked?[...current,key]:current.filter(value=>value!==key));setMissingnessConfirmed(false);}}/>{pair[0]} と {pair[1]}</label>;})}</fieldset>}
   <p className={styles.small}>この実行で指定した全比較を1集合としてHolm補正します。比較A − 比較Bの差を示します。</p>
   <details className={styles.metadataHelp} open={!acquisitionConfirmed||!missingnessConfirmed||(needsSampling&&!samplingConfirmed)}><summary>撮影条件と採否の確認</summary>
    <p>{area?"領域の定義・採取方法を比較できることを確認します。":"同じ対象・標識、撮影設定、検出器の値の尺度、背景補正の妥当性と信号の飽和を確認します。撮影日／バッチも記録してください。"} 自動的な輝度正規化やバッチ補正は行いません。</p>
    <label className={styles.checkbox}><input type="checkbox" checked={acquisitionConfirmed} onChange={event=>setAcquisitionConfirmed(event.target.checked)}/>{area?"領域定義・採取方法と面積の尺度を比較できると確認しました。":"撮影・標識・背景と非飽和の信号を比較できると確認しました。"}</label>
    {needsSampling&&<label className={styles.checkbox}><input type="checkbox" checked={samplingConfirmed} onChange={event=>setSamplingConfirmed(event.target.checked)}/>画素の空間的な大きさとサンプリングが同じです。</label>}
    <label className={styles.checkbox}><input type="checkbox" checked={missingnessConfirmed} onChange={event=>setMissingnessConfirmed(event.target.checked)}/>除外・欠測と比較対象を確認しました。</label>
    <p>値のない未除外の実験単位や不完全な対応ペアは、黙って除かず比較を止めます。各条件2単位または2ペア以上が必要ですが、十分な検出力を保証する数ではありません。</p>
   </details>
   <details className={styles.metadataHelp}><summary>集計方法と図の設定</summary><p>視野内の中央値 → 試料内の視野平均 → 独立実験単位内の試料平均。各実験単位が等しく1点を持ちます。</p><p>{design==="paired"?"対応ありt検定":"Welchのt検定"}、両側検定。95%信頼区間は多重比較補正前の区間です。</p>
    <div className={styles.formGrid}><label>図の言語<select aria-label="比較図の言語" value={language} onChange={event=>setLanguage(event.target.value as typeof language)}><option value="en">English</option><option value="ja">日本語</option></select></label><label>図の幅<select aria-label="比較図の幅" value={preset} onChange={event=>setPreset(event.target.value as typeof preset)}><option value="nature-single">89 mm</option><option value="nature-double">183 mm</option></select></label></div>
    {design==="paired"&&<p>対応ありでは、宣言したペアを線で結びます。</p>}
   </details>
   {missingMetadata&&<p className={styles.notice}>比較に必要な実験情報が未記録です。上の表で確認・保存してください。</p>}{(dirty||metadataDirty)&&<p className={styles.notice}>未反映の変更を保存し、品質確認を完了してください。</p>}
   <button className={styles.primary} disabled={disabled} onClick={()=>run(submit)}>比較と図を作成</button>
  </div><div className={styles.statsResults}>
   {submitting?<div className={styles.card} role="status">比較と図の生成を受け付けています。</div>:job&&job.state!=="succeeded"?<div className={styles.card} role={job.state==="failed"?"alert":"status"}><h3>{job.state==="failed"?"比較できませんでした":job.state==="cancelled"?"比較を中止しました":"比較と図を作成しています"}</h3>{job.error&&<p>{errorCodeMessage(job.error)}</p>}<p>以前の結果は履歴から確認できます。</p></div>:selectedJob&&!job?<p role="status">処理状態を確認しています。</p>:result.error?<div role="alert" className={styles.error}>{errorMessage(result.error)}</div>:job?.state==="succeeded"&&result.isPending?<p role="status">結果を読み込んでいます。</p>:!data?<div className={styles.card}><h3>実験情報から比較へ</h3><p>独立性や撮影条件が未確認でも「分布と図」から測定値を確認できます。比較は実験デザインを確定してから行います。</p></div>:<>
    <div className={styles.card} aria-label="保存済みの群間比較"><div className={styles.sectionHeader}><h3>群間の比較</h3><span>{data.revision_id===revision?.id?"採用中の解析版":"旧版の結果"}</span></div><p aria-label="保存済みの比較指標"><b>{comparisonLabel(data)}</b></p><p>{revisionLabels[data.revision_id]||"保存済みの解析版"} · 単位 {data.unit} · {data.spec.design.kind==="paired"?"対応あり":"独立群"}</p><p className={styles.small}>以下は保存済みの解析条件に対応する結果です。設定を変更したら「比較と図を作成」で更新します。</p>{image&&<img src={image} alt="実験単位の集計値と群間比較の図" style={{maxWidth:"100%",height:"auto"}}/>}
     <div className={styles.actionRow}>{(Array.isArray(data.figure.source_files)?data.figure.source_files:[]).filter((name):name is string=>typeof name==="string"&&!!fileLabels[name]).map(name=><button className={styles.secondary} key={name} onClick={()=>run(()=>download(`/v1/jobs/${job!.id}/files/${name}`,name))}>{fileLabels[name]} ↓</button>)}</div>
    </div>
    <div className={styles.card}><h3>差と不確かさ</h3><div className={styles.tableWrap}><table><thead><tr><th>比較A</th><th>比較B</th><th>差（A − B）</th><th>95%信頼区間</th><th>p（未補正）</th><th>p（Holm）</th></tr></thead><tbody>{data.comparisons.map((row,i)=><tr key={i}><td>{asText(row.group_a)}</td><td>{asText(row.group_b)}</td><td>{formatValue(row.estimate)}</td><td>{formatValue(row.ci_low)} ～ {formatValue(row.ci_high)}</td><td>{probabilityLabel(row.p_value)}</td><td>{probabilityLabel(row.p_holm)}</td></tr>)}</tbody></table></div><p className={styles.small}>Holm補正は指定した {data.spec.comparison_family.contrasts.length} 比較に適用。信頼区間は個別の95%区間です。</p>
     <Records rows={data.counts} columns={[["condition","条件"],["observations","領域"],["selected_fields","視野"],["samples","試料"],["experimental_units","独立実験単位"],["complete_pairs","完全なペア"]]}/>
     {!!data.warnings.length&&<ul className={styles.comparisonWarnings}>{data.warnings.map(warning=><li key={warning}>{comparisonWarnings[warning]||warning}</li>)}</ul>}
    </div>
    <RegionComparisonHierarchy key={JSON.stringify([job!.id,data.revision_id,data.source_fingerprint])} result={data} fieldLabels={fieldLabels} revisionLabel={revisionLabels[data.revision_id]||"保存済みの解析版"} disabled={blocked||dirty||metadataDirty||submitting||traceBlocked} onInspectSourceField={onInspectSourceField}/>
    <div className={styles.card}><h3>採用・除外と元画像</h3><p>入力 {formatValue(data.selection.input_rows)} · 採用 {formatValue(data.selection.selected)} · 明示除外 {formatValue(data.selection.excluded??0)} · 欠測 {formatValue(data.selection.missing??0)} · 比較対象外 {formatValue(data.selection.out_of_scope??0)}</p><p className={styles.small}>失敗を確認して除外した視野 {data.excluded_failed_fields.length} 件の観測数は不明です。</p>
     <div className={styles.tableWrap}><table><thead><tr><th>視野</th><th>条件</th><th>試料</th><th>実験単位</th><th>状態</th><th>元画像</th></tr></thead><tbody>{data.source_field_ledger.map((row,i)=><tr key={i}><td>{fieldLabels[String(row.field_id)]||"保存済みの視野"}</td><td>{asText(row.condition)}</td><td>{asText(row.sample)}</td><td>{asText(row.experimental_unit)}</td><td>{row.explicitly_excluded?`除外：${asText(row.exclusion_reason)}`:row.in_scope?"比較対象":"対象外"}</td><td><button className={styles.linkButton} disabled={blocked||dirty||metadataDirty||traceBlocked} onClick={()=>onInspectField(String(row.field_id),data.revision_id)}>この解析版の画像を確認</button></td></tr>)}</tbody></table></div>
     <details className={styles.measurementDetails}><summary>保存済みの設計と出典</summary><p>実験単位：{data.spec.design.unit_definition}{data.spec.design.pairing_basis&&<> / 対応：{data.spec.design.pairing_basis}</>}</p><p>解析版: <code>{data.revision_id}</code></p><p>出典ハッシュ: <code>{data.source_fingerprint}</code></p><p>比較集合: <code>{data.spec.comparison_family.family_id}</code></p></details>
    </div>
   </>}
   {!!available.length&&<details className={styles.card}><summary>比較の履歴</summary>{available.map(item=><button className={styles.linkButton} key={item.id} onClick={()=>setSelectedJob(item.id)}>{new Date(item.created*1000).toLocaleString("ja-JP")} · {revisionLabels[item.revision_id]||"解析版"} · {item.state==="succeeded"?"作成済み":item.state==="failed"?"失敗":item.state==="cancelled"?"中止":item.state==="running"?"実行中":"待機中"}</button>)}</details>}
  </div></div>
 </section>;
}
