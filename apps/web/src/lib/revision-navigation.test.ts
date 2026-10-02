import { describe,expect,it } from "vitest";
import { RevisionNavigation } from "./revision-navigation";
import { defaultRecipe,type Revision } from "./types";
function revision(id:string,parent_id:string|null,created:number):Revision{return {id,parent_id,created,state:"succeeded",reviewed:false,config:{recipe:defaultRecipe,backgrounds:{},exclusions:[]}};}
describe("branched mask revision navigation",()=>{
 it("redo returns to the branch most recently undone, even when an older branch is revisited",()=>{
  const a=revision("a",null,0),b=revision("b","a",1),c=revision("c","a",2);let navigation=new RevisionNavigation();
  navigation=navigation.selected(b,"a");expect(navigation.redo([a,b],a)?.id).toBe("b");
  navigation=navigation.selected(a,"c");navigation=navigation.selected(c,"a");expect(navigation.redo([a,b,c],a)?.id).toBe("c");
  navigation=navigation.selected(a,"b");navigation=navigation.selected(b,"a");expect(navigation.redo([a,b,c],a)?.id).toBe("b");
 });
 it("after reload offers the newest successful branch and never a failed revision",()=>{
  const a=revision("a",null,0),b=revision("b","a",1),c=revision("c","a",2),failed={...revision("failed","a",3),state:"failed"};
  expect(new RevisionNavigation().redo([a,b,c,failed],a)?.id).toBe("c");
 });
});
