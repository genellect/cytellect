import {describe,expect,it} from "vitest";
import {cellposeDetector,nclCellposeDetector,legacyNclCellposeDetector} from "./cellpose-settings";
import {defaultRuntimeSettings,runtimeRecipe} from "./use-workspace-runtime";
import {applicableProcessing,savedProcessing,type ProposalProcessing} from "./proposal-processing";
import type {ChannelDefinition} from "./grouping";
import type {SavedResult,ValidatedProposal} from "./api-adapter";

// Transport/configuration contracts only. These records contain no image pixels.
const nuclear:ChannelDefinition={token:"dna",stain:"DAPI",role:"nuclear",evidence:"user"};
const ncl:ChannelDefinition={token:"marker",stain:"NCL",role:"measure",evidence:"user"};
const membrane:ChannelDefinition={token:"membrane",stain:"membrane",role:"measure",evidence:"user"};
const result:SavedResult={revision:"adopted-nuclei",field:"field",rows:[],masks:{regions:[],metadata:{mask_revision_id:"adopted-nuclei"}},exclusions:[]};
const base=runtimeRecipe("nuclei",nuclear,defaultRuntimeSettings(),{},null);
const parent={nuclei:{recipe:base,result}};

describe("Cellpose manual/saved/AI contracts",()=>{
  it("keeps nuclear detection fixed and binds NCL to its exact adopted parent",()=>{
    const settings={...defaultRuntimeSettings(),nucleolarDefinition:{source:"ncl" as const,marker:"marker",pixelUm:null,relative:.7,algorithm:"cellpose" as const},nucleolarMinimumArea:800,nucleolarMaximumArea:1000,nucleolarSigma:5};
    const recipe=runtimeRecipe("nucleoli",nuclear,settings,parent,null);
    expect(recipe).toMatchObject({nuclear_revision_id:"adopted-nuclei",nuclear_channel_id:"dna",defining_channel_id:"marker"});
    expect(recipe.detector).toEqual(nclCellposeDetector());
    expect(runtimeRecipe("nuclei",nuclear,settings,parent,null).detector?.engine).toBe("fiji-stardist-2d");
  });
  it("keeps the cell image separate from GFP/nuclear channel roles",()=>{
    const settings={...defaultRuntimeSettings(),cellDefinition:{source:"cellpose" as const,channel:"membrane"}};
    const recipe=runtimeRecipe("cell",membrane,settings,parent,null);
    expect(recipe).toMatchObject({version:"1.8.0",source:"cellpose_cell",region_set_id:"cell",defining_channel_id:"membrane",nuclear_revision_id:"adopted-nuclei"});
    expect(savedProcessing(base,undefined,undefined,recipe)?.cells).toEqual({channel:"membrane",detector:cellposeDetector()});
  });
  it("requires an explicitly selected defining cell image",()=>{
    expect(()=>runtimeRecipe("cell",membrane,{...defaultRuntimeSettings(),cellDefinition:{source:"cellpose",channel:""}},parent,null)).toThrow("analysis_run_cell_channel_required");
  });
  it("keeps manual cell ROIs independent of a previously selected detector image",()=>{
    const recipe=runtimeRecipe("cell",nuclear,{...defaultRuntimeSettings(),cellDefinition:{source:"manual",channel:"membrane"}},parent,null);
    expect(recipe).toMatchObject({version:"1.0.0",source:"manual",defining_channel_id:"dna"});
  });
  it("applies confirmed Cellpose proposals without converting their algorithm",()=>{
    const detector={...cellposeDetector(),diameter_px:90,cellprob_threshold:-1};
    const processing:ProposalProcessing={version:"1.0.0",nuclei:null,nucleoli:null,signal:null,cells:{channel:"membrane",detector}};
    const proposal:ValidatedProposal={needs_confirmation:[],draft:{recipe:"supplied-regions",channels:[],metrics:[],figures:[],statistics:{kind:"descriptive",test:null,omnibus:null,association:null},missing_information:[],reference_ids:[],rationale:"",processing}};
    expect(applicableProcessing(proposal,[nuclear,ncl,membrane])).toEqual(processing);
    expect(applicableProcessing({...proposal,needs_confirmation:["membrane"]},[membrane])).toBeNull();
    const recipe=runtimeRecipe("cell",membrane,{...defaultRuntimeSettings(),cellDefinition:{source:"cellpose",channel:"membrane"}},parent,processing);
    expect(recipe.detector).toEqual(detector);
  });
  it("retains historical NCL semantics until an explicit algorithm choice",()=>{
    const settings={...defaultRuntimeSettings(),nucleolarDefinition:{source:"ncl" as const,marker:"marker",pixelUm:null,relative:.7}};
    expect(runtimeRecipe("nucleoli",nuclear,settings,parent,null).detector?.engine).toBe("cytellect-ncl-objects");
  });
  it("keeps NCL local-background preprocessing in manual, saved and AI settings",()=>{
    const detector={...legacyNclCellposeDetector(),smoothing_sigma_px:1.2,background_radius_px:14};
    const processing:ProposalProcessing={version:"1.0.0",nuclei:{channel:"dna",detection_max_side_px:null,detector:base.detector as NonNullable<ProposalProcessing["nuclei"]>["detector"]},nucleoli:{channel:"marker",detector},signal:null};
    const settings={...defaultRuntimeSettings(),nucleolarDefinition:{source:"ncl" as const,marker:"marker",pixelUm:null,relative:.7,algorithm:"cellpose" as const}};
    const recipe=runtimeRecipe("nucleoli",nuclear,settings,parent,processing);
    expect(recipe.detector).toEqual(detector);
    expect(savedProcessing(base,recipe)?.nucleoli).toEqual(processing.nucleoli);
    expect(runtimeRecipe("cell",membrane,{...settings,cellDefinition:{source:"cellpose",channel:"membrane"}},parent,processing).detector).toEqual(cellposeDetector());
  });
});
