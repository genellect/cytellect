import {describe,expect,it} from "vitest";
import type {NucleusTableData} from "@/lib/workspace/api-adapter";
import {nucleusTableView} from "./nucleus-table-model";

const values=(channel_id:string,role:"nuclear_stain"|"measure",mean:number,integrated:number,corrected:number|null,saturation=0)=>({
  channel_id,role,mean,integrated,mean_corrected:corrected,integrated_corrected:corrected===null?null:corrected*4,
  intensity_missing_reason:null,correction_missing_reason:corrected===null?"background_not_established":null,
  storage_limit_fraction:0,acquisition_saturation_fraction:saturation,acquisition_saturation_missing_reason:null});
const measured={status:"measured" as const,reason:null,count:2,union_area_px:5,union_area_um2:1.25,area_fraction:0.2,
  largest_object_area_px:4,largest_object_fraction:0.8,eccentricity:0.5,eccentricity_missing_reason:null};
const missing=(reason:string)=>({status:"missing" as const,reason,count:null,union_area_px:null,union_area_um2:null,area_fraction:null,
  largest_object_area_px:null,largest_object_fraction:null,eccentricity:null,eccentricity_missing_reason:null});
const row=(nucleus_id:number,nucleoli:NucleusTableData["rows"][number]["nucleoli"],extra:Partial<NucleusTableData["rows"][number]>={})=>({
  nucleus_id,excluded:false,exclusion_reason:null,touches_border:false,nucleus_area_px:25,nucleus_area_um2:6.25,area_missing_reason:null,
  channels:[values("dna","nuclear_stain",100,2500,null),values("npm1","measure",40.25,1006,30,nucleus_id===2?0.01:0)],nucleoli,...extra});
const table:NucleusTableData={protocol:"nucleus-table/1.0.0",field_id:"f1",nuclear_revision_id:"n",nuclear_mask_revision_id:"n",nuclear_mask_sha256:"a".repeat(64),
  measurement_protocol_version:"4.0.0",nuclear_channel_id:"dna",nucleolar_source:{revision_id:"c",mask_revision_id:"c",mask_sha256:"b".repeat(64)},
  calibration:{pixel_size_x_um:0.5,pixel_size_y_um:0.5,confirmed:true},field_excluded:false,
  rows:[row(1,measured),row(2,missing("no_candidate")),row(3,{...missing("nucleus_excluded"),status:"not_measured"},{excluded:true,exclusion_reason:"mitotic"})]};
const channels=[{id:"dna",stain:"Hoechst"},{id:"npm1",stain:"NPM1"}];

describe("nucleus table view",()=>{
  it("shows each stain by name, the nuclear stain as integrated signal, and corrected values only where measured",()=>{
    const view=nucleusTableView(table,channels);
    expect(view.columns.map(column=>column.label)).toEqual(["核","核面積 / µm²","Hoechst 積算","NPM1 平均","NPM1 平均（背景補正）",
      "核小体数","核小体の面積 / 核","最大の核小体 / 核小体全体","離心率","状態"]);
    expect(view.rows[0].cells.map(cell=>cell.text)).toEqual(["6.3","2,500","40.3","30.0","2","20.0%","80.0%","0.500",""]);
  });
  it("keeps a nucleus without an adopted nucleolus missing with its reason, never zero, and accounts for every nucleus",()=>{
    const view=nucleusTableView(table,channels);
    const second=view.rows[1].cells;
    expect(second.slice(4,8).map(cell=>cell.text)).toEqual(["—","—","—","—"]);
    expect(second[4].title).toBe("核小体の候補なし");
    expect(second[8].text).toBe("核小体の候補なし");
    expect(view.rows[2].cells.at(-1)?.text).toBe("除外：mitotic");
    expect(view.ledger).toBe("核 3 個 · 除外 1 · 核小体を確定 1 · 欠測 1（核小体の候補なし 1） · NPM1の飽和画素を含む核 1");
  });
  it("invites nucleolar analysis when only nuclei are adopted, and uses pixels without a confirmed calibration",()=>{
    const view=nucleusTableView({...table,nucleolar_source:null,calibration:null,rows:[row(1,{...missing("nucleolar_revision_not_selected"),status:"not_measured"})]},channels);
    expect(view.columns.map(column=>column.label)).toEqual(["核","核面積 / px²","Hoechst 積算","NPM1 平均","NPM1 平均（背景補正）","状態"]);
    expect(view.rows[0].cells[0].text).toBe("25");
    expect(view.ledger).toBe("核 1 個 · 核小体を解析すると、核ごとの核小体の値が加わります");
  });
});
