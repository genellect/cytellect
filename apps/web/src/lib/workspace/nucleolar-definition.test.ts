import {describe, expect, it} from "vitest";
import {MINIMUM_CONTRAST_SNR, nucleolarDetectorV2} from "./nucleolar-definition";

describe("nucleolar definition", () => {
  it("uses pixel defaults without a pixel size and DAPI-poor as the default source", () => {
    expect(nucleolarDetectorV2({source: "dapi_poor", marker: "", pixelUm: null, relative: 0.7})).toMatchObject({
      protocol_version: "2.0.0", source: "dapi_poor", smoothing_sigma_px: 2, rim_exclusion_px: 4, minimum_area_px: 4});
  });
  it("scales physical marker defaults while retaining the recorded marker sigma", () => {
    const detector = nucleolarDetectorV2({source: "marker", marker: "ubf", pixelUm: 0.0355, relative: 0.7});
    expect(detector).toMatchObject({protocol_version: "2.2.0", source: "marker", smoothing_sigma_px: 0.7, rim_exclusion_px: 17, background_radius_px: 28, minimum_area_px: 238,
      minimum_area_um2: 0.3, minimum_contrast_snr: MINIMUM_CONTRAST_SNR});
  });
  it("uses marker protocol 2.2.0 without a pixel size: a 4 px floor and 0.3 µm² from each field's calibration", () => {
    expect(nucleolarDetectorV2({source: "marker", marker: "npm1", pixelUm: null, relative: 0.7})).toMatchObject({
      protocol_version: "2.2.0", minimum_area_px: 4, minimum_area_um2: 0.3, minimum_contrast_snr: MINIMUM_CONTRAST_SNR});
  });
});
