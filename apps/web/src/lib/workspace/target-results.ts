import type {Recipe, SavedResult} from "./api-adapter";

export type Target = "nuclei" | "gfp" | "ncl" | "nucleoli" | "nucleoplasm";
export type TargetResult = {result: SavedResult; recipe: Recipe};
export type TargetResults = Partial<Record<Target, TargetResult>>;
export function targetOf(recipe?: Recipe): Target {
  if (recipe?.compartment === "nucleoli") return "nucleoli";
  if (recipe?.compartment === "nucleoplasm") return "nucleoplasm";
  if (recipe?.region_set_id === "gfp_positive") return "gfp";
  if (recipe?.region_set_id === "ncl_positive") return "ncl";
  if (recipe && recipe.source !== "stardist_nuclear") throw new Error("保存された領域の種類を識別できません。解析方法を選んで再実行してください。");
  return "nuclei";
}

/** The channel that defines a compartment is not necessarily the measured NCL channel. */
export function nucleolarSource(recipe: Recipe): "ncl" | "dapi_poor" | "marker" {
  const detector = recipe.detector;
  return detector?.engine === "cytellect-nucleolar-v2" ? detector.source : "ncl";
}

/** Derived masks are usable only with the exact selected parent and channel mapping. */
export function validTargetResults(cached: TargetResults | undefined, current?: TargetResult, channels: {nuclear?: string; ncl?: string; gfp?: string} = {}): TargetResults {
  const targets = {...cached, ...(current ? {[targetOf(current.recipe)]: current} : {})};
  for (const [target, channel] of [["nuclei", channels.nuclear], ["ncl", channels.ncl], ["gfp", channels.gfp]] as const) {
    if (channel && targets[target]?.recipe.defining_channel_id !== channel) delete targets[target];
  }
  const parent = targets.nuclei;
  for (const key of ["nucleoli", "nucleoplasm"] as const) {
    const derived = targets[key];
    if (derived && (!parent || derived.recipe.nuclear_revision_id !== parent.result.revision ||
      derived.recipe.nuclear_channel_id !== parent.recipe.defining_channel_id ||
      (channels.nuclear && parent.recipe.defining_channel_id !== channels.nuclear) ||
      (nucleolarSource(derived.recipe) === "ncl" && channels.ncl && derived.recipe.defining_channel_id !== channels.ncl) ||
      (nucleolarSource(derived.recipe) === "dapi_poor" && derived.recipe.defining_channel_id !== parent.recipe.defining_channel_id))) delete targets[key];
  }
  return targets;
}
