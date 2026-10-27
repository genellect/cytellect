import {descriptiveSupported} from "../../../lib/workspace/comparison-adapter";
import {describe,it,expect} from "vitest";
import {associationAxes,associationSupported,checkedPlot,saturatedGroups,emptyMetadata,numericFigureFiles,restoredMetric,resultRequest,resultSeries,runTable,seriesOrder,withMaskCorrections,type ResultDesign} from "./connected-results-model";

const design:ResultDesign={operation:"comparison",metric:"mean",channel:"gfp",regionSet:"nuclei",paired:false,rank:false,unit:"independent cultures",pairing:"",confirmed:true,contrasts:[["A","B"]],xMetric:"area_px",xChannel:null};
const fields={f1:{...emptyMetadata,condition:"A",sample:"s1",experimental_unit:"u1",acquisition_date:"day1"},f2:{...emptyMetadata,condition:"B",sample:"s2",experimental_unit:"u2",acquisition_date:"day1"}};
const plot=checkedPlot(178,100,7,"","","","");
describe("connected result contracts",()=>{
  it("restores no metric from a proposal that named none, so the selector keeps its own",()=>{
    // A descriptive proposal with metrics: [] saves statistics without a metric (the AI asked for channels first).
    expect(restoredMetric({})).toBeNull();
    expect(restoredMetric({metric:null})).toBeNull();
    expect(restoredMetric({metric:"mean"})).toBe("mean");
    expect(restoredMetric({metric:"ncl_log2_nucleoplasm_over_nucleoli"})).toBe("log2_nucleoplasm_over_nucleolus");
  });
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
  it("figure series and order list exactly the compared groups",()=>{
    const three={...fields,f3:{...emptyMetadata,condition:"C",sample:"s3",experimental_unit:"u3",acquisition_date:"day1"}};
    const conditions=["A","B","C"];
    const series=resultSeries("comparison",["f1","f2","f3"],conditions,[["B","A"]]);
    expect(series).toEqual(["A","B"]);
    // A reordered or restored order that names an uncompared group never reaches the request.
    expect(seriesOrder(["C","B","A"],series)).toEqual(["B","A"]);
    expect(seriesOrder([],series)).toEqual([]);
    expect(seriesOrder(["B"],series)).toEqual(["B","A"]);
    const request=resultRequest({...design,contrasts:[["A","B"]]},three,{...plot,group_order:seriesOrder(["C","B","A"],series)}) as {conditions:string[];plot:{group_order:string[]}};
    expect(new Set(request.plot.group_order)).toEqual(new Set(request.conditions));
    expect(resultSeries("association",["f1"],conditions,[["A","B"]])).toEqual(conditions);
    expect(resultSeries("distribution",["f1","f2"],conditions,[["A","B"]])).toEqual(["f1","f2"]);
  });
  it("rejects invalid axis ranges and preserves explicit negative bounds",()=>{
    expect(()=>checkedPlot(178,100,7,"","","10","1")).toThrow();
    expect(checkedPlot(178,100,7,"Field","Intensity","-10","20")).toMatchObject({y_min:-10,y_max:20,x_label:"Field",y_label:"Intensity"});
  });
});

describe("association choices", () => {
  it("offers an association only for region measurements, never for per-nucleus nucleolar summaries", () => {
    expect(associationSupported({regionSet:"nuclei",metric:"mean",channel:"npm1",gfp:null})).toBe(true);
    expect(associationSupported({regionSet:"nuclei",metric:"area_px",channel:null,gfp:null})).toBe(true);
    expect(associationSupported({regionSet:"nuclei",metric:"nucleolar_count",channel:null,gfp:null})).toBe(false);
    expect(associationSupported({regionSet:"nuclei",metric:"log2_nucleoplasm_over_nucleolus",channel:"npm1",gfp:null})).toBe(false);
  });
  it("never offers the vertical measurement as the horizontal axis", () => {
    expect(associationAxes("area_px",null,"npm1")).toEqual(["mean","median","integrated"]);
    expect(associationAxes("mean","npm1","npm1")).toEqual(["area_px","median","integrated"]);
    expect(associationAxes("mean","npm1","hoechst")).toEqual(["area_px","mean","median","integrated"]);
  });
});

describe("saturated signal", () => {
  const row = (region_id: number, channel_id: string, saturation: number) => ({region_id, channel_id, area_px: 1, area_um2: null, mean: 1, median: 1, integrated: 1, storage_limit_fraction: 0, acquisition_saturation_fraction: saturation});
  const source = (field: string, rows: ReturnType<typeof row>[], excluded: number[] = []) => ({field, result: {rows, exclusions: excluded.map(region_id => ({region_id}))}});
  const fields = {a: {condition: "A"}, b: {condition: "B "}, c: {condition: "C"}};
  it("names the groups whose adopted regions are saturated in that channel", () => {
    const sources = [source("a", [row(1, "npm1", 0)]), source("b", [row(1, "hoechst", 0.02)]), source("c", [row(1, "hoechst", 0)])];
    expect([...saturatedGroups(sources, fields, "mean", "hoechst")]).toEqual(["B"]);
    expect([...saturatedGroups(sources, fields, "mean", "npm1")]).toEqual([]);
  });
  it("ignores excluded regions, areas, per-nucleus counts and fields without a group", () => {
    expect(saturatedGroups([source("a", [row(1, "hoechst", 0.02)], [1])], fields, "mean", "hoechst").size).toBe(0);
    expect(saturatedGroups([source("a", [row(1, "hoechst", 0.02)])], fields, "area_px", "hoechst").size).toBe(0);
    expect(saturatedGroups([source("a", [row(1, "hoechst", 0.02)])], fields, "nucleolar_count", null).size).toBe(0);
    expect(saturatedGroups([source("x", [row(1, "hoechst", 0.02)])], fields, "mean", "hoechst").size).toBe(0);
  });
});

describe("run table", () => {
  it("lays saved field medians out by run and group, control first, without combining them", () => {
    const design = {groups:[{id:"t",label:"ActD"},{id:"c",label:"Untreated"}], control_group_id:"c",
      runs:[{id:"r1",label:"Rep1"},{id:"r2",label:"Rep2"},{id:"r3",label:"Rep3"}],
      fields:{a:{group_id:"c",run_id:"r1"},b:{group_id:"c",run_id:"r1"},d:{group_id:"t",run_id:"r1"},e:{group_id:"t",run_id:"r2"}}};
    const table = runTable(design, [{field_id:"a",median:10},{field_id:"b",median:12},{field_id:"d",median:2},{field_id:"e",median:null},{field_id:"x",median:5}]);
    expect(table!.groups.map(group => group.label)).toEqual(["Untreated", "ActD"]);
    expect(table!.runs).toEqual([{id:"r1",label:"Rep1",cells:[[10,12],[2]]},{id:"r2",label:"Rep2",cells:[[],[null]]}]);
    expect(runTable({...design, groups:[design.groups[0]]}, [])).toBeNull();
  });
});


describe("one-group summary distributions", () => {
  it.each([
    ["nucleus_count", "field-summary", "1.0.0"],
    ["nucleus_density_per_mm2", "field-summary", "1.0.0"],
    ["nucleolar_area_px", "compartment-summary", "1.1.0"],
    ["nucleolar_area_um2", "compartment-summary", "1.1.0"],
    ["nucleolar_eccentricity", "compartment-summary", "1.1.0"],
  ])("keeps %s descriptive with unknown independence and one field", (metric, source, version) => {
    expect(descriptiveSupported(metric)).toBe(true);
    const result = resultRequest({...design, operation:"distribution", metric, confirmed:false,
      channel:null, regionSet:source === "field-summary" ? "nuclei" : "nucleoplasm"}, {f1:emptyMetadata}, plot);
    expect(result).toMatchObject({mode:"descriptive", group_by:"field", selection:{source, version, metric},
      figure_policy:{version:"2.0.0", layout:"field-pages"}});
    expect(result).not.toHaveProperty("design");
    expect(result).not.toHaveProperty("test");
    expect(result).not.toHaveProperty("conditions");
  });
  it("does not enable unconnected positivity", () => {
    expect(descriptiveSupported("positive_count")).toBe(false);
    expect(descriptiveSupported("positive_fraction")).toBe(false);
  });
});

describe("saved mask-correction counts",()=>{
  it("adds the recorded hand edits beside exclusions and leaves unrecorded history empty",()=>{
    const rows=[{field_id:"a",input_rows:349,excluded:0},{field_id:"b",input_rows:242,excluded:0},{field_id:"c",input_rows:5,excluded:1}];
    const edited={field_id:"a",status:"recorded" as const,initial_regions:350,deleted_regions:1,added_regions:0,redrawn_regions:0,split_regions:0,merged_regions:0};
    const unrecorded={...edited,field_id:"c",status:"not_recorded" as const,initial_regions:null,deleted_regions:0};
    const merged=withMaskCorrections(rows,{fields:[edited,unrecorded]});
    expect(merged[0]).toEqual({field_id:"a",input_rows:349,excluded:0,initial_regions:350,deleted_regions:1,added_regions:0,redrawn_regions:0,split_regions:0,merged_regions:0});
    expect(merged[1]).toEqual(rows[1]);
    expect(merged[2]).toMatchObject({excluded:1,initial_regions:null,deleted_regions:null});
    expect(withMaskCorrections(rows,undefined)).toBe(rows);
  });
});
