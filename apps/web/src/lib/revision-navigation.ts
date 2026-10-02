import type { Revision } from "./types";

/** Session-only navigation; scientific revisions themselves remain immutable. */
export class RevisionNavigation {
 constructor(private undoneChildren:ReadonlyMap<string,string>=new Map()){}
 selected(previous:Revision|undefined,nextId:string){
  if(previous?.parent_id!==nextId)return this;
  return new RevisionNavigation(new Map([...this.undoneChildren,[nextId,previous.id]]));
 }
 redo(revisions:Revision[],active:Revision|undefined){
  if(!active)return undefined;
  const children=revisions.filter(r=>r.parent_id===active.id&&r.state==="succeeded");
  return children.find(r=>r.id===this.undoneChildren.get(active.id))||children.toSorted((a,b)=>b.created-a.created)[0];
 }
}
