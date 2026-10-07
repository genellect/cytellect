import {describe, expect, it} from "vitest";
import {applicableProcessing, proposalNuclearRecipe, proposalNucleolarRecipe, proposalSignalRecipe, savedProcessing, withProcessingSettings, type ProposalProcessing} from "./proposal-processing";
import {createApiAdapter, type Transport, type ValidatedProposal} from "./api-adapter";
import type {ChannelDefinition} from "./grouping";

const channels: ChannelDefinition[] = [{token:"dapi",stain:"DAPI",role:"nuclear",evidence:"user"},
  {token:"ncl",stain:"NCL",role:"measure",evidence:"user"}];
const processing: ProposalProcessing = {version:"1.0.0",
  nuclei:{channel:"dapi",detection_max_side_px:1024,detector:{engine:"fiji-stardist-2d",model:"Versatile (fluorescent nuclei)",probability:0.65,nms:0.25,percentile_low:2,percentile_high:99}},
  nucleoli:{channel:"dapi",detector:{engine:"cytellect-nucleolar-v2",protocol_version:"2.0.0",source:"dapi_poor",smoothing_sigma_px:1.5,rim_exclusion_px:3,relative_threshold:0.55,marker_fraction:0.4,background_radius_px:10,minimum_area_px:7,maximum_area_px:120,minimum_solidity:0.7}},
  signal:{channel:"ncl",detector:{engine:"fiji-positive-regions",protocol_version:"1.0.0",threshold_method:"manual",threshold:420,smoothing_sigma_px:1,minimum_area_px:9,split_touching:true}}};
const proposal: ValidatedProposal = {needs_confirmation:[],draft:{recipe:"nuclear-ncl",channels:[],metrics:[],figures:[],statistics:{kind:"descriptive",test:null,omnibus:null,association:null},missing_information:[],reference_ids:[],rationale:"",processing}};

describe("registered AI processing settings", () => {
  it("keeps exact model settings and resolves the parent only at execution", () => {
    expect(proposalNuclearRecipe(channels[0],processing)).toMatchObject({version:"1.5.0",detection_max_side_px:1024,detector:processing.nuclei!.detector});
    expect(proposalNucleolarRecipe(processing,{revision:"adopted-7",channel:"dapi"})).toMatchObject({nuclear_revision_id:"adopted-7",defining_channel_id:"dapi",detector:processing.nucleoli!.detector});
    expect(proposalSignalRecipe(processing,"ncl").detector).toEqual(processing.signal!.detector);
  });
  it("restores all detector settings from adopted revisions for the next instruction", () => {
    expect(savedProcessing(proposalNuclearRecipe(channels[0],processing),
      proposalNucleolarRecipe(processing,{revision:"parent",channel:"dapi"}),proposalSignalRecipe(processing,"ncl"))).toEqual(processing);
  });
  it("does not confirm unknown channels and never mutates the proposal", () => {
    expect(applicableProcessing({...proposal,needs_confirmation:["dapi"]},channels)).toBeNull();
    expect(applicableProcessing(proposal,channels.slice(1))).toBeNull();
    const copy = applicableProcessing(proposal,channels)!;
    copy.nuclei!.detector.probability = 0.2;
    expect(processing.nuclei!.detector.probability).toBe(0.65);
  });
  it("preserves manual threshold changes while carrying hidden detector settings", () => {
    const signal = proposalSignalRecipe(processing,"ncl");
    signal.detector = {...processing.signal!.detector,threshold:800,minimum_area_px:1};
    expect(withProcessingSettings(signal,processing).detector).toEqual({...processing.signal!.detector,threshold:800});
    const nucleus = {...proposalNuclearRecipe(channels[0],processing),detection_max_side_px:640};
    expect(withProcessingSettings(nucleus,processing)).toMatchObject({detection_max_side_px:640,detector:processing.nuclei!.detector});
  });
  it("uses manual relative threshold and drops hidden overrides after calibration changes", () => {
    const child = proposalNucleolarRecipe(processing,{revision:"parent",channel:"dapi"});
    if (!child.detector || !("relative_threshold" in child.detector)) throw new Error("wrong fixture");
    child.detector = {...child.detector,relative_threshold:0.8,minimum_area_px:1};
    expect(withProcessingSettings(child,processing).detector).toMatchObject({relative_threshold:0.8,minimum_area_px:7});
    expect(withProcessingSettings(child,processing,true).detector).toMatchObject({relative_threshold:0.8,minimum_area_px:1});
  });
  it("keeps old drafts and unrelated channels unchanged", () => {
    expect(applicableProcessing({...proposal,draft:{...proposal.draft,processing:undefined}},channels)).toBeNull();
    const unrelated = {...proposalSignalRecipe(processing,"ncl"),defining_channel_id:"other"};
    expect(withProcessingSettings(unrelated,processing)).toBe(unrelated);
  });
  it("submits the exact adopted processing settings to the real analysis transport", async () => {
    const accepted = applicableProcessing(proposal,channels)!;
    const recipe = proposalNuclearRecipe(channels[0],accepted);
    let sent: unknown;
    const adapter = createApiAdapter({
      request: (async (path: string) => {
        if (path.endsWith("/selection")) return {version:0,entries:[{id:"field",field_id:"field",revision_id:null,exclusion_reason:null}]};
        throw new Error("polling ends the no-execution fixture");
      }) as Transport["request"],
      post: (async (_path: string, body: unknown) => {sent = body; return {job_id:"job",revision_id:"rev"};}) as Transport["post"],
      wait: async () => {},
    });
    await expect(adapter.run("workspace","field",recipe)).rejects.toThrow("polling ends");
    expect(sent).toMatchObject({field_ids:["field"],recipe:{detection_max_side_px:1024,
      defining_channel_id:"dapi",detector:{probability:0.65,nms:0.25,percentile_low:2,percentile_high:99}}});
  });
});
