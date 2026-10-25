import {describe, expect, it} from "vitest";
import {validScenes} from "./index";

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
});
