import type { Config, Recipe, Revision } from "./types";

export type AnalysisScope = "trial" | "batch";

function canonical(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.entries(value).sort(([a], [b]) => a.localeCompare(b)).map(([key, item]) => [key, canonical(item)]));
  }
  return value;
}

export function sameRecipe(left: Recipe, right: Recipe): boolean {
  return JSON.stringify(canonical(left)) === JSON.stringify(canonical(right));
}

/** The API validates reuse again against its current immutable revision. */
export function analysisSubmission(config: Config, active: Revision | undefined, fieldIds: string[], scope: AnalysisScope, fieldId: string) {
  const selected = scope === "trial" ? [fieldId] : fieldIds;
  const previous = active?.state === "succeeded" ? active.config.field_ids ?? [] : [];
  const unchanged = !!active && sameRecipe(config.recipe, active.config.recipe);
  const reuse = scope === "batch" && previous.length > 0 && unchanged && previous.every(id => selected.includes(id));
  const replacedCount = reuse ? 0 : previous.filter(id => selected.includes(id)).length;
  return {
    field_ids: scope === "trial" ? selected : null,
    reuse_revision: reuse ? active!.id : null,
    preservedCount: reuse ? previous.length : 0,
    detectedCount: selected.length - (reuse ? previous.length : 0),
    replacedCount,
    confirmationRequired: replacedCount > 0,
    recipeChanged: !!active && !unchanged,
  };
}

export function missingBackgroundFields(config: Config, fieldIds: string[]): string[] {
  return config.recipe.id === "ncl-legacy-rgb" ? [] : fieldIds.filter(id => !config.backgrounds[id]?.confirmed);
}
