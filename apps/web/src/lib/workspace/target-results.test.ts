import {describe, expect, it} from "vitest";
import type {Recipe, SavedResult} from "./api-adapter";
import {targetOf, validTargetResults, type TargetResult, type TargetResults} from "./target-results";

const result = (revision: string): SavedResult => ({revision, field: "field-a", rows: [], masks: {regions: [], metadata: {mask_revision_id: revision}}, exclusions: []});
const nuclear = (revision = "nucleus-a", channel = "c4"): TargetResult => ({result: result(revision), recipe: {id: "region-2d", version: "1.2.0", region_set_id: "nuclei", label: "核", source: "stardist_nuclear", defining_channel_id: channel, nuclear_role_source: "user_selected_role"}});
const compartment = (kind: "nucleoli" | "nucleoplasm", parent = "nucleus-a", ncl = "c1", nuclearChannel = "c4"): TargetResult => ({result: result(kind + "-a"), recipe: {id: "region-2d", version: "1.4.0", region_set_id: kind, label: kind, source: "fiji_nuclear_compartment", compartment: kind, nuclear_revision_id: parent, nuclear_channel_id: nuclearChannel, defining_channel_id: ncl}});
const cache = (): TargetResults => ({nuclei: nuclear(), nucleoli: compartment("nucleoli"), nucleoplasm: compartment("nucleoplasm")});

describe("derived target validity", () => {
  it("retains both compartments only against the exact parent and selected channels", () => {
    const original = cache();
    expect(validTargetResults(original, undefined, {nuclear: "c4", ncl: "c1"})).toEqual(original);
  });
  it("current selected parent overrides a newer cached parent after undo", () => {
    const original = {...cache(), nuclei: nuclear("new-parent")};
    const chosen = nuclear();
    const valid = validTargetResults(original, chosen);
    expect(valid.nuclei).toBe(chosen);
    expect(valid.nucleoli).toBe(original.nucleoli);
    expect(valid.nucleoplasm).toBe(original.nucleoplasm);
  });
  it("a nucleus edit invalidates both compartments but preserves independent GFP", () => {
    const gfp: TargetResult = {result: result("gfp"), recipe: {id: "region-2d", version: "1.3.0", source: "fiji_positive_regions", region_set_id: "gfp_positive", label: "GFP", defining_channel_id: "c3"}};
    const original = {...cache(), gfp};
    const edited = nuclear("nucleus-edited");
    expect(validTargetResults(original, edited)).toEqual({nuclei: edited, gfp});
    expect(Object.keys(original)).toEqual(["nuclei", "nucleoli", "nucleoplasm", "gfp"]);
  });
  it("rejects the nucleus and both compartments after nuclear channel remapping", () => {
    expect(validTargetResults(cache(), undefined, {nuclear: "c2"})).toEqual({});
  });
  it("rejects both compartments but retains the nucleus after NCL channel remapping", () => {
    expect(validTargetResults(cache(), undefined, {ncl: "c3"})).toEqual({nuclei: nuclear()});
  });
  it.each(["dapi_poor", "marker"] as const)("keeps %s compartments when only the measurement NCL channel changes", source => {
    const original = cache();
    for (const target of ["nucleoli", "nucleoplasm"] as const) {
      original[target]!.recipe = {...original[target]!.recipe, defining_channel_id:source === "dapi_poor" ? "c4" : "c2", detector:{engine:"cytellect-nucleolar-v2",protocol_version:"2.0.0",source,smoothing_sigma_px:1,rim_exclusion_px:2,relative_threshold:0.7,marker_fraction:0.4,background_radius_px:20,minimum_area_px:1,maximum_area_px:null,minimum_solidity:0.5}};
    }
    expect(validTargetResults(original, undefined, {nuclear:"c4",ncl:"c1"})).toEqual(original);
    if (source === "dapi_poor") {
      original.nucleoli!.recipe = {...original.nucleoli!.recipe,defining_channel_id:"c2"};
      expect(validTargetResults(original, undefined, {nuclear:"c4",ncl:"c1"}).nucleoli).toBeUndefined();
    }
  });
  it("does not relabel an unknown positive mask as a nuclear mask", () => {
    const recipe: Recipe = {id:"region-2d",version:"1.3.0",source:"fiji_positive_regions",region_set_id:"signal_positive",label:"陽性領域",defining_channel_id:"c2"};
    expect(() => targetOf(recipe)).toThrow("領域の種類を識別できません");
    expect(() => validTargetResults(cache(), {recipe,result:result("signal")})).toThrow();
  });
  it.each(["gfp", "ncl"] as const)("invalidates %s positive regions only on an explicit changed channel", target => {
    const saved: TargetResult = {result: result(target), recipe: {id: "region-2d", version: "1.3.0", source: "fiji_positive_regions", region_set_id: target + "_positive", label: target, defining_channel_id: "c3"}};
    const original = {...cache(), [target]: saved};
    expect(validTargetResults(original)[target]).toBe(saved);
    expect(validTargetResults(original, undefined, {[target]: "c3"})[target]).toBe(saved);
    expect(validTargetResults(original, undefined, {[target]: "c2"})[target]).toBeUndefined();
    expect(original[target]).toBe(saved);
  });
  it("cannot restore a mismatched current nucleus by overriding cached targets", () => {
    expect(validTargetResults(cache(), nuclear("other", "c2"), {nuclear: "c4"})).toEqual({});
  });
  it("rejects a compartment recorded against a different nuclear channel", () => {
    const original = cache();
    original.nucleoli = compartment("nucleoli", "nucleus-a", "c1", "c2");
    expect(validTargetResults(original).nucleoli).toBeUndefined();
    expect(validTargetResults(original).nucleoplasm).toBe(original.nucleoplasm);
  });
  it("rejects orphaned compartments even when both share a parent reference", () => {
    expect(validTargetResults({nucleoli: compartment("nucleoli"), nucleoplasm: compartment("nucleoplasm")})).toEqual({});
  });
  it("current derived output cannot revive an invalidated parent", () => {
    const original = {nuclei: nuclear("edited")};
    expect(validTargetResults(original, compartment("nucleoli"))).toEqual(original);
  });
  it("restore insertion order cannot change parent validity", () => {
    const forward = cache();
    const reversed = Object.fromEntries(Object.entries(forward).reverse()) as TargetResults;
    expect(validTargetResults(reversed)).toEqual(validTargetResults(forward));
    expect(validTargetResults(reversed, nuclear("edited"))).toEqual(validTargetResults(forward, nuclear("edited")));
  });
  it("never mutates the input cache or saved records when invalidating", () => {
    const original = cache();
    const before = structuredClone(original);
    Object.values(original).forEach(value => {Object.freeze(value!.recipe); Object.freeze(value!.result); Object.freeze(value);});
    Object.freeze(original);
    const valid = validTargetResults(original, nuclear("edited"));
    expect(valid).not.toBe(original);
    expect(valid.nucleoli).toBeUndefined();
    expect(original).toEqual(before);
  });
  it.each(["nucleoli", "nucleoplasm"] as const)("identifies %s from compartment even when the display region ID differs", kind => {
    const recipe: Recipe = {...compartment(kind).recipe, region_set_id: "custom"};
    expect(targetOf(recipe)).toBe(kind);
  });
});
