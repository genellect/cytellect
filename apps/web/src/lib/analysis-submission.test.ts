import { describe, expect, it } from "vitest";
import { analysisSubmission, missingBackgroundFields, sameRecipe } from "./analysis-submission";
import { defaultRecipe, type Config, type Revision } from "./types";

const config: Config = { recipe: structuredClone(defaultRecipe), backgrounds: {}, exclusions: [] };
function revision(overrides: Partial<Revision> = {}): Revision {
  return { id: "edited-trial", parent_id: "initial", state: "succeeded", reviewed: false, created: 1, config: { ...config, field_ids: ["field-a"] }, ...overrides };
}

describe("representative field to batch", () => {
  it("reuses the edited successful trial, while detecting only the remaining fields", () => {
    const plan = analysisSubmission(config, revision(), ["field-a", "field-b", "field-c"], "batch", "field-a");
    expect(plan).toMatchObject({ reuse_revision: "edited-trial", preservedCount: 1, detectedCount: 2, confirmationRequired: false, field_ids: null });
  });

  it("requires explicit re-detection after a changed recipe, including nested legacy options", () => {
    const changed: Config = { ...config, recipe: { ...config.recipe, legacy: { ...config.recipe.legacy, dapi_snr_min: config.recipe.legacy.dapi_snr_min * 2 } } };
    expect(analysisSubmission(changed, revision(), ["field-a", "field-b"], "batch", "field-a")).toMatchObject({ reuse_revision: null, replacedCount: 1, detectedCount: 2, recipeChanged: true, confirmationRequired: true });
  });

  it("a repeated trial cannot silently overwrite the previously edited field", () => {
    expect(analysisSubmission(config, revision(), ["field-a", "field-b"], "trial", "field-a")).toMatchObject({ field_ids: ["field-a"], reuse_revision: null, replacedCount: 1, confirmationRequired: true });
    expect(analysisSubmission(config, revision(), ["field-a", "field-b"], "trial", "field-b")).toMatchObject({ field_ids: ["field-b"], confirmationRequired: false });
  });

  it("never reuses a failed revision or a source containing fields outside the batch", () => {
    expect(analysisSubmission(config, revision({ state: "failed" }), ["field-a"], "batch", "field-a").reuse_revision).toBeNull();
    expect(analysisSubmission(config, revision(), ["field-b"], "batch", "field-b").reuse_revision).toBeNull();
  });

  it("background and exclusion changes retain masks, without claiming unchanged measurement conditions", () => {
    const changed: Config = { ...config, backgrounds: { "field-a": { confirmed: true, polygon: [[1, 1], [4, 1], [4, 4]] } }, exclusions: [{ field_id: "field-a", nucleus_id: 2, reason: "Review exclusion" }] };
    expect(analysisSubmission(changed, revision(), ["field-a", "field-b"], "batch", "field-a").reuse_revision).toBe("edited-trial");
    expect(missingBackgroundFields(changed, ["field-a", "field-b"])).toEqual(["field-b"]);
  });

  it("compares complete recipe values independently of JSON property order", () => {
    expect(sameRecipe(config.recipe, Object.fromEntries(Object.entries(config.recipe).reverse()) as typeof config.recipe)).toBe(true);
    expect(missingBackgroundFields({ ...config, recipe: { ...config.recipe, id: "ncl-legacy-rgb" } }, ["field-a"])).toEqual([]);
  });
});
