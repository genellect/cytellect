import {describe,expect,it} from "vitest";
import {emptyBatchMetadata} from "./region-batch";
import {applyCommonMetadata,planCommonMetadata,undoCommonMetadata} from "./batch-common-metadata";

const rows={
 f01:{...emptyBatchMetadata,condition:"A",sample:"A1-s1",experimental_unit:"U-A1",pair:"P1"},
 f02:{...emptyBatchMetadata,condition:"B",sample:"B2-s1",experimental_unit:"U-B2",pair:"P2"},
};

describe("explicit common metadata edits",()=>{
 it("fills only the entered acquisition column without losing distinct row identities",()=>{
  const plan=planCommonMetadata(rows,["f01","f02"],{...emptyBatchMetadata,acquisition_date:" batch-1 "});
  expect(plan.columns).toEqual([{key:"acquisition_date",label:"撮影日／バッチ",value:"batch-1",empty:2,replace:0,unchanged:0}]);
  const next=applyCommonMetadata(rows,plan);
  expect(next).toEqual({f01:{...rows.f01,acquisition_date:"batch-1"},f02:{...rows.f02,acquisition_date:"batch-1"}});
  expect(rows.f01.acquisition_date).toBe("");
 });
 it("ignores blank or whitespace common values and treats zero as explicitly entered",()=>{
  const plan=planCommonMetadata(rows,["f01"],{...emptyBatchMetadata,condition:" \t",repeat_length:"0"});
  expect(plan.changes).toEqual([{row:"f01",column:"repeat_length",before:"",after:"0"}]);
  expect(planCommonMetadata(rows,["f01"],emptyBatchMetadata).changes).toEqual([]);
 });
 it("reports exact replacement and fill counts before a separate application",()=>{
  const current={...rows,f03:{...emptyBatchMetadata,condition:"A"},f04:{...emptyBatchMetadata}};
  const plan=planCommonMetadata(current,["f01","f02","f03","f04"],{...emptyBatchMetadata,condition:"A",acquisition_date:"batch-1"});
  expect(plan.columns).toEqual([
   {key:"condition",label:"条件",value:"A",empty:1,replace:1,unchanged:2},
   {key:"acquisition_date",label:"撮影日／バッチ",value:"batch-1",empty:4,replace:0,unchanged:0},
  ]);
  expect(current.f02.condition).toBe("B");
  expect(applyCommonMetadata(current,plan).f02).toEqual({...rows.f02,condition:"A",acquisition_date:"batch-1"});
 });
 it("rejects stale previews without partially applying any column",()=>{
  const plan=planCommonMetadata(rows,["f01","f02"],{...emptyBatchMetadata,condition:"C",acquisition_date:"batch-1"});
  const changed={...rows,f02:{...rows.f02,condition:"D"}};
  expect(()=>applyCommonMetadata(changed,plan)).toThrow("common_metadata_preview_changed");
  expect(changed.f01).toEqual(rows.f01);expect(changed.f02.acquisition_date).toBe("");
 });
 it("undoes only that application while keeping later manual changes and new rows",()=>{
  const plan=planCommonMetadata(rows,["f01","f02"],{...emptyBatchMetadata,condition:"C",acquisition_date:"batch-1"});
  const applied=applyCommonMetadata(rows,plan);
  const later={...applied,f01:{...applied.f01,sample:"manually corrected"},f02:{...applied.f02,acquisition_date:"batch-2"},f03:{...emptyBatchMetadata,condition:"new",experimental_unit:"new-unit"}};
  const undone=undoCommonMetadata(later,plan.changes);
  expect(undone.metadata).toEqual({f01:{...rows.f01,sample:"manually corrected"},f02:{...rows.f02,acquisition_date:"batch-2"},f03:later.f03});
  expect(undone.restored).toBe(3);expect(undone.kept).toBe(1);
  expect(later.f01.condition).toBe("C");
 });
 it("preserves unmapped rows and gives a new mapped row only explicitly entered values",()=>{
  const plan=planCommonMetadata(rows,["f01","f03"],{...emptyBatchMetadata,acquisition_date:"batch-1"});
  const next=applyCommonMetadata(rows,plan);
  expect(next.f02).toBe(rows.f02);expect(next.f03).toEqual({...emptyBatchMetadata,acquisition_date:"batch-1"});
  const undone=undoCommonMetadata(next,plan.changes).metadata;
  expect(undone.f01).toEqual(rows.f01);expect(undone.f03).toEqual(emptyBatchMetadata);
 });
});
