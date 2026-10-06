import {describe, expect, it} from "vitest";
import {uniqueRegionCount} from "./FieldImage";

describe("region counts from display contours", () => {
  it("counts a region with a hole and disconnected pieces only once", () => {
    expect(uniqueRegionCount([{id: 7}, {id: 7}, {id: 7}, {id: 19}])).toBe(2);
  });
  it("accepts saved numeric and display string IDs without double counting", () => {
    expect(uniqueRegionCount([{id: 7}, {id: "7"}, {id: "19"}])).toBe(2);
    expect(uniqueRegionCount([])).toBe(0);
  });
});
