import { describe, expect, it } from "vitest";
import { applyChannelMapping, groupFiles, unresolvedChannels } from "./grouping";

const file = (path: string, extra = {}) => ({ path, size: 1, ...extra });

describe("groupFiles", () => {
  it("pairs fields by removing a delimited stain token and keeps stain identity", () => {
    const grouping = groupFiles([file("exp/A01_DAPI.tif"), file("exp/A01_GFP.tif"), file("exp/A02_DAPI.tif"), file("exp/A02_GFP.tif")]);
    expect(grouping.fields.map((field) => field.key)).toEqual(["exp/A01", "exp/A02"]);
    expect(grouping.channels).toEqual([
      { token: "dapi", stain: "DAPI", role: "nuclear", evidence: "filename" },
      { token: "gfp", stain: "GFP", role: "measure", evidence: "filename" },
    ]);
    expect(grouping.fields[0].candidates).toEqual({ well: "A01", folder: "exp" });
    expect(grouping.issues).toEqual([]);
  });

  it("never treats index tokens as stains and requires one set-wide mapping", () => {
    const grouping = groupFiles([file("Channel1-01-A-01.BMP"), file("Channel2-01-A-01.BMP"), file("Channel1-01-A-06.BMP"), file("Channel2-01-A-06.BMP")]);
    expect(grouping.fields).toHaveLength(2);
    expect(unresolvedChannels(grouping).map((channel) => channel.token)).toEqual(["channel1", "channel2"]);
    const mapped = applyChannelMapping(grouping, { channel1: { stain: "FKHR-EGFP", role: "measure" }, channel2: { stain: "DRAQ", role: "nuclear" } });
    expect(unresolvedChannels(mapped)).toEqual([]);
    expect(mapped.channels.every((channel) => channel.evidence === "user")).toBe(true);
    expect(mapped.issues).toEqual([]);
  });

  it("leaves two candidates for one field and channel unresolved instead of using file order", () => {
    const grouping = groupFiles([file("A01_dapi.tif"), file("A01_gfp.tif"), file("copy/A01_gfp.tif"), file("A01-gfp.tif")]);
    const duplicate = grouping.issues.find((issue) => issue.kind === "duplicate_channel");
    expect(duplicate).toEqual({ kind: "duplicate_channel", field: "A01", token: "gfp", paths: ["A01_gfp.tif", "A01-gfp.tif"] });
    expect(grouping.fields.find((field) => field.key === "A01")!.files.gfp).toBeUndefined();
  });

  it("reports missing channels, identical content and unidentifiable names", () => {
    const grouping = groupFiles([
      file("A01_dapi.tif", { sha256: "x" }), file("A01_gfp.tif"), file("A02_dapi.tif", { sha256: "x" }), file("image.tif"), file("A03_c1_gfp.tif"),
    ]);
    expect(grouping.issues).toEqual(expect.arrayContaining([
      { kind: "missing_channel", field: "A02", token: "gfp" },
      { kind: "duplicate_content", paths: ["A01_dapi.tif", "A02_dapi.tif"] },
      { kind: "channel_unidentified", path: "image.tif" },
      { kind: "channel_unidentified", path: "A03_c1_gfp.tif" },
    ]));
  });

  it("uses a channel folder only when the name has no channel token and never derives units", () => {
    const grouping = groupFiles([file("2026-10-01/DAPI/s1.tif"), file("2026-10-01/GFP/s1.tif")]);
    expect(grouping.fields).toEqual([expect.objectContaining({ key: "2026-10-01/s1", candidates: { folder: "2026-10-01" } })]);
    expect(grouping.channels.map((channel) => channel.evidence)).toEqual(["folder", "folder"]);
  });

  it("rejects a blank stain in a mapping", () => {
    const grouping = groupFiles([file("A01_c1.tif")]);
    expect(() => applyChannelMapping(grouping, { c1: { stain: " ", role: "nuclear" } })).toThrow("stain_required");
  });
});
