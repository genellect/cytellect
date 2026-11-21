import {describe,expect,it} from "vitest";
import {automaticOperation,sameMethod,savedMethod,choiceFilter,conditionChannel,conditionKey,measureLabel,savedCondition,savedFor,savedMeasureLabel,sameSources,type ResultCondition,type SavedResultLike} from "./result-choice";

const npm1={channel_id:"npm1",label:"NPM1",stain:"NPM1"};
const sources=[{field:"f1",mask:"m1",protocol:"4.0.0",mode:"automatic_background"},{field:"f2",mask:"m2",protocol:"4.0.0",mode:"automatic_background"}];
// A saved result records each field's adopted regions (mask revision) and measurement; its analysis revision is the cohort's.
const fieldsOf=(masks=["m1","m2"])=>masks.map((mask,index)=>({field_id:`f${index+1}`,analysis_revision_id:"cohort",region_set:{region_set_id:"nucleoli",mask_revision_id:mask},
  measurement_protocol:"4.0.0",measurement:{mode:"automatic_background"}}));
const meanNucleoli:SavedResultLike={metric:"mean",channel:npm1,estimates:{metric:"mean"},spec:{selection:{source:"region",region_set_id:"nucleoli",metric:"mean",channel_id:"npm1"}},source_fields:fieldsOf()};
const eccentricity:SavedResultLike={estimates:{metric:"nucleolar_eccentricity"},spec:{selection:{source:"compartment-summary",region_set_id:"nucleoplasm",metric:"nucleolar_eccentricity",channel_id:null}},source_fields:fieldsOf()};
const choice=(value:Partial<ResultCondition>):ResultCondition=>({operation:"comparison",regionSet:"nucleoli",metric:"mean",channel:"npm1",filter:"",x:null,stratum:null,...value});

describe("result conditions (#257 D-1, D-2)",()=>{
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

describe("saved result for the chosen condition (#257 D-1)",()=>{
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

describe("one name for a measure (#257 B-3)",()=>{
  it("names the region and the stain, not the channel identifier",()=>{
    expect(measureLabel("mean","nucleoli","5-EU")).toBe("核小体の平均輝度（5-EU）");
    expect(measureLabel("area_px","nuclei","Hoechst")).toBe("核の面積（px²）");
    expect(measureLabel("nucleolar_eccentricity","nucleoplasm","NPM1")).toBe("核小体の離心率");
    expect(measureLabel("log2_nucleoplasm_over_nucleolus","nucleoplasm","NPM1")).toBe("核質／核小体 log₂ 比（NPM1）");
    expect(measureLabel("positive_fraction","nuclei","5-EU")).toBe("陽性率（5-EU）");
    expect(measureLabel("nucleus_count","nuclei",null)).toBe("視野あたりの核数");
    expect(measureLabel("median","nuclei","Hoechst")).toBe("核の中央値（Hoechst）");
    expect(measureLabel("integrated_corrected","nucleoli","NPM1")).toBe("核小体の積算輝度（背景補正、NPM1）");
  });
  it("names a saved result by its recorded stain",()=>{
    expect(savedMeasureLabel("comparison",meanNucleoli)).toBe("核小体の平均輝度（NPM1）");
    expect(savedMeasureLabel("comparison",{...meanNucleoli,channel:{channel_id:"npm1"}})).toBe("核小体の平均輝度（npm1）");
    expect(savedMeasureLabel("comparison",{spec:{selection:{source:"field-summary",region_set_id:"nuclei",metric:"positive_fraction",positivity:{channel_id:"eu5"}}},selection:{channel_gate:{channel:{channel_id:"eu5",stain:"5-EU"}}}})).toBe("陽性率（5-EU）");
  });
});

describe("analysis changed by the view (#257 SR-04, owner decision 15)",()=>{
  const base={operation:"comparison" as const,comparable:true,canAssociate:true,unconfirmed:false,saturated:false,saturatedAny:false,descriptive:true};
  it("compares two or more groups instead of describing their distribution, without a notice",()=>{
    expect(automaticOperation({...base,operation:"distribution"})).toEqual({operation:"comparison",reason:""});
    // A design without a comparison keeps the distribution.
    expect(automaticOperation({...base,operation:"distribution",comparable:false})).toBeNull();
  });
  it("says why an analysis someone chose cannot be calculated",()=>{
    expect(automaticOperation({...base,operation:"association",unconfirmed:true})).toEqual({operation:"comparison",reason:"実験回の独立性が未確認のため、相関は計算しません。"});
    expect(automaticOperation({...base,operation:"comparison",saturated:true,saturatedAny:true})?.operation).toBe("distribution");
    expect(automaticOperation({...base,operation:"distribution",comparable:false,descriptive:false})).toEqual({operation:"comparison",reason:"この指標は分布を出せません。"});
  });
  it("leaves an analysis the measure and design can have",()=>{
    expect(automaticOperation(base)).toBeNull();
    expect(automaticOperation({...base,operation:"association"})).toBeNull();
  });
});

describe("a saved result answers only the method now chosen (#257 review)",()=>{
  const chosen={paired:true,rank:false,inference:true};
  it("tells a paired t test from a rank test, an independent design and a description",()=>{
    expect(sameMethod("comparison",{test:"paired-t",design:{kind:"paired"}},chosen)).toBe(true);
    expect(sameMethod("comparison",{test:"paired-t",design:{kind:"paired"}},{...chosen,rank:true})).toBe(false);
    expect(sameMethod("comparison",{test:"welch-t",design:{kind:"independent"}},chosen)).toBe(false);
    expect(sameMethod("comparison",{test:"paired-t",design:{kind:"paired"}},{...chosen,inference:false})).toBe(false);
    expect(sameMethod("comparison",{test:"none",design:{kind:"paired"}},{...chosen,inference:false})).toBe(true);
  });
  it("tells Pearson from Spearman, and takes a result without a recorded method as it was",()=>{
    expect(sameMethod("association",{method:"spearman"},chosen)).toBe(false);
    expect(sameMethod("association",{method:"pearson"},chosen)).toBe(true);
    expect(sameMethod("comparison",{},chosen)).toBe(true);
    expect(sameMethod("distribution",{test:"anything"},chosen)).toBe(true);
  });
  it("gives the side panel the saved method",()=>{
    expect(savedMethod("comparison",{test:"wilcoxon",design:{kind:"paired"}})).toEqual({paired:true,rank:true});
    expect(savedMethod("comparison",{test:"none",design:{kind:"independent"}})).toEqual({paired:false});
    expect(savedMethod("association",{method:"spearman"})).toEqual({rank:true});
  });
});
