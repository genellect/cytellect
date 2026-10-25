import {describe, expect, it} from "vitest";
import {validReference, validScenes} from "./index";

const dataset = {title: "Public images", attribution: "Source, CC0", licence: "CC0-1.0", licenceUrl: "https://example.org/l", sourceUrl: "https://example.org/s", caveats: ["note"]};
describe("demo scenes", () => {
  it("keeps complete scenes with their own dataset, regions and examples", () => {
    const scenes = validScenes({version: 1, scenes: [
      {id: "count", label: "核数", workspaceId: "w1", ...dataset, regions: ["nuclei"], examples: [{label: "a", instruction: "b"}]},
      {id: "nucleoli", label: "核小体", workspaceId: "w2", ...dataset, regions: ["nuclei", "nucleoli", "nucleoplasm"], examples: []},
      {id: "broken", label: "", workspaceId: "w3", ...dataset},
    ]});
    expect(scenes.map(scene => scene.id)).toEqual(["count", "nucleoli"]);
    expect(scenes[0].dataset.regions).toEqual(["nuclei"]);
    expect(scenes[0].examples).toEqual([{label: "a", instruction: "b"}]);
  });
  it("reads a single-scene demo as no scenes", () => {
    expect(validScenes(null)).toEqual([]);
    expect(validScenes({version: 1})).toEqual([]);
  });
  it("keeps only a snapshot reference file name", () => {
    const [kept, dropped] = validScenes({version: 1, scenes: [
      {id: "count", label: "核数", workspaceId: "w1", ...dataset, reference: "reference-jump.json"},
      {id: "other", label: "他", workspaceId: "w2", ...dataset, reference: "../secret.json"},
    ]});
    expect(kept.reference).toBe("reference-jump.json");
    expect(dropped.reference).toBeUndefined();
  });
});

describe("reference objects", () => {
  it("reads match counts and drops malformed markers", () => {
    const reference = validReference({version: 1, label: "CellProfiler", note: "n", fields: {
      f1: {both: 3, split: 1, reference_only: 2, labels_only: 1, labels: 5, count_nuclei: 6, median_area_px: {both: 900, split: null, reference_only: 330},
        markers: [[10, 12, 8, "both"], [1, 2, 3, "unknown"], [1, "x", 3, "split"], [4, 5, 0.5, "reference_only"]]},
      f2: {both: "3"},
    }});
    expect(Object.keys(reference!.fields)).toEqual(["f1"]);
    expect(reference!.fields.f1).toMatchObject({both: 3, referenceOnly: 2, countNuclei: 6, medianAreaPx: {both: 900, split: null, referenceOnly: 330}});
    expect(reference!.fields.f1.markers).toEqual([{x: 10, y: 12, r: 8, tone: "both"}, {x: 4, y: 5, r: 2, tone: "reference_only"}]);
    expect(reference!.groups).toEqual([]);
    expect(validReference({version: 2, label: "x", fields: {}})).toBeNull();
  });
  it("reads the build's group means and ratios", () => {
    const reference = validReference({version: 1, label: "CellProfiler", fields: {f1: {both: 1, split: 0, reference_only: 0, labels_only: 0, labels: 1, markers: []}},
      groups: [{id: "control", label: "NT", fields: 9, cytellect_per_field: 300, cellprofiler_per_field: 310, reference_only_per_field: 2, split_per_field: 1, labels_only_per_field: 3,
        matched_fraction: 0.95, reference_only_median_area_px: 250, matched_median_area_px: 900}, {id: "bad", label: "x"}],
      ratio: {cytellect: 0.18, cellprofiler: 0.25}, runs: [{id: "run1", label: "Run1", ratio: null}]});
    expect(reference!.groups).toHaveLength(1);
    expect(reference!.groups[0]).toMatchObject({cytellect: 300, cellprofiler: 310, matchedFraction: 0.95});
    expect(reference!.ratio).toEqual({cytellect: 0.18, cellprofiler: 0.25});
    expect(reference!.runs).toEqual([{id: "run1", label: "Run1", ratio: null}]);
  });
});
