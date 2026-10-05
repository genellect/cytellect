import { describe, expect, it } from "vitest";
import { groupFiles } from "./grouping";
import { affectedFields, initialState, phase, reducer, regionState, type WorkspaceState } from "./model";
import { createPrototypeAdapter, fieldDistribution } from "./adapter";

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

  it("refuses adoption until the single nuclear choice is made, and records that choice", () => {
    const unknown = groupFiles(["c1-A01.tif", "c2-A01.tif"].map((path) => ({ path, size: 1 })));
    let state = reducer(reducer(initialState(), { type: "imported", name: "w", grouping: unknown }), { type: "adopt" });
    expect(state.adopted).toBeNull();
    state = reducer(state, { type: "choose-nuclear", token: "c2" });
    expect(state.channelHistory).toEqual([{ token: "c2", change: "nuclear", value: "c2" }]);
    state = reducer(state, { type: "adopt" });
    expect(state.adopted?.proposal.recipe).toBe("nuclear-intensity");
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

describe("stop and resume", () => {
  it("keeps completed fields and continues only the waiting ones", () => {
    let state = reducer(adopted(), { type: "field-done", field: "A01", result: result([1]) });
    state = reducer(state, { type: "stop" });
    expect(phase(state)).toBe("results");
    expect(reducer(state, { type: "field-started", field: "A02" }).runs.A02.status).toBe("waiting");
    state = reducer(state, { type: "resume" });
    expect(phase(state)).toBe("running");
    expect(state.runs).toEqual({ A01: { status: "done" }, A02: { status: "waiting" } });
  });
});

describe("prototype exports", () => {
  const sample = groupFiles(["Channel1-01-A-01.BMP", "Channel2-01-A-01.BMP"].map((name) => ({ path: `BBBC013/${name}`, size: 0 })));
  const adapter = createPrototypeAdapter({ fetcher: (async () => new Response(JSON.stringify({
    dataset: "d", attribution: "a", source: "s", license: "l",
    fields: [{ well: "A01", width: 1, height: 1, outlines: null, measurements: [],
      channels: [{ source_name: "Channel1-01-A-01.BMP", stain: "x", preview: "p", recorded_role: "gfp" }] }],
  }))) as typeof fetch });
  const hrefs = (state: WorkspaceState) => Object.fromEntries(adapter.exports(state).map((item) => [item.label, item.href ?? item.reason]));

  it("offers saved outputs only for the completed example, unchanged and as displayed", async () => {
    await adapter.loadSample();
    let state = reducer(reducer(initialState(), { type: "imported", name: "w", grouping: sample }), { type: "choose-nuclear", token: "channel2" });
    state = reducer(state, { type: "adopt" });
    expect(hrefs(state).CSV).toBe("すべての画像の解析が終わると書き出せます");
    state = reducer(state, { type: "field-done", field: "BBBC013/01-A-01", result: result([5]) });
    expect(hrefs(state)).toMatchObject({ SVG: "/marketing/figure-public.svg", CSV: "/marketing/figure-public.csv" });
    const other = reducer(state, { type: "figure", settings: { metric: "channel1:mean_raw" } });
    expect(hrefs(other).SVG).toContain("表示中のグラフが異なります");
    expect(hrefs(other).CSV).toBe("/marketing/figure-public.csv");
    const corrected = reducer(state, { type: "correct", correction: { kind: "exclude", field: "BBBC013/01-A-01", region: 1 } });
    expect(hrefs(corrected).CSV).toBe("修正後の書き出しはプロトタイプでは未対応");
  });

  it("never offers the example's files for images the user added", () => {
    let state = reducer(initialState(), { type: "imported", name: "w", grouping });
    state = reducer(state, { type: "adopt" });
    state = reducer(state, { type: "field-done", field: "A01", result: result([1]) });
    state = reducer(state, { type: "field-done", field: "A02", result: result([1]) });
    expect(Object.values(hrefs(state)).every((value) => !String(value).startsWith("/"))).toBe(true);
    expect(hrefs(state).CSV).toBe("この画像の書き出しはプロトタイプでは未対応");
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
