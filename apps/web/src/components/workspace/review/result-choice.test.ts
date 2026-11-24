import {describe,expect,it} from "vitest";
import {automaticOperation,backgroundFingerprint,changedInputs,changedSources,excludedRegions,fieldAssignment,sameMethod,savedMethod,choiceFilter,conditionChannel,conditionKey,gateKey,measureLabel,recordedGateMatches,savedCondition,savedFor,savedMeasureLabel,sameSources,type ResultCondition,type SavedResultLike} from "./result-choice";

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
  it("tells a classification by raw values from one by background-corrected values",()=>{
    const raw={channel_id:"eu5",values:"raw",keep:"positive"},corrected={...raw,values:"corrected"};
    expect(gateKey(raw)).toBe("eu5:raw:positive");
    expect(choiceFilter("area_px",null,raw)).not.toBe(choiceFilter("area_px",null,corrected));
    const saved:SavedResultLike={spec:{selection:{source:"region",region_set_id:"nuclei",metric:"area_px",channel_gate:raw}}};
    expect(savedCondition("comparison",saved)?.filter).toBe(choiceFilter("area_px",null,raw));
  });
});

describe("the demo's recorded nucleus filter (#257 SR-05)",()=>{
  const raw=choiceFilter("area_px",null,{channel_id:"eu5",values:"raw",keep:"positive"});
  const corrected=choiceFilter("area_px",null,{channel_id:"eu5",values:"corrected",keep:"positive"});
  it("offers a classified measure only for the classification the tour recorded it under",()=>{
    expect(recordedGateMatches("eu5:corrected:positive",corrected)).toBe(true);
    expect(recordedGateMatches("eu5:corrected:positive",raw)).toBe(false);
    expect(recordedGateMatches("eu5:corrected:negative",corrected)).toBe(false);
    expect(recordedGateMatches(null,"")).toBe(true);
    expect(recordedGateMatches(null,raw)).toBe(false);
    expect(recordedGateMatches("eu5:raw:positive","")).toBe(false);
  });
  it("reads an index written before the measured value was part of the key as naming any value",()=>{
    expect(recordedGateMatches("eu5:positive",raw)).toBe(true);
    expect(recordedGateMatches("eu5:positive",corrected)).toBe(true);
    expect(recordedGateMatches("eu5:negative",raw)).toBe(false);
    expect(recordedGateMatches("gfp:positive",raw)).toBe(false);
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
  // genellect/cytellect#257 NS-04: a background ROI drawn again keeps the regions' mask revision, protocol 1.0.0 and the
  // mode; only the channels' recorded background (and the analysis revision that measured it) changes.
  const roi=(median:number,mask:string,revision:string)=>[{channel:{channel_id:"npm1"},background_mask_sha256:mask,background_pixel_count:900,background_median:median,background_revision_id:revision},
    {channel:{channel_id:"dna"},background_mask_sha256:mask,background_pixel_count:900,background_median:3,background_revision_id:revision}];
  // Protocol 1.0.0 (a confirmed ROI) records no measurement policy in a result's source fields.
  const confirmed=(provenance:ReturnType<typeof roi>|undefined)=>fieldsOf().map(field=>({field_id:field.field_id,analysis_revision_id:field.analysis_revision_id,region_set:field.region_set,channel_provenance:provenance}));
  const current=(provenance:ReturnType<typeof roi>|undefined)=>sources.map(({field,mask})=>({field,mask,background:backgroundFingerprint(provenance)}));
  it("tells a result corrected by an earlier background ROI apart from the current measurement",()=>{
    expect(sameSources(confirmed(roi(7,"roi-a","r1")),current(roi(15,"roi-b","r2")))).toBe(false);
    const stale={job:"mean-roi-a",operation:"comparison" as const,result:{...meanNucleoli,source_fields:confirmed(roi(7,"roi-a","r1"))}};
    expect(savedFor([stale],choice({}),current(roi(15,"roi-b","r2")))).toEqual({current:undefined,older:stale});
  });
  it("keeps a result current when the same background is measured again or another region set is measured",()=>{
    // Measuring again (a new analysis revision, the background's revision with it) with the same ROI keeps the values.
    expect(sameSources(confirmed(roi(7,"roi-a","r1")),current(roi(7,"roi-a","r2")))).toBe(true);
    // The channels' order in a table does not matter; an automatic background compares by its whole record.
    expect(sameSources(confirmed(roi(7,"roi-a","r1")),current([...roi(7,"roi-a","r1")].reverse()))).toBe(true);
    const automatic=(threshold:number)=>[{channel:{channel_id:"npm1"},background:{status:"established",bright_threshold:threshold,exclusion_mask_sha256:"e"}}];
    expect(sameSources(fieldsOf().map(field=>({...field,channel_provenance:automatic(40)})),sources.map(source=>({...source,background:backgroundFingerprint(automatic(40))})))).toBe(true);
    expect(sameSources(fieldsOf().map(field=>({...field,channel_provenance:automatic(40)})),sources.map(source=>({...source,background:backgroundFingerprint(automatic(41))})))).toBe(false);
    // A result or table that records no background is taken as it was.
    expect(sameSources(confirmed(undefined),current(roi(7,"roi-a","r1")))).toBe(true);
    expect(sameSources(confirmed(roi(7,"roi-a","r1")),current(undefined))).toBe(true);
    expect(backgroundFingerprint(undefined)).toBe("");
  });
  it("finds the result opened with the view changed only when a field it read was measured again differently",()=>{
    expect(changedSources(confirmed(roi(7,"roi-a","r1")),current(roi(15,"roi-b","r2")))).toBe(true);
    expect(changedSources(fieldsOf(["m1","m2b"]),sources)).toBe(true);
    expect(changedSources(confirmed(roi(7,"roi-a","r1")),current(roi(7,"roi-a","r2")))).toBe(false);
    // Fields still loading, a field not chosen now, or a table without a mask revision are no evidence of a change.
    expect(changedSources(fieldsOf(),[])).toBe(false);
    expect(changedSources(fieldsOf(),sources.slice(0,1))).toBe(false);
    expect(changedSources(fieldsOf(),sources.map(source=>({...source,mask:""})))).toBe(false);
    expect(changedSources(undefined,sources)).toBe(false);
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

// genellect/cytellect#257 NS-04 (integration review of #291): excluding a nucleus in 画像 keeps the regions' mask
// revision, and the assignment in 実験 and the compared pairs are not in the measurement at all. A result saved before
// the workspace was reopened is compared with them by what it recorded.
describe("a saved result answers only the exclusions, assignment and pairs now chosen (#257 NS-04)",()=>{
  const assigned=(condition:string,unit:string)=>({condition,experimental_unit:unit,sample:`${unit} · ${condition}`,acquisition_date:"2021-12-01",pair:unit});
  const assignment={f1:assigned("Untreated","Rep1"),f2:assigned("Oxaliplatin","Rep1")};
  const observation=(field:string,region:number,excluded:boolean)=>({observation_id:JSON.stringify([field,"nucleoli",region]),field_id:field,region_id:region,excluded});
  const ledger=(excluded:Array<[string,number]>)=>["f1","f2"].flatMap(field=>[1,2,3].map(region=>observation(field,region,excluded.some(([f,r])=>f===field&&r===region))));
  const recordedFields=(values:Record<string,ReturnType<typeof assigned>>=assignment)=>fieldsOf().map(field=>({...field,metadata:values[field.field_id]}));
  const comparison=(excluded:Array<[string,number]>=[[ "f1",2]],contrasts=[["Oxaliplatin","Untreated"]],values=assignment):SavedResultLike=>({...meanNucleoli,
    spec:{...meanNucleoli.spec,comparison_family:{contrasts}},source_fields:recordedFields(values),observation_ledger:ledger(excluded)});
  const now=(excluded:Record<string,number[]>={f1:[2],f2:[]},values:Record<string,ReturnType<typeof assigned>|undefined>=assignment)=>sources.map(source=>({...source,excluded:excluded[source.field],assignment:fieldAssignment(values[source.field])}));
  const pairs=[["Oxaliplatin","Untreated"]];
  const entry=(result:SavedResultLike,operation:"comparison"|"distribution"|"association"="comparison")=>({job:"saved",operation,result});
  it("keeps a result current when the same nuclei, assignment and pairs are chosen",()=>{
    expect(savedFor([entry(comparison())],choice({}),now(),pairs).current).toBeDefined();
    expect(changedInputs("comparison",comparison(),now(),pairs)).toBe(false);
  });
  it("does not open a result as current once another nucleus is excluded or one is included again",()=>{
    const saved=entry(comparison());
    expect(savedFor([saved],choice({}),now({f1:[2,3],f2:[]}),pairs)).toEqual({current:undefined,older:saved});
    expect(savedFor([saved],choice({}),now({f1:[],f2:[]}),pairs)).toEqual({current:undefined,older:saved});
    expect(changedInputs("comparison",saved.result,now({f1:[2],f2:[1]}),pairs)).toBe(true);
  });
  it("reads a distribution's exclusions from its selection records and an association's from its axes",()=>{
    const distribution:SavedResultLike={...meanNucleoli,spec:{selection:meanNucleoli.spec!.selection},selection:{records:ledger([["f2",1]]).map(({observation_id,field_id,excluded})=>({observation_id,field_id,excluded}))}};
    expect(savedFor([entry(distribution,"distribution")],choice({operation:"distribution"}),now({f1:[],f2:[1]})).current).toBeDefined();
    expect(savedFor([entry(distribution,"distribution")],choice({operation:"distribution"}),now({f1:[],f2:[]})).current).toBeUndefined();
    const association:SavedResultLike={spec:{x_selection:{region_set_id:"nucleoli",metric:"area_px",channel_id:null},y_selection:{region_set_id:"nucleoli",metric:"mean",channel_id:"npm1"}},
      x_source:{source_fields:recordedFields(),observation_ledger:ledger([["f1",2]])},y_source:{source_fields:recordedFields(),observation_ledger:ledger([["f1",2]])}};
    const axes=choice({operation:"association",x:{metric:"area_px",channel:null}});
    expect(savedFor([entry(association,"association")],axes,now()).current).toBeDefined();
    expect(savedFor([entry(association,"association")],axes,now({f1:[],f2:[]})).current).toBeUndefined();
  });
  it("compares a per-field summary by the number of excluded nuclei it recorded",()=>{
    const perField:SavedResultLike={...meanNucleoli,source_fields:recordedFields().map((field,index)=>({...field,field_summary:{excluded_region_count:index===0?1:0}})),
      observation_ledger:["f1","f2"].map(field=>({observation_id:JSON.stringify([field,"nuclei","field"]),field_id:field,region_id:null,excluded:false}))};
    expect(changedInputs("comparison",perField,now({f1:[4],f2:[]}),pairs)).toBe(false);
    expect(changedInputs("comparison",perField,now({f1:[4,5],f2:[]}),pairs)).toBe(true);
  });
  it("does not open a comparison as current once a field's group, run or pair is assigned differently",()=>{
    const saved=entry(comparison());
    expect(savedFor([saved],choice({}),now(undefined,{f1:assigned("Oxaliplatin","Rep1"),f2:assigned("Untreated","Rep1")}),pairs)).toEqual({current:undefined,older:saved});
    expect(changedInputs("comparison",saved.result,now(undefined,{...assignment,f2:assigned("Oxaliplatin","Rep2")}),pairs)).toBe(true);
    expect(changedInputs("comparison",saved.result,now(undefined,{...assignment,f2:{...assignment.f2,pair:"Rep9"}}),pairs)).toBe(true);
    // Spacing and an empty entry are recorded as the cohort stores them.
    expect(changedInputs("comparison",saved.result,now(undefined,{...assignment,f1:{...assignment.f1,condition:" Untreated ",pair:"Rep1"}}),pairs)).toBe(false);
  });
  it("does not open a comparison as current once other pairs of groups are compared",()=>{
    const saved=entry(comparison());
    expect(savedFor([saved],choice({}),now(),[["Untreated","Oxaliplatin"]])).toEqual({current:undefined,older:saved});
    expect(changedInputs("comparison",saved.result,now(),[["Oxaliplatin","Untreated"],["Cisplatin","Untreated"]])).toBe(true);
    // The order the pairs are listed in does not change a result.
    const two=comparison(undefined,[["A","C"],["B","C"]]);
    expect(changedInputs("comparison",two,now(),[["B","C"],["A","C"]])).toBe(false);
  });
  it("takes a result that records none of them, or a choice not known yet, as it was",()=>{
    // An older result without observation records, metadata or pairs.
    expect(savedFor([entry(meanNucleoli)],choice({}),now({f1:[1,2,3],f2:[]},{f1:assigned("X","Rep7"),f2:assigned("Y","Rep8")}),[["X","Y"]]).current).toBeDefined();
    // The fields' tables, the design or the pairs not loaded yet.
    expect(changedInputs("comparison",comparison(),sources,[])).toBe(false);
    expect(changedInputs("comparison",comparison(),now(undefined,{f1:undefined,f2:undefined}),[])).toBe(false);
    // A distribution does not read the assignment (a single field is described from its own revision's record).
    expect(changedInputs("distribution",{...comparison(),observation_ledger:undefined},now(undefined,{f1:assigned("X","Rep7"),f2:assigned("Y","Rep8")}),[])).toBe(false);
    // A whole field excluded in the current table is no evidence about its nuclei.
    expect(excludedRegions([{field_id:"f1",region_id:null,reason:"r"},{field_id:"f1",region_id:3,reason:"r"}],"f1")).toBeUndefined();
    expect(excludedRegions([{field_id:"f1",region_id:3,reason:"r"},{field_id:"f2",region_id:1,reason:"r"},{field_id:"f1",region_id:1,reason:"r"}],"f1")).toEqual([1,3]);
    expect(excludedRegions(undefined,"f1")).toBeUndefined();
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
  it("takes a description as the answer to a choice that could be tested, which 計算 then tests (decision 11)",()=>{
    expect(sameMethod("comparison",{test:"none",design:{kind:"paired"}},chosen)).toBe(true);
    expect(sameMethod("comparison",{test:"none",design:{kind:"paired"}},{...chosen,rank:true})).toBe(true);
    // The pairing still has to match.
    expect(sameMethod("comparison",{test:"none",design:{kind:"independent"}},chosen)).toBe(false);
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
