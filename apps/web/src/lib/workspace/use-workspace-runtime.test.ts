import {describe, expect, it, vi} from "vitest";
import {createWorkspaceRuntime, defaultRuntimeSettings, runtimeRecipe, sameRuntimeRecipe} from "./use-workspace-runtime";
import type {createApiAdapter, ImportedField, Recipe, SavedResult, ValidatedProposal} from "./api-adapter";
import type {ReviewData, ReviewTarget} from "./review-preview";
import type {ChannelDefinition} from "./grouping";
const nuclear:ChannelDefinition={token:"c4",stain:"DAPI",role:"nuclear",evidence:"user"};
function result(id:string,field="f1"):SavedResult{return {revision:id,field,rows:[],masks:{regions:[{id:17,points:[[1,1],[3,1],[3,3]]}],metadata:{mask_revision_id:id}},exclusions:[]};}
function fixture(withResult=true){
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
    draft:vi.fn(async()=>({proposal:{draft:{recipe:"nuclear-intensity",channels:[],metrics:[],statistics:{kind:"descriptive",test:null,omnibus:null,association:null},figures:[],missing_information:[],reference_ids:[],rationale:"fixture",processing:{version:"1.0.0",nuclei:{channel:"c4",detection_max_side_px:null,detector:{engine:"fiji-stardist-2d",model:"Versatile (fluorescent nuclei)",probability:.65,nms:.3,percentile_low:1,percentile_high:99.8}},nucleoli:null,signal:null}},needs_confirmation:[]} as ValidatedProposal})),
    registerImport:vi.fn(),uploadOme:vi.fn(async()=>input),upload:vi.fn(async()=>input),create:vi.fn(async()=>({id:"w",title:"fixture"})),selection:()=>({version:1,entries:[]}),
  };
  let spec:import("./use-workspace-runtime").RuntimeSpecification={version:0,spec:null};
  const runtime=createWorkspaceRuntime({adapter:adapter as unknown as ReturnType<typeof createApiAdapter>,loadPreview,releasePreview:vi.fn(),readSpecification:async()=>spec,writeSpecification:async(_id,value)=>{spec={...value,version:spec.version+1};return spec;}});
  return {runtime,adapter,adopted,recipe,revisions,assignments,loadPreview};
}
describe("functional workspace runtime",()=>{
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
    const {runtime,adopted}=fixture();await runtime.load("w");await runtime.requestProposal("","f1");expect(runtime.getSnapshot().settings.nuclearProbability).toBe(.65);
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
    await runtime.requestProposal("","f1");expect(adapter.draft.mock.calls[0]).toBeDefined();expect(adapter.run).toHaveBeenCalledTimes(1);expect(adapter.run.mock.calls[0][1]).toBe("f1");
  });
  it("retains separate file identities when later images have the same filename",async()=>{
    const {runtime,adapter}=fixture();await runtime.load("w");
    await runtime.importFiles([new File([new Uint8Array([1])],"view_c4.tif")]);
    await runtime.importFiles([new File([new Uint8Array([2])],"view_c4.tif")]);
    expect(adapter.upload).toHaveBeenCalledTimes(2);expect(adapter.draft).not.toHaveBeenCalled();expect(adapter.run).not.toHaveBeenCalled();
  });
  it("allows a text-only consultation in a new workspace without analysis",async()=>{
    const {runtime,adapter}=fixture();runtime.newWorkspace();adapter.getChannelAssignments.mockResolvedValue({version:0,assignments:[]});await runtime.requestProposal("Plan an experiment");
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
});
