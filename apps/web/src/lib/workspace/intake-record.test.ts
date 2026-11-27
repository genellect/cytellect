import {describe, expect, it} from "vitest";
import {missingImages, namesText, needsAttention, outcomeLine} from "./intake-record";
import type {SelectionEntry} from "./api-adapter";
import type {ExperimentDesign} from "./experiment-design";

const design = {version:"1.0.0",layout:"pair",control_group_id:"c",independence_confirmed:false,groups:[{id:"c",label:"未処理"},{id:"t",label:"ActD"}],runs:[{id:"r1",label:"Rep1"}],fields:{}} as unknown as ExperimentDesign;
const row = (id:string, value:Partial<SelectionEntry>):SelectionEntry => ({id, field_id:null, revision_id:null, exclusion_reason:null, ...value});

describe("intake record", () => {
  it("states what one addition did, and that an empty choice or a choice without TIFF did nothing", () => {
    expect(outcomeLine(null)).toBe("");
    expect(outcomeLine({registered:[{fieldId:"a",names:["a.tif"]},{fieldId:"b",names:["b.tif"]}],rejected:[{entry:"e",names:["x.tif"],code:"unsupported_or_invalid_region_image"},{entry:"m",names:["mask.tif"],code:"region_image_bit_depth_unsupported"}],held:[],duplicates:[{id:"d",name:"a copy.tif",sameAs:"a.tif"}],skipped:[{name:"readme.txt"}]}))
      .toBe("登録：2 視野 · 読み取れない：1 件 · マスクの候補：1 件 · 同一内容：1 件 · 対象外：1 件");
    // A 32-bit float image the judgement before adding found unreadable shares the mask candidate's code and is not one.
    expect(outcomeLine({registered:[{fieldId:"a",names:["a.tif"]}],rejected:[{entry:"recorded",names:["float.tif"],code:"region_image_bit_depth_unsupported",stage:"inspect"}],held:[],duplicates:[],skipped:[]}))
      .toBe("登録：1 視野 · 読み取れない：1 件");
    // 実行を中止 is a result of the addition, not an error.
    expect(outcomeLine({registered:[{fieldId:"a",names:["a.tif"]}],rejected:[],held:[],duplicates:[],skipped:[],stopped:true})).toBe("登録：1 視野 · 追加：中止");
    expect(outcomeLine({registered:[],rejected:[],held:[],duplicates:[],skipped:[],empty:"nothing"})).toBe("受け取ったファイル：0 件");
    expect(outcomeLine({registered:[],rejected:[],held:[],duplicates:[],skipped:[{name:"a.txt"}],empty:"no_images"})).toBe("TIFF：0 件 · 対象外：1 件");
    expect(needsAttention({registered:[{fieldId:"a",names:["a.tif"]}],rejected:[],held:[],duplicates:[],skipped:[{name:"a.txt"}]})).toBe(false);
    expect(needsAttention({registered:[],rejected:[],held:[{names:["a.tif","b.tif"],reason:"duplicate_channel"}],duplicates:[],skipped:[]})).toBe(true);
    expect(namesText(["a","b","c","d","e"])).toBe("a、b、c ほか 2 件");
  });
  it("counts images that never became a field by the group the researcher chose, without mask candidates or registered rows", () => {
    const entries = [
      row("field", {field_id:"f", intake:{names:["a.tif"], state:"registered"}}),
      row("broken", {intake:{names:["test-truncated-DRAQ.tif"], state:"rejected", stage:"register", code:"unsupported_or_invalid_region_image", target:{run_id:"r1", group_id:"c", sample:null}}}),
      row("lost", {intake:{names:["b.tif"], state:"pending", target:{run_id:"r1", group_id:"c", sample:null}}}),
      row("mask", {intake:{names:["mask.tif"], state:"rejected", stage:"register", code:"region_image_bit_depth_unsupported"}}),
      row("old", {}),
      row("older", {exclusion_reason:"Upload interrupted"}),
    ];
    expect(missingImages({entries}, design)).toEqual([
      {group:"未処理", run:"Rep1", reason:"不正または未対応の TIFF", count:1},
      {group:"未処理", run:"Rep1", reason:"登録未完了", count:1},
      {group:"群の指定なし", run:null, reason:"理由の記録なし", count:1},
      {group:"群の指定なし", run:null, reason:"除外の理由：Upload interrupted", count:1},
    ]);
    expect(missingImages(null, design)).toEqual([]);
  });
});
