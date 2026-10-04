import {expect,it} from "vitest";
import {associationIssues,associationJobs,associationSourceLabel,associationScopeLabel,associationAxisLabel,commonComparisonRequest,commonResultPath,comparisonMethod} from "./common-statistics";
import type {RegionComparisonRequest,RegionField} from "./region-types";
import type {Job} from "./types";
it("labels each axis's source tables without changing download filenames",()=>{expect(associationSourceLabel("x-plot-data.csv")).toBe("横軸 · 図の元データ");expect(associationSourceLabel("y-sample-summary.csv")).toBe("縦軸 · 試料集計");expect(associationSourceLabel("future.csv")).toBe("future.csv");});
it("keeps literal condition names and labels saved axes independently of editable plot text",()=>{
 expect(associationScopeLabel("per-condition","pooled")).toBe("pooled");expect(associationScopeLabel("pooled","pooled")).toBe("全条件");
 expect(associationAxisLabel({region:{label:"Imported nuclei"},channel:{label:"Signal"},unit:"a.u."},{source:"region",region_set_id:"regions",channel_id:"signal",metric:"mean_corrected"})).toBe("Imported nuclei · Signal · 平均（背景補正） · a.u.");
});
it("requires an explicit v2 choice and uses design-appropriate tests and independent omnibus",()=>{
 expect(comparisonMethod("legacy","independent",3)).toBeNull();
 expect(comparisonMethod("parametric","independent",2)).toEqual({version:"2.0.0",test:"welch-t",omnibus:null});
 expect(comparisonMethod("parametric","independent",3)?.omnibus).toBe("welch-anova");
 expect(comparisonMethod("rank","independent",3)).toEqual({version:"2.0.0",test:"mann-whitney-u",omnibus:"kruskal-wallis"});
 expect(comparisonMethod("rank","paired",3)).toEqual({version:"2.0.0",test:"wilcoxon",omnibus:null});
 expect(comparisonMethod("parametric","paired",2)?.test).toBe("paired-t");
 const base={version:"1.0.0",design:{kind:"independent"},conditions:["a","b"],plot:{x_label:"Treatments",y_label:"Signal",width_inches:6,font_size:8}} as RegionComparisonRequest;
 expect(commonComparisonRequest(base,"legacy","box",15)).toBe(base);
 expect(commonComparisonRequest(base,"rank","histogram",15)).toMatchObject({version:"2.0.0",test:"mann-whitney-u",plot:{...base.plot,kind:"histogram",histogram_bins:15}});
});
it("routes saved jobs using their stored version rather than the current UI choice",()=>{
 const base={id:"job",revision_id:"r",kind:"statistics",state:"succeeded",created:1,error:null,attempts:1,analysis_mode:"region-experimental-unit"} as Job;
 expect(commonResultPath(base)).toBe("/v1/jobs/job/region-comparison");
 expect(commonResultPath({...base,analysis_version:"2.0.0"})).toBe("/v1/jobs/job/common-statistics");
 const association={...base,analysis_mode:"region-association" as const,analysis_version:"1.0.0"};
 expect(commonResultPath(association)).toBe("/v1/jobs/job/common-statistics");
 expect(associationJobs([base,association]).length).toBe(1);
});
it("gates unmatched metrics, missing metadata, sampling and explicit pooling without guessing independence",()=>{
 const x={source:"region" as const,region_set_id:"r",channel_id:"a",metric:"mean"};const y={...x,channel_id:"b"};
 const field={id:"f",metadata:{condition:"A",sample:"s",experimental_unit:"u",acquisition_date:"batch",pair:null,repeat_length:null}} as RegionField;
 const valid={x,y,conditions:["A"],fields:[field],unitDefinition:"Independent cultures",independence:true,acquisition:true,sampling:false,missingness:true,scope:"per-condition" as const,pooling:false};
 expect(associationIssues(valid)).toEqual([]);
 expect(associationIssues({...valid,y:x})).toContain("横軸と縦軸には異なる測定値を指定してください。");
 expect(associationIssues({...valid,y:{...y,region_set_id:"other"}})).toContain("横軸と縦軸には同じ領域の測定値が必要です。");
 expect(associationIssues({...valid,scope:"pooled"})).toHaveLength(1);
 expect(associationIssues({...valid,scope:"pooled",pooling:true})).toEqual([]);
 expect(associationIssues({...valid,y:{...y,metric:"integrated"}})).toContain("画素の大きさと空間サンプリングを確認してください。");
 expect(associationIssues({...valid,independence:false})).toHaveLength(1);
 expect(associationIssues({...valid,fields:[{...field,metadata:{...field.metadata,experimental_unit:null}}]})).toHaveLength(1);
});
