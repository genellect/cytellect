import type {RegionMetadata} from "./region-types";

export type ComparisonControl="metadata-save"|"metric"|"design"|"unit-definition"|"pairing-basis"|"design-confirmed"|"conditions"|"control"|"contrasts"|"acquisition"|"sampling"|"missingness"|"review";
export type ComparisonReadinessIssue={id:string;message:string;action?:string;target?:ComparisonControl;fieldId?:string;metadataKey?:keyof RegionMetadata};
export type ComparisonReadinessInput={
 blocked:boolean;submitting:boolean;dirty:boolean;metadataDirty:boolean;hasRevision:boolean;reviewed:boolean;hasMetric:boolean;metric:string;
 design:""|"independent"|"paired";unitDefinition:string;pairingBasis:string;designConfirmed:boolean;
 conditions:string[];familyKind:"control"|"planned";control:string;contrasts:string[][];
 fieldLabels?:Record<string,string>;fields:{id:string;metadata:RegionMetadata}[];acquisitionConfirmed:boolean;samplingConfirmed:boolean;missingnessConfirmed:boolean;
};

/** Explain existing form gates only. Never infer effective n or recompute server results. */
export function comparisonReadiness(input:ComparisonReadinessInput):ComparisonReadinessIssue[]{
 const {conditions,contrasts,design,metric}=input;
 if(input.submitting)return [{id:"submitting",message:"比較を受け付けています。"}];
 if(input.blocked)return [{id:"processing",message:"作業中の処理が完了すると比較できます。"}];
 const issues:ComparisonReadinessIssue[]=[];
 const add=(id:string,message:string,target:ComparisonControl,action:string)=>issues.push({id,message,target,action});
 if(input.dirty)add("measurement-draft","画像と領域の変更を再測定へ反映してください。","review","画像と領域へ");
 if(input.metadataDirty)add("metadata-draft","入力した実験情報を新しい解析版に保存してください。","metadata-save","実験情報を保存する操作へ");
 if(!input.hasRevision)add("measurement-required","領域を測定してから比較へ進みます。","review","画像と領域へ");
 else if(!input.reviewed)add("review-required","この解析版の品質確認を完了してください。","review","画像と品質確認へ");
 if(!input.hasMetric)add("metric-required","この解析版で比較する測定値を選んでください。","metric","測定値を選ぶ");
 if(conditions.length<2)add("conditions-required","比較に含める条件を2つ以上選んでください。","conditions","対象条件を選ぶ");
 if(input.familyKind==="control"){
  if(!input.control)add("control-required","選んだ条件の中から対照群を選んでください。","control","対照群を選ぶ");
  else if(!conditions.includes(input.control))add("control-outside-scope",`対照群「${input.control}」が比較対象から外れています。対照群と対象条件を確認してください。`,"control","対照群を確認する");
 }else if(!contrasts.length)add("contrasts-required","事前に決めた比較の組み合わせを選んでください。","contrasts","組み合わせを選ぶ");
 if(conditions.length>=2&&contrasts.length&&(input.familyKind!=="control"||conditions.includes(input.control))){
  const used=new Set(contrasts.flat());const unused=conditions.filter(value=>!used.has(value));const outside=[...used].filter(value=>!conditions.includes(value));
  if(unused.length)add("unused-conditions",`「${unused.join("」「")}」を使う比較がありません。対象条件か比較の組み合わせを見直してください。`,"contrasts","比較の組み合わせへ");
  if(outside.length)add("outside-conditions",`比較に含まれる「${outside.join("」「")}」が対象条件にありません。`,"conditions","対象条件を確認する");
 }
 if(!design)add("design-required","実験単位の独立性・対応に合うデザインを選んでください。","design","実験デザインを選ぶ");
 if(!input.unitDefinition.trim())add("unit-definition-required","条件を独立に割り付けた単位を記録してください。","unit-definition","実験単位の定義へ");
 if(design==="paired"&&!input.pairingBasis.trim())add("pairing-basis-required","どの試料同士が対応するか、その根拠を記録してください。","pairing-basis","対応の根拠へ");
 // Saved metadata remains authoritative until its new analysis revision exists.
 // When a draft is present the save instruction takes precedence over stale gaps.
 if(!input.metadataDirty)input.fields.forEach(field=>{
  const label=input.fieldLabels?.[field.id]||"保存済みの視野";
  const missing:[keyof RegionMetadata,string][]=[];const value=field.metadata;
  if(!value.condition)missing.push(["condition","条件"]);
  else if(conditions.includes(value.condition)){
   if(!value.sample)missing.push(["sample","試料"]);
   if(!value.experimental_unit)missing.push(["experimental_unit","独立実験単位"]);
   if(design==="paired"&&!value.pair)missing.push(["pair","対応ペア"]);
   if(!metric.startsWith("area_")&&!value.acquisition_date)missing.push(["acquisition_date","撮影日／バッチ"]);
  }
  if(missing.length)issues.push({id:`metadata-${field.id}`,message:`${label}：${missing.map(([,label])=>label).join("・")}が未記録です。`,fieldId:field.id,metadataKey:missing[0][0],action:`${label} の${missing[0][1]}へ`});
 });
 if(!input.designConfirmed)add("design-confirmation","独立性と対応関係を実験記録で確認してください。","design-confirmed","独立性・対応を確認する");
 if(!input.acquisitionConfirmed)add("acquisition-confirmation",metric.startsWith("area_")?"領域定義・採取方法と面積の尺度を確認してください。":"撮影・標識・背景と信号の飽和を確認してください。","acquisition","撮影条件を確認する");
 if((metric==="area_px"||metric.includes("integrated"))&&!input.samplingConfirmed)add("sampling-confirmation","画素の大きさと空間サンプリングを確認してください。","sampling","空間サンプリングを確認する");
 if(!input.missingnessConfirmed)add("missingness-confirmation","除外・欠測と比較対象を確認してください。","missingness","採否を確認する");
 return issues;
}
