import {describe, expect, it} from "vitest";
import {nucleolarDetectorV2} from "./nucleolar-definition";

describe("nucleolar definition", () => {
  it("uses pixel defaults without a pixel size and DAPI-poor as the default source", () => {
    expect(nucleolarDetectorV2({source: "dapi_poor", marker: "", pixelUm: null, relative: 0.7})).toMatchObject({
      protocol_version: "2.0.0", source: "dapi_poor", smoothing_sigma_px: 2, rim_exclusion_px: 4, minimum_area_px: 4});
  });
  it("scales physical defaults by the pixel size", () => {
    const detector = nucleolarDetectorV2({source: "marker", marker: "ubf", pixelUm: 0.0355, relative: 0.7});
    expect(detector).toMatchObject({source: "marker", smoothing_sigma_px: 9.9, rim_exclusion_px: 17, background_radius_px: 28, minimum_area_px: 238});
  });
});
