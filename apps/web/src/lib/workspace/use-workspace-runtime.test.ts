import {describe, expect, it, vi} from "vitest";
import {ApiError} from "../api";
import {createWorkspaceRuntime, defaultRuntimeSettings, IntakeInterrupted, runtimeRecipe, sameRuntimeRecipe} from "./use-workspace-runtime";
import type {AssistantMessage, createApiAdapter, ImportedField, IntakeRecord, Recipe, SavedResult, SelectionEntry, ValidatedProposal} from "./api-adapter";
import type {ReviewData, ReviewTarget} from "./review-preview";
import type {ChannelDefinition} from "./grouping";
const nuclear:ChannelDefinition={token:"c4",stain:"DAPI",role:"nuclear",evidence:"user"};
function result(id:string,field="f1"):SavedResult{return {revision:id,field,rows:[],masks:{regions:[{id:17,points:[[1,1],[3,1],[3,3]]}],metadata:{mask_revision_id:id}},exclusions:[]};}
function fixture(withResult=true,initialSpecification:import("./use-workspace-runtime").RuntimeSpecification={version:0,spec:null}){
  const settings=defaultRuntimeSettings(),recipe=runtimeRecipe("nuclei",nuclear,settings,{},null);
  const input:ImportedField={id:"f1",workspace_id:"w",metadata:{},image_info:{shape:[10,10],channels:[{channel_id:"c4",label:"DAPI",stain:"DAPI"}]}};
  const revisions=new Map<string,Recipe>(),adopted=new Map<ReviewTarget,SavedResult>();
  if(withResult){revisions.set("corrected",recipe);adopted.set("nuclei",result("corrected"));}
  const assignments={version:1,assignments:[{channel_id:"c4",stain:"DAPI",role:"nuclear" as const}]};
  const target=(recipe:Recipe):ReviewTarget=>recipe.source==="manual"?"cell":recipe.compartment||"nuclei";
  const loadPreview=vi.fn(async():Promise<ReviewData>=>({workspaceId:"w",title:"fixture",channels:[{id:"c4",label:"DAPI",stain:"DAPI",role:"nuclear"}],fields:[{id:"f1",label:"View",width:10,height:10,channels:[{id:"c4",label:"DAPI",stain:"DAPI",role:"nuclear"}],previews:{},results:Object.fromEntries(adopted),nuclearChannelId:adopted.has("nuclei")?"c4":undefined}]}));
  let serial=0;
  const adapter={
    restore:vi.fn(async()=>({record:{id:"w"},fields:[input],revisions:[...revisions].map(([id,recipe])=>({id,state:"succeeded",created:1,config:{recipe,field_ids:["f1"]}})),jobs:[],selection:{version:1,entries:[{id:"f1",field_id:"f1",revision_id:adopted.get("nuclei")?.revision||null}]}})),
    getChannelAssignments:vi.fn(async()=>assignments),isSelectionCurrent:vi.fn(async()=>true),
    run:vi.fn(async(_workspace:string,_field:string,recipe:Recipe,_progress?:unknown,_measurement?:unknown,options?:{adopt?:boolean})=>{const saved=result(`run${++serial}`);revisions.set(saved.revision,recipe);const key=target(recipe);if(options?.adopt!==false){adopted.set(key,saved);if(key==="nuclei"){adopted.delete("nucleoli");adopted.delete("nucleoplasm");}}return saved;}),
    editMask:vi.fn(async(_workspace:string,_source:SavedResult,recipe:Recipe)=>{const saved=result(`edit${++serial}`);revisions.set(saved.revision,recipe);adopted.set(target(recipe),saved);return saved;}),
    selectRevision:vi.fn(async(_workspace:string,id:string)=>{const saved=result(id);adopted.set(target(revisions.get(id)!),saved);return saved;}),
    draft:vi.fn(async()=>({proposal:{draft:{recipe:"nuclear-intensity",channels:[],metrics:[],statistics:{kind:"descriptive",test:null,omnibus:null,association:null},figures:[],missing_information:[],reference_ids:[],rationale:"fixture",processing:{version:"1.0.0",nuclei:{channel:"c4",detection_max_side_px:null,detector:{engine:"fiji-stardist-2d",model:"Versatile (fluorescent nuclei)",probability:.65,nms:.3,percentile_low:1,percentile_high:99.8}},nucleoli:null,signal:null}},needs_confirmation:[]} as ValidatedProposal,message:message()})),
    registerImport:vi.fn<(workspace:string,id:string,intake?:IntakeRecord)=>Promise<void>>(),recordImport:vi.fn<(workspace:string,id:string,intake:Partial<IntakeRecord>)=>Promise<void>>(),removeImport:vi.fn<(workspace:string,id:string)=>Promise<void>>(),clearTargets:vi.fn<(workspace:string,ids:string[])=>Promise<void>>(),excludeField:vi.fn<(workspace:string,id:string,reason:string|null)=>Promise<void>>(),uploadOme:vi.fn(async()=>input),upload:vi.fn<(workspace:string,field:{key:string},channels?:unknown,files?:unknown,entry?:string)=>Promise<ImportedField>>(async()=>input),create:vi.fn(async()=>({id:"w",title:"fixture"})),recordEffect:vi.fn<(workspace:string,id:string,effect:string)=>Promise<null>>(async()=>null),listMessages:vi.fn<(workspace:string)=>Promise<AssistantMessage[]>>(async()=>[]),selection:vi.fn(():{version:number;entries:SelectionEntry[]}|null=>({version:1,entries:[]})),
  };
  let spec=initialSpecification;
  const writeSpecification=vi.fn(async(_id:string,value:import("./use-workspace-runtime").RuntimeSpecification)=>{spec={...value,version:spec.version+1};return spec;});
  const runtime=createWorkspaceRuntime({adapter:adapter as unknown as ReturnType<typeof createApiAdapter>,loadPreview,releasePreview:vi.fn(),readSpecification:async()=>spec,writeSpecification});
  return {runtime,adapter,adopted,recipe,revisions,assignments,loadPreview,writeSpecification};
}
/** The four BBBC007 files of #284 by name (a9 and f9620, C01 = DNA and C02 = actin). The bytes are synthetic: the
 * name decides the grouping, and each file has its own content (implementation plan §11). */
const bbbc007=()=>["BBBC007-a9-C01.tif","BBBC007-a9-C02.tif","BBBC007-f9620-C01.tif","BBBC007-f9620-C02.tif"].map((name,index)=>new File([new Uint8Array([index+1])],name));
/** The rows the API keeps, as the adapter writes them: an addition writes a row, an accepted upload joins its field. */
function withLedger(adapter:ReturnType<typeof fixture>["adapter"]){
  let rows:SelectionEntry[]=[{id:"f1",field_id:"f1",revision_id:"corrected",exclusion_reason:null}];const fields=new Map<string,ImportedField>();
  adapter.selection.mockImplementation(()=>({version:1,entries:rows}));
  adapter.registerImport.mockImplementation(async(_workspace,id,intake)=>{const row=rows.find(entry=>entry.id===id);if(!row)rows=[...rows,{id,field_id:null,revision_id:null,exclusion_reason:null,...(intake?{intake}:{})}];else if(intake&&!row.field_id)rows=rows.map(entry=>entry.id===id?{...entry,intake}:entry);});
  adapter.recordImport.mockImplementation(async(_workspace,id,change)=>{rows=rows.map(entry=>{if(entry.id!==id||!entry.intake)return entry;const intake={...entry.intake,...change} as IntakeRecord;for(const key of ["stage","code","target"] as const)if(intake[key]===undefined)delete intake[key];return {...entry,intake};});});
  adapter.removeImport.mockImplementation(async(_workspace,id)=>{rows=rows.filter(entry=>entry.id!==id||!!entry.field_id);});
  adapter.clearTargets.mockImplementation(async(_workspace,ids)=>{rows=rows.map(entry=>{if(!ids.includes(entry.id)||!entry.intake?.target)return entry;const intake={...entry.intake};delete intake.target;return {...entry,intake};});});
  const restore=adapter.restore.getMockImplementation()!;
  adapter.restore.mockImplementation(async(...args:Parameters<typeof restore>)=>{const value=await restore(...args);return {...value,fields:[...value.fields,...fields.values()],selection:{version:1,entries:rows}} as unknown as typeof value;});
  adapter.upload.mockImplementation(async()=>{throw new Error("no upload behaviour");});
  return {
    entries:()=>rows,
    fill(size:number){while(rows.length<size)rows=[...rows,{id:`filler-${rows.length}`,field_id:`filler-${rows.length}`,revision_id:null,exclusion_reason:null}];},
    /** Accepts an upload: the field exists and its row is joined, with the stored input hashes. */
    accept(entry:string,id:string){
      const sent=adapter.upload.mock.calls.findLast(call=>call[4]===entry);
      const inputs:Record<string,{sha256:string;bytes:number}>={};
      const field:ImportedField={id,workspace_id:"w",metadata:{},image_info:{shape:[10,10],channels:[{channel_id:"c4",label:"DAPI",stain:"DAPI"}],inputs}};
      if(sent){const grouped=sent[1] as unknown as {files:Record<string,{path:string;sha256?:string}>};Object.values(grouped.files).forEach((file,index)=>{if(file.sha256)inputs[`ch${index}`]={sha256:file.sha256,bytes:1};});}
      fields.set(id,field);
      rows=rows.map(row=>{if(row.id!==entry)return row;const intake=row.intake?{...row.intake,state:"registered" as const}:undefined;if(intake){delete intake.stage;delete intake.code;}return {...row,field_id:id,...(intake?{intake}:{})};});
      return field;
    },
  };
}
/** Sends a message and applies its answer as the researcher's 「適用して試行」 (#284 W2: an answer alone changes nothing). */
const message=(id="m1")=>({id,field_id:null,created:1,text:"",state:"answered" as const,reply:null,applicable:true,reasons:[],stage:null,effect:"none" as const});
async function ask(runtime:ReturnType<typeof createWorkspaceRuntime>,goal:string,field?:string,trial=true){const response=await runtime.requestProposal(goal,field);await runtime.applyAnswer(response.message.id,trial,field);return response;}
describe("functional workspace runtime",()=>{
  it("resends a failed proposal only after an explicit retry, with the same instruction",async()=>{
    const {runtime,adapter}=fixture();await runtime.load("w");
    adapter.draft.mockRejectedValueOnce(new ApiError("proposal_explicit_retry_required",409));
    await expect(runtime.requestProposal("same instruction","f1")).rejects.toMatchObject({code:"proposal_explicit_retry_required"});
    expect(adapter.draft).toHaveBeenCalledTimes(1);
    runtime.dismissError();
    expect(runtime.getSnapshot().error).toBe("");
    await runtime.requestProposal("same instruction","f1",true);
    expect(adapter.draft).toHaveBeenCalledTimes(2);
    expect(adapter.draft).toHaveBeenLastCalledWith("w","same instruction",true,expect.anything(),undefined);
  });
  it("shows the first field before loading the others, and loads a single field once",async()=>{
    const calls=(mock:ReturnType<typeof fixture>["loadPreview"])=>mock.mock.calls as unknown as Array<[string|undefined,string[]|undefined,{limit?:number;reuse?:ReviewData|null}|undefined]>;
    const stages=(mock:ReturnType<typeof fixture>["loadPreview"])=>calls(mock).map(([id,fields,options])=>[id,fields,options?.limit]);
    const single=fixture();await single.runtime.load("w");
    expect(stages(single.loadPreview)).toEqual([["w",undefined,1]]);
    const several=fixture(),restore=several.adapter.restore.getMockImplementation()!;
    several.adapter.restore.mockImplementation(async(...args:Parameters<typeof restore>)=>{const value=await restore(...args);return {...value,fields:[...value.fields,{...value.fields[0],id:"f2"}]};});
    await several.runtime.load("w");
    expect(stages(several.loadPreview)).toEqual([["w",undefined,1],["w",undefined,undefined]]);
    // The remaining fields reuse the previews already shown instead of fetching them again.
    expect(calls(several.loadPreview)[1][2]).toMatchObject({reuse:{workspaceId:"w"}});
  });
  it("opens a two-group design on both fields of its first run, loaded together before the others",async()=>{
    const design={version:"1.0.0",layout:"pair",control_group_id:"c",independence_confirmed:false,groups:[{id:"t",label:"KO"},{id:"c",label:"NT"}],
      runs:[{id:"r1",label:"Run1"}],fields:{f1:{group_id:"t",run_id:"r1"},f2:{group_id:"c",run_id:"r1"},f3:{group_id:"c",run_id:"r1"}}};
    const pair=fixture(true,{version:1,spec:{channel_assignment_version:1,target:"nuclei",settings:defaultRuntimeSettings(),processing:null,measurement:null,experiment:design as never}});
    const restore=pair.adapter.restore.getMockImplementation()!;
    pair.adapter.restore.mockImplementation(async(...args:Parameters<typeof restore>)=>{const value=await restore(...args);return {...value,fields:["f1","f2","f3"].map(id=>({...value.fields[0],id}))};});
    await pair.runtime.load("w");
    expect((pair.loadPreview.mock.calls as unknown as Array<[string,string[]|undefined]>).map(([id,fields])=>[id,fields])).toEqual([["w",["f2","f1"]],["w",undefined]]);
  });
  it("saves a target selection without sending back the read-only design hash of a stratified plan",async()=>{
    const read={version:3,experiment_sha256:"a".repeat(64),spec:{channel_assignment_version:1,target:"nuclei",settings:defaultRuntimeSettings(),processing:null,measurement:null}};
    const loaded=fixture(true,read as never);
    await loaded.runtime.load("w");
    await loaded.runtime.saveSelection({kind:"gfp"} as never);
    const written=loaded.writeSpecification.mock.calls.at(-1)![1] as unknown as Record<string,unknown>;
    expect(Object.keys(written).sort()).toEqual(["spec","version"]);
    expect((written.spec as {selection:unknown}).selection).toEqual({kind:"gfp"});
  });
  it("repairs historical result settings in one versioned write with current manual settings",async()=>{
    const settings=defaultRuntimeSettings();
    const invalid={method:{kind:"association",association:"spearman"},x_metric:"nucleolar_count",y_metric:"nuclear_area"};
    const {runtime,writeSpecification,adapter}=fixture(true,{version:7,spec:{channel_assignment_version:1,target:"nuclei",settings,processing:null,measurement:{version:"1.1.0",mode:"raw_intensity"},statistics:invalid,selection:{revision_id:"corrected"},figure:{width_mm:89},additional_analyses:[invalid]}});
    await runtime.load("w");expect(runtime.specification().spec?.statistics).toEqual(invalid);
    runtime.setSettings(value=>({...value,nuclearProbability:.71}));
    const repaired={method:{kind:"descriptive",test:null,omnibus:null,association:null},x_metric:null,y_metric:"nuclear_area"};
    await runtime.saveResultDraft({statistics:repaired,additional_analyses:[]});
    expect(writeSpecification).toHaveBeenCalledTimes(1);
    expect(writeSpecification).toHaveBeenCalledWith("w",{version:7,spec:expect.objectContaining({settings:expect.objectContaining({nuclearProbability:.71}),statistics:repaired,additional_analyses:[],selection:{revision_id:"corrected"},figure:{width_mm:89}})});
    expect(runtime.specification().version).toBe(8);expect(adapter.run).not.toHaveBeenCalled();expect(adapter.draft).not.toHaveBeenCalled();
  });
  it("routes one OME container once through the API and takes channel metadata from its response",async()=>{
    const {runtime,adapter}=fixture();await runtime.load("w");
    const xml=new TextEncoder().encode('<OME xmlns="http://www.openmicroscopy.org/Schemas/OME/2016-06"><Image/></OME>');
    const bytes=new ArrayBuffer(26+xml.length),view=new DataView(bytes);view.setUint16(0,0x4949);view.setUint16(2,42,true);view.setUint32(4,8,true);view.setUint16(8,1,true);view.setUint16(10,270,true);view.setUint16(12,2,true);view.setUint32(14,xml.length,true);view.setUint32(18,26,true);new Uint8Array(bytes,26).set(xml);
    await runtime.importFiles([new File([bytes],"container.ome.tif")]);
    expect(adapter.uploadOme).toHaveBeenCalledTimes(1);expect(adapter.upload).not.toHaveBeenCalled();expect(adapter.draft).not.toHaveBeenCalled();expect(adapter.run).not.toHaveBeenCalled();
  });
  it("keeps successful candidates from a failed batch without adopting or changing the viewed target",async()=>{
    const {runtime,adapter,recipe,adopted}=fixture();
    const run:import("./api-adapter").WorkspaceRun={id:"partial",workspace_id:"w",spec_version:1,target:"nucleoli",state:"failed",created:1,updated:1,steps:[{field_id:"f1",target:"nuclei",state:"succeeded",revision_id:"candidate",job_id:"job1",recipe,error:null},{field_id:"f1",target:"nucleoli",state:"failed",revision_id:null,job_id:"job2",recipe:null,error:"synthetic_failure"}]};
    const acceptWorkspaceRun=vi.fn();
    Object.assign(adapter,{startWorkspaceRun:vi.fn(async()=>run),waitWorkspaceRun:vi.fn(async()=>run),acceptWorkspaceRun,listWorkspaceRuns:vi.fn(async()=>[]),readResult:vi.fn(async()=>result("candidate"))});
    await runtime.load("w");await expect(runtime.preview("f1","nucleoli")).rejects.toThrow("synthetic_failure");
    expect(runtime.candidateResult("f1","nuclei")?.revision).toBe("candidate");expect(adopted.get("nuclei")?.revision).toBe("corrected");expect(acceptWorkspaceRun).not.toHaveBeenCalled();expect(runtime.getSnapshot().activeTarget).toBe("nuclei");expect(runtime.getSnapshot().data?.fields[0].error).toContain("synthetic_failure");
  });
  it("uses one persistent server run and accepts previews without a browser dependency loop",async()=>{
    const {runtime,adapter,recipe,revisions,adopted}=fixture();
    const run:import("./api-adapter").WorkspaceRun={id:"durable",workspace_id:"w",spec_version:1,target:"nuclei",state:"succeeded",created:1,updated:1,steps:[{field_id:"f1",target:"nuclei",state:"succeeded",revision_id:"server1",job_id:"job",recipe,error:null}]};
    const startWorkspaceRun=vi.fn(async()=>run),acceptWorkspaceRun=vi.fn(async()=>{adopted.set("nuclei",result("server1"));revisions.set("server1",recipe);return {...run,state:"adopted" as const};});
    Object.assign(adapter,{startWorkspaceRun,waitWorkspaceRun:vi.fn(async()=>run),acceptWorkspaceRun,listWorkspaceRuns:vi.fn(async()=>[]),readResult:vi.fn(async()=>result("server1"))});
    await runtime.load("w");await runtime.preview("f1","nuclei");
    expect(startWorkspaceRun).toHaveBeenCalledWith("w",expect.objectContaining({spec_version:1,target:"nuclei",field_ids:["f1"]}));
    expect(adapter.run).not.toHaveBeenCalled();expect(acceptWorkspaceRun).not.toHaveBeenCalled();expect(runtime.getSnapshot().data?.fields[0].results.nuclei?.revision).toBe("corrected");
    await runtime.run("nuclei","f1");expect(startWorkspaceRun).toHaveBeenCalledTimes(1);expect(acceptWorkspaceRun).toHaveBeenCalledWith("w","durable");expect(runtime.canUndo("f1","nuclei")).toBe(true);
  });
  it("undoes AI settings without changing corrected mask adoption",async()=>{
    const {runtime,adopted}=fixture();await runtime.load("w");await ask(runtime,"","f1");expect(runtime.getSnapshot().settings.nuclearProbability).toBe(.65);
    expect(runtime.canUndoProposal()).toBe(true);await runtime.undoProposal();expect(runtime.getSnapshot().settings.nuclearProbability).toBe(.5);
    expect(adopted.get("nuclei")?.revision).toBe("corrected");expect(runtime.candidateResult("f1","nuclei")).toBeUndefined();expect(runtime.specification().spec?.settings.nuclearProbability).toBe(.5);
  });
  it("preserves corrected nuclei for an unchanged full recipe and binds nucleoli to that revision",async()=>{
    const {runtime,adapter}=fixture();await runtime.load("w");await runtime.run("nuclei","f1");expect(adapter.run).not.toHaveBeenCalled();
    await runtime.run("nucleoli","f1");expect(adapter.run).toHaveBeenCalledTimes(1);
    expect(adapter.run.mock.calls[0][2]).toMatchObject({source:"fiji_nuclear_compartment",nuclear_revision_id:"corrected",nuclear_channel_id:"c4",compartment:"nucleoli"});
  });
  it("reruns nuclei when probability changes even if image scale is unchanged",async()=>{
    const {runtime,adapter}=fixture();await runtime.load("w");runtime.setSettings(value=>({...value,nuclearProbability:.7}));await runtime.run("nuclei","f1");
    expect(adapter.run).toHaveBeenCalledTimes(1);expect(adapter.run.mock.calls[0][2].detector).toMatchObject({probability:.7});
  });
  it("keeps corrected adoption during preview and accepts its exact candidate without rerunning",async()=>{
    const {runtime,adapter,adopted}=fixture();await runtime.load("w");runtime.setSettings(value=>({...value,nuclearProbability:.7}));
    await runtime.preview("f1","nuclei");
    expect(adopted.get("nuclei")?.revision).toBe("corrected");expect(runtime.getSnapshot().data?.fields[0].results.nuclei?.revision).toBe("corrected");
    expect(runtime.candidateResult("f1","nuclei")?.revision).toBe("run1");expect(adapter.run.mock.calls[0][5]).toEqual({adopt:false});
    await runtime.run("nuclei","f1");expect(adapter.run).toHaveBeenCalledTimes(1);expect(adapter.selectRevision).toHaveBeenLastCalledWith("w","run1","f1");
    expect(runtime.getSnapshot().data?.fields[0].results.nuclei?.revision).toBe("run1");expect(runtime.candidateResult("f1","nuclei")).toBeUndefined();
  });
  it("previews dependent masks separately and adopts them in exact parent order",async()=>{
    const {runtime,adapter,adopted}=fixture();await runtime.load("w");runtime.setSettings(value=>({...value,nuclearProbability:.7}));
    await runtime.preview("f1","nucleoplasm");expect(adapter.run).toHaveBeenCalledTimes(3);expect(adopted.size).toBe(1);
    expect(runtime.candidates("f1","nucleoplasm")?.recipe).toMatchObject({nuclear_revision_id:"run1",nucleolar_revision_id:"run2"});
    await runtime.run("nucleoplasm","f1");expect(adapter.run).toHaveBeenCalledTimes(3);
    expect(adapter.selectRevision.mock.calls.map(call=>call[1])).toEqual(["run1","run2","run3"]);
  });
  it("never accepts a candidate after settings change",async()=>{
    const {runtime,adapter}=fixture();await runtime.load("w");runtime.setSettings(value=>({...value,nuclearProbability:.7}));await runtime.preview("f1","nuclei");
    runtime.setSettings(value=>({...value,nuclearProbability:.8}));expect(runtime.candidateResult("f1","nuclei")).toBeUndefined();
    await expect(runtime.acceptCandidates("f1","nuclei")).rejects.toThrow("一致する候補");expect(adapter.selectRevision).not.toHaveBeenCalled();
  });
  it("keeps a candidate when a save only declares the primary measure, and drops it on any other saved change",async()=>{
    // #257 RP-04: the declaration leaves detection and measurement unchanged (as the server's same_detection_spec).
    const {runtime,adapter}=fixture();await runtime.load("w");runtime.setSettings(value=>({...value,nuclearProbability:.7}));await runtime.preview("f1","nuclei");
    await runtime.savePrimaryOutcome({version:"1.0.0",metric:"area_px",region_set_id:"nuclei",channel_id:null});
    expect((runtime.specification().spec as {primary_outcome?:unknown}|null)?.primary_outcome).toMatchObject({metric:"area_px"});expect(runtime.candidateResult("f1","nuclei")?.revision).toBe("run1");
    await runtime.savePrimaryOutcome(null);expect(runtime.candidateResult("f1","nuclei")?.revision).toBe("run1");
    await runtime.saveResultDraft({figure:{metric:"area_px"}});expect(runtime.candidateResult("f1","nuclei")).toBeUndefined();
    await expect(runtime.acceptCandidates("f1","nuclei")).rejects.toThrow("一致する候補");expect(adapter.selectRevision).not.toHaveBeenCalled();
  });
  it("recovers an earlier version's run after a reload only when the server reports its specification current",async()=>{
    for(const [current,expected] of [[true,"server1"],[false,undefined]] as const){
      const {runtime,adapter,recipe}=fixture(true,{version:2,spec:null});
      const run:import("./api-adapter").WorkspaceRun={id:"earlier",workspace_id:"w",spec_version:1,spec_current:current,target:"nuclei",state:"succeeded",created:1,updated:1,steps:[{field_id:"f1",target:"nuclei",state:"succeeded",revision_id:"server1",job_id:"job",recipe,error:null}]};
      Object.assign(adapter,{listWorkspaceRuns:vi.fn(async()=>[run]),waitWorkspaceRun:vi.fn(async()=>run),readResult:vi.fn(async()=>result("server1"))});
      await runtime.load("w");expect(runtime.candidateResult("f1","nuclei")?.revision).toBe(expected);
    }
  });
  it("dismisses the last message without reloading the saved state",async()=>{
    const {runtime,adapter}=fixture();await runtime.load("w");adapter.draft.mockRejectedValueOnce(new Error("showcase_proposal_not_recorded"));
    await expect(runtime.requestProposal("free text","f1")).rejects.toThrow();expect(runtime.getSnapshot().error).not.toBe("");
    const restores=adapter.restore.mock.calls.length;runtime.dismissError();
    expect(runtime.getSnapshot().error).toBe("");expect(adapter.restore.mock.calls.length).toBe(restores);
  });
  it("initializes a separate manual cell ROI set without nuclei or signal segmentation",async()=>{
    const {runtime,adapter}=fixture(false);await runtime.load("w");await runtime.run("cell","f1");
    expect(adapter.run).toHaveBeenCalledTimes(1);expect(adapter.run.mock.calls[0][2]).toMatchObject({source:"manual",version:"1.0.0",region_set_id:"cell"});
  });
  it("refuses stale drawing identity and persists edit undo/redo through revision adoption",async()=>{
    const {runtime,adapter}=fixture();await runtime.load("w");
    await expect(runtime.editMask("f1","nuclei","stale","add",[[1,1],[2,1],[2,2]])).rejects.toThrow("解析版");expect(adapter.editMask).not.toHaveBeenCalled();
    await runtime.editMask("f1","nuclei","corrected","add",[[1,1],[2,1],[2,2]]);expect(runtime.canUndo("f1","nuclei")).toBe(true);
    await runtime.undo("f1","nuclei");expect(adapter.selectRevision).toHaveBeenLastCalledWith("w","corrected","f1");expect(runtime.canRedo("f1","nuclei")).toBe(true);
    await runtime.redo("f1","nuclei");expect(adapter.selectRevision).toHaveBeenLastCalledWith("w","edit1","f1");
  });
  it("never requests AI or starts analysis on import, but explicitly sent empty text applies and previews",async()=>{
    const {runtime,adapter,loadPreview}=fixture();await runtime.load("w");await runtime.importFiles([new File([new Uint8Array(4)],"view_c4.tif")]);expect(adapter.draft).not.toHaveBeenCalled();expect(adapter.run).not.toHaveBeenCalled();expect(loadPreview).toHaveBeenCalledWith("w",["f1"]);
    // Sending changes nothing and runs nothing; the researcher's 「適用して試行」 applies and previews (#284 W2).
    const answered=await runtime.requestProposal("","f1");expect(adapter.draft.mock.calls[0]).toBeDefined();expect(adapter.run).not.toHaveBeenCalled();expect(runtime.getSnapshot().proposal).toBeNull();
    await runtime.applyAnswer(answered.message.id,true,"f1");expect(adapter.run).toHaveBeenCalledTimes(1);expect(adapter.run.mock.calls[0][1]).toBe("f1");
  });
  it("names a rejected file, keeps its row with the reason, never resends it and never asks for an exclusion",async()=>{
    const {runtime,adapter}=fixture();await runtime.load("w");const ledger=withLedger(adapter);
    adapter.upload.mockImplementation(async(_workspace,field,_channels,_files,entry)=>{if(field.key.endsWith("-labels"))throw new ApiError("region_image_bit_depth_unsupported",422);return ledger.accept(entry!,`f-${field.key.split("/").at(-1)}`);});
    const files=["a_c1.tif","a_c4.tif","b_c4.tif","a-labels.tif","b-labels.tif"].map((name,index)=>new File([new Uint8Array([index])],name));
    const outcome=await runtime.importFiles(files);
    expect(outcome.registered.map(item=>item.fieldId).sort()).toEqual(["f-a","f-b"]);
    expect(outcome.rejected.map(item=>[item.names,item.code]).sort()).toEqual([[["a-labels.tif"],"region_image_bit_depth_unsupported"],[["b-labels.tif"],"region_image_bit_depth_unsupported"]]);
    expect(runtime.getSnapshot().error).toBe("");
    const keys=()=>adapter.upload.mock.calls.map(call=>call[1].key.split("/").at(-1));
    expect(keys().sort()).toEqual(["a","a-labels","b","b-labels"]);
    // Issues name the researcher's own files, not the private batch folder.
    expect(runtime.getSnapshot().importIssues).toContainEqual({kind:"missing_channel",field:"b",token:"c1"});
    expect(JSON.stringify(runtime.getSnapshot().importIssues)).not.toContain("import-");
    const rows=runtime.getSnapshot().intakeRows;
    expect(rows.map(row=>row.names[0]).sort()).toEqual(["a-labels.tif","b-labels.tif"]);
    // A 32-bit label image is a mask candidate, not missing data.
    expect(rows.every(row=>row.state==="rejected"&&row.mask&&row.code==="region_image_bit_depth_unsupported")).toBe(true);
    await runtime.importFiles([new File([new Uint8Array([9])],"c_c4.tif")]);
    expect(keys().sort()).toEqual(["a","a-labels","b","b-labels","c"]);
    expect(runtime.getSnapshot().intakeRows).toHaveLength(2);
    expect(adapter.excludeField).not.toHaveBeenCalled();
    // A restart keeps the names and the reason (the row is the record, #284 involvement 3).
    const restarted=fixture();restarted.adapter.restore.mockImplementation(adapter.restore.getMockImplementation()!);await restarted.runtime.load("w");
    expect(restarted.runtime.getSnapshot().intakeRows.map(row=>[row.names[0],row.code]).sort()).toEqual([["a-labels.tif","region_image_bit_depth_unsupported"],["b-labels.tif","region_image_bit_depth_unsupported"]]);
  });
  it("makes no field of a copy and names what it copies; the researcher can record it as a separate acquisition (#284 control A, synthetic bytes)",async()=>{
    const {runtime,adapter}=fixture();await runtime.load("w");const ledger=withLedger(adapter);
    adapter.upload.mockImplementation(async(_workspace,field,_channels,_files,entry)=>ledger.accept(entry!,`f-${field.key.split("/").at(-1)}`));
    const outcome=await runtime.importFiles([...bbbc007(),new File([new Uint8Array([1])],"BBBC007-a9-C01.tif")]);
    expect(outcome.registered.map(item=>item.names)).toEqual([["BBBC007-a9-C01.tif","BBBC007-a9-C02.tif"],["BBBC007-f9620-C01.tif","BBBC007-f9620-C02.tif"]]);
    expect(outcome.duplicates).toEqual([{id:expect.any(String),name:"BBBC007-a9-C01.tif",sameAs:"BBBC007-a9-C01.tif"}]);
    expect(adapter.upload).toHaveBeenCalledTimes(2);
    // A later selection of the same bytes is found against the registered field's inputs.
    const again=await runtime.importFiles([new File([new Uint8Array([2])],"BBBC007-a9-C02.tif")]);
    expect(again.duplicates).toHaveLength(1);expect(again.registered).toEqual([]);expect(adapter.upload).toHaveBeenCalledTimes(2);
    const separate=await runtime.addSeparately(outcome.duplicates[0].id);
    expect(separate.registered).toHaveLength(1);expect(adapter.upload).toHaveBeenCalledTimes(3);
    expect(adapter.registerImport.mock.calls.at(-1)?.[2]).toMatchObject({separate:true,names:["BBBC007-a9-C01.tif"]});
  });
  it("registers the unrelated field of a name conflict and never finds the conflict again (#284 control B, synthetic bytes)",async()=>{
    const {runtime,adapter}=fixture();await runtime.load("w");const ledger=withLedger(adapter);
    adapter.upload.mockImplementation(async(_workspace,field,_channels,_files,entry)=>ledger.accept(entry!,`f-${field.key.split("/").at(-1)}`));
    // The Issue's renamed copy has a9-C01's bytes: it is a copy, not a conflict (implementation plan §11.1).
    const copy=await runtime.importFiles([...bbbc007(),new File([new Uint8Array([1])],"BBBC007-a9_c01.tif")]);
    expect(copy.held).toEqual([]);expect(copy.duplicates.map(item=>item.name)).toEqual(["BBBC007-a9_c01.tif"]);expect(copy.registered).toHaveLength(2);
    // Different bytes under a9's C01 name: only a9 waits; f9620 is registered.
    const second=fixture();await second.runtime.load("w");const other=withLedger(second.adapter);
    second.adapter.upload.mockImplementation(async(_workspace,field,_channels,_files,entry)=>other.accept(entry!,`f-${field.key.split("/").at(-1)}`));
    const conflict=await second.runtime.importFiles([...bbbc007(),new File([new Uint8Array([7])],"BBBC007-a9_c01.tif")]);
    expect(conflict.held).toEqual([{names:["BBBC007-a9-C01.tif","BBBC007-a9_c01.tif","BBBC007-a9-C02.tif"],reason:"duplicate_channel"}]);
    expect(conflict.registered.map(item=>item.fieldId)).toEqual(["f-BBBC007-f9620"]);
    expect(second.runtime.getSnapshot().error).toBe("");
    // Choosing again with the right two files registers a9; the earlier conflict is not found again.
    const resolved=await second.runtime.importFiles(bbbc007().slice(0,2));
    expect(resolved.held).toEqual([]);expect(resolved.registered.map(item=>item.fieldId)).toEqual(["f-BBBC007-a9"]);
  });
  it("puts the registered fields of a group's cell where the researcher asked, though one image is refused (#284 control C, synthetic bytes)",async()=>{
    const design={version:"1.0.0",layout:"pair",control_group_id:"c",independence_confirmed:false,groups:[{id:"t",label:"処理"},{id:"c",label:"対照"}],runs:[{id:"r1",label:"実験回1"}],fields:{}};
    const {runtime,adapter,writeSpecification}=fixture(true,{version:1,spec:{channel_assignment_version:1,target:"nuclei",settings:defaultRuntimeSettings(),processing:null,measurement:null,experiment:design as never}});
    await runtime.load("w");const ledger=withLedger(adapter);
    adapter.upload.mockImplementation(async(_workspace,field,_channels,_files,entry)=>{if(field.key.includes("truncated"))throw new ApiError("unsupported_or_invalid_region_image",422);return ledger.accept(entry!,`f-${field.key.split("/").at(-1)}`);});
    const outcome=await runtime.importFiles([...bbbc007(),new File([new Uint8Array([5])],"test-truncated-DRAQ.tif")],"automatic",{run_id:"r1",group_id:"c",sample:null});
    expect(outcome.registered).toHaveLength(2);expect(outcome.rejected).toHaveLength(1);
    const placed=writeSpecification.mock.calls.at(-1)![1].spec!.experiment!.fields as Record<string,{group_id:string;run_id:string}>;
    expect(Object.keys(placed).sort()).toEqual(["f-BBBC007-a9","f-BBBC007-f9620"]);
    expect(Object.values(placed).every(value=>value.group_id==="c"&&value.run_id==="r1")).toBe(true);
    // The refused image keeps its target, so the n breakdown counts it in the control group; placed rows forget theirs.
    const rows=ledger.entries();
    expect(rows.find(entry=>!entry.field_id)?.intake).toMatchObject({state:"rejected",code:"unsupported_or_invalid_region_image",target:{group_id:"c"}});
    expect(rows.filter(entry=>entry.field_id&&entry.intake).every(entry=>!entry.intake!.target)).toBe(true);
  });
  it("keeps what was registered when the service stops answering, and places it after a restart",async()=>{
    const design={version:"1.0.0",layout:"single",control_group_id:null,independence_confirmed:false,groups:[{id:"g",label:"条件"}],runs:[{id:"r1",label:"実験回1"}],fields:{}};
    const {runtime,adapter,writeSpecification}=fixture(true,{version:1,spec:{channel_assignment_version:1,target:"nuclei",settings:defaultRuntimeSettings(),processing:null,measurement:null,experiment:design as never}});
    await runtime.load("w");const ledger=withLedger(adapter);
    let calls=0;adapter.upload.mockImplementation(async(_workspace,field,_channels,_files,entry)=>{if(++calls===2)throw new TypeError("Failed to fetch");return ledger.accept(entry!,`f-${field.key.split("/").at(-1)}`);});
    const failure=await runtime.importFiles(bbbc007(),"automatic",{run_id:"r1",group_id:"g",sample:null}).catch((error:unknown)=>error);
    expect(failure).toBeInstanceOf(IntakeInterrupted);
    expect((failure as IntakeInterrupted).outcome.registered.map(item=>item.fieldId)).toEqual(["f-BBBC007-a9"]);
    expect(runtime.getSnapshot().intakeRows).toEqual([expect.objectContaining({state:"pending",names:["BBBC007-f9620-C01.tif","BBBC007-f9620-C02.tif"]})]);
    expect(Object.keys(writeSpecification.mock.calls.at(-1)![1].spec!.experiment!.fields!)).toEqual(["f-BBBC007-a9"]);
    // The answer was lost but the field exists (the API joins it to the row); opening the workspace places it.
    ledger.accept(ledger.entries().find(entry=>!entry.field_id)!.id,"f-BBBC007-f9620");
    await runtime.reload();
    expect(Object.keys(writeSpecification.mock.calls.at(-1)![1].spec!.experiment!.fields!).sort()).toEqual(["f-BBBC007-a9","f-BBBC007-f9620"]);
    expect(runtime.getSnapshot().intakeRows).toEqual([]);
  });
  it("never sends an interrupted field with a later addition; adding it again resolves its own row (#284 independent review)",async()=>{
    const design={version:"1.0.0",layout:"pair",control_group_id:"c",independence_confirmed:false,groups:[{id:"t",label:"処理"},{id:"c",label:"対照"}],runs:[{id:"r1",label:"実験回1"}],fields:{}};
    const {runtime,adapter,writeSpecification}=fixture(true,{version:1,spec:{channel_assignment_version:1,target:"nuclei",settings:defaultRuntimeSettings(),processing:null,measurement:null,experiment:design as never}});
    await runtime.load("w");const ledger=withLedger(adapter);
    const a01=()=>[new File([new Uint8Array([40])],"A01_c1.tif")],a06=()=>[new File([new Uint8Array([41])],"A06_c1.tif")];
    // 対照: A01 is registered, a9's upload meets no answer (its row stays pending), f9620 was never reached (no row).
    let calls=0;adapter.upload.mockImplementation(async(_workspace,field,_channels,_files,entry)=>{if(++calls===2)throw new TypeError("Failed to fetch");return ledger.accept(entry!,`f-${field.key.split("/").at(-1)}`);});
    await runtime.importFiles([...bbbc007(),...a01()],"automatic",{run_id:"r1",group_id:"c",sample:null}).catch(()=>undefined);
    const pending=ledger.entries().find(entry=>!entry.field_id)!;
    expect(pending.intake).toMatchObject({state:"pending",names:["BBBC007-a9-C01.tif","BBBC007-a9-C02.tif"],target:{group_id:"c"}});
    expect(ledger.entries().filter(entry=>entry.intake).map(entry=>entry.intake!.names[0]).sort()).toEqual(["A01_c1.tif","BBBC007-a9-C01.tif"]);
    // The next images go to 処理. Nothing of the interrupted addition goes with them: not a9, not the unreached f9620.
    const sent=adapter.upload.mock.calls.length;
    const next=await runtime.importFiles(a06(),"automatic",{run_id:"r1",group_id:"t",sample:null});
    expect(next.registered.map(item=>item.fieldId)).toEqual(["f-A06"]);
    expect(adapter.upload).toHaveBeenCalledTimes(sent+1);
    expect(ledger.entries().find(entry=>entry.id===pending.id)?.field_id).toBeNull();
    // Adding them again (the list still holds them, with their cell): neither is a copy of itself, a9 resolves its
    // own row and f9620 gets its first.
    const rows=ledger.entries().length;
    const again=await runtime.importFiles(bbbc007(),"automatic",{run_id:"r1",group_id:"c",sample:null});
    expect(again.duplicates).toEqual([]);
    expect(again.registered.map(item=>item.fieldId).sort()).toEqual(["f-BBBC007-a9","f-BBBC007-f9620"]);
    expect(adapter.upload.mock.calls.find(call=>(call[1] as {key:string}).key.endsWith("BBBC007-a9")&&call[4]===pending.id)).toBeTruthy();
    expect(ledger.entries()).toHaveLength(rows+1);
    const fields=writeSpecification.mock.calls.at(-1)![1].spec!.experiment!.fields as Record<string,{group_id:string}>;
    expect(Object.fromEntries(Object.entries(fields).map(([id,value])=>[id,value.group_id]))).toEqual({"f-BBBC007-a9":"c","f-BBBC007-f9620":"c","f-A01":"c","f-A06":"t"});
  });
  it("images added again after a restart resolve the row their names left pending, so it is not counted as missing",async()=>{
    const {runtime,adapter}=fixture();await runtime.load("w");const ledger=withLedger(adapter);
    adapter.upload.mockImplementationOnce(async()=>{throw new TypeError("Failed to fetch");});
    await runtime.importFiles(bbbc007().slice(0,2)).catch(()=>undefined);
    const pending=ledger.entries().find(entry=>!entry.field_id)!;
    // A restart: this session no longer holds the files; the researcher chooses the same images again.
    const restarted=createWorkspaceRuntime({adapter:adapter as never,loadPreview:vi.fn(async()=>({workspaceId:"w",title:"fixture",channels:[],fields:[]})) as never,releasePreview:vi.fn(),readSpecification:async()=>({version:0,spec:null}),writeSpecification:vi.fn(async(_id:string,value:import("./use-workspace-runtime").RuntimeSpecification)=>({...value,version:1}))});
    await restarted.load("w");
    adapter.upload.mockImplementation(async(_workspace,field,_channels,_files,entry)=>ledger.accept(entry!,`f-${field.key.split("/").at(-1)}`));
    const rows=ledger.entries().length;
    const outcome=await restarted.importFiles(bbbc007().slice(0,2));
    expect(outcome.registered).toHaveLength(1);
    expect(ledger.entries()).toHaveLength(rows);
    expect(ledger.entries().find(entry=>entry.id===pending.id)?.field_id).toBe("f-BBBC007-a9");
    expect(restarted.getSnapshot().intakeRows).toEqual([]);
  });
  it("records a folder-relative name too long for a row by its file name, without stopping the addition",async()=>{
    const {runtime,adapter}=fixture();await runtime.load("w");const ledger=withLedger(adapter);
    adapter.upload.mockImplementation(async(_workspace,field,_channels,_files,entry)=>ledger.accept(entry!,`f-${field.key.split("/").at(-1)}`));
    const deep=new File([new Uint8Array([50])],"deep_c1.tif");Object.defineProperty(deep,"webkitRelativePath",{value:`${"階層/".repeat(90)}deep_c1.tif`});
    const outcome=await runtime.importFiles([deep,new File([new Uint8Array([51])],"near_c1.tif")]);
    expect(outcome.registered).toHaveLength(2);
    expect(ledger.entries().map(entry=>entry.intake?.names).filter(Boolean)).toEqual(expect.arrayContaining([["deep_c1.tif"],["near_c1.tif"]]));
  });
  it("replaces a refused row in place, removes a row on request, and reports a full record and an empty choice",async()=>{
    const {runtime,adapter}=fixture();await runtime.load("w");const ledger=withLedger(adapter);
    let broken=true;adapter.upload.mockImplementation(async(_workspace,field,_channels,_files,entry)=>{if(broken)throw new ApiError("unsupported_or_invalid_region_image",422);return ledger.accept(entry!,`f-${field.key.split("/").at(-1)}`);});
    const first=await runtime.importFiles(bbbc007().slice(0,2));const entry=first.rejected[0].entry!;
    broken=false;const replaced=await runtime.replaceImport(entry,bbbc007().slice(0,2).map((file,index)=>new File([new Uint8Array([30+index])],file.name)));
    expect(replaced.registered).toHaveLength(1);
    expect(adapter.upload.mock.calls.at(-1)?.[4]).toBe(entry);
    expect(ledger.entries().filter(value=>value.id===entry)).toEqual([expect.objectContaining({field_id:"f-BBBC007-a9",intake:{names:["BBBC007-a9-C01.tif","BBBC007-a9-C02.tif"],state:"registered"}})]);
    broken=true;const refused=await runtime.importFiles([new File([new Uint8Array([8])],"x_c1.tif")]);
    await runtime.cancelImport(refused.rejected[0].entry!);
    expect(runtime.getSnapshot().intakeRows).toEqual([]);
    ledger.fill(100);broken=false;
    const full=await runtime.importFiles([new File([new Uint8Array([6])],"y_c1.tif")]);
    expect(full.rejected).toEqual([{entry:null,names:["y_c1.tif"],code:"ledger_full"}]);expect(full.registered).toEqual([]);
    expect((await runtime.importFiles([])).empty).toBe("nothing");
    const text=await runtime.importFiles([new File(["notes"],"readme.txt")]);
    expect(text).toMatchObject({empty:"no_images",skipped:[{name:"readme.txt"}]});
  });
  it("refuses a field above the size limit without sending it, and sends the other fields",async()=>{
    const {runtime,adapter}=fixture();await runtime.load("w");const ledger=withLedger(adapter);
    adapter.upload.mockImplementation(async(_workspace,field,_channels,_files,entry)=>ledger.accept(entry!,`f-${field.key.split("/").at(-1)}`));
    const large=new File([new Uint8Array([4])],"large_c1.tif");Object.defineProperty(large,"size",{value:257*1024*1024});
    const outcome=await runtime.importFiles([large,new File([new Uint8Array([5])],"small_c1.tif")]);
    expect(outcome.rejected).toEqual([{entry:expect.any(String),names:["large_c1.tif"],code:"field_upload_limit"}]);
    expect(outcome.registered.map(item=>item.names)).toEqual([["small_c1.tif"]]);
    expect(adapter.upload).toHaveBeenCalledTimes(1);
  });
  it("keeps the conversation per workspace, applies only on request, never applies a refused answer, and continues from the last applicable one (#284 W2)",async()=>{
    const {runtime,adapter,writeSpecification}=fixture();
    const saved=[{...message("old"),text:"前の質問",reply:"前の回答"}];
    adapter.listMessages.mockResolvedValueOnce(saved);
    await runtime.load("w");
    expect(runtime.getSnapshot().messages).toEqual(saved);
    // A saved answer is shown but cannot be applied without sending it again (no model call: answered from the record).
    expect(runtime.canApply("old")).toBe(false);
    const writes=writeSpecification.mock.calls.length,settings=runtime.getSnapshot().settings;
    const first=await runtime.requestProposal("DRAQ を核染色にする","f1");
    expect(adapter.run).not.toHaveBeenCalled();expect(runtime.getSnapshot().settings).toEqual(settings);expect(writeSpecification.mock.calls.length).toBeLessThanOrEqual(writes+1);
    expect(runtime.canApply(first.message.id)).toBe(true);
    // A refused answer is shown with its reasons; its settings are never applied.
    const refused={...message("refused"),applicable:false,reasons:["proposal_channels_mismatch"],reply:"ch1 は DRAQ"};
    adapter.draft.mockResolvedValueOnce({proposal:null,message:refused} as never);
    await runtime.requestProposal("チャンネル名を教えて。まだ測定しない","f1");
    expect(runtime.canApply("refused")).toBe(false);
    await expect(runtime.applyAnswer("refused",true,"f1")).rejects.toThrow("再送");
    expect(adapter.run).not.toHaveBeenCalled();
    // The next message continues from the last applicable answer and the message that produced it.
    adapter.draft.mockImplementationOnce(async()=>({proposal:null,message:{...message("next"),applicable:false}}) as never);
    await runtime.requestProposal("正常な全視野の核を数えて","f1");
    expect((adapter.draft.mock.calls.at(-1) as unknown[]|undefined)?.[3]).toMatchObject({previous_goal:"DRAQ を核染色にする",previous_proposal:expect.objectContaining({recipe:"nuclear-intensity"})});
    expect(runtime.getSnapshot().messages.map(value=>value.id)).toEqual(["old","m1","refused","next"]);
    // Applying is the researcher's action and is recorded on the message.
    await runtime.applyAnswer(first.message.id,false,"f1");
    expect(adapter.recordEffect).toHaveBeenCalledWith("w","m1","settings");expect(adapter.run).not.toHaveBeenCalled();
    expect(runtime.getSnapshot().messages.find(value=>value.id==="m1")?.effect).toBe("settings");
    // A failed request re-reads the record, so the failed message shows its reasons.
    const failed={...message("failed"),state:"failed" as const,applicable:null,reasons:["proposal_shape_invalid"]};
    adapter.draft.mockRejectedValueOnce(new ApiError("proposal_rejected",502,["proposal_shape_invalid"]));
    adapter.listMessages.mockResolvedValueOnce([...runtime.getSnapshot().messages,failed]);
    await expect(runtime.requestProposal("x","f1")).rejects.toMatchObject({reasons:["proposal_shape_invalid"]});
    expect(runtime.getSnapshot().messages.at(-1)).toEqual(failed);
    // Another workspace starts with no conversation and no previous answer.
    runtime.newWorkspace();
    expect(runtime.getSnapshot().messages).toEqual([]);expect(runtime.canApply("m1")).toBe(false);
  });
  it("leaves no 準備中 behind when the request does not start (#284 W8)",async()=>{
    const {runtime,adapter,writeSpecification}=fixture();
    const startWorkspaceRun=vi.fn();
    Object.assign(adapter,{startWorkspaceRun,waitWorkspaceRun:vi.fn(),acceptWorkspaceRun:vi.fn(),listWorkspaceRuns:vi.fn(async()=>[])});
    await runtime.load("w");
    // The settings changed, so the run saves them first; that save meets no connection.
    runtime.setSettings(previous=>({...previous,nuclearProbability:.4}));
    writeSpecification.mockRejectedValueOnce(new Error("offline"));
    await expect(runtime.run("nuclei")).rejects.toThrow("offline");
    expect(startWorkspaceRun).not.toHaveBeenCalled();
    expect(runtime.getSnapshot().progress).toEqual({});
  });
  it("measures in fields, adopts the fields that succeeded when another fails, and marks the failed one (#284 W8)",async()=>{
    const {runtime,adapter,recipe,loadPreview}=fixture();
    const preview=loadPreview.getMockImplementation()!;
    loadPreview.mockImplementation(async(...args:Parameters<typeof preview>)=>{const value=await preview(...args);return {...value,fields:[value.fields[0],{...value.fields[0],id:"f2",label:"View 2"}]};});
    const restore=adapter.restore.getMockImplementation()!;
    adapter.restore.mockImplementation(async(...args:Parameters<typeof restore>)=>{const value=await restore(...args);return {...value,fields:[...value.fields,{...value.fields[0],id:"f2"}],selection:{version:1,entries:[...value.selection.entries,{id:"f2",field_id:"f2",revision_id:null}]}} as unknown as typeof value;});
    type Run=import("./api-adapter").WorkspaceRun;type Step=Run["steps"][number];
    const step=(field_id:string,state:Step["state"],extra:Partial<Step>={}):Step=>({field_id,target:"nuclei",state,revision_id:state==="failed"?null:`rev-${field_id}`,job_id:null,recipe:state==="failed"?null:recipe,error:state==="failed"?"field_image_unreadable":null,...extra});
    const first:Run={id:"both",workspace_id:"w",spec_version:1,target:"nuclei",state:"failed",created:1,updated:1,steps:[step("f1","succeeded"),step("f2","failed")]};
    const again:Run={...first,id:"f1-only",state:"succeeded",steps:[step("f1","reused")]};
    const seen:Array<Record<string,string>>=[];
    const startWorkspaceRun=vi.fn(async(_w:string,body:{field_ids:string[]})=>body.field_ids.length===2?{...first,state:"running" as const,steps:[step("f1","queued"),step("f2","pending")]}:again);
    const waitWorkspaceRun=vi.fn(async(_w:string,id:string,onState?:(run:Run)=>void)=>{const run=id==="both"?first:again;if(id==="both"){onState?.({...run,state:"running",steps:[step("f1","succeeded"),step("f2","queued")]});seen.push({...runtime.getSnapshot().progress});}return run;});
    const acceptWorkspaceRun=vi.fn(async()=>({...again,state:"adopted" as const}));
    Object.assign(adapter,{startWorkspaceRun,waitWorkspaceRun,acceptWorkspaceRun,listWorkspaceRuns:vi.fn(async()=>[]),readResult:vi.fn(async(revision:string,field:string)=>result(revision,field))});
    await runtime.load("w");
    await runtime.run("nuclei");
    // While running, each field has its own state and the header counts fields (not field × target steps).
    expect(seen[0]).toEqual({f1:"候補を確認",f2:"検出中"});
    expect(startWorkspaceRun.mock.calls.map(call=>call[1].field_ids)).toEqual([["f1","f2"],["f1"]]);
    expect(acceptWorkspaceRun).toHaveBeenCalledWith("w","f1-only");
    expect(runtime.getSnapshot().progress).toEqual({f2:"失敗"});
    expect(runtime.getSnapshot().error).toContain("View 2");
  });
  it("keeps following a run while the connection is lost for a moment, and reports a longer loss",async()=>{
    const {createApiAdapter}=await import("./api-adapter");
    const run={id:"r",state:"succeeded",steps:[]};let calls=0;
    const request=vi.fn(async()=>{if(++calls<=2)throw new TypeError("Failed to fetch");return run;});
    const adapter=createApiAdapter({request:request as never,wait:async()=>{}});
    const retries:number[]=[];
    expect(await adapter.waitWorkspaceRun("w","r",undefined,attempt=>retries.push(attempt))).toEqual(run);
    expect(retries).toEqual([1,2]);
    const lost=createApiAdapter({request:vi.fn(async()=>{throw new TypeError("Failed to fetch");}) as never,wait:async()=>{}});
    await expect(lost.waitWorkspaceRun("w","r")).rejects.toThrow("Failed to fetch");
    const refused=createApiAdapter({request:vi.fn(async()=>{throw new ApiError("workspace_not_found",404);}) as never,wait:async()=>{}});
    await expect(refused.waitWorkspaceRun("w","r",undefined,()=>{throw new Error("not retried");})).rejects.toMatchObject({code:"workspace_not_found"});
  });
  it("retains separate file identities when later images have the same filename",async()=>{
    const {runtime,adapter}=fixture();await runtime.load("w");
    await runtime.importFiles([new File([new Uint8Array([1])],"view_c4.tif")]);
    await runtime.importFiles([new File([new Uint8Array([2])],"view_c4.tif")]);
    expect(adapter.upload).toHaveBeenCalledTimes(2);expect(adapter.draft).not.toHaveBeenCalled();expect(adapter.run).not.toHaveBeenCalled();
  });
  it("allows a text-only consultation in a new workspace without analysis",async()=>{
    const {runtime,adapter}=fixture();runtime.newWorkspace();adapter.getChannelAssignments.mockResolvedValue({version:0,assignments:[]});await ask(runtime,"Plan an experiment");
    expect(adapter.create).toHaveBeenCalledTimes(1);expect(adapter.draft).toHaveBeenCalledTimes(1);expect(adapter.run).not.toHaveBeenCalled();expect(runtime.specification()).toMatchObject({version:2,spec:{processing:null,metrics:[],statistics:{method:{kind:"descriptive"}},channel_assignment_version:0}});expect(runtime.canUndoProposal()).toBe(true);
  });
  it("persists manual settings with channel identity and reloads the same specification",async()=>{
    const {runtime}=fixture();await runtime.load("w");runtime.setSettings(value=>({...value,nuclearProbability:.71}));
    await runtime.saveSettings("nuclei");expect(runtime.specification()).toMatchObject({version:1,spec:{target:"nuclei",channel_assignment_version:1,settings:{nuclearProbability:.71},measurement:{mode:"raw_intensity"}}});
    runtime.setSettings(value=>({...value,nuclearProbability:.2}));await runtime.reload();expect(runtime.getSnapshot().settings.nuclearProbability).toBe(.71);
  });
  it("blocks stale cross-tab assignments before analysis submission",async()=>{
    const {runtime,adapter}=fixture();await runtime.load("w");adapter.getChannelAssignments.mockResolvedValue({version:2,assignments:[]});
    await expect(runtime.run("nuclei","f1")).rejects.toThrow("染色設定");expect(adapter.run).not.toHaveBeenCalled();
  });  it("compares every detector field and ignores object property ordering",()=>{
    const recipe=runtimeRecipe("nuclei",nuclear,defaultRuntimeSettings(),{},null);
    expect(sameRuntimeRecipe(recipe,{...recipe,detector:{...recipe.detector!,nms:.1}} as Recipe)).toBe(false);
    expect(sameRuntimeRecipe(recipe,Object.fromEntries(Object.entries(recipe).reverse()) as unknown as Recipe)).toBe(true);
  });
  it("treats the API's null nucleolar parent of a nucleolar recipe as the omitted client field",()=>{
    const recipe={...runtimeRecipe("nuclei",nuclear,defaultRuntimeSettings(),{},null),region_set_id:"nucleoli"} as Recipe;
    expect(sameRuntimeRecipe({...recipe,nucleolar_revision_id:null} as unknown as Recipe,recipe)).toBe(true);
    expect(sameRuntimeRecipe({...recipe,nucleolar_revision_id:"r2"},recipe)).toBe(false);
  });
});
describe("connection loss and reconnection (#284 W9)",()=>{
  const singleDesign={version:"1.0.0",layout:"single",control_group_id:null,independence_confirmed:false,groups:[{id:"g",label:"条件"}],runs:[{id:"r1",label:"実験回1"}],fields:{}};
  const withDesign=()=>fixture(true,{version:1,spec:{channel_assignment_version:1,target:"nuclei",settings:defaultRuntimeSettings(),processing:null,measurement:null,experiment:singleDesign as never}});
  const target={run_id:"r1",group_id:"g",sample:null};
  const unreachable=()=>new ApiError("api_unreachable",0);
  const placed=(writeSpecification:ReturnType<typeof fixture>["writeSpecification"])=>Object.keys(writeSpecification.mock.calls.at(-1)?.[1].spec!.experiment!.fields??{}).sort();
  it("unsent: the row stays pending with its names, and reconnecting re-reads it without sending anything",async()=>{
    const {runtime,adapter,writeSpecification}=withDesign();await runtime.load("w");const ledger=withLedger(adapter);
    let calls=0;adapter.upload.mockImplementation(async(_workspace,field,_channels,_files,entry)=>{if(++calls===2)throw unreachable();return ledger.accept(entry!,`f-${field.key.split("/").at(-1)}`);});
    const failure=await runtime.importFiles(bbbc007(),"automatic",target).catch((error:unknown)=>error);
    expect(failure).toBeInstanceOf(IntakeInterrupted);
    // The connection failure reads as one, not as the browser's "Failed to fetch".
    expect(runtime.getSnapshot().error).toBe("APIに接続できません。解析サーバーの起動と接続先を確認してください。");
    const sent=adapter.upload.mock.calls.length;
    await runtime.reconnected();
    expect(adapter.upload).toHaveBeenCalledTimes(sent);
    expect(runtime.getSnapshot().intakeRows).toEqual([expect.objectContaining({state:"pending",names:["BBBC007-f9620-C01.tif","BBBC007-f9620-C02.tif"]})]);
    expect(placed(writeSpecification)).toEqual(["f-BBBC007-a9"]);
    expect(runtime.getSnapshot().error).toBe("");
  });
  it("answer lost after sending: reconnecting shows the row as registered and places it, with no second upload",async()=>{
    const {runtime,adapter,writeSpecification}=withDesign();await runtime.load("w");const ledger=withLedger(adapter);
    let calls=0;adapter.upload.mockImplementation(async(_workspace,field,_channels,_files,entry)=>{const saved=ledger.accept(entry!,`f-${field.key.split("/").at(-1)}`);if(++calls===2)throw unreachable();return saved;});
    await runtime.importFiles(bbbc007(),"automatic",target).catch(()=>undefined);
    await runtime.reconnected();
    expect(runtime.getSnapshot().intakeRows).toEqual([]);
    expect(placed(writeSpecification)).toEqual(["f-BBBC007-a9","f-BBBC007-f9620"]);
    expect(adapter.upload).toHaveBeenCalledTimes(2);
    expect(ledger.entries().filter(entry=>entry.field_id?.startsWith("f-BBBC007"))).toHaveLength(2);
  });
  it("reconnected: choosing the same images again for the pending row sends them under that row, so the record does not grow",async()=>{
    const {runtime,adapter,writeSpecification}=withDesign();await runtime.load("w");const ledger=withLedger(adapter);
    let down=true;adapter.upload.mockImplementation(async(_workspace,field,_channels,_files,entry)=>{if(down&&field.key.includes("f9620"))throw unreachable();return ledger.accept(entry!,`f-${field.key.split("/").at(-1)}`);});
    await runtime.importFiles(bbbc007(),"automatic",target).catch(()=>undefined);
    const pending=ledger.entries().find(entry=>!entry.field_id)!,rows=ledger.entries().length;
    down=false;await runtime.reconnected();
    // The same bytes as the files this session still holds for the row: not "same content" as themselves.
    const replaced=await runtime.replaceImport(pending.id,bbbc007().slice(2));
    expect(replaced.duplicates).toEqual([]);expect(replaced.registered).toHaveLength(1);
    expect(adapter.upload.mock.calls.filter(call=>call[4]===pending.id)).toHaveLength(2);
    expect(ledger.entries()).toHaveLength(rows);
    expect(ledger.entries().find(entry=>entry.id===pending.id)?.field_id).toBe("f-BBBC007-f9620");
    expect(placed(writeSpecification)).toEqual(["f-BBBC007-a9","f-BBBC007-f9620"]);
  });
  it.each([
    ["an ended session that a new session did not resolve (401)",new ApiError("session_required",401)],
    ["the wrong origin (403)",new ApiError("local_origin_required",403)],
  ])("%s interrupts the addition; the rows stay pending, never refused as images",async(_label,error)=>{
    const {runtime,adapter}=withDesign();await runtime.load("w");const ledger=withLedger(adapter);
    adapter.upload.mockImplementation(async()=>{throw error;});
    const failure=await runtime.importFiles(bbbc007().slice(0,2),"automatic",target).catch((value:unknown)=>value);
    expect(failure).toBeInstanceOf(IntakeInterrupted);
    expect((failure as IntakeInterrupted).outcome.rejected).toEqual([]);
    expect(ledger.entries().find(entry=>!entry.field_id)?.intake).toMatchObject({state:"pending",names:["BBBC007-a9-C01.tif","BBBC007-a9-C02.tif"]});
    expect(adapter.recordImport).not.toHaveBeenCalled();
    expect(adapter.upload).toHaveBeenCalledTimes(1); // the runtime never repeats it; the API client retries a 401 once
  });
  it("opens the workspace when the first load met no answer",async()=>{
    const {runtime,adapter}=fixture();
    adapter.restore.mockRejectedValueOnce(unreachable());
    await expect(runtime.load("w")).rejects.toMatchObject({code:"api_unreachable"});
    await runtime.reconnected();
    expect(runtime.getSnapshot().data?.workspaceId).toBe("w");
    expect(runtime.getSnapshot().error).toBe("");
  });
});
describe("the kind of request (#284 W7)",()=>{
  type Draft=ValidatedProposal["draft"];
  async function answered(intent:Draft["intent"],extra:Partial<Draft>={},links:Array<{token:string;field_id:string}>=[]){
    const context=fixture();await context.runtime.load("w");
    const base=(await (context.adapter.draft.getMockImplementation() as unknown as ()=>Promise<{proposal:ValidatedProposal}>)()).proposal;
    const proposal={...base,draft:{...base.draft,intent,...extra}};
    context.adapter.draft.mockResolvedValueOnce({proposal,message:message(`m-${intent}`),fields:links} as never);
    const settings=context.runtime.getSnapshot().settings,writes=context.writeSpecification.mock.calls.length;
    const response=await context.runtime.requestProposal("依頼","f1");
    return {...context,response,settings,writes};
  }
  it.each(["answer","settings","run"] as const)("an answer of intent %s changes no setting and runs nothing until the researcher acts",async intent=>{
    const {runtime,adapter,response,settings,writes,writeSpecification}=await answered(intent,{scope:intent==="run"?"all":null});
    expect(adapter.run).not.toHaveBeenCalled();expect(adapter.recordEffect).not.toHaveBeenCalled();
    expect(runtime.getSnapshot().settings).toEqual(settings);expect(runtime.getSnapshot().proposal).toBeNull();
    // Sending saves the current specification at most once, as before (#284 W2); the answer adds nothing to it.
    expect(writeSpecification.mock.calls.length).toBeLessThanOrEqual(writes+1);
    const id=response.message.id;
    expect(runtime.answerOf(id)?.intent).toBe(intent);
    // The actions follow the intent: none for a question, 「設定を適用」 for settings, 「適用して実行」 for a run.
    expect([runtime.canApply(id),runtime.canTry(id),runtime.canRun(id,"f1")]).toEqual(
      intent==="answer"?[false,false,false]:intent==="settings"?[true,false,false]:[true,false,true]);
  });
  it("runs a run request only from 「適用して実行」, as candidates on its target fields",async()=>{
    const {runtime,adapter,response}=await answered("run",{scope:"selected"});
    expect(runtime.runTargets(response.message.id,"f1")).toEqual({scope:"selected",fields:[{id:"f1",label:"View"}],excluded:0});
    expect(runtime.runTargets(response.message.id,undefined)?.fields).toEqual([]);
    await runtime.runAnswer(response.message.id,"f1");
    expect(adapter.run).toHaveBeenCalledTimes(1);expect(adapter.run.mock.calls[0][1]).toBe("f1");
    // Candidates only: adopting them stays the researcher's.
    expect(adapter.run.mock.calls[0][5]).toEqual({adopt:false});
    expect(adapter.recordEffect).toHaveBeenCalledWith("w",response.message.id,"run");
  });
  it("waits for the researcher's nuclear stain before a proposed nuclear channel is applied or run (#284 判定 2, 受入 5)",async()=>{
    // The Issue's input: DRAQ's stain is known from the file name, its role is not recorded yet.
    const context=fixture();let role:"nuclear"|null=null;
    // GFP has no role either; the answer proposes to leave it unused.
    const channels=()=>[{id:"c4",label:"DRAQ",stain:"DRAQ",role},{id:"c5",label:"GFP",stain:"GFP",role:role?"measure" as const:null}];
    context.loadPreview.mockImplementation(async()=>({workspaceId:"w",title:"fixture",channels:channels(),fields:[{id:"f1",label:"View",width:10,height:10,channels:channels(),previews:{},results:{}}]}) as never);
    const saved:unknown[]=[];
    (context.adapter as unknown as {saveChannelAssignments:unknown}).saveChannelAssignments=vi.fn(async(_workspace:string,body:unknown)=>{saved.push(body);role="nuclear";});
    await context.runtime.load("w");
    const base=(await (context.adapter.draft.getMockImplementation() as unknown as ()=>Promise<{proposal:ValidatedProposal}>)()).proposal;
    const proposal={...base,needs_confirmation:["c4"],draft:{...base.draft,intent:"run" as const,scope:"all" as const,channels:[{token:"c4",stain:"DRAQ",role:"nuclear"},{token:"c5",stain:"GFP",role:"unused"}]}} as ValidatedProposal;
    context.adapter.draft.mockResolvedValueOnce({proposal,message:message("m-run"),fields:[]} as never);
    const {runtime,adapter}=context,id=(await runtime.requestProposal("全視野で核を数えて","f1")).message.id;
    // Until the researcher names the nuclear stain, nothing can be applied or run, and the screen says what is missing.
    expect(runtime.confirmationOf(id,"f1")).toEqual([{channel:"c4",label:"DRAQ"}]);
    expect([runtime.canApply(id,"f1"),runtime.canRun(id,"f1")]).toEqual([false,false]);
    await runtime.confirmNuclear(id,"c4","f1");
    // Recording the stain's role is the researcher's own choice (as in 染色対応): no settings applied, nothing run.
    // Only the named channel's role is recorded as chosen: GFP is measured, not 未使用 as the answer proposed.
    expect(saved).toEqual([expect.objectContaining({assignments:[{channel_id:"c4",stain:"DRAQ",role:"nuclear"},{channel_id:"c5",stain:"GFP",role:"measure"}]})]);
    expect(adapter.run).not.toHaveBeenCalled();expect(adapter.recordEffect).not.toHaveBeenCalled();
    expect(runtime.confirmationOf(id,"f1")).toEqual([]);
    expect([runtime.canApply(id,"f1"),runtime.canRun(id,"f1")]).toEqual([true,true]);
    await runtime.runAnswer(id,"f1");
    expect(adapter.run).toHaveBeenCalledTimes(1);expect(adapter.recordEffect).toHaveBeenCalledWith("w",id,"run");
    await expect(runtime.confirmNuclear(id,"c9","f1")).rejects.toThrow();
  });
  it("judges an answer by the field it was made for, also while a field of other channels is selected",async()=>{
    // f1 holds DRAQ (no role yet); f2 is another acquisition with other channels.
    const context=fixture();let role:"nuclear"|null=null;
    const field=(id:string,channel:{id:string;label:string;stain:string;role:"nuclear"|null})=>({id,label:id,width:10,height:10,channels:[channel],previews:{},results:{}});
    context.loadPreview.mockImplementation(async()=>({workspaceId:"w",title:"fixture",channels:[],fields:[field("f1",{id:"c4",label:"DRAQ",stain:"DRAQ",role}),field("f2",{id:"c9",label:"DNA",stain:"DNA",role:null})]}) as never);
    const saved:Array<{assignments:unknown}>=[];
    (context.adapter as unknown as {saveChannelAssignments:unknown}).saveChannelAssignments=vi.fn(async(_workspace:string,body:{assignments:unknown})=>{saved.push(body);role="nuclear";});
    await context.runtime.load("w");
    const base=(await (context.adapter.draft.getMockImplementation() as unknown as ()=>Promise<{proposal:ValidatedProposal}>)()).proposal;
    const proposal={...base,needs_confirmation:["c4"],draft:{...base.draft,intent:"settings" as const,channels:[{token:"c4",stain:"DRAQ",role:"nuclear"}]}} as ValidatedProposal;
    context.adapter.draft.mockResolvedValueOnce({proposal,message:{...message("m-f1"),field_id:"f1"},fields:[]} as never);
    const {runtime,adapter}=context,id=(await runtime.requestProposal("DRAQ を核染色にする","f1")).message.id;
    // With f2 selected, the answer still waits for f1's nuclear stain, and naming it records f1's channels.
    expect(runtime.confirmationOf(id,"f2")).toEqual([{channel:"c4",label:"DRAQ"}]);
    expect(runtime.canApply(id,"f2")).toBe(false);
    await runtime.confirmNuclear(id,"c4","f2");
    expect(saved.map(value=>value.assignments)).toEqual([[{channel_id:"c4",stain:"DRAQ",role:"nuclear"}]]);
    expect(runtime.canApply(id,"f2")).toBe(true);
    await runtime.applyAnswer(id,false,"f2");
    expect(adapter.recordEffect).toHaveBeenCalledWith("w",id,"settings");
    // The next message about f2 does not continue a proposal whose channels f2 does not have.
    await runtime.requestProposal("この視野の核を数えて","f2");
    expect((adapter.draft.mock.calls.at(-1) as unknown[]|undefined)?.[3]).toMatchObject({previous_goal:"",previous_proposal:null,field_id:"f2"});
  });
  it("refuses to run a question's answer or a settings request",async()=>{
    for(const intent of ["answer","settings"] as const){
      const {runtime,adapter,response}=await answered(intent);
      await expect(runtime.runAnswer(response.message.id,"f1")).rejects.toThrow();
      expect(adapter.run).not.toHaveBeenCalled();expect(runtime.runTargets(response.message.id,"f1")).toBeNull();
    }
  });
  it("offers a question's choices and keeps no settings to continue from",async()=>{
    const choices=[{question:"核染色のチャンネル",options:["核染色は DRAQ","核染色は GFP"]}];
    const {runtime,adapter,response}=await answered("answer",{recipe:"none",choices});
    expect(runtime.answerOf(response.message.id)?.choices).toEqual(choices);
    await runtime.requestProposal("核染色は DRAQ","f1");
    expect((adapter.draft.mock.calls.at(-1) as unknown[]|undefined)?.[3]).toMatchObject({previous_goal:"",previous_proposal:null});
  });
  it("holds the answer's assignment suggestions by field, without saving them",async()=>{
    const assignments=[{field:"f1",run:"Rep1",group:"未処理"},{field:"f9",run:"Rep1",group:"ActD"},{field:"f1",run:"Rep · 1",group:"x"}];
    const {runtime,writeSpecification,writes}=await answered("answer",{recipe:"none",assignments},[{token:"f1",field_id:"f1"}]);
    // Only fields the response names (an unknown identifier is dropped) and labels the design can hold; nothing is
    // written to the design. The experiment table shows them only for its unassigned fields.
    expect(runtime.getSnapshot().assignmentSuggestions).toEqual([{fieldId:"f1",runLabel:"Rep1",groupLabel:"未処理",source:"ai"}]);
    expect(writeSpecification.mock.calls.length).toBeLessThanOrEqual(writes+1);
    expect(writeSpecification.mock.calls.every(call=>!JSON.stringify(call[1]).includes("Rep1"))).toBe(true);
    runtime.newWorkspace();expect(runtime.getSnapshot().assignmentSuggestions).toEqual([]);
  });
});
