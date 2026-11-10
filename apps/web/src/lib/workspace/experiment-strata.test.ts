import {describe,expect,it} from "vitest";
import {unassignedFieldCount,labelProblem,factorProblem,levelProblem,savePlan,stratumProblem,LEVEL_LIMIT,addFactor,addLevel,addStratumCombination,combinationLabel,fieldsInStrata,removeFactor,removeLevel,removeStrataById,strataNaming,addStratum,assignFields,assignStratum,declareStrata,fieldMetadata,isStratified,readiness,removeStrata,pairPanes,paneKey,scopedIdentity,strataOf,stratumRequestFor,type PlainExperimentDesign} from "./experiment-design";

// The same cases as tests/test_experiment_strata.py: strata are declared, never inferred, and read one at a time.
const plain:PlainExperimentDesign={version:"1.0.0",layout:"pair",groups:[{id:"a",label:"A"},{id:"b",label:"B"}],control_group_id:"a",
  runs:[{id:"r1",label:"R1",performed_on:null,acquired_on:"2026-01-01"}],independence_confirmed:true,
  fields:{f1:{group_id:"a",run_id:"r1",sample:null,acquired_on:null},f2:{group_id:"b",run_id:"r1",sample:null,acquired_on:null}}};

describe("declared strata",()=>{
  it("declares one level per stratum and leaves every field's stratum to the researcher",()=>{
    const design=declareStrata(plain,"因子",["水準A","水準B"]);
    expect(isStratified(design)).toBe(true);
    expect(design.strata.map(value=>value.label)).toEqual(["水準A","水準B"]);
    expect(Object.values(design.fields??{}).every(value=>value.stratum_id===null)).toBe(true);
    expect(readiness(design,["f1","f2"])).toContainEqual({code:"experiment_design_unstratified_fields",field_ids:["f1","f2"]});
    // Derived metadata (condition, unit, sample) are unchanged by strata.
    expect(fieldMetadata(design)).toEqual(fieldMetadata(plain));
  });
  it("counts fields without a stratum unless they are excluded, and none for an unstratified design",()=>{
    let design=declareStrata(plain,"因子",["水準A","水準B"]);
    design=assignStratum(design,["f1"],design.strata[0].id);
    // f2 is unassigned and f3 is not in the design: both block the calculation until assigned or excluded.
    expect(unassignedFieldCount(design,[{fieldId:"f1"},{fieldId:"f2"},{fieldId:"f3"}])).toBe(2);
    expect(unassignedFieldCount(design,[{fieldId:"f1"},{fieldId:"f2",excluded:true},{fieldId:"f3",excluded:true}])).toBe(0);
    expect(unassignedFieldCount(plain,[{fieldId:"f1"},{fieldId:"f9"}])).toBe(0);
    expect(unassignedFieldCount(null,[{fieldId:"f1"}])).toBe(0);
  });
  it("assigns fields explicitly, checks each stratum on its own, and keeps the stratum on reassignment",()=>{
    let design=declareStrata(plain,"因子",["水準A","水準B"]);
    const levelA=design.strata[0].id;
    design=assignStratum(design,["f1"],levelA);
    expect(readiness(design,["f1","f2"])).toContainEqual({code:"experiment_design_missing_combination",run_id:"r1",group_ids:["b"],stratum_id:levelA});
    design=assignStratum(design,["f2"],levelA);
    expect(strataOf(design).map(value=>value.fieldIds)).toEqual([["f1","f2"],[]]);
    expect(readiness(design,["f1","f2"])).toContainEqual({code:"experiment_design_empty_stratum",stratum_id:design.strata[1].id});
    const moved=assignFields(design,["f1"],{group_id:"a",run_id:"r1",sample:"cover 1"});
    expect(moved.fields?.f1).toMatchObject({stratum_id:levelA,sample:"cover 1"});
    expect(()=>assignStratum(design,["f1"],"elsewhere")).toThrow("experiment_design_unknown_stratum");
  });
  it("adds a level as a stratum and can return to one undivided 1.0.0 design",()=>{
    const design=addStratum(declareStrata(plain,"因子",["水準A"]),"水準B");
    expect(design.factors[0].levels.map(value=>value.label)).toEqual(["水準A","水準B"]);
    expect(design.strata[1].levels).toEqual({[design.factors[0].id]:design.factors[0].levels[1].id});
    expect(removeStrata(assignStratum(design,["f1"],design.strata[0].id))).toEqual(plain);
  });
  it("makes a saved classification, cohort or result stale when a stratum is added or a field moves",()=>{
    // The same sources, metadata and selection before and after: only the design and stratum differ.
    const base=JSON.stringify(["nuclei",[["f1","r-f1"],["f2","r-f2"]],fieldMetadata(plain),{version:3}]);
    let design=declareStrata(plain,"因子",["水準A"]);
    const s1=design.strata[0].id;
    design=assignStratum(design,["f1","f2"],s1);
    const saved=scopedIdentity(base,stratumRequestFor(design,"a".repeat(64),s1));
    // Adding S2 is a new saved design; the API names its new hash (tests/test_experiment_strata.py).
    const withS2=addStratum(design,"水準B");
    expect(scopedIdentity(base,stratumRequestFor(withS2,"b".repeat(64),s1))).not.toBe(saved);
    // Moving a field to S2 changes the design again.
    const moved=assignStratum(withS2,["f2"],withS2.strata[1].id);
    expect(scopedIdentity(base,stratumRequestFor(moved,"c".repeat(64),s1))).not.toBe(saved);
    // Another stratum of the same design is another identity; no stratum is sent without the saved hash.
    expect(scopedIdentity(base,stratumRequestFor(withS2,"a".repeat(64),withS2.strata[1].id))).not.toBe(saved);
    expect(stratumRequestFor(withS2,null,s1)).toBeNull();
    // An undivided design keeps its identity unchanged.
    expect(scopedIdentity(base,stratumRequestFor(plain,"a".repeat(64),s1))).toBe(base);
  });
  it("pairs images within the selected field's stratum only and never pairs an unassigned field",()=>{
    const four:PlainExperimentDesign={...plain,fields:{f1:{group_id:"a",run_id:"r1",sample:null,acquired_on:null},f2:{group_id:"b",run_id:"r1",sample:null,acquired_on:null},
      f3:{group_id:"a",run_id:"r1",sample:null,acquired_on:null},f4:{group_id:"b",run_id:"r1",sample:null,acquired_on:null},f5:{group_id:"a",run_id:"r1",sample:null,acquired_on:null}}};
    let design=declareStrata(four,"因子",["S1","S2"]);
    const [s1,s2]=design.strata.map(value=>value.id);
    design=assignStratum(assignStratum(design,["f1","f2"],s1),["f3","f4"],s2);
    // Selecting f3 (S2, group A) shows S2's B field beside it, never S1's f2.
    const chosen=pairPanes(design,"r1","f3",{});
    expect(chosen.stratumId).toBe(s2);
    expect(chosen.panes.map(pane=>pane.fieldId)).toEqual(["f3","f4"]);
    expect(chosen.panes.map(pane=>pane.ids)).toEqual([["f3"],["f4"]]);
    expect(chosen.panes[1].key).toBe(paneKey(design,"r1","b",s2));
    // A field remembered in S1 does not reappear when S2 is shown.
    expect(pairPanes(design,"r1","f3",{[paneKey(design,"r1","b",s1)]:"f2"}).panes[1].fieldId).toBe("f4");
    // An unassigned field is shown alone.
    const lone=pairPanes(design,"r1","f5",{});
    expect(lone.unassigned).toBe(true);
    expect(lone.panes.map(pane=>pane.fieldId)).toEqual(["f5",undefined]);
    // Without a stratified design the panes are unchanged (group only).
    expect(pairPanes(four,"r1","f3",{}).panes.map(pane=>pane.ids)).toEqual([["f1","f3","f5"],["f2","f4"]]);
  });
  it("declares strata as one level of each of up to three factors, and never moves fields when they are removed",()=>{
    const declared=declareStrata(plain,"因子",["水準A","水準B"]);
    let design=assignStratum(declared,["f1","f2"],declared.strata[0].id);
    // A second factor: the one-factor strata no longer name a level of every factor, so they go and the fields wait.
    design=addFactor(design,"因子2",["水準X"]);
    expect(design.strata).toEqual([]);
    expect(Object.values(design.fields??{}).map(value=>value.stratum_id)).toEqual([null,null]);
    expect(readiness(design,["f1","f2"])).toContainEqual({code:"experiment_design_no_strata"});
    const [line,time]=design.factors;
    design=addLevel(design,time.id,"水準Y");
    const levels={[line.id]:line.levels[0].id,[time.id]:design.factors[1].levels[1].id};
    expect(combinationLabel(design,levels)).toBe("水準A / 水準Y");
    design=addStratumCombination(design,levels,"水準A / 水準Y");
    expect(()=>addStratumCombination(design,levels,"again")).toThrow("experiment_design_duplicate");
    expect(()=>addStratumCombination(design,{[line.id]:line.levels[0].id},"one level")).toThrow("experiment_design_stratum_levels");
    const stratum=design.strata[0].id;
    design=assignStratum(design,["f1"],stratum);
    expect(fieldsInStrata(design,strataNaming(design,time.id,design.factors[1].levels[1].id))).toEqual(["f1"]);
    const third=addFactor(design,"因子3",["水準P"]);
    expect(()=>addFactor(third,"因子4",["x"])).toThrow("experiment_design_factor_limit");
    // Removing a level removes the strata that named it; the field stays in its group and run, without a stratum.
    const fewer=removeLevel(design,time.id,design.factors[1].levels[1].id);
    expect(fewer.strata).toEqual([]);
    expect(fewer.fields?.f1).toMatchObject({group_id:"a",run_id:"r1",stratum_id:null});
    expect(()=>removeLevel(fewer,line.id,line.levels[0].id)).not.toThrow();
    expect(()=>removeLevel(removeLevel(fewer,line.id,line.levels[0].id),line.id,line.levels[1].id)).toThrow("experiment_design_stratum_levels");
    expect(removeStrataById(design,[stratum]).fields?.f1?.stratum_id).toBeNull();
    // Removing a factor removes every stratum; removing the last one returns to the undivided 1.0.0 design.
    expect(removeFactor(design,time.id)).toMatchObject({version:"1.1.0",strata:[]});
    expect(removeFactor(removeFactor(design,time.id) as typeof design,line.id)).toEqual(plain);
  });
  it("refuses a repeated factor, a repeated level and too many levels before anything is saved",()=>{
    expect(factorProblem(plain,"因子",["水準A","水準a"])).toBe("同じ名前の水準が重なっています。");
    const many=Array.from({length:LEVEL_LIMIT+1},(_,index)=>`水準${index}`);
    expect(factorProblem(plain,"因子",many)).toMatch(/12 個まで/);
    expect(factorProblem(plain,"因子",["水準A","水準B"])).toBeNull();
    const design=declareStrata(plain,"因子",["水準A","水準B"]);
    expect(factorProblem(design,"因子",["水準X"])).toBe("同じ名前の因子がすでにあります。");
    expect(levelProblem(design,design.factors[0].id,"水準B")).toBe("同じ名前の水準がすでにあります。");
    expect(levelProblem(design,design.factors[0].id,"水準C")).toBeNull();
    const two=addFactor(design,"因子2",["水準X"]);
    const levels={[two.factors[0].id]:two.factors[0].levels[0].id,[two.factors[1].id]:two.factors[1].levels[0].id};
    const declared=addStratumCombination(two,levels,"水準A / 水準X");
    expect(stratumProblem(declared,levels,"別の名前")).toBe("同じ水準の組み合わせの層がすでにあります。");
    expect(stratumProblem(declared,{...levels,[two.factors[0].id]:two.factors[0].levels[1].id},"水準A / 水準X")).toBe("同じ名前の層がすでにあります。");
    expect(stratumProblem(declared,{[two.factors[0].id]:two.factors[0].levels[1].id},"水準B")).toMatch(/1 つずつ/);
  });
  it("returns to the last stored plan when a save is refused, then stores the corrected plan",async()=>{
    // Stored: one factor, f1 in its first stratum. The refused edit adds a second factor (which unassigns f1).
    const declared=declareStrata(plain,"因子",["水準A","水準B"]);
    const stored=assignStratum(declared,["f1"],declared.strata[0].id);
    const refused=addFactor(stored,"因子2",["水準X"]);
    expect(refused.fields?.f1?.stratum_id).toBeNull();
    const saves:unknown[]=[];
    const refuse=async()=>{throw new Error("同じ名前の群・実験回・因子・水準・層があります。");};
    const first=await savePlan(stored,refused,refuse);
    expect(first.ok).toBe(false);
    expect(first.shown).toBe(stored);
    expect(first.stored).toBe(stored);
    expect(isStratified(first.shown)&&first.shown.factors.length).toBe(1);
    expect((first.shown as typeof stored).fields?.f1?.stratum_id).toBe(declared.strata[0].id);
    expect(first.error).toMatch(/最後に保存した計画に戻しました/);
    // Corrected and saved again: the editor now shows and keeps the stored correction.
    const corrected=addFactor(first.shown as typeof stored,"因子3",["水準Y"]);
    const second=await savePlan(first.stored,corrected,async design=>{saves.push(design);});
    expect(second).toEqual({ok:true,stored:corrected,shown:corrected,error:""});
    expect(saves).toEqual([corrected]);
  });
  it("folds case like the API and never cuts a character in half when naming a stratum",()=>{
    expect(factorProblem(plain,"因子",["Straße","STRASSE"])).toBe("同じ名前の水準が重なっています。");
    const long=declareStrata(plain,"因子",["😀".repeat(20),"水準B"]);
    const two=addFactor(long,"因子2",["😀".repeat(20)]);
    const label=combinationLabel(two,{[two.factors[0].id]:two.factors[0].levels[0].id,[two.factors[1].id]:two.factors[1].levels[0].id});
    expect([...label].length).toBeLessThanOrEqual(24);
    expect(labelProblem(label)).toBeNull();
    expect(labelProblem("水準\ud83d")).toBe("使えない文字が含まれています。");
  });
});
