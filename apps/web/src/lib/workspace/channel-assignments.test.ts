import {describe,expect,it} from "vitest";
import {assignmentChannels,assignmentDraft,assignmentRoles,channelCaption,editAssignmentStain} from "./channel-assignments";
import type {Grouping} from "./grouping";

const grouping: Grouping = {fields:[],issues:[],channels:["c1","c2","c3","c4"].map(token=>({token,stain:null,role:null,evidence:"registered_source"}))};
describe("explicit channel assignments",()=>{
  it("does not assign stains or nuclei from numbered channel names",()=>{
    expect(assignmentRoles(assignmentDraft(grouping.channels))).toEqual({nuclear:"",gfp:"",ncl:""});
  });
  it("binds explicit stains to execution roles and names without rewriting input metadata",()=>{
    let values=assignmentDraft(grouping.channels);
    values=editAssignmentStain(values,"c4","DAPI");values=editAssignmentStain(values,"c3","GFP");values=editAssignmentStain(values,"c1","NCL");
    expect(assignmentRoles(values)).toEqual({nuclear:"c4",gfp:"c3",ncl:"c1"});
    const mapped=assignmentChannels(grouping,{version:1,assignments:values});
    expect(channelCaption("c1",mapped.channels)).toBe("c1 · NCL");
    expect(grouping.channels[0].stain).toBeNull();
  });
  it("remaps the nuclear role once, and clears it when renamed to a signal",()=>{
    let values=editAssignmentStain(assignmentDraft(grouping.channels),"c1","DAPI");
    values=editAssignmentStain(values,"c4","Hoechst33342");
    expect(values.filter(value=>value.role==="nuclear").map(value=>value.channel_id)).toEqual(["c4"]);
    values=editAssignmentStain(values,"c4","GFP");expect(assignmentRoles(values).nuclear).toBe("");
  });
  it("retains arbitrary marker names, does not choose between duplicate GFP assignments",()=>{
    let values=editAssignmentStain(assignmentDraft(grouping.channels),"c2","my marker");
    values=editAssignmentStain(values,"c1","GFP");values=editAssignmentStain(values,"c3","GFP");
    expect(values[1].stain).toBe("my marker");expect(assignmentRoles(values).gfp).toBe("");
  });
});

describe("configuration-scoped assignment lookup",()=>{
  it("uses an explicit field group and never applies a legacy mapping to new fields",async()=>{
    const {effectiveChannelAssignments}=await import("./channel-assignments");
    const saved={version:3,assignments:[{channel_id:"c1",stain:"DAPI",role:"nuclear" as const}],global_field_ids:["old"],groups:[{id:"g",field_ids:["other"],channel_ids:["c1"],assignments:[{channel_id:"c1",stain:"GFP",role:"measure" as const}]}]};
    expect(effectiveChannelAssignments(saved,"old")[0].stain).toBe("DAPI");
    expect(effectiveChannelAssignments(saved,"other")[0].stain).toBe("GFP");
    expect(effectiveChannelAssignments(saved,"new")).toEqual([]);
  });
});