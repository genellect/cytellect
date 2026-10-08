import {describe, expect, it, vi} from "vitest";
import {createWorkspaceRuntime, defaultRuntimeSettings, runtimeRecipe} from "./use-workspace-runtime";
import type {createApiAdapter, Recipe, SavedResult, ValidatedProposal} from "./api-adapter";
import type {ReviewData} from "./review-preview";
import type {ProposalProcessing} from "./proposal-processing";
import type {ChannelDefinition} from "./grouping";
import {nclObjectDetector,nucleolarDetectorV2} from "./nucleolar-definition";
import {cellposeDetector,nclCellposeDetector} from "./cellpose-settings";

// Contract-only records: no image pixels, decoding, detector execution or image fixtures.
const nuclear:ChannelDefinition={token:"dna",stain:"DAPI",role:"nuclear",evidence:"user"};
const ncl={engine:"fiji-nucleolar-compartments" as const,protocol_version:"1.1.0" as const,
  threshold_method:"manual" as const,threshold:8,smoothing_sigma_px:3,minimum_area_px:12,maximum_area_px:140,split_touching:true};
const base=runtimeRecipe("nuclei",nuclear,defaultRuntimeSettings(),{},null);
const processing:ProposalProcessing={version:"1.0.0",nuclei:{channel:"dna",detection_max_side_px:null,
  detector:{engine:"fiji-stardist-2d",model:"Versatile (fluorescent nuclei)",probability:.5,nms:.3,percentile_low:1,percentile_high:99.8}},nucleoli:{channel:"marker",detector:ncl},signal:null};
const child:Recipe={id:"region-2d",version:"1.4.0",source:"fiji_nuclear_compartment",region_set_id:"nucleoli",label:"核小体",compartment:"nucleoli",nuclear_revision_id:"n",nuclear_channel_id:"dna",defining_channel_id:"marker",detector:ncl};
const record=(revision:string):SavedResult=>({revision,field:"f",rows:[],masks:{regions:[],metadata:{mask_revision_id:revision}},exclusions:[]});
function contractRuntime(detector:NonNullable<ProposalProcessing["nucleoli"]>["detector"]=ncl){
  const configuredProcessing={...processing,nucleoli:{channel:"marker",detector}};
  const configuredChild={...child,detector};
  const channels=[{id:"dna",label:"DAPI",stain:"DAPI",role:"nuclear" as const},{id:"marker",label:"NCL",stain:"NCL",role:"measure" as const}];
  const data:ReviewData={workspaceId:"w",title:"contract",channels,fields:[{id:"f",label:"field",width:1,height:1,channels,previews:{},results:{nuclei:record("n"),nucleoli:record("u")},nuclearChannelId:"dna"}]};
  const assignments={version:1,assignments:channels.map(value=>({channel_id:value.id,stain:value.stain,role:value.role}))};
  const proposal={draft:{recipe:"nuclear-ncl",channels:[],metrics:[],statistics:{kind:"descriptive",test:null,omnibus:null,association:null},figures:[],missing_information:[],reference_ids:[],rationale:"",processing:configuredProcessing},needs_confirmation:[]} as unknown as ValidatedProposal;
  const adapter={run:vi.fn(),restore:vi.fn(async()=>({record:{id:"w"},fields:[{id:"f",workspace_id:"w",metadata:{},image_info:{shape:[1,1],channels:channels.map(value=>({channel_id:value.id,label:value.label,stain:value.stain}))}}],revisions:[{id:"n",config:{recipe:base}},{id:"u",config:{recipe:configuredChild}}],jobs:[]})),getChannelAssignments:vi.fn(async()=>assignments),isSelectionCurrent:vi.fn(async()=>true),draft:vi.fn(async()=>({proposal}))};
  const writeSpecification=vi.fn(async(_id:string,value:import("./use-workspace-runtime").RuntimeSpecification)=>({...value,version:value.version+1}));
  const runtime=createWorkspaceRuntime({adapter:adapter as unknown as ReturnType<typeof createApiAdapter>,loadPreview:async()=>structuredClone(data),releasePreview:vi.fn(),readSpecification:async()=>({version:0,spec:null}),writeSpecification});
  return {runtime,adapter,writeSpecification};
}
describe("NCL settings contracts without images",()=>{
  it("restores exact saved NCL controls",async()=>{
    const {runtime}=contractRuntime();await runtime.load("w");
    expect(runtime.getSnapshot().settings).toMatchObject({nucleolarDefinition:{source:"ncl",marker:"marker"},nucleolarSigma:3,nucleolarMinimumArea:12,nucleolarMaximumArea:140});
    runtime.dispose();
  });
  it("applies AI settings into the same visible controls",async()=>{
    const {runtime,adapter,writeSpecification}=contractRuntime();await runtime.load("w");runtime.setSettings(value=>({...value,nucleolarSigma:1,nucleolarMinimumArea:2,nucleolarMaximumArea:9}));
    await runtime.requestProposal("set NCL settings","f");
    expect(writeSpecification.mock.calls[0][1].spec?.settings).toMatchObject({nucleolarSigma:1,nucleolarMinimumArea:2,nucleolarMaximumArea:9});
    expect(writeSpecification.mock.invocationCallOrder[0]).toBeLessThan(adapter.draft.mock.invocationCallOrder[0]);
    expect(runtime.specification()?.spec?.settings).toMatchObject({nucleolarSigma:3,nucleolarMinimumArea:12,nucleolarMaximumArea:140});
    expect(runtime.getSnapshot().settings).toMatchObject({nucleolarSigma:3,nucleolarMinimumArea:12,nucleolarMaximumArea:140});
    runtime.dispose();
  });
  it("prioritizes explicit values and preserves registered detector semantics",()=>{
    const settings={...defaultRuntimeSettings(),nucleolarDefinition:{source:"ncl" as const,marker:"marker",pixelUm:null,relative:.7},nucleolarSigma:2,nucleolarMinimumArea:5,nucleolarMaximumArea:null};
    const recipe=runtimeRecipe("nucleoli",nuclear,settings,{nuclei:{recipe:base,result:record("n")}},processing);
    expect(recipe.detector).toEqual({...ncl,smoothing_sigma_px:2,minimum_area_px:5,maximum_area_px:null});
  });
});


describe("marker smoothing protocol compatibility without images",()=>{
  const definition={source:"marker" as const,marker:"marker",pixelUm:null,relative:.7};
  const old={...nucleolarDetectorV2(definition),protocol_version:"2.0.0" as const,smoothing_sigma_px:2};
  it("creates new marker settings at 2.1 / 0.7 without changing DAPI defaults",()=>{
    expect(nucleolarDetectorV2(definition)).toMatchObject({protocol_version:"2.1.0",source:"marker",smoothing_sigma_px:.7});
    expect(nucleolarDetectorV2({...definition,source:"dapi_poor"})).toMatchObject({protocol_version:"2.0.0",source:"dapi_poor",smoothing_sigma_px:2});
    expect(nucleolarDetectorV2({...definition,pixelUm:.1}).smoothing_sigma_px).toBe(.7);
  });
  it("keeps historical parameters while showing effective sigma and editing unrelated controls",async()=>{
    const {runtime}=contractRuntime(old);await runtime.load("w");
    expect(runtime.getSnapshot().settings.nucleolarSigma).toBe(.7);
    expect(runtime.getSnapshot().processing?.nucleoli?.detector).toEqual(old);
    runtime.setSettings(value=>({...value,nucleolarMinimumArea:8}));
    const state=runtime.getSnapshot(),recipe=runtimeRecipe("nucleoli",nuclear,state.settings,{nuclei:{recipe:base,result:record("n")}},state.processing);
    expect(recipe.detector).toMatchObject({protocol_version:"2.0.0",smoothing_sigma_px:2,minimum_area_px:8});
    runtime.dispose();
  });
  it("retains an adopted historical marker when processing is absent",()=>{
    const settings={...defaultRuntimeSettings(),nucleolarDefinition:definition,nucleolarSigma:2};
    const recipe=runtimeRecipe("nucleoli",nuclear,settings,{nuclei:{recipe:base,result:record("n")},nucleoli:{recipe:{...child,detector:old},result:record("u")}},null);
    expect(recipe.detector).toMatchObject({protocol_version:"2.0.0",smoothing_sigma_px:2});
  });
  it("upgrades only explicit sigma edits and resets new sigma to 0.7",async()=>{
    const {runtime}=contractRuntime(old);await runtime.load("w");runtime.setNucleolarSigma(1.2);
    expect(runtime.getSnapshot().processing?.nucleoli?.detector).toMatchObject({protocol_version:"2.1.0",source:"marker",smoothing_sigma_px:1.2});
    const state=runtime.getSnapshot();expect(runtimeRecipe("nucleoli",nuclear,state.settings,{nuclei:{recipe:base,result:record("n")}},state.processing).detector).toMatchObject({protocol_version:"2.1.0",smoothing_sigma_px:1.2});
    runtime.setNucleolarSigma(null);
    expect(runtime.getSnapshot().processing?.nucleoli?.detector).toMatchObject({protocol_version:"2.1.0",smoothing_sigma_px:.7});
    runtime.dispose();
  });
});


describe("new NCL object contracts",()=>{
  it("creates the registered detector with its adopted nuclear revision",()=>{
    const settings={...defaultRuntimeSettings(),nucleolarDefinition:{source:"ncl" as const,marker:"marker",pixelUm:null,relative:.7}};
    const recipe=runtimeRecipe("nucleoli",nuclear,settings,{nuclei:{recipe:base,result:record("n")}},null);
    expect(recipe.detector).toEqual(nclObjectDetector());
    expect(recipe).toMatchObject({nuclear_revision_id:"n",defining_channel_id:"marker"});
  });
  it("restores AI/manual parameters for the new protocol without legacy conversion",async()=>{
    const detector={...nclObjectDetector(),boundary_fraction:.6,minimum_area_px:40};
    const {runtime}=contractRuntime(detector);await runtime.load("w");
    expect(runtime.getSnapshot().settings).toMatchObject({nucleolarDefinition:{source:"ncl",marker:"marker"},nucleolarSigma:.9,nucleolarMinimumArea:40,nucleolarMaximumArea:800});
    expect(runtime.nclDetector("f")).toEqual(detector);
    runtime.setNclParameter("f","minimum_peak_difference",45);
    expect(runtime.nclDetector("f")).toMatchObject({minimum_peak_difference:45,boundary_fraction:.6});
    runtime.dispose();
  });
  it("keeps saved masks while hiding them after an explicit method change",async()=>{
    const {runtime}=contractRuntime();await runtime.load("w");
    expect(runtime.currentResult("f","nucleoli")?.revision).toBe("u");
    runtime.selectNucleolarSource("ncl","marker","objects");
    expect(runtime.currentResult("f","nucleoli")).toBeUndefined();
    expect(runtime.getSnapshot().data?.fields[0].results.nucleoli?.revision).toBe("u");
    expect(runtime.nclDetector("f")).toMatchObject({protocol_version:"3.0.0"});
    runtime.dispose();
  });
  it("does not submit any detector job when the NCL image is unset",async()=>{
    const {runtime,adapter}=contractRuntime();await runtime.load("w");
    runtime.selectNucleolarSource("ncl","");
    await expect(runtime.preview("f","nucleoli")).rejects.toThrow("analysis_run_nucleolar_marker_required");
    expect(adapter.run).not.toHaveBeenCalled();
    runtime.dispose();
  });
});

describe("Cellpose runtime contracts without images",()=>{
  it("does not create another settings version for unchanged compatible defaults",async()=>{
    const {runtime,writeSpecification,adapter}=contractRuntime(cellposeDetector());await runtime.load("w");
    await runtime.saveSettings("nucleoli");await runtime.saveSettings("nucleoli");
    expect(writeSpecification).toHaveBeenCalledTimes(1);
    expect(adapter.draft).not.toHaveBeenCalled();expect(adapter.run).not.toHaveBeenCalled();
    runtime.dispose();
  });
  it("restores Cellpose without inheriting classical area or smoothing values",async()=>{
    const detector={...cellposeDetector(),diameter_px:120,cellprob_threshold:-1};
    const {runtime}=contractRuntime(detector);await runtime.load("w");
    expect(runtime.getSnapshot().settings).toMatchObject({nucleolarDefinition:{source:"ncl",marker:"marker",algorithm:"cellpose"},nucleolarSigma:null,nucleolarMinimumArea:null,nucleolarMaximumArea:null});
    expect(runtime.cellposeSettings("f","nucleoli")).toEqual(detector);
    expect(runtime.currentResult("f","nucleoli")?.revision).toBe("u");
    runtime.setCellposeParameter("f","nucleoli","diameter_px",90);
    expect(runtime.cellposeSettings("f","nucleoli")).toMatchObject({diameter_px:90,cellprob_threshold:-1});
    expect(runtime.currentResult("f","nucleoli")).toBeUndefined();
    expect(runtime.getSnapshot().data?.fields[0].results.nucleoli?.revision).toBe("u");
    runtime.dispose();
  });
  it("uses the parent-conditioned 4.2 NCL workflow only after an explicit new selection",async()=>{
    const {runtime,adapter}=contractRuntime(cellposeDetector());await runtime.load("w");
    expect(runtime.cellposeSettings("f","nucleoli").engine).toBe("cellpose-sam");
    expect(runtime.currentResult("f","nucleoli")?.revision).toBe("u");
    runtime.selectNucleolarSource("ncl","marker");
    expect(runtime.getSnapshot().settings.nucleolarDefinition).toMatchObject({source:"ncl",marker:"marker",algorithm:"cellpose"});
    expect(runtime.getSnapshot().processing?.nucleoli?.detector).toEqual(nclCellposeDetector());
    expect(runtime.cellposeSettings("f","nucleoli")).toEqual(nclCellposeDetector());
    expect(runtime.currentResult("f","nucleoli")).toBeUndefined();
    expect(runtime.getSnapshot().data?.fields[0].results.nucleoli?.revision).toBe("u");
    expect(adapter.run).not.toHaveBeenCalled();expect(adapter.draft).not.toHaveBeenCalled();
    runtime.setCellposeParameter("f","nucleoli","parent_background_percentile",70);
    expect(runtime.cellposeSettings("f","nucleoli")).toMatchObject({engine:"cellpose-sam-ncl-parent",protocol_version:"4.2.1",parent_background_percentile:70,smoothing_sigma_px:.9});
    runtime.dispose();
  });
  it("completes an algorithm-first manual selection and starts the selected durable preview",async()=>{
    const {runtime,adapter,writeSpecification}=contractRuntime();await runtime.load("w");
    runtime.selectNucleolarSource("ncl","");
    expect(runtime.getSnapshot().settings.nucleolarDefinition.algorithm).toBe("cellpose");
    expect(runtime.getSnapshot().processing?.nucleoli).toBeNull();
    expect(adapter.run).not.toHaveBeenCalled();
    runtime.setSettings(previous=>({...previous,nucleolarDefinition:{...previous.nucleolarDefinition,marker:"marker"}}));
    const state=runtime.getSnapshot();
    expect(state.processing?.nucleoli).toEqual({channel:"marker",detector:nclCellposeDetector()});
    const recipe=runtimeRecipe("nucleoli",nuclear,state.settings,{nuclei:{recipe:base,result:record("n")}},state.processing);
    const run={id:"ncl-preview",workspace_id:"w",spec_version:1,target:"nucleoli" as const,state:"succeeded" as const,created:1,updated:1,
      steps:[{field_id:"f",target:"nucleoli" as const,state:"succeeded" as const,revision_id:"new-ncl",job_id:"job",recipe,error:null}]};
    const startWorkspaceRun=vi.fn(async()=>run),acceptWorkspaceRun=vi.fn();
    Object.assign(adapter,{startWorkspaceRun,waitWorkspaceRun:vi.fn(async()=>run),acceptWorkspaceRun,readResult:vi.fn(async()=>({...record("new-ncl"),regionSet:"nucleoli"}))});
    await runtime.preview("f","nucleoli");
    expect(writeSpecification.mock.calls.at(-1)?.[1].spec).toMatchObject({target:"nucleoli",processing:{nucleoli:{channel:"marker",detector:nclCellposeDetector()}}});
    expect(startWorkspaceRun).toHaveBeenCalledWith("w",expect.objectContaining({target:"nucleoli",field_ids:["f"],purpose:"preview",spec_version:1}));
    expect(runtime.candidateResult("f","nucleoli")?.revision).toBe("new-ncl");
    expect(runtime.getSnapshot().data?.fields[0].results.nuclei?.revision).toBe("n");
    expect(runtime.getSnapshot().data?.fields[0].results.nucleoli?.revision).toBe("u");
    expect(adapter.draft).not.toHaveBeenCalled();expect(adapter.run).not.toHaveBeenCalled();expect(acceptWorkspaceRun).not.toHaveBeenCalled();
    runtime.dispose();
  });
  it("preserves a historical Cellpose protocol and parameters when only its NCL input changes",async()=>{
    const detector={...cellposeDetector(),diameter_px:120};
    const {runtime}=contractRuntime(detector);await runtime.load("w");
    runtime.setSettings(previous=>({...previous,nucleolarDefinition:{...previous.nucleolarDefinition,marker:"other-ncl"}}));
    expect(runtime.getSnapshot().processing?.nucleoli).toEqual({channel:"other-ncl",detector});
    runtime.dispose();
  });
  it("restores an AI NCL 4.1 proposal without converting it to generic Cellpose",async()=>{
    const detector={...nclCellposeDetector(),background_radius_px:14};
    const {runtime}=contractRuntime(detector);await runtime.load("w");
    expect(runtime.cellposeSettings("f","nucleoli")).toEqual(detector);
    await runtime.requestProposal("NCLを検出","f");
    expect(runtime.getSnapshot().processing?.nucleoli?.detector).toEqual(detector);
    expect(runtime.specification().spec?.processing?.nucleoli?.detector).toEqual(detector);
    runtime.dispose();
  });
  it("starts only a selected preview for an explicit AI cell request",async()=>{
    const {runtime,adapter}=contractRuntime();await runtime.load("w");
    const proposal:ValidatedProposal={draft:{recipe:"supplied-regions",channels:[],metrics:[{metric:"area",channel:null,region:"cell"}],statistics:{kind:"descriptive",test:null,omnibus:null,association:null},figures:[],missing_information:[],reference_ids:[],rationale:"",processing:{version:"1.0.0",nuclei:null,nucleoli:null,signal:null,cells:{channel:"marker",detector:cellposeDetector()}}},needs_confirmation:[]};
    adapter.draft.mockResolvedValue({proposal});adapter.run.mockResolvedValue({...record("cell-candidate"),regionSet:"cell"});
    runtime.setSettings(settings=>({...settings,cellDefinition:{source:"cellpose",channel:"marker"}}));
    expect(adapter.draft).not.toHaveBeenCalled();expect(adapter.run).not.toHaveBeenCalled();
    await runtime.requestProposal("detect cells","f");
    expect(runtime.getSnapshot().activeTarget).toBe("cell");
    expect(adapter.run).toHaveBeenCalledTimes(1);
    expect(adapter.run.mock.calls[0].slice(0,2)).toEqual(["w","f"]);
    expect(adapter.run.mock.calls[0][2]).toMatchObject({source:"cellpose_cell",defining_channel_id:"marker",detector:{engine:"cellpose-sam"}});
    expect(adapter.run.mock.calls[0][5]).toEqual({adopt:false});
    expect(runtime.candidateResult("f","cell")?.revision).toBe("cell-candidate");
    expect(runtime.getSnapshot().data?.fields[0].results.cell).toBeUndefined();
    runtime.dispose();
  });
});
