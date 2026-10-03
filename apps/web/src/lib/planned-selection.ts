import type {PlanResolution} from "./analysis-plan";
type Option={id:string;selection:{source:string;metric:string;channel_id?:string|null}};
export function plannedSelection<T extends Option>(options:T[],choice:string,plan?:PlanResolution|null):T|undefined{
 if(choice)return options.find(option=>option.id===choice);
 if(!plan)return options[0];
 return options.find(option=>option.selection.metric===plan.metric&&(option.selection.source!=="region"||option.selection.channel_id===plan.channel_id));
}
export function selectionChangedFromPlan(option:Option|undefined,plan?:PlanResolution|null){return !!plan&&!!option&&(option.selection.metric!==plan.metric||(option.selection.source==="region"&&option.selection.channel_id!==plan.channel_id));}
