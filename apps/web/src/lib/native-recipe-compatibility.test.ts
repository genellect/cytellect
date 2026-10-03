import { describe, expect, it } from "vitest";
import { defaultRecipe, type Config, type Recipe } from "./types";
import { nativeRecipeCompatibility, recipeCompatibilityMessage, requiredNativeRoles, savedRecipeFields } from "./native-recipe-compatibility";

const recipe = (value: Partial<Recipe> = {}): Recipe => ({ ...structuredClone(defaultRecipe), ...value });
const ncl = { id: "ncl-field", image_info: { legacy: false, channel_roles: ["dapi", "ncl"] } };
const gfp = { id: "gfp-field", image_info: { legacy: false, channel_roles: ["dapi", "gfp"] } };
const all = { id: "all-field", image_info: { legacy: false, channel_roles: ["dapi", "ncl", "gfp"] } };
const fields = [ncl, gfp, all];

describe("native recipe acquired-channel guidance", () => {
  it("requires the actual recipe roles, including NCL for a low nuclear-stain region definition", () => {
    expect(requiredNativeRoles(recipe())).toEqual(["dapi", "ncl"]);
    expect(requiredNativeRoles(recipe({ nucleolar_method: "dapi-low" }))).toEqual(["dapi", "ncl"]);
    expect(requiredNativeRoles(recipe({ id: "gfp-nuclear-2d" }))).toEqual(["dapi", "gfp"]);
    expect(requiredNativeRoles(recipe({ id: "ncl-legacy-rgb" }))).toEqual(["dapi", "ncl", "gfp"]);
  });

  it.each(["manual", "negative-control", "otsu-batch"] as const)("requires GFP for %s selection", gfp_gate => {
    expect(nativeRecipeCompatibility(recipe({ gfp_gate }), [ncl], [ncl.id]).issues[0].missingRoles).toEqual(["gfp"]);
  });

  it.each([-2, 0, 2])("requires GFP for a maximum of %s, including zero and signed bounds", gfp_maximum => {
    expect(nativeRecipeCompatibility(recipe({ gfp_maximum }), [ncl], [ncl.id]).ready).toBe(false);
  });

  it("does not treat an unused threshold alone as GFP selection", () => {
    expect(nativeRecipeCompatibility(recipe({ gfp_threshold: 10, gfp_gate: "none", gfp_maximum: null }), [ncl], [ncl.id]).ready).toBe(true);
  });

  it("validates exactly the trial or full batch without dropping a deficient field", () => {
    const selected = recipe({ id: "gfp-nuclear-2d" });
    const original = structuredClone(fields);
    expect(nativeRecipeCompatibility(selected, fields, [gfp.id]).ready).toBe(true);
    const batch = nativeRecipeCompatibility(selected, fields, fields.map(field => field.id));
    expect(batch.ready).toBe(false);
    expect(batch.issues).toMatchObject([{ fieldId: ncl.id, missingRoles: ["gfp"] }]);
    expect(recipeCompatibilityMessage(batch, fields.map(field => field.id))).toBe("視野 1：GFPが未取得。");
    expect(fields).toEqual(original);
  });

  it("only reconfigure can use explicitly supplied whole-field exclusions", () => {
    const gated = recipe({ gfp_gate: "otsu-batch" });
    const ids = [ncl.id, all.id];
    expect(nativeRecipeCompatibility(gated, fields, ids).ready).toBe(false);
    expect(nativeRecipeCompatibility(gated, fields, ids, [ncl.id]).ready).toBe(true);
    expect(nativeRecipeCompatibility(gated, fields, ids, ids).ready).toBe(true);
    expect(nativeRecipeCompatibility(gated, fields, ids).issues).toHaveLength(1);
  });

  it("retains negative-control scope even when that field was explicitly excluded from remeasurement", () => {
    const selected = recipe({ gfp_negative_control_fields: [all.id] });
    expect(nativeRecipeCompatibility(selected, fields, [ncl.id]).outsideControls).toEqual([all.id]);
    expect(nativeRecipeCompatibility(selected, fields, [ncl.id]).ready).toBe(false);
    expect(nativeRecipeCompatibility(selected, fields, [ncl.id, all.id], [all.id]).ready).toBe(true);
  });

  it("does not describe a grayscale input as available for the RGB compatibility recipe", () => {
    expect(nativeRecipeCompatibility(recipe({ id: "ncl-legacy-rgb" }), [all], [all.id]).issues[0].inputModeMismatch).toBe(true);
    const rgb = { ...all, image_info: { ...all.image_info, legacy: true } };
    expect(nativeRecipeCompatibility(recipe({ id: "ncl-legacy-rgb" }), [rgb], [rgb.id]).ready).toBe(true);
    expect(nativeRecipeCompatibility(recipe(), [rgb], [rgb.id]).ready).toBe(false);
  });

  it("fails closed for a missing field or empty selection, not treating absence as historical three-channel input", () => {
    expect(nativeRecipeCompatibility(recipe(), fields, []).ready).toBe(false);
    const absent = nativeRecipeCompatibility(recipe(), fields, ["absent"]);
    expect(absent.ready).toBe(false);
    expect(absent.issues[0].unavailable).toBe(true);
    expect(nativeRecipeCompatibility(recipe(), [], ["absent"], ["absent"]).ready).toBe(false);
  });

  it("uses saved snapshots and preserves only the API's absent-channel_roles historical fallback", () => {
    const config: Config & { field_snapshot: unknown } = { recipe: recipe(), backgrounds: {}, exclusions: [], field_ids: [gfp.id], field_snapshot: { [gfp.id]: gfp } };
    const original = structuredClone(config);
    expect(nativeRecipeCompatibility(config.recipe, savedRecipeFields(config), [gfp.id]).issues[0].missingRoles).toEqual(["ncl"]);
    expect(config).toEqual(original);
    config.field_snapshot = { [all.id]: { image_info: { legacy: false } } };
    expect(nativeRecipeCompatibility(recipe(), savedRecipeFields(config), [all.id]).ready).toBe(true);
  });

  it.each([undefined, null, [], {}, { broken: { image_info: { legacy: false, channel_roles: null } } }])("does not substitute current uploads for missing or malformed snapshots: %j", field_snapshot => {
    const config: Config & { field_snapshot?: unknown } = { recipe: recipe(), backgrounds: {}, exclusions: [], field_snapshot };
    expect(savedRecipeFields(config)).toEqual([]);
  });
});
