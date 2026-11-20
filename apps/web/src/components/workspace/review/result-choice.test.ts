import {describe,expect,it} from "vitest";
import {automaticOperation,calculationNeeds,choiceFilter,conditionChannel,conditionKey,measureLabel,savedCondition,savedFor,savedMeasureLabel,sameSources,type ResultCondition,type SavedResultLike} from "./result-choice";

const npm1={channel_id:"npm1",label:"NPM1",stain:"NPM1"};
const sources=[{field:"f1",mask:"m1",protocol:"4.0.0",mode:"automatic_background"},{field:"f2",mask:"m2",protocol:"4.0.0",mode:"automatic_background"}];
// A saved result records each field's adopted regions (mask revision) and measurement; its analysis revision is the cohort's.
const fieldsOf=(masks=["m1","m2"])=>masks.map((mask,index)=>({field_id:`f${index+1}`,analysis_revision_id:"cohort",region_set:{region_set_id:"nucleoli",mask_revision_id:mask},
  measurement_protocol:"4.0.0",measurement:{mode:"automatic_background"}}));
const meanNucleoli:SavedResultLike={metric:"mean",channel:npm1,estimates:{metric:"mean"},spec:{selection:{source:"region",region_set_id:"nucleoli",metric:"mean",channel_id:"npm1"}},source_fields:fieldsOf()};
const eccentricity:SavedResultLike={estimates:{metric:"nucleolar_eccentricity"},spec:{selection:{source:"compartment-summary",region_set_id:"nucleoplasm",metric:"nucleolar_eccentricity",channel_id:null}},source_fields:fieldsOf()};
const choice=(value:Partial<ResultCondition>):ResultCondition=>({operation:"comparison",regionSet:"nucleoli",metric:"mean",channel:"npm1",filter:"",x:null,stratum:null,...value});

describe("result conditions (SR-01, SR-02)",()=>{
  it("reads the condition a saved result answers from the request it saved",()=>{
    expect(savedCondition("comparison",meanNucleoli)).toEqual(choice({}));
    // A nucleolar summary reads no stain: a stain chosen in the side panel does not make it another condition.
    expect(savedCondition("comparison",eccentricity)).toEqual(choice({regionSet:"nucleoplasm",metric:"nucleolar_eccentricity",channel:null}));
    expect(conditionChannel("nucleolar_eccentricity","npm1",null)).toBeNull();
    expect(conditionChannel("area_px","npm1",null)).toBeNull();
    expect(conditionChannel("positive_fraction",null,"eu5")).toBe("eu5");
  });
  it("tells conditions apart by analysis, region, metric, stain, nucleus filter and stratum",()=>{
    const base=conditionKey(choice({}));
    for(const other of [{operation:"distribution" as const},{regionSet:"nucleoplasm"},{metric:"median"},{channel:"eu5"},{filter:"cg:gfp:positive"},{stratum:"24 h"}])
      expect(conditionKey(choice(other))).not.toBe(base);
    expect(conditionKey(null)).toBe("");
  });
  it("names the classified channel of a positivity result and the filter of a filtered one",()=>{
    const positivity:SavedResultLike={spec:{selection:{source:"field-summary",region_set_id:"nuclei",metric:"positive_fraction",positivity:{channel_id:"eu5"}}}};
    expect(savedCondition("comparison",positivity)).toEqual(choice({regionSet:"nuclei",metric:"positive_fraction",channel:"eu5"}));
    const filtered:SavedResultLike={spec:{selection:{source:"region",region_set_id:"nuclei",metric:"area_px",channel_gate:{channel_id:"gfp",keep:"positive"}}}};
    expect(savedCondition("distribution",filtered)?.filter).toBe(choiceFilter("area_px",null,{channel_id:"gfp",keep:"positive"}));
    expect(choiceFilter("positive_fraction",null,{channel_id:"eu5",keep:"positive"})).toBe("");
    expect(choiceFilter("mean",{channel:"gfp"},null)).toBe("gfp:gfp");
    expect(choiceFilter("mean",{gfp_channel_id:"gfp"},null)).toBe(savedCondition("distribution",{spec:{selection:{region_set_id:"nuclei",metric:"mean",channel_id:"npm1",gfp_gate:{gfp_channel_id:"gfp"}}}})?.filter);
  });
  it("reads both axes of an association",()=>{
    const association:SavedResultLike={spec:{x_selection:{source:"region",region_set_id:"nuclei",metric:"area_px",channel_id:null},y_selection:{source:"region",region_set_id:"nuclei",metric:"mean",channel_id:"npm1"}}};
    expect(savedCondition("association",association)).toEqual(choice({operation:"association",regionSet:"nuclei",x:{metric:"area_px",channel:null}}));
  });
  it("does not invent a condition for a result that saved none",()=>{
    expect(savedCondition("comparison",{})).toBeNull();
  });
});

describe("saved result for the chosen condition (D-1)",()=>{
  const entries=[{job:"new-ecc",operation:"comparison" as const,result:eccentricity},{job:"old-mean",operation:"comparison" as const,result:{...meanNucleoli,source_fields:fieldsOf(["m0","m2"])}},{job:"mean",operation:"comparison" as const,result:meanNucleoli}];
  it("opens the newest result of the same condition calculated from the measurements now chosen",()=>{
    expect(savedFor(entries,choice({}),sources)).toMatchObject({current:{job:"mean"},older:{job:"old-mean"}});
  });
  it("offers an earlier measurement's result separately, never as the current one",()=>{
    expect(savedFor(entries.slice(0,2),choice({}),sources)).toEqual({current:undefined,older:entries[1]});
    expect(sameSources(fieldsOf(),[...sources,{field:"f3",mask:"m3"}])).toBe(false);
    expect(sameSources(undefined,sources)).toBe(false);
    // Redrawn outlines (a new mask revision) or another measurement protocol or mode is an earlier measurement.
    expect(sameSources(fieldsOf(["m1","m2b"]),sources)).toBe(false);
    expect(sameSources(fieldsOf(),sources.map(source=>({...source,protocol:"3.0.0"})))).toBe(false);
    expect(sameSources(fieldsOf(),sources.map(source=>({...source,mode:"raw_intensity"})))).toBe(false);
    expect(sameSources(fieldsOf(),sources.map(({field,mask})=>({field,mask})))).toBe(true);
  });
  it("reads an association's fields from its axes",()=>{
    const association:SavedResultLike={spec:{x_selection:{region_set_id:"nucleoli",metric:"area_px",channel_id:null},y_selection:{region_set_id:"nucleoli",metric:"mean",channel_id:"npm1"}},
      x_source:{source_fields:fieldsOf()},y_source:{source_fields:fieldsOf()}};
    const entry={job:"assoc",operation:"association" as const,result:association};
    expect(savedFor([entry],choice({operation:"association",x:{metric:"area_px",channel:null}}),sources).current).toBe(entry);
  });
  it("finds nothing for a condition without a result",()=>{
    expect(savedFor(entries,choice({operation:"distribution"}),sources)).toEqual({current:undefined,older:undefined});
    expect(savedFor(entries,null,sources)).toEqual({});
  });
});

describe("one name for a measure (B-3, SL-02)",()=>{
  it("names the region and the stain, not the channel identifier",()=>{
    expect(measureLabel("mean","nucleoli","5-EU")).toBe("核小体の平均輝度（5-EU）");
    expect(measureLabel("area_px","nuclei","Hoechst")).toBe("核の面積（px²）");
    expect(measureLabel("nucleolar_eccentricity","nucleoplasm","NPM1")).toBe("核小体の離心率");
    expect(measureLabel("log2_nucleoplasm_over_nucleolus","nucleoplasm","NPM1")).toBe("核質／核小体 log₂ 比（NPM1）");
    expect(measureLabel("positive_fraction","nuclei","5-EU")).toBe("陽性率（5-EU）");
    expect(measureLabel("nucleus_count","nuclei",null)).toBe("視野あたりの核数");
    expect(measureLabel("median","nuclei","Hoechst")).toBe("核の輝度の中央値（Hoechst）");
  });
  it("names a saved result by its recorded stain",()=>{
    expect(savedMeasureLabel("comparison",meanNucleoli)).toBe("核小体の平均輝度（NPM1）");
    expect(savedMeasureLabel("comparison",{...meanNucleoli,channel:{channel_id:"npm1"}})).toBe("核小体の平均輝度（npm1）");
    expect(savedMeasureLabel("comparison",{spec:{selection:{source:"field-summary",region_set_id:"nuclei",metric:"positive_fraction",positivity:{channel_id:"eu5"}}},selection:{channel_gate:{channel:{channel_id:"eu5",stain:"5-EU"}}}})).toBe("陽性率（5-EU）");
  });
});

describe("analysis changed by the view (SR-04)",()=>{
  const state={operation:"comparison" as const,canAssociate:true,unconfirmed:false,saturated:false,saturatedAny:false,descriptive:true};
  it("says why the analysis changed",()=>{
    expect(automaticOperation({...state,saturated:true,saturatedAny:true})).toEqual({operation:"distribution",reason:expect.stringContaining("飽和")});
    expect(automaticOperation({...state,operation:"association",unconfirmed:true})?.reason).toContain("独立性が未確認");
    expect(automaticOperation({...state,operation:"association",canAssociate:false})?.reason).toContain("相関を計算できない");
    expect(automaticOperation({...state,operation:"distribution",descriptive:false})).toEqual({operation:"comparison",reason:expect.stringContaining("分布を出せない")});
  });
  it("leaves an analysis the measure can have",()=>{
    expect(automaticOperation(state)).toBeNull();
    expect(automaticOperation({...state,operation:"distribution",descriptive:false,saturated:true})).toBeNull();
  });
});

describe("what the calculation still needs (SR-03)",()=>{
  const ready={stratumMissing:false,unstratified:0,sources:2,missing:0,reviewed:true,ledgerError:false,unresolvedUnconfirmed:false,designUnconfirmed:false,metadata:null,datesMissing:false,independenceMissing:false,positivityMissing:false,classificationMissing:false,unsupportedAxes:false};
  it("is empty when everything is in place",()=>{expect(calculationNeeds(ready)).toEqual([]);});
  it("names each missing confirmation and input",()=>{
    expect(calculationNeeds({...ready,reviewed:false,designUnconfirmed:true,unresolvedUnconfirmed:true,missing:2,metadata:"視野の群の入力"}))
      .toEqual(["2 視野の測定","視野の群の入力","核小体を確定できない核の一覧の確認","実験回の定義と解析条件の確認","測定領域と採用する視野の確認"]);
  });
});
