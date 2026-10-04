export type ComparisonDraft={metadata:boolean;form:boolean};
export type DraftState={region:boolean;config:boolean;comparison:ComparisonDraft};
export type DraftAction="view"|"revision"|"exit"|"measure"|"region-save"|"metadata-save";
/** Only include drafts this action would lose; a save's own payload is not discarded. */
export function navigationLosses(action:DraftAction,state:DraftState){
 return {
  region:state.region&&action!=="region-save",
  config:state.config&&(action==="revision"||action==="exit"),
  metadata:state.comparison.metadata&&!["view","metadata-save"].includes(action),
  form:state.comparison.form&&action!=="view",
 };
}
