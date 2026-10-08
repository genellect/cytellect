import {describe,it,expect} from "vitest";
import {checkedPlot,emptyMetadata,numericFigureFiles,resultRequest,type ResultDesign} from "./connected-results-model";

const design:ResultDesign={operation:"comparison",metric:"mean",channel:"gfp",regionSet:"nuclei",paired:false,rank:false,unit:"independent cultures",pairing:"",confirmed:true,contrasts:[["A","B"]],xMetric:"area_px",xChannel:null};
const fields={f1:{...emptyMetadata,condition:"A",sample:"s1",experimental_unit:"u1",acquisition_date:"day1"},f2:{...emptyMetadata,condition:"B",sample:"s2",experimental_unit:"u2",acquisition_date:"day1"}};
const plot=checkedPlot(178,100,7,"","","","");
describe("connected result contracts",()=>{
  it("uses only declared numeric formats for the original renderer manifest",()=>{
    expect(numericFigureFiles({source_files:["data.csv","figure.svg"],formats:["svg","pdf","png","html"]})).toEqual(["data.csv","figure.svg","figure.pdf","figure.png"]);
    expect(numericFigureFiles({source_files:["data.csv"]})).toEqual(["data.csv"]);
  });
  it("uses selected raw metric and declared contrasts without changing observation units",()=>{
    const result=resultRequest(design,fields,plot);
    expect(result).toMatchObject({mode:"region-experimental-unit",test:"welch-t",selection:{source:"region",metric:"mean",channel_id:"gfp"},aggregation:"field-median_sample-mean_unit-mean-v1",comparison_family:{contrasts:[["A","B"]]}});
  });
  it("carries an explicit GFP nucleus filter into actual selection",()=>{
    expect(resultRequest({...design,gfp:{channel:"gfp",controls:["f1"]}},fields,plot)).toMatchObject({selection:{gfp_gate:{gfp_channel_id:"gfp",control_field_ids:["f1"],percentile:99}}});
    expect(()=>resultRequest({...design,gfp:{channel:"gfp",controls:[]}},fields,plot)).toThrow();
  });
  it("carries the same GFP selection into both association axes",()=>{
    const result=resultRequest({...design,operation:"association",gfp:{channel:"gfp",controls:["f1"]}},fields,plot);
    expect(result).toMatchObject({version:"1.1.0",x_selection:{gfp_gate:{control_field_ids:["f1"]}},y_selection:{gfp_gate:{control_field_ids:["f1"]}}});
  });
  it("preserves exploratory GFP method, threshold and corrected-value selection",()=>{
    const filter={version:"1.1.0" as const,gate_protocol:"gfp-gate/3.0.0" as const,gfp_channel_id:"gfp",method:"manual" as const,threshold:-2,values:"corrected" as const,keep:"negative" as const};
    expect(resultRequest({...design,gfp:filter},fields,plot)).toMatchObject({selection:{gfp_gate:filter}});
    expect(resultRequest({...design,operation:"distribution",gfp:{...filter,method:"batch_otsu",threshold:null}},fields,plot)).toMatchObject({selection:{gfp_gate:{method:"batch_otsu",threshold:null,values:"corrected"}}});
  });
  it("associations retain selected axes and condition scope",()=>{
    expect(resultRequest({...design,operation:"association",rank:true},fields,plot)).toMatchObject({mode:"region-association",method:"spearman",scope:"per-condition",x_selection:{metric:"area_px",channel_id:null},y_selection:{metric:"mean",channel_id:"gfp"},plot:{kind:"scatter"}});
  });
  it("blocks unconfirmed design and missing experimental metadata",()=>{
    expect(()=>resultRequest({...design,confirmed:false},fields,plot)).toThrow();
    expect(()=>resultRequest(design,{...fields,f1:{...fields.f1,experimental_unit:null}},plot)).toThrow();
  });
  it("distribution needs no fabricated experiment metadata",()=>{
    expect(resultRequest({...design,operation:"distribution",confirmed:false},{f1:emptyMetadata},plot)).toMatchObject({mode:"descriptive",group_by:"field",selection:{metric:"mean",channel_id:"gfp"}});
  });
  it("rejects invalid axis ranges and preserves explicit negative bounds",()=>{
    expect(()=>checkedPlot(178,100,7,"","","10","1")).toThrow();
    expect(checkedPlot(178,100,7,"Field","Intensity","-10","20")).toMatchObject({y_min:-10,y_max:20,x_label:"Field",y_label:"Intensity"});
  });
});
