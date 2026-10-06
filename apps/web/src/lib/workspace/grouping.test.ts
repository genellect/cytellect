import { describe, expect, it } from "vitest";
import { chooseNuclearChannel, groupFiles, nameChannel, restoredChannels } from "./grouping";

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

  it("never treats index tokens as stains; one nuclear choice is the only channel decision", () => {
    const grouping = groupFiles([file("Channel1-01-A-01.BMP"), file("Channel2-01-A-01.BMP"), file("Channel1-01-A-06.BMP"), file("Channel2-01-A-06.BMP")]);
    expect(grouping.fields).toHaveLength(2);
    expect(grouping.channels.map((channel) => [channel.token, channel.stain, channel.role])).toEqual([["channel1", null, null], ["channel2", null, null]]);
    expect(grouping.issues).toEqual([]);
    const chosen = chooseNuclearChannel(grouping, "channel2");
    expect(chosen.channels.map((channel) => [channel.token, channel.stain, channel.role, channel.evidence]))
      .toEqual([["channel1", null, null, "filename"], ["channel2", null, "nuclear", "user"]]);
    // Choosing again moves the role; it never leaves two nuclear channels.
    expect(chooseNuclearChannel(chosen, "channel1").channels.map((channel) => channel.role)).toEqual(["nuclear", "measure"]);
    expect(() => chooseNuclearChannel(grouping, "c9")).toThrow("channel_unknown");
  });

  it("leaves two candidates for one field and channel unresolved instead of using file order", () => {
    const grouping = groupFiles([file("A01_dapi.tif"), file("A01_gfp.tif"), file("copy/A01_gfp.tif"), file("A01-gfp.tif")]);
    const duplicate = grouping.issues.find((issue) => issue.kind === "duplicate_channel");
    expect(duplicate).toEqual({ kind: "duplicate_channel", field: "A01", token: "gfp", paths: ["A01_gfp.tif", "A01-gfp.tif"] });
    expect(grouping.fields.find((field) => field.key === "A01")!.files.gfp).toBeUndefined();
  });

  it("reports missing channels, identical content and unidentifiable names", () => {
    const grouping = groupFiles([
      file("A01_dapi.tif", { sha256: "x" }), file("A01_gfp.tif"), file("A02_dapi.tif", { sha256: "x" }), file("image.tif"), file("A03_dapi_gfp.tif"),
    ]);
    expect(grouping.issues).toEqual(expect.arrayContaining([
      { kind: "missing_channel", field: "A02", token: "gfp" },
      { kind: "duplicate_content", paths: ["A01_dapi.tif", "A02_dapi.tif"] },

      // Two stains in one name are ambiguous and never guessed.

    ]));
  });

  it("groups common instrument names: a named stain wins over channel numbers", () => {
    const metaxpress = groupFiles([file("A01_s1_w1_DAPI.tif"), file("A01_s1_w2_GFP.tif"), file("A01_s2_w1_DAPI.tif"), file("A01_s2_w2_GFP.tif")]);
    expect(metaxpress.fields.map((field) => field.key)).toEqual(["A01-s1", "A01-s2"]);
    expect(metaxpress.channels.map((channel) => [channel.token, channel.stain, channel.role])).toEqual([["dapi", "DAPI", "nuclear"], ["gfp", "GFP", "measure"]]);
    expect(metaxpress.issues).toEqual([]);
    const dyes = groupFiles([file("f1_Hoechst33342.tif"), file("f1_GFP.tif")]);
    expect(dyes.channels.find((channel) => channel.token === "hoechst33342")).toMatchObject({ stain: "Hoechst33342", role: "nuclear" });
    expect(dyes.issues).toEqual([]);
    const glued = groupFiles([file("xy01c1.tif"), file("xy01c2.tif"), file("xy02c1.tif"), file("xy02c2.tif")]);
    expect(glued.fields.map((field) => field.key)).toEqual(["xy01", "xy02"]);
    expect(glued.channels.map((channel) => [channel.token, channel.stain])).toEqual([["c1", null], ["c2", null]]);
  });

  it("keeps a name-less multi-channel OME-TIFF as pending and expands read channels", () => {
    expect(groupFiles([file("field01.ome.tif")]).fields).toHaveLength(1);
    const read = groupFiles([file("field01.ome.tif", { omeChannels: ["DAPI", "", "NCL"] })]);
    expect(read.fields.map((field) => [field.key, Object.keys(field.files).sort()])).toEqual([["field01", ["c2", "dapi", "ncl"]]]);
    expect(read.channels.map((channel) => [channel.token, channel.stain, channel.evidence])).toEqual([
      ["c2", null, "ome"], ["dapi", "DAPI", "ome"], ["ncl", "NCL", "ome"]]);
  });

  it("uses a channel folder only when the name has no channel token and never derives units", () => {
    const grouping = groupFiles([file("2026-10-01/DAPI/s1.tif"), file("2026-10-01/GFP/s1.tif")]);
    expect(grouping.fields).toEqual([expect.objectContaining({ key: "2026-10-01/s1", candidates: { folder: "2026-10-01" } })]);
    expect(grouping.channels.map((channel) => channel.evidence)).toEqual(["folder", "folder"]);
  });

  it("keeps unnamed files and same-stain batches without filename constraints", () => {
    const unknown = groupFiles([file("one.tif"), file("two.tif")]);
    expect(unknown.fields).toHaveLength(2);
    expect(unknown.channels).toEqual([{token: "c1", stain: null, role: null, evidence: "user"}]);
    const single = groupFiles([file("A01_c1.tif"), file("A01_c2.tif")], "single");
    expect(single.fields).toHaveLength(2);
    expect(single.issues).toEqual([]);
  });

  it("names a channel only when the user wants to, and an empty name keeps the stain unknown", () => {
    const grouping = groupFiles([file("A01_c1.tif")]);
    expect(nameChannel(grouping, "c1", " FKHR-EGFP ").channels[0]).toMatchObject({ stain: "FKHR-EGFP", evidence: "user" });
    expect(nameChannel(grouping, "c1", " ").channels[0].stain).toBeNull();
    // Known stains are normalised so recipes recognise them regardless of case.
    expect(nameChannel(grouping, "c1", "ncl").channels[0].stain).toBe("NCL");
  });
});

it("restores all channels when the first field is incomplete", () => {
  const c1 = {channel_id: "c1", label: "marker", stain: null};
  const c4 = {channel_id: "c4", label: "nuclei", stain: "DAPI"};
  const channels = restoredChannels([{image_info: {channels: [c1]}}, {image_info: {channels: [c1, c4]}}]);
  const grouping = chooseNuclearChannel({channels, fields: [], issues: []}, "c4");
  expect(grouping.channels.map(value => [value.token, value.role])).toEqual([["c1", null], ["c4", "nuclear"]]);
  expect(() => restoredChannels([{image_info: {channels: [c1]}}, {image_info: {channels: [{...c1, stain: "GFP"}]}}])).toThrow("チャンネル情報");
});
