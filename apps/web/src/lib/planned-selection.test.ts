import {expect,it} from "vitest";
import {plannedSelection,selectionChangedFromPlan} from "./planned-selection";
import type {PlanResolution} from "./analysis-plan";
const plan:PlanResolution={version:"1.0.0",plan_sha256:"a".repeat(64),candidate_id:"regions-manual",metric:"integrated",channel_id:"actin",changes_acknowledged:false};
const options=[{id:"dna-mean",selection:{source:"region",metric:"mean",channel_id:"dna"}},{id:"actin-total",selection:{source:"region",metric:"integrated",channel_id:"actin"}}];
it("uses exact adopted metric and actual channel rather than the first metric",()=>{expect(plannedSelection(options,"",plan)).toBe(options[1]);expect(plannedSelection(options,"dna-mean",plan)).toBe(options[0]);expect(selectionChangedFromPlan(options[0],plan)).toBe(true);});
it("does not silently replace an unavailable planned metric or channel",()=>{expect(plannedSelection(options,"",{...plan,channel_id:"missing"})).toBeUndefined();expect(plannedSelection(options,"",{...plan,metric:"area_um2"})).toBeUndefined();expect(plannedSelection(options,"",null)).toBe(options[0]);});
it("matches legacy selection by its explicit metric",()=>{const legacy=[{id:"gfp",selection:{source:"legacy-cell",metric:"gfp_mean_corrected"}}];expect(plannedSelection(legacy,"",{...plan,metric:"gfp_mean_corrected",channel_id:"gfp"})).toBe(legacy[0]);});
