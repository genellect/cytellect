import { describe, expect, it } from "vitest";
import { chooseNuclearChannel, groupFiles } from "./grouping";
import { buildProposal } from "./proposal";

const files = (names: string[]) => groupFiles(names.map((path) => ({ path, size: 1 })));

describe("buildProposal", () => {
  it("proposes nuclear detection and raw channel intensity with descriptive figures when units are unknown", () => {
    const proposal = buildProposal(files(["A01_dapi.tif", "A01_gfp.tif"]));
    expect(proposal.recipe).toBe("nuclear-intensity");
    expect(proposal.metrics.map((metric) => metric.key)).toEqual(["area_px", "gfp:mean_raw"]);
    expect(proposal.statistics).toEqual({ kind: "descriptive" });
    expect(proposal.figures.every((figure) => figure.point === "region")).toBe(true);
    expect(proposal.background).toBe("raw-only");
  });

  it("asks only which channel detects nuclei when names do not say, then measures the rest", () => {
    const grouping = files(["Channel1-A01.tif", "Channel2-A01.tif"]);
    expect(buildProposal(grouping)).toMatchObject({ recipe: null, unresolved: ["核検出に使うチャンネル"] });
    const proposal = buildProposal(chooseNuclearChannel(grouping, "channel2"));
    expect(proposal).toMatchObject({ recipe: "nuclear-intensity", unresolved: [] });
    expect(proposal.metrics.map((metric) => metric.label)).toEqual(["核面積", "channel1 平均輝度（補正前）"]);
  });

  it("needs no channel decision when a file name already names the nuclear stain", () => {
    expect(buildProposal(files(["A01_dapi.tif", "A01_c2.tif"]))).toMatchObject({ recipe: "nuclear-intensity", unresolved: [] });
  });

  it("flags NCL-defined regions and requires one nuclear channel", () => {
    const proposal = buildProposal(files(["A01_dapi.tif", "A01_ncl.tif"]));
    expect(proposal.recipe).toBe("nuclear-ncl");
    expect(proposal.notes.join("")).toContain("NCL自身から定義");
    expect(buildProposal(files(["A01_hoechst.tif", "A01_dapi.tif"])).recipe).toBeNull();
  });

  it("proposes a unit comparison only when every field has a condition and an independent unit", () => {
    const grouping = files(["A01_dapi.tif", "A02_dapi.tif"]);
    expect(buildProposal(grouping, { conditions: { A01: "a", A02: "b" }, units: { A01: "u1" } }).statistics.kind).toBe("descriptive");
    const proposal = buildProposal(grouping, { conditions: { A01: "a", A02: "b" }, units: { A01: "u1", A02: "u2" } });
    expect(proposal.statistics).toEqual({ kind: "comparison", test: "welch-t" });
    expect(proposal.figures.some((figure) => figure.point === "experimental unit")).toBe(true);
  });
});
