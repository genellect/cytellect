import { describe, expect, it } from "vitest";
import { groupFiles } from "./grouping";
import { affectedFields, initialState, phase, reducer, regionState, type WorkspaceState } from "./model";
import { fieldDistribution } from "./adapter";

const grouping = groupFiles(["A01_dapi.tif", "A01_gfp.tif", "A02_dapi.tif", "A02_gfp.tif"].map((path) => ({ path, size: 1 })));
const result = (values: number[]) => ({ measurements: values.map((area, index) => ({ region_id: index + 1, area_px: area })), outlines: null });

function adopted(): WorkspaceState {
  let state = reducer(initialState(), { type: "imported", name: "w", grouping });
  state = reducer(state, { type: "adopt" });
  return state;
}

describe("workspace reducer", () => {
  it("moves from empty to proposal to running to results without job chaining", () => {
    expect(phase(initialState())).toBe("empty");
    const imported = reducer(initialState(), { type: "imported", name: "w", grouping });
    expect(phase(imported)).toBe("proposal");
    let state = reducer(imported, { type: "adopt" });
    expect(phase(state)).toBe("running");
    state = reducer(state, { type: "field-done", field: "A01", result: result([1, 2]) });
    expect(phase(state)).toBe("running");
    state = reducer(state, { type: "field-failed", field: "A02", error: "x" });
    expect(phase(state)).toBe("results");
    expect(state.results.A01.measurements).toHaveLength(2);
  });

  it("refuses adoption while the proposal has unresolved items", () => {
    const unknown = groupFiles(["c1-A01.tif"].map((path) => ({ path, size: 1 })));
    const state = reducer(reducer(initialState(), { type: "imported", name: "w", grouping: unknown }), { type: "adopt" });
    expect(state.adopted).toBeNull();
  });

  it("keeps successful fields when one fails and retries only the failed field", () => {
    let state = reducer(adopted(), { type: "field-done", field: "A01", result: result([3]) });
    state = reducer(state, { type: "field-failed", field: "A02", error: "x" });
    state = reducer(state, { type: "retry", field: "A02" });
    expect(state.runs).toEqual({ A01: { status: "done" }, A02: { status: "waiting" } });
    expect(state.results.A01).toBeDefined();
  });

  it("records corrections as user records with undo/redo and limits invalidation to that field", () => {
    let state = reducer(adopted(), { type: "field-done", field: "A01", result: result([1, 2, 3]) });
    state = reducer(state, { type: "field-done", field: "A02", result: result([4]) });
    state = reducer(state, { type: "correct", correction: { kind: "exclude", field: "A01", region: 2 } });
    state = reducer(state, { type: "correct", correction: { kind: "exclude", field: "A01", region: 99 } });
    expect(state.corrections).toEqual([{ kind: "exclude", field: "A01", region: 2, origin: "user" }]);
    expect(affectedFields(state)).toEqual(new Set(["A01"]));
    expect(regionState(state, "A01", 2)).toBe("excluded");
    state = reducer(state, { type: "undo" });
    expect(regionState(state, "A01", 2)).toBe("included");
    state = reducer(state, { type: "redo" });
    expect(regionState(state, "A01", 2)).toBe("excluded");
  });

  it("changes figure styling without touching runs, results or corrections", () => {
    const state = reducer(adopted(), { type: "field-done", field: "A01", result: result([1]) });
    const styled = reducer(state, { type: "figure", settings: { widthMm: 183, yLabel: "Area" } });
    expect(styled.runs).toBe(state.runs);
    expect(styled.results).toBe(state.results);
    expect(styled.corrections).toBe(state.corrections);
  });
});

describe("fieldDistribution", () => {
  it("summarizes included values with linear quartiles and keeps excluded values visible", () => {
    let state = reducer(adopted(), { type: "field-done", field: "A01", result: result([1, 2, 3, 4, 100]) });
    state = reducer(state, { type: "correct", correction: { kind: "exclude", field: "A01", region: 5 } });
    state = reducer(state, { type: "correct", correction: { kind: "delete", field: "A01", region: 1 } });
    const { points, summaries } = fieldDistribution(state, "area_px");
    expect(points.map((point) => [point.region, point.state])).toEqual([[2, "included"], [3, "included"], [4, "included"], [5, "excluded"]]);
    expect(summaries[0]).toEqual({ field: "A01", n: 3, excluded: 1, median: 3, q1: 2.5, q3: 3.5 });
  });
});
