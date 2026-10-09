import type {components} from "../generated";

export type CellposeProcessingDetector = Required<components["schemas"]["CellposeDetectorSpec"]>;
export type NclCellposeProcessingDetector = Required<components["schemas"]["NclCellposeDetectorSpec"]>;
export type NclParentCellposeProcessingDetector = Required<components["schemas"]["NclParentCellposeDetectorSpec"]>;
export type AnyCellposeProcessingDetector = CellposeProcessingDetector | NclCellposeProcessingDetector | NclParentCellposeProcessingDetector;

/** Pinned inference settings shared by manual controls, saved recipes and AI proposals. */
export const cellposeDetector = ():CellposeProcessingDetector => ({
  engine:"cellpose-sam",protocol_version:"4.0.0",model:"cpsam_v2",
  model_sha256:"0f1cc3f7ecdd8a037a57c6c48d9d8921391be4cbce3fa9f13c3e3a2e1253c667",
  diameter_px:null,normalization_percentile_low:1,normalization_percentile_high:99,
  flow_threshold:.4,cellprob_threshold:0,minimum_area_px:15,maximum_size_fraction:1,iterations:null,batch_size:1,compute_device:"cpu",
});

/** NCL protocol 4.1 keeps local-background preprocessing separate from measurement pixels. */
export const legacyNclCellposeDetector = ():NclCellposeProcessingDetector => ({
  ...cellposeDetector(),engine:"cellpose-sam-ncl",protocol_version:"4.1.0",smoothing_sigma_px:.9,background_radius_px:10,
});

/** Parent-conditioned candidates with versioned signal-support refinement.
 * Saved protocols, including 4.2.1, are never implicitly upgraded. */
export const nclCellposeDetector = ():NclParentCellposeProcessingDetector => ({
  ...cellposeDetector(),engine:"cellpose-sam-ncl-parent",protocol_version:"4.3.0",smoothing_sigma_px:.9,
  parent_background_percentile:75,nuclear_diameter_fraction:.25,crop_padding_px:32,
  minimum_contrast_snr:5,local_background_radius_px:8,maximum_nuclear_coverage:.5,
});

export function isCellposeDetector(value:unknown):value is AnyCellposeProcessingDetector {
  return !!value&&typeof value==="object"&&"engine" in value&&(value.engine==="cellpose-sam"||value.engine==="cellpose-sam-ncl"||value.engine==="cellpose-sam-ncl-parent");
}
