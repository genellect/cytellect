import { describe, expect, it } from "vitest";
import { descriptiveFieldNumber, descriptiveFieldStatus, descriptiveJobs, sameDescriptiveSettings, savedDescriptiveLabel, selectedDescriptiveJob, type DescriptiveResult } from "./descriptive-view";
import type { Job } from "./types";

const job = (id: string, state: string, created: number, revision_id = "r1"): Job => ({ id, state, created, revision_id, kind: "statistics", analysis_mode: "descriptive", error: null, attempts: 1 });
const saved: DescriptiveResult = {
  analysis_kind: "descriptive", revision_id: "r1", metric: "mean_corrected", unit: "a.u.",
  spec: { selection: { source: "region", region_set_id: "cytoplasm", channel_id: "actin", metric: "mean_corrected" }, plot: { language: "en", preset: "nature-double" } },
  counts: { observations: 2, input_fields: 2, selected_fields: 1, excluded_failed_fields: 1, experimental_units: null },
  selection: { input_rows: 2, excluded: 0, gate_unselected: 0, missing_metric_selected: 0 },
  field_summary: [], source_fields: [{ field_id: "f1", region_set: { label: "Cell interiors" }, channel_provenance: [{ channel: { channel_id: "actin", label: "Actin", stain: "Phalloidin" } }, { channel: { channel_id: "dna", label: "DNA", stain: null } }] }],
  excluded_failed_fields: [{ field_id: "f2", reason: "Unusable image" }], figure: { source_files: [] }, warnings: [],
};

describe("source-bound descriptive display", () => {
  it.each(["queued", "running", "failed", "cancelled"])("retains the selected %s job instead of falling back to an older success", state => {
    const previous = job("previous", "succeeded", 1);
    const requested = job("requested", state, 2);
    expect(selectedDescriptiveJob([previous, requested], "requested", "r1")).toBe(requested);
  });

  it("does not substitute history before the selected job is visible to polling", () => {
    expect(selectedDescriptiveJob([job("previous", "succeeded", 1)], "not-yet-polled", "r1")).toBeUndefined();
  });

  it("selects the latest current-version request on first entry, including failures", () => {
    const current = job("current", "failed", 2);
    expect(selectedDescriptiveJob([job("historical", "succeeded", 3, "r0"), current, job("old-current", "succeeded", 1)], "", "r1")).toBe(current);
  });

  it("permits an explicit historical result without claiming the current revision", () => {
    expect(selectedDescriptiveJob([job("current", "succeeded", 2), job("historical", "succeeded", 1, "r0")], "historical", "r1")?.revision_id).toBe("r0");
  });

  it("never uses an inferential or export result as a descriptive result", () => {
    expect(descriptiveJobs([{ ...job("inference", "succeeded", 2), analysis_mode: "experimental-unit" }, { ...job("export", "succeeded", 3), kind: "export" }, job("description", "succeeded", 1)]).map(value => value.id)).toEqual(["description"]);
  });

  it("attributes the saved metric to the selected actual channel and region, not another source channel", () => {
    expect(savedDescriptiveLabel(saved)).toBe("Cell interiors · Actin（標識: Phalloidin） · 平均（背景補正）");
    const area = { ...saved, spec: { ...saved.spec, selection: { source: "region" as const, region_set_id: "cytoplasm", channel_id: null, metric: "area_px" } } };
    expect(savedDescriptiveLabel(area)).toBe("Cell interiors · 面積 / px²");
  });

  it("does not fabricate a missing stain or apply labels from the current options", () => {
    const dna = { ...saved, spec: { ...saved.spec, selection: { ...saved.spec.selection, source: "region" as const, region_set_id: "cytoplasm", channel_id: "dna" } } };
    expect(savedDescriptiveLabel(dna)).toContain("DNA（標識: 未記録）");
  });

  it("recognizes ungenerated channel, region, metric, language and width choices", () => {
    expect(sameDescriptiveSettings(saved, saved.spec.selection, "en", "nature-double")).toBe(true);
    for (const patch of [{ channel_id: "dna" }, { region_set_id: "nucleus" }, { metric: "mean" }]) {
      expect(sameDescriptiveSettings(saved, { source: "region", region_set_id: "cytoplasm", channel_id: "actin", metric: "mean_corrected", ...patch }, "en", "nature-double")).toBe(false);
    }
    expect(sameDescriptiveSettings(saved, saved.spec.selection, "ja", "nature-double")).toBe(false);
    expect(sameDescriptiveSettings(saved, saved.spec.selection, "en", "nature-single")).toBe(false);
    expect(sameDescriptiveSettings(saved, undefined, "en", "nature-double")).toBe(false);
  });

  it("keeps absent regions distinct from regions whose values cannot be selected", () => {
    expect(descriptiveFieldStatus("no_regions")).toBe("領域なし");
    expect(descriptiveFieldStatus("no_selected_values")).toBe("採用可能な値なし");
  });
});


it("uses the saved figure order rather than list positions for field tracing", () => {
 const fields=["f1","f2"].map(field_id=>({field_id,selected_rows:0,median:null,q1:null,q3:null,status:"no_regions"}));
 const source={...saved,field_summary:fields,spec:{...saved.spec,plot:{...saved.spec.plot,group_order:["f2","f1"]}}};
 expect(descriptiveFieldNumber(source,"f1")).toBe(2);
 expect(descriptiveFieldNumber(source,"f2")).toBe(1);
 expect(descriptiveFieldNumber(source,"absent")).toBeNull();
 expect(descriptiveFieldNumber({...source,spec:{...source.spec,plot:{...source.spec.plot,group_order:[]}}},"f1")).toBe(1);
});
