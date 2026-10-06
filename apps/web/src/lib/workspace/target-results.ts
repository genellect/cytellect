import type {Recipe, SavedResult} from "./api-adapter";

export type Target = "nuclei" | "gfp" | "ncl" | "nucleoli" | "nucleoplasm";
export type TargetResult = {result: SavedResult; recipe: Recipe};
export type TargetResults = Partial<Record<Target, TargetResult>>;
export const targetOf = (recipe?: Recipe): Target => recipe?.compartment === "nucleoli" ? "nucleoli" : recipe?.compartment === "nucleoplasm" ? "nucleoplasm" : recipe?.region_set_id === "gfp_positive" ? "gfp" : recipe?.region_set_id === "ncl_positive" ? "ncl" : "nuclei";

/** Derived masks are usable only with the exact selected parent and channel mapping. */
export function validTargetResults(cached: TargetResults | undefined, current?: TargetResult, channels: {nuclear?: string; ncl?: string} = {}): TargetResults {
  const targets = {...cached, ...(current ? {[targetOf(current.recipe)]: current} : {})};
  const parent = targets.nuclei;
  for (const key of ["nucleoli", "nucleoplasm"] as const) {
    const derived = targets[key];
    if (derived && (!parent || derived.recipe.nuclear_revision_id !== parent.result.revision ||
      derived.recipe.nuclear_channel_id !== parent.recipe.defining_channel_id ||
      (channels.nuclear && parent.recipe.defining_channel_id !== channels.nuclear) ||
      (channels.ncl && derived.recipe.defining_channel_id !== channels.ncl))) delete targets[key];
  }
  return targets;
}
