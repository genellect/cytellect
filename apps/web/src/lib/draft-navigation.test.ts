import {expect,it} from "vitest";
import {navigationLosses} from "./draft-navigation";
const all={region:true,config:true,comparison:{metadata:true,form:true}};
it("preserves compatible settings and comparison drafts across ordinary image/tool navigation",()=>{
 expect(navigationLosses("view",all)).toEqual({region:true,config:false,metadata:false,form:false});
});
it("never treats a save's own payload as a discard, but protects unrelated drafts",()=>{
 expect(navigationLosses("region-save",all)).toEqual({region:false,config:false,metadata:true,form:true});
 expect(navigationLosses("metadata-save",all)).toEqual({region:true,config:false,metadata:false,form:true});
 expect(navigationLosses("measure",all)).toEqual({region:true,config:false,metadata:true,form:true});
});
it("protects every draft on revision replacement or workspace exit",()=>{
 for(const action of ["revision","exit"] as const)expect(navigationLosses(action,all)).toEqual({region:true,config:true,metadata:true,form:true});
 expect(navigationLosses("revision",{region:false,config:false,comparison:{metadata:false,form:false}})).toEqual({region:false,config:false,metadata:false,form:false});
});
