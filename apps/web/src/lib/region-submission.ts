import type { RegionConfig, RegionRecipe, RegionRevision } from "./region-types";

function canonical(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === "object") return Object.fromEntries(Object.entries(value).sort(([a],[b])=>a.localeCompare(b)).map(([key,item])=>[key,canonical(item)]));
  return value;
}

export function sameRegionRecipe(left:RegionRecipe,right:RegionRecipe):boolean {
  return JSON.stringify(canonical(left))===JSON.stringify(canonical(right));
}

/** A changed recipe never reuses masks; an explicit re-detection always replaces its scope. */
export function regionSubmission(config:RegionConfig,active:RegionRevision|undefined,fieldIds:string[],fieldId:string,scope:"add"|"batch"|"redetect") {
  const previous=active?.state==="succeeded"?active.config.field_ids??[]:[];
  const unchanged=!!active&&sameRegionRecipe(config.recipe,active.config.recipe);
  const target=scope==="batch"?fieldIds:scope==="add"&&unchanged?[...new Set([...previous,fieldId])]:[fieldId];
  const reuse=scope!=="redetect"&&unchanged&&previous.length>0&&previous.every(id=>target.includes(id));
  const replacedCount=reuse?0:previous.filter(id=>target.includes(id)).length;
  return {field_ids:target,reuse_revision:reuse?active!.id:null,preservedCount:reuse?previous.length:0,replacedCount,confirmationRequired:replacedCount>0,recipeChanged:!!active&&!unchanged};
}
