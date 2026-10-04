"use client";
import {useEffect,useState} from "react";
import {useQuery} from "@tanstack/react-query";
import {download,errorCodeMessage,errorMessage,post,request} from "@/lib/api";
import {associationIssues,associationJobs,associationSourceLabel,associationAxisLabel,associationScopeLabel,commonResultPath,commonWarnings,type AssociationRequest,type AssociationResult} from "@/lib/common-statistics";
import {defaultFigureEdits,figureOrder,validFigureEdits} from "@/lib/figure-controls";
import {comparisonWarnings,probabilityLabel} from "@/lib/region-comparison-view";
import {formatValue,type Job} from "@/lib/types";
import type {RegionField,RegionRevision} from "@/lib/region-types";
import {usePrivateImage} from "@/lib/usePrivateImage";
import type {DescriptiveOption} from "./DescriptivePanel";
import FigureControls from "./FigureControls";
import styles from "./workspace.module.css";

type Props={revision?:RegionRevision;fields:RegionField[];options:DescriptiveOption[];jobs:Job[];blocked:boolean;dirty:boolean;metadataDirty:boolean;run:(work:()=>Promise<void>)=>void;onDraftChange:(dirty:boolean)=>void};
const fileNames:Record<string,string>={"figure.svg":"SVG","figure.pdf":"PDF","figure.png":"PNG","associations.csv":"相関結果","experimental-units.csv":"両軸の実験単位","counts.csv":"対象数","unit-ledger.csv":"実験単位の採否","missingness.csv":"欠測","figure-data.json":"条件と出典","figure-caption.md":"図の説明","methods.md":"Methods"};
export default function RegionAssociationPanel({revision,fields,options,jobs,blocked,dirty,metadataDirty,run,onDraftChange}:Props){
 const [xId,setX]=useState("");const [yId,setY]=useState("");const [conditions,setConditions]=useState<string[]>([]);
 const [method,setMethod]=useState<"pearson"|"spearman">("pearson");const [scope,setScope]=useState<"per-condition"|"pooled">("per-condition");
 const [unitDefinition,setDefinition]=useState("");const [independence,setIndependence]=useState(false);const [acquisition,setAcquisition]=useState(false);const [sampling,setSampling]=useState(false);const [missingness,setMissingness]=useState(false);const [pooling,setPooling]=useState(false);
 const [figure,setFigure]=useState(defaultFigureEdits);const [preset,setPreset]=useState<"nature-single"|"nature-double"|"custom">("nature-double");const [language,setLanguage]=useState<"en"|"ja">("en");
 const [selectedId,setSelectedId]=useState("");const [submitting,setSubmitting]=useState(false);
 const fingerprint=JSON.stringify([xId,yId,conditions,method,scope,unitDefinition,independence,acquisition,sampling,missingness,pooling,figure,preset,language]);const [saved,setSaved]=useState(fingerprint);
 useEffect(()=>{onDraftChange(fingerprint!==saved);},[fingerprint,saved,onDraftChange]);
 const regionOptions=options.filter(option=>option.selection.source==="region");const x=regionOptions.find(option=>option.id===xId)?.selection;const y=regionOptions.find(option=>option.id===yId)?.selection;
 const knownConditions=[...new Set(fields.flatMap(field=>field.metadata.condition?[field.metadata.condition]:[]))];
 const issues=associationIssues({x,y,conditions,fields,unitDefinition,independence,acquisition,sampling,missingness,scope,pooling});
 const disabled=blocked||dirty||metadataDirty||!revision?.reviewed||submitting||!!issues.length||!validFigureEdits(figure,preset);
 const available=associationJobs(jobs);const job=selectedId?available.find(job=>job.id===selectedId):available.find(job=>job.revision_id===revision?.id);
 const result=useQuery({queryKey:["region-association",job?.id],queryFn:()=>request<AssociationResult>(commonResultPath(job!)),enabled:job?.state==="succeeded"});
 const data=!submitting&&job?.state==="succeeded"&&result.data?.revision_id===job.revision_id?result.data:undefined;
 const image=usePrivateImage(data&&job?`/v1/jobs/${job.id}/files/figure.png`:null);
 const files=(Array.isArray(data?.figure.source_files)?data.figure.source_files:[]).filter((file):file is string=>typeof file==="string");const primaryFiles=["figure.svg","figure.pdf","figure.png","associations.csv"];
 const fileButton=(file:string)=><button className={styles.secondary} key={file} onClick={()=>run(()=>download(`/v1/jobs/${job!.id}/files/${file}`,file))}>{fileNames[file]||associationSourceLabel(file)} ↓</button>;
 function resetMetric(){setAcquisition(false);setSampling(false);setMissingness(false);setPooling(false);}
 async function submit(){
  if(disabled||!revision||x?.source!=="region"||y?.source!=="region")return;
  const spec:AssociationRequest={mode:"region-association",version:"1.0.0",x_selection:{...x,metric:x.metric as AssociationRequest["x_selection"]["metric"]},y_selection:{...y,metric:y.metric as AssociationRequest["y_selection"]["metric"]},design:{kind:"independent",confirmed:true,unit_definition:unitDefinition.trim(),pairing_basis:null},conditions,method,scope,pooling_confirmed:pooling,acquisition_review:{confirmed:true,basis:x.metric==="area_um2"&&y.metric==="area_um2"?"calibrated-area":"same-settings",field_batches:{},spatial_sampling_confirmed:sampling},missingness_confirmed:true,aggregation:"field-median_sample-mean_unit-mean-v1",missingness_policy:"require-matched-unexcluded-units-v1",plot:{kind:"scatter",preset,language,...figure,group_order:figureOrder(figure.group_order,conditions)}};
  setSubmitting(true);try{const created=await post<{job_id:string}>(`/v1/revisions/${revision.id}/common-statistics`,spec);setSelectedId(created.job_id);setSaved(fingerprint);}finally{setSubmitting(false);}
 }
 return <section className={styles.statistics} aria-label="相関解析"><div className={styles.statsControls}><h2>相関解析</h2>
  <label>横軸の測定値<select aria-label="相関の横軸" value={xId} onChange={event=>{setX(event.target.value);resetMetric();}}><option value="">選択してください</option>{regionOptions.map(option=><option key={option.id} value={option.id}>{option.label}</option>)}</select></label>
  <label>縦軸の測定値<select aria-label="相関の縦軸" value={yId} onChange={event=>{setY(event.target.value);resetMetric();}}><option value="">選択してください</option>{regionOptions.map(option=><option key={option.id} value={option.id}>{option.label}</option>)}</select></label>
  <p className={styles.small}>同じ領域から測定した2つの指標を、独立実験単位ごとに集計して対応させます。細胞数・視野数を反復数には使いません。</p>
  <label>相関係数<select aria-label="相関係数" value={method} onChange={event=>setMethod(event.target.value as typeof method)}><option value="pearson">Pearson（直線的な関係）</option><option value="spearman">Spearman（順位の関係）</option></select></label>
  <p className={styles.small}>{method==="pearson"?"Pearsonのp値は独立な正規標本の仮定に基づきます。外れ値や非線形の関係は散布図で確認してください。":"Spearmanは単調な関係を順位で評価します。同順位は平均順位とし、対応を置き換えた検定を行います。"} 各条件で両軸が揃う独立実験単位が3以上必要です。</p>
  <fieldset className={styles.comparisonGroup}><legend>相関に含める条件</legend>{knownConditions.map(condition=><label key={condition} className={styles.checkbox}><input aria-label={`相関の条件 ${condition}`} type="checkbox" checked={conditions.includes(condition)} onChange={event=>{setConditions(current=>event.target.checked?[...current,condition]:current.filter(value=>value!==condition));setIndependence(false);resetMetric();}}/>{condition}</label>)}</fieldset>
  <label>解析範囲<select aria-label="相関の解析範囲" value={scope} onChange={event=>{setScope(event.target.value as typeof scope);setPooling(false);}}><option value="per-condition">条件別</option><option value="pooled">全条件を統合</option></select></label>
  {scope==="pooled"&&<label className={styles.checkbox}><input type="checkbox" checked={pooling} onChange={event=>setPooling(event.target.checked)}/>条件を統合する根拠を確認し、群・撮影バッチの差が相関に与える影響を検討しました。</label>}
  <label>独立実験単位の定義<input aria-label="相関の独立実験単位の定義" value={unitDefinition} maxLength={200} onChange={event=>{setDefinition(event.target.value);setIndependence(false);}}/></label>
  <label className={styles.checkbox}><input type="checkbox" checked={independence} onChange={event=>setIndependence(event.target.checked)}/>相関に用いる実験単位の独立性を確認しました。</label>
  <label className={styles.checkbox}><input type="checkbox" checked={acquisition} onChange={event=>setAcquisition(event.target.checked)}/>両軸の撮影条件・領域定義と測定尺度を確認しました。</label>
  {[x?.metric,y?.metric].some(metric=>metric==="area_px"||metric?.includes("integrated"))&&<label className={styles.checkbox}><input type="checkbox" checked={sampling} onChange={event=>setSampling(event.target.checked)}/>両軸の画素サイズと空間サンプリングを確認しました。</label>}
  <label className={styles.checkbox}><input type="checkbox" checked={missingness} onChange={event=>setMissingness(event.target.checked)}/>両軸の除外・欠測と対応する実験単位を確認しました。</label>
  <p className={styles.small}>片方の測定値だけがある実験単位は、黙って除かず解析を停止します。条件別のp値は、この実行で指定した条件全体にHolm補正を適用します。</p>
  <details><summary>相関図の設定</summary><label>図の言語<select aria-label="相関図の言語" value={language} onChange={event=>setLanguage(event.target.value as typeof language)}><option value="en">English</option><option value="ja">日本語</option></select></label><label>図の幅<select aria-label="相関図の幅" value={preset} onChange={event=>setPreset(event.target.value as typeof preset)}><option value="nature-single">89 mm</option><option value="nature-double">183 mm</option><option value="custom">カスタム</option></select></label><FigureControls prefix="相関図" preset={preset} value={figure} onChange={setFigure} groups={conditions.map(id=>({id,label:id}))}/></details>
  {(!revision?.reviewed||dirty||metadataDirty)&&<p className={styles.notice}>画像・実験情報の変更を保存し、この解析版の品質確認を完了してください。</p>}
  {!!issues.length&&<ul className={styles.small}>{issues.map(issue=><li key={issue}>{issue}</li>)}</ul>}
  <button className={styles.primary} disabled={disabled} onClick={()=>run(submit)}>相関と図を作成</button>
 </div><div className={styles.statsResults}>
  {submitting?<p role="status">相関と図の生成を受け付けています。</p>:job&&job.state!=="succeeded"?<p role={job.state==="failed"?"alert":"status"}>{job.state==="failed"?errorCodeMessage(job.error||"request_failed"):job.state==="cancelled"?"相関解析を中止しました。":"相関と図を作成しています。"}</p>:selectedId&&!job?<p role="status">処理状態を確認しています。</p>:result.error?<p role="alert">{errorMessage(result.error)}</p>:data?<div className={styles.card} aria-label="保存済みの相関解析"><h3>{data.spec.method==="pearson"?"Pearsonの相関":"Spearmanの順位相関"}</h3><p>{data.revision_id===revision?.id?"採用中の解析版":"旧版の結果"} · {data.spec.scope==="per-condition"?"条件別":"全条件を統合"}</p><p aria-label="保存済みの相関横軸">横軸：{associationAxisLabel(data.x_source,data.spec.x_selection)}</p><p aria-label="保存済みの相関縦軸">縦軸：{associationAxisLabel(data.y_source,data.spec.y_selection)}</p><p className={styles.small}>保存済みの条件に対応する結果です。設定の変更後は「相関と図を作成」で更新します。</p>{image&&<img src={image} alt="独立実験単位の散布図" style={{maxWidth:"100%",height:"auto"}}/>}
   <div className={styles.actionRow}>{files.filter(file=>primaryFiles.includes(file)).map(fileButton)}</div>
   <details><summary>元データ・集計表</summary><div className={styles.actionRow}>{files.filter(file=>!primaryFiles.includes(file)).map(fileButton)}</div></details>
   <div className={styles.tableWrap}><table><thead><tr><th>条件</th><th>独立実験単位</th><th>相関係数</th><th>p（未補正）</th><th>p（Holm）</th></tr></thead><tbody>{data.associations.map((row,i)=><tr key={i}><td>{associationScopeLabel(data.spec.scope,row.scope)}</td><td>{formatValue(row.n_units)}</td><td>{formatValue(row.coefficient)}</td><td>{probabilityLabel(row.p_value)}</td><td>{probabilityLabel(row.p_holm)}</td></tr>)}</tbody></table></div>
   <p className={styles.small}>回帰直線と相関係数の信頼区間は算出していません。相関だけから因果関係は判断できません。</p>
   {!!data.warnings.length&&<ul>{data.warnings.map(warning=><li key={warning}>{commonWarnings[warning]||comparisonWarnings[warning]||warning}</li>)}</ul>}
   <details><summary>保存済みの設計と出典</summary><p>実験単位：{data.spec.design.unit_definition}</p><p>解析版：<code>{data.revision_id}</code></p><p>出典ハッシュ：<code>{data.source_fingerprint}</code></p></details>
  </div>:<p>測定値と実験情報を指定すると、相関と散布図を作成できます。</p>}
  {!!available.length&&<details className={styles.card}><summary>相関の履歴</summary>{available.map(item=><button key={item.id} className={styles.linkButton} onClick={()=>setSelectedId(item.id)}>{new Date(item.created*1000).toLocaleString("ja-JP")} · {item.state==="succeeded"?"作成済み":item.state==="failed"?"失敗":item.state==="cancelled"?"中止":"処理中"}</button>)}</details>}
 </div></section>;
}
