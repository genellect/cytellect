import type {RegionComparisonRequest,RegionField} from "./region-types";
import type {DescriptiveSelection} from "./descriptive-view";
import type {components} from "./generated";
import {defaultFigureEdits} from "./figure-controls";
import type {Job} from "./types";
export type CommonComparisonRequest=components["schemas"]["RegionComparisonRequestV2"];
export type AssociationRequest=components["schemas"]["RegionAssociationRequest"];
export type AssociationResult=components["schemas"]["AssociationView"];

export type ComparisonMethod="legacy"|"parametric"|"rank";
export type CommonPlotKind="distribution"|"paired"|"histogram"|"box"|"violin";
export function comparisonMethod(method:ComparisonMethod,design:"independent"|"paired",count:number){
 if(method==="legacy")return null;
 return {version:"2.0.0" as const,test:design==="paired"?(method==="rank"?"wilcoxon" as const:"paired-t" as const):(method==="rank"?"mann-whitney-u" as const:"welch-t" as const),omnibus:design==="independent"&&count>=3?(method==="rank"?"kruskal-wallis" as const:"welch-anova" as const):null};
}
export function comparisonMethodLabel(method:ComparisonMethod,design:string,count:number){
 if(method==="rank")return design==="paired"?"Wilcoxon符号付順位検定":count>=3?"Kruskal–Wallis検定・Mann–Whitney U検定":"Mann–Whitney U検定";
 return design==="paired"?"対応ありt検定":method!=="legacy"&&count>=3?"Welch ANOVA・Welchのt検定":"Welchのt検定";
}
export function commonComparisonRequest(base:RegionComparisonRequest,method:ComparisonMethod,kind:CommonPlotKind,bins:number):RegionComparisonRequest|CommonComparisonRequest{
 const settings=comparisonMethod(method,base.design.kind,base.conditions.length);
 return settings?{...base,...settings,plot:{...defaultFigureEdits(),preset:"nature-double",language:"en",...base.plot,kind,histogram_bins:bins}}:base;
}
export function commonResultPath(job:Job){return `/v1/jobs/${job.id}/${job.analysis_version==="2.0.0"||job.analysis_mode==="region-association"?"common-statistics":"region-comparison"}`;}
export function associationJobs(jobs:Job[]){return jobs.filter(job=>job.kind==="statistics"&&job.analysis_mode==="region-association").toSorted((a,b)=>b.created-a.created);}
const sourceTableLabels:Record<string,string>={"plot-data.csv":"図の元データ","observations.csv":"観測値と採否","source-fields.csv":"視野の実験情報","field-summary.csv":"視野集計","sample-summary.csv":"試料集計","unit-summary.csv":"実験単位集計","pair-ledger.csv":"対応ペア","excluded-failed-fields.csv":"失敗視野の除外"};
export function associationSourceLabel(file:string){const axis=file.startsWith("x-")?"横軸":file.startsWith("y-")?"縦軸":null;return axis&&sourceTableLabels[file.slice(2)]?`${axis} · ${sourceTableLabels[file.slice(2)]}`:file;}
export const commonWarnings:Record<string,string>={
 association_does_not_establish_causation_no_regression_or_batch_adjustment:"相関は因果関係を示しません。回帰分析・バッチ補正は行っていません。",
 pooled_association_may_reflect_condition_or_acquisition_batch_confounding:"統合した相関には、条件や撮影バッチ間の違いが影響している可能性があります。",
};
export function associationIssues(input:{x?:DescriptiveSelection;y?:DescriptiveSelection;conditions:string[];fields:RegionField[];unitDefinition:string;independence:boolean;acquisition:boolean;sampling:boolean;missingness:boolean;scope:"per-condition"|"pooled";pooling:boolean}){
 const {x,y}=input;const issues:string[]=[];
 if(!x||!y||x.source!=="region"||y.source!=="region")issues.push("横軸と縦軸の測定値を指定してください。");
 else if(x.region_set_id!==y.region_set_id)issues.push("横軸と縦軸には同じ領域の測定値が必要です。");
 else if(x.metric===y.metric&&x.channel_id===y.channel_id)issues.push("横軸と縦軸には異なる測定値を指定してください。");
 if(!input.conditions.length)issues.push("解析に含める条件を指定してください。");
 if(!input.unitDefinition.trim()||!input.independence)issues.push("独立実験単位の定義と独立性を確認してください。");
 const area=!!x&&!!y&&x.metric.startsWith("area_")&&y.metric.startsWith("area_");
 if(input.fields.some(field=>!field.metadata.condition||(input.conditions.includes(field.metadata.condition)&&(!field.metadata.sample||!field.metadata.experimental_unit||(!area&&!field.metadata.acquisition_date)))))issues.push("実験情報に条件・試料・独立実験単位と必要な撮影日を記録してください。");
 if(!input.acquisition)issues.push("撮影条件・領域定義と測定尺度を確認してください。");
 if([x?.metric,y?.metric].some(metric=>metric==="area_px"||metric?.includes("integrated"))&&!input.sampling)issues.push("画素の大きさと空間サンプリングを確認してください。");
 if(!input.missingness)issues.push("両軸の採否と欠測を確認してください。");
 if(input.scope==="pooled"&&!input.pooling)issues.push("全条件を統合する根拠と群・撮影バッチの影響を確認してください。");
 return issues;
}
