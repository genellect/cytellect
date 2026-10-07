import {describe, expect, it, vi} from "vitest";
import {comparisonRequest, createComparisonAdapter, type ComparisonChoices, type ComparisonSource} from "./comparison-adapter";
import type {Transport} from "./api-adapter";
const choices: ComparisonChoices = {metric: "area_px", channel: null, regionSet: "nuclei", design: "independent", method: "rank", unitDefinition: "independent culture", pairingBasis: "", contrasts: [["A", "B"]], independence: true, acquisition: true, sampling: true, missingness: true, kind: "box", width: 178, height: 76, yLabel: ""};
const sources: ComparisonSource[] = ["f1", "f2"].map((field, i) => ({field, revision: `r${i}`, label: field, metadata: {}, result: {field, revision: `r${i}`, rows: [], masks: {regions: [], metadata: {mask_revision_id: `m${i}`}}, exclusions: []}}));
function fake(handler: (path: string) => Promise<unknown>, accept?: (path: string, body: unknown) => Promise<unknown>) {
  const request = vi.fn(handler) as unknown as Transport["request"];
  const post = vi.fn(accept ?? (async () => ({job_id: "j", revision_id: "cohort"}))) as unknown as Transport["post"];
  return {adapter: createComparisonAdapter({request, post, wait: async () => {}}), request, post};
}
describe("workspace inference boundaries", () => {
  it("never fabricates decisions or treats observations as independent units", () => {
    for (const key of ["independence", "acquisition", "sampling", "missingness"] as const) expect(() => comparisonRequest({...choices, [key]: false})).toThrow();
    const request = comparisonRequest(choices);
    expect(request.test).toBe("mann-whitney-u");
    expect(request.aggregation).toBe("field-median_sample-mean_unit-mean-v1");
    expect(request.comparison_family.contrasts).toEqual([["A", "B"]]);
    expect(request.design.unit_definition).toBe("independent culture");
    expect(() => comparisonRequest({...choices, design: "paired"})).toThrow("対応");
    expect(comparisonRequest({...choices, design: "paired", pairingBasis: "same culture before/after", kind: "paired"}).test).toBe("wilcoxon");
  });
  it("selects per-nucleus compartment-summary metrics without inventing a channel", () => {
    const ratio = comparisonRequest({...choices, metric: "log2_nucleoplasm_over_nucleolus", regionSet: "nucleoplasm", channel: "ncl"});
    expect(ratio.selection).toEqual({source: "compartment-summary", version: "1.0.0", region_set_id: "nucleoplasm", metric: "log2_nucleoplasm_over_nucleolus", channel_id: "ncl"});
    expect(comparisonRequest({...choices, metric: "nucleolar_count", channel: "ncl"}).selection.channel_id).toBeNull();
    expect(() => comparisonRequest({...choices, metric: "nucleolar_area_fraction", sampling: false})).toThrow();
    expect(comparisonRequest(choices).selection).toEqual({source: "region", region_set_id: "nuclei", metric: "area_px", channel_id: null});
  });
  it("adds the GFP nucleus filter only from an explicit channel and control-field decision", () => {
    expect("gfp_gate" in comparisonRequest(choices).selection).toBe(false);
    expect("gfp_gate" in comparisonRequest({...choices, gfp: null}).selection).toBe(false);
    const gated = comparisonRequest({...choices, metric: "mean", channel: "ncl", gfp: {channel: "gfp", controls: ["f-control", "f-control"]}});
    expect(gated.selection).toEqual({source: "region", region_set_id: "nuclei", metric: "mean", channel_id: "ncl",
      gfp_gate: {version: "1.0.0", gate_protocol: "gfp-gate/2.0.0", gfp_channel_id: "gfp", percentile: 99, control_field_ids: ["f-control"], keep: "positive"}});
    const ratio = comparisonRequest({...choices, metric: "log2_nucleoplasm_over_nucleolus", regionSet: "nucleoplasm", channel: "ncl", gfp: {channel: "gfp", controls: ["c"], keep: "negative", percentile: 95}});
    expect(ratio.selection).toMatchObject({source: "compartment-summary", gfp_gate: {keep: "negative", percentile: 95, control_field_ids: ["c"]}});
    expect(() => comparisonRequest({...choices, gfp: {channel: "gfp", controls: []}})).toThrow("陰性対照");
    expect(() => comparisonRequest({...choices, gfp: {channel: "", controls: ["c"]}})).toThrow("GFP");
    for (const percentile of [49, 100, Number.NaN]) expect(() => comparisonRequest({...choices, gfp: {channel: "gfp", controls: ["c"], percentile}})).toThrow("percentile");
  });
  it("records the predeclared whole family and omnibus independently of obtained p-values", () => {
    const request = comparisonRequest({...choices, contrasts: [["A", "B"], ["A", "C"]]});
    expect(request.omnibus).toBe("kruskal-wallis"); expect(request.conditions).toEqual(["A", "B", "C"]);
    expect(request.comparison_family.kind).toBe("planned");
  });
  it("keeps the explicit cell ROI gate unit and refuses it for nuclear compartment summaries", () => {
    const gfp={version:"1.1.0" as const,gate_protocol:"gfp-gate/3.0.0" as const,gfp_channel_id:"gfp",method:"manual" as const,threshold:20,values:"corrected" as const,keep:"positive" as const};
    expect(comparisonRequest({...choices,gfp}).selection.gfp_gate).toMatchObject({unit:"nucleus",threshold:20,values:"corrected"});
    expect(comparisonRequest({...choices,regionSet:"cell",gfp:{...gfp,unit:"cell_roi"}}).selection.gfp_gate).toMatchObject({unit:"cell_roi"});
    expect(()=>comparisonRequest({...choices,metric:"nucleolar_count",gfp:{...gfp,unit:"cell_roi"}})).toThrow("細胞ROI");
  });
  it("assembles exact saved sources with CAS; review is separate and explicit", async () => {
    const {adapter, post} = fake(async path => path.endsWith("/jobs") ? [{id: "j", state: "succeeded"}] : {active_revision: "latest"});
    expect(await adapter.cohort("w", sources, {f1: {condition: "A"}, f2: {condition: "B"}})).toBe("cohort");
    expect(post).toHaveBeenCalledTimes(1);
    expect(post).toHaveBeenCalledWith("/v1/workspaces/w/region-cohorts", {expected_active_revision_id: "latest", sources: [{field_id: "f1", revision_id: "r0"}, {field_id: "f2", revision_id: "r1"}], metadata: {f1: {condition: "A"}, f2: {condition: "B"}}});
    await expect(adapter.review("cohort", false)).rejects.toThrow(); expect(post).toHaveBeenCalledTimes(1);
    await adapter.review("cohort", true); expect(post).toHaveBeenLastCalledWith("/v1/revisions/cohort/review", {accept_invalidated_fields: []});
  });
  it("resumes the accepted cohort despite an active-revision change after a polling failure", async () => {
    let polls = 0; let active = 0;
    const {adapter, post} = fake(async path => {
      if (path.endsWith("/jobs")) {if (++polls === 1) throw new TypeError("offline"); return [{id: "j", state: "succeeded"}];}
      return {active_revision: `active-${++active}`};
    });
    await expect(adapter.cohort("w", sources, {})).rejects.toThrow("offline");
    expect(await adapter.cohort("w", sources, {})).toBe("cohort"); expect(post).toHaveBeenCalledTimes(1);
  });
  it("does not issue silent duplicate jobs after uncertain writes and rejects mismatched result provenance", async () => {
    const uncertain = fake(async () => ({active_revision: null}), async () => {throw new TypeError("offline");});
    await expect(uncertain.adapter.cohort("w", sources, {})).rejects.toThrow();
    await expect(uncertain.adapter.cohort("w", sources, {})).rejects.toThrow("受付状態"); expect(uncertain.post).toHaveBeenCalledTimes(1);
    const mismatch = fake(async path => path.endsWith("/jobs") ? [{id: "j", state: "succeeded"}] : {revision_id: "other", analysis_kind: "region-comparison", region_comparison_version: "2.0.0"});
    await expect(mismatch.adapter.compare("w", "cohort", comparisonRequest(choices))).rejects.toThrow("出典");
  });
});

describe("stored cohort metadata restoration", () => {
  it("chooses the newest complete exact-source cohort and does not infer identities for mismatches", async () => {
    const revision = (id: string, created: number, second = "r1") => ({id, created, state: "succeeded", config: {cohort_sources: {f1: {revision_id: "r0"}, f2: {revision_id: second}}, field_snapshot: {f1: {metadata: {condition: id, experimental_unit: "declared-unit"}}, f2: {metadata: {condition: "B"}}}}});
    const {adapter, post} = fake(async () => [revision("old", 1), revision("current", 2), revision("changed-source", 3, "different")]);
    expect(await adapter.metadata("w", sources)).toEqual({revision: "current", fields: {f1: {condition: "current", experimental_unit: "declared-unit"}, f2: {condition: "B"}}});
    expect(await adapter.metadata("w", [sources[0]])).toBeNull();
    expect(post).not.toHaveBeenCalled();
  });
});
