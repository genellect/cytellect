import { describe, expect, it } from "vitest";
import { signalQualityItems } from "./signal-quality";
import type { Cell } from "./types";

const row:Cell={field_id:"f",nucleus_id:1,condition:"synthetic",excluded:false,gfp_positive:true,signal_qc_protocol_version:"1.0.0"};
describe("server-authored native signal diagnostics",()=>{
 it("shows positive weak signals without recalculating or changing selection",()=>{
  const cell={...row,gfp_signal_to_background:0.5,gfp_weak_signal:true,gfp_signal_qc_reason:"below_threshold"};
  expect(signalQualityItems(cell).find(item=>item.prefix==="gfp")).toEqual({prefix:"gfp",label:"GFP 核内",value:"0.5",weak:true,reason:"弱い信号・要確認"});
  expect(cell.gfp_positive).toBe(true);expect(cell.excluded).toBe(false);
 });
 it("retains explicit missing-background and empty-compartment reasons",()=>{
  const items=signalQualityItems({...row,gfp_signal_to_background:null,gfp_signal_qc_reason:"background_dispersion_zero",ncl_nucleoli_signal_to_background:null,ncl_nucleoli_signal_qc_reason:"compartment_empty"});
  expect(items.find(item=>item.prefix==="gfp")).toMatchObject({value:"—",weak:false,reason:"背景のばらつきが0"});
  expect(items.find(item=>item.prefix==="ncl_nucleoli")).toMatchObject({value:"—",reason:"領域なし"});
 });
 it("does not label an unset threshold or old report as passed",()=>{
  const cell={...row,gfp_signal_to_background:-0.5,gfp_weak_signal:null,gfp_signal_qc_reason:"threshold_not_set"};
  expect(signalQualityItems(cell).find(item=>item.prefix==="gfp")).toMatchObject({value:"-0.5",weak:false,reason:"閾値未設定"});
  expect(signalQualityItems({...row,signal_qc_protocol_version:null})).toEqual([]);
 });
});
