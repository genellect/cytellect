import {describe, expect, it} from "vitest";
import {validRecordedStatistics} from "./index";

describe("the demo's recorded statistics (genellect/cytellect#257 D-1)", () => {
  it("reads each scene's recorded choices and drops malformed items", () => {
    expect(validRecordedStatistics({version: 1, scenes: {
      oxaliplatin: [
        {analysis: "comparison", region: "nucleoli", metric: "mean", channel: "npm1", positivity: null, gate: null},
        {analysis: "association", region: "nuclei", metric: "mean", channel: "npm1", positivity: null, gate: null, x: {metric: "area_px", channel: null}},
        {analysis: "test", region: "nuclei", metric: "mean"},
        {analysis: "distribution", region: "", metric: "mean"},
        null,
      ],
      broken: "not a list",
    }})).toEqual({
      oxaliplatin: [
        {analysis: "comparison", region: "nucleoli", metric: "mean", channel: "npm1", positivity: null, gate: null},
        {analysis: "association", region: "nuclei", metric: "mean", channel: "npm1", positivity: null, gate: null, x: {metric: "area_px", channel: null}},
      ],
      broken: [],
    });
  });
  it("offers every choice when no index is published", () => {
    expect(validRecordedStatistics(null)).toBeNull();
    expect(validRecordedStatistics({version: 2, scenes: {}})).toBeNull();
    expect(validRecordedStatistics({version: 1})).toBeNull();
  });
});
