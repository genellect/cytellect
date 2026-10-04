import {describe,expect,it} from "vitest";
import {comparisonReadiness,type ComparisonReadinessInput} from "./region-comparison-readiness";
import type {RegionMetadata} from "./region-types";

const metadata=(values:Partial<RegionMetadata>={}):RegionMetadata=>({condition:"A",sample:"sample",experimental_unit:"unit",acquisition_date:"batch",pair:null,repeat_length:null,...values});
const ready=(values:Partial<ComparisonReadinessInput>={}):ComparisonReadinessInput=>({blocked:false,submitting:false,dirty:false,metadataDirty:false,hasRevision:true,reviewed:true,hasMetric:true,metric:"mean_corrected",design:"independent",unitDefinition:"Separately assigned experimental units",pairingBasis:"",designConfirmed:true,conditions:["A","B"],familyKind:"control",control:"A",contrasts:[["A","B"]],fields:[{id:"f1",metadata:metadata()},{id:"f2",metadata:metadata({condition:"B"})}],acquisitionConfirmed:true,samplingConfirmed:false,missingnessConfirmed:true,...values});

describe("comparison readiness uses recorded choices, not inferred scientific validity",()=>{
 it("identifies the unused third condition without changing scope or contrasts",()=>{
  const state=ready({conditions:["A","B","C"],familyKind:"planned"});const copy=structuredClone(state);
  expect(comparisonReadiness(state)).toEqual([{id:"unused-conditions",message:"「C」を使う比較がありません。対象条件か比較の組み合わせを見直してください。",target:"contrasts",action:"比較の組み合わせへ"}]);
  expect(state).toEqual(copy);
  expect(comparisonReadiness({...state,contrasts:[["A","B"],["B","C"]]})).toEqual([]);
  expect(comparisonReadiness({...state,conditions:["A","B"]})).toEqual([]);
 });
 it("distinguishes missing and stale control instead of silently replacing it",()=>{
  expect(comparisonReadiness(ready({control:"",contrasts:[["","A"],["","B"]]})).map(issue=>issue.id)).toEqual(["control-required"]);
  const stale=comparisonReadiness(ready({conditions:["B","C"],control:"A",contrasts:[["A","B"],["A","C"]]}));
  expect(stale).toEqual([{id:"control-outside-scope",message:"対照群「A」が比較対象から外れています。対照群と対象条件を確認してください。",target:"control",action:"対照群を確認する"}]);
 });
 it("explains one condition and the cleared planned comparisons independently",()=>{
  expect(comparisonReadiness(ready({conditions:["A"],familyKind:"planned",contrasts:[]})).map(issue=>issue.id)).toEqual(["conditions-required","contrasts-required"]);
 });
 it("names each missing recorded field and its first exact control",()=>{
  const issues=comparisonReadiness(ready({design:"paired",pairingBasis:"Recorded matching",fieldLabels:{unknown:"視野 2",selected:"視野 3"},fields:[
   {id:"unknown",metadata:metadata({condition:null})},
   {id:"selected",metadata:metadata({sample:null,experimental_unit:null,pair:null,acquisition_date:null})},
   {id:"outside",metadata:metadata({condition:"C",sample:null,experimental_unit:null})},
  ]}));
  expect(issues).toEqual([
   {id:"metadata-unknown",message:"視野 2：条件が未記録です。",fieldId:"unknown",metadataKey:"condition",action:"視野 2 の条件へ"},
   {id:"metadata-selected",message:"視野 3：試料・独立実験単位・対応ペア・撮影日／バッチが未記録です。",fieldId:"selected",metadataKey:"sample",action:"視野 3 の試料へ"},
  ]);
 });
 it("does not invent an ordinal when the original field label is unavailable",()=>{
  const issues=comparisonReadiness(ready({fields:[{id:"later-field",metadata:metadata({condition:null})}]}));
  expect(issues[0]).toMatchObject({fieldId:"later-field",message:"保存済みの視野：条件が未記録です。",action:"保存済みの視野 の条件へ"});
 });
 it("keeps batch mandatory for intensity and does not invent it for area",()=>{
  const fields=[{id:"field",metadata:metadata({acquisition_date:null})}];
  expect(comparisonReadiness(ready({fields}))[0]).toMatchObject({fieldId:"field",metadataKey:"acquisition_date"});
  expect(comparisonReadiness(ready({fields,metric:"area_um2"}))).toEqual([]);
  expect(comparisonReadiness(ready({fields,metric:"area_px"})).map(issue=>issue.id)).toEqual(["sampling-confirmation"]);
 });
 it("retains explicit independent, acquisition, selection and sampling acknowledgements",()=>{
  expect(comparisonReadiness(ready({metric:"integrated_corrected",designConfirmed:false,acquisitionConfirmed:false,missingnessConfirmed:false})).map(issue=>issue.target)).toEqual(["design-confirmed","acquisition","sampling","missingness"]);
  expect(comparisonReadiness(ready({design:"paired",pairingBasis:"  "})).some(issue=>issue.target==="pairing-basis")).toBe(true);
 });
 it("separates unsaved metadata from old saved gaps and never calls the draft reviewed",()=>{
  expect(comparisonReadiness(ready({metadataDirty:true,fields:[{id:"field",metadata:metadata({condition:null})}]})).map(issue=>issue.id)).toEqual(["metadata-draft"]);
  expect(comparisonReadiness(ready({reviewed:false})).map(issue=>issue.id)).toEqual(["review-required"]);
  expect(comparisonReadiness(ready({dirty:true})).map(issue=>issue.id)).toEqual(["measurement-draft"]);
 });
 it("reports unavailable metric and unchosen design without choosing replacements",()=>{
  expect(comparisonReadiness(ready({hasMetric:false,design:"",unitDefinition:" "})).map(issue=>issue.id)).toEqual(["metric-required","design-required","unit-definition-required"]);
 });
 it("treats processing and submission as waiting, not missing experimental confirmations",()=>{
  expect(comparisonReadiness(ready({blocked:true,designConfirmed:false}))).toEqual([{id:"processing",message:"作業中の処理が完了すると比較できます。"}]);
  expect(comparisonReadiness(ready({submitting:true,blocked:true}))).toEqual([{id:"submitting",message:"比較を受け付けています。"}]);
 });
 it("does not calculate or claim valid effective replication from form metadata",()=>{
  // Zero observations, incomplete pairs, repeated units and batch confounding
  // remain backend decisions; a complete form does not assert acceptance.
  expect(comparisonReadiness(ready())).toEqual([]);
 });
});
