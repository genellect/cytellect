import { describe, expect, it } from "vitest";
import type { DisplayReceipt } from "./preview-display";
import { percentileRange, remapTable, sharedRange } from "./shared-display";

const receipt = (black: number, white: number, composite = false): DisplayReceipt => ({status: "verified", value: {
  version: "1.0.0", field_id: "f", requested_channel: "c", composite, gain: 1, scope: "whole-plane", mode: "per-plane-percentile",
  low_percentile: 0, high_percentile: 100,
  planes: [{channel_id: "c", dtype: "uint16", value_basis: "native-grayscale", constant_plane: false, source_min: black, source_max: white,
    percentile_low_value: black, percentile_high_value: white, normalization_span: white - black, display_black_value: black, display_white_value: white}],
} as never});

describe("shared display range", () => {
  it("uses the union of both previews' own ranges", () => {
    expect(sharedRange([receipt(100, 1100), receipt(300, 2100)])).toEqual({status: "shared", black: 100, white: 2100});
  });

  it("refuses to guess a range without verified receipts", () => {
    expect(sharedRange([receipt(0, 10), {status: "missing"}])).toEqual({status: "unavailable", reason: "receipt"});
    expect(sharedRange([receipt(0, 10, true), receipt(0, 10)])).toEqual({status: "unavailable", reason: "composite"});
  });

  it("maps each preview's stored values onto the shared scale", () => {
    // Own range 100–1100 shown within the shared range 100–2100: white (1100) becomes mid-grey.
    const table = remapTable({black: 100, white: 1100}, {black: 100, white: 2100});
    expect(table[0]).toBe(0);
    expect(table[255]).toBe(Math.round(255 * 1000 / 2000));
    // The preview that defines the shared white keeps its full range.
    const full = remapTable({black: 100, white: 2100}, {black: 100, white: 2100});
    expect([full[0], full[128], full[255]]).toEqual([0, 128, 255]);
    // Equal stored values give equal grey levels in both previews.
    const other = remapTable({black: 300, white: 2100}, {black: 100, white: 2100});
    expect(other[0]).toBe(table[Math.round(255 * 200 / 1000)]);
  });

  it("takes the shared range from both previews' stored values, so a few bright objects do not darken the other image (1.1.0)", () => {
    // Control: 1000 pixels over its own range 100–1100 (values 0–255 evenly); treatment: same, plus
    // 5 very bright pixels that set its own white at 10100.
    const even = Uint32Array.from({length: 256}, () => 4);
    const bright = Uint32Array.from({length: 256}, (_, value) => value === 255 ? 5 : value < 26 ? 40 : 0);
    const range = percentileRange([even, bright], [{black: 100, white: 1100}, {black: 100, white: 10100}]);
    expect(range.black).toBeGreaterThanOrEqual(100);
    // The 99.5th percentile stops below the few bright pixels: the control's range is not compressed tenfold.
    expect(range.white).toBeLessThan(2100);
    // The same table logic then maps equal stored values to equal grey levels in both images.
    expect(remapTable({black: 100, white: 1100}, range)[255]).toBe(255);
  });

  it("falls back to the union when the previews hold no pixels", () => {
    expect(percentileRange([new Uint32Array(256), new Uint32Array(256)], [{black: 0, white: 10}, {black: 5, white: 20}])).toEqual({black: 0, white: 20});
  });
});
