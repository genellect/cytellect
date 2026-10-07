import {describe, expect, it, vi} from "vitest";
import {createWorkspaceRuntime, defaultRuntimeSettings, runtimeRecipe} from "./use-workspace-runtime";
import type {createApiAdapter, Recipe, SavedResult, ValidatedProposal} from "./api-adapter";
import type {ReviewData} from "./review-preview";
import type {ProposalProcessing} from "./proposal-processing";
import type {ChannelDefinition} from "./grouping";
import {nucleolarDetectorV2} from "./nucleolar-definition";

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
  const proposal={draft:{recipe:"ncl-compartments",channels:[],metrics:[],statistics:{kind:"descriptive",test:null,omnibus:null,association:null},figures:[],missing_information:[],reference_ids:[],rationale:"",processing:configuredProcessing},needs_confirmation:[]} as unknown as ValidatedProposal;
  const adapter={restore:vi.fn(async()=>({record:{id:"w"},fields:[{id:"f",workspace_id:"w",metadata:{},image_info:{shape:[1,1],channels:channels.map(value=>({channel_id:value.id,label:value.label,stain:value.stain}))}}],revisions:[{id:"n",config:{recipe:base}},{id:"u",config:{recipe:configuredChild}}],jobs:[]})),getChannelAssignments:vi.fn(async()=>assignments),isSelectionCurrent:vi.fn(async()=>true),draft:vi.fn(async()=>({proposal}))};
  const runtime=createWorkspaceRuntime({adapter:adapter as unknown as ReturnType<typeof createApiAdapter>,loadPreview:async()=>structuredClone(data),releasePreview:vi.fn(),readSpecification:async()=>({version:0,spec:null}),writeSpecification:async(_id,value)=>({...value,version:value.version+1})});
  return {runtime,adapter};
}
describe("NCL settings contracts without images",()=>{
  it("restores exact saved NCL controls",async()=>{
    const {runtime}=contractRuntime();await runtime.load("w");
    expect(runtime.getSnapshot().settings).toMatchObject({nucleolarDefinition:{source:"ncl",marker:"marker"},nucleolarSigma:3,nucleolarMinimumArea:12,nucleolarMaximumArea:140});
    runtime.dispose();
  });
  it("applies AI settings into the same visible controls",async()=>{
    const {runtime}=contractRuntime();await runtime.load("w");runtime.setSettings(value=>({...value,nucleolarSigma:1,nucleolarMinimumArea:2,nucleolarMaximumArea:9}));
    await runtime.requestProposal("set NCL settings","f");
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
