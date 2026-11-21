import {describe,expect,it} from "vitest";
import {emptyDesign,withAcquisition,type ExperimentDesign} from "../../../lib/workspace/experiment-design";
import {declarations,remainingWork} from "./statistics-readiness";

// genellect/cytellect#257 decision 11 (owner, 2026-11-21): 統計 has no confirmations; what a request states is read from
// the adoption in 画像 and the declarations in 実験, and the one piece of earlier work left is named at the result.
const pair=(change:Partial<ExperimentDesign>={}):ExperimentDesign=>({...emptyDesign("pair"),...change} as ExperimentDesign);

describe("statistics declarations",()=>{
  it("reads acquisition, pixel settings and independence from 実験 only",()=>{
    expect(declarations({demo:false,experiment:pair(),unmeasured:0})).toEqual({regions:true,independence:false,acquisition:false,sampling:false,missingness:true});
    expect(declarations({demo:false,experiment:withAcquisition(pair({independence_confirmed:true}),true),unmeasured:0}))
      .toEqual({regions:true,independence:true,acquisition:true,sampling:true,missingness:true});
    // A workspace without a declared design states nothing: no acquisition, no independence.
    expect(declarations({demo:false,experiment:null,unmeasured:0})).toMatchObject({acquisition:false,sampling:false,independence:false});
  });
  it("takes the regions and fields from 画像: every included field measured and adopted",()=>{
    expect(declarations({demo:false,experiment:pair(),unmeasured:3}).regions).toBe(false);
    expect(declarations({demo:false,experiment:pair(),unmeasured:0}).regions).toBe(true);
  });
  it("keeps the demo's recorded confirmations and never adds independence to public data",()=>{
    expect(declarations({demo:true,experiment:pair(),unmeasured:0})).toEqual({regions:true,independence:false,acquisition:true,sampling:true,missingness:true});
  });
});

describe("remaining work",()=>{
  const declared=withAcquisition(pair({independence_confirmed:true}),true);
  it("names the one item left, in the order of the screens, as 画面：項目 値",()=>{
    expect(remainingWork({demo:false,experiment:pair(),unmeasured:3,operation:"comparison"})).toEqual({screen:"experiment",label:"実験：撮影条件 未確認"});
    expect(remainingWork({demo:false,experiment:declared,unmeasured:3,operation:"comparison"})).toEqual({screen:"image",label:"画像：未測定 3 視野"});
    expect(remainingWork({demo:false,experiment:declared,unmeasured:0,operation:"comparison"})).toBeNull();
  });
  it("asks for the acquisition statement for associations too, and only measurements for a description",()=>{
    expect(remainingWork({demo:false,experiment:pair(),unmeasured:0,operation:"association"})?.label).toBe("実験：撮影条件 未確認");
    expect(remainingWork({demo:false,experiment:pair(),unmeasured:0,operation:"distribution"})).toBeNull();
    expect(remainingWork({demo:false,experiment:null,unmeasured:2,operation:"distribution"})).toEqual({screen:"image",label:"画像：未測定 2 視野"});
  });
  it("does not compare a workspace without a declared design: it points to 実験 (an owner question)",()=>{
    expect(remainingWork({demo:false,experiment:null,unmeasured:0,operation:"comparison"})).toEqual({screen:"experiment",label:"実験：実験デザイン 未宣言"});
  });
  it("does not depend on independence: an unconfirmed design is described, never sent to 実験 first (E-05)",()=>{
    expect(remainingWork({demo:false,experiment:withAcquisition(pair(),true),unmeasured:0,operation:"comparison"})).toBeNull();
  });
  it("never asks the demo's visitor for anything (decision 2)",()=>{
    expect(remainingWork({demo:true,experiment:pair(),unmeasured:4,operation:"comparison"})).toBeNull();
    expect(remainingWork({demo:true,experiment:null,unmeasured:0,operation:"association"})).toBeNull();
  });
});
