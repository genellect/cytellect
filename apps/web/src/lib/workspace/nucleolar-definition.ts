/** Researcher-selected nucleolar definition (DAPI protocol 2.0.0 / marker protocol 2.1.0, see docs/nucleolar-compartments.md). */
import type {components} from "../generated";
export type NclObjectProcessingDetector = Required<components["schemas"]["NclObjectDetector"]>;
export const nclObjectDetector = ():NclObjectProcessingDetector => ({
  engine:"cytellect-ncl-objects",protocol_version:"3.0.0",smoothing_sigma_px:.9,
  background_radius_px:10,coarse_sigma_px:1.5,core_contrast:36,core_coarse_contrast:27,
  minimum_core_area_px:6,local_crop_radius_px:24,background_inner_radius_px:12,background_outer_radius_px:22,
  background_signal_floor:15,minimum_background_pixels:40,peak_radius_px:2,
  minimum_peak_difference:30,minimum_peak_ratio:1.6,boundary_fraction:.5,
  minimum_area_px:28,maximum_area_px:800,minimum_solidity:.8,minimum_circularity:.5,
  hole_fill_max_px:64,overlap_suppression_fraction:.5,
});
export type NucleolarSource = "dapi_poor" | "marker" | "ncl";
export type NucleolarDefinition = {source: NucleolarSource; marker: string; pixelUm: number | null; relative: number; algorithm?: "cellpose" | "objects" | "legacy" | null};

export const nucleolarSourceText: Record<NucleolarSource, {label: string; description: string}> = {
  dapi_poor: {label: "DAPI の暗い部分", description: "核小体は DNA が少ないため核染色で暗く写ります。NCL が移動しても使えます。"},
  marker: {label: "核小体マーカー（UBF／FBL など）", description: "核小体の中心部を示すマーカーで決めます。マーカーの染色を確認したうえで使います。"},
  ncl: {label: "NCL陽性領域", description: "NCL画像から核内の核小体候補を検出します。"},
};

/** Physical defaults (µm) follow the cited protocols; without a pixel size the pixel defaults apply. */
export function nucleolarDetectorV2(definition: NucleolarDefinition) {
  const um = definition.pixelUm && definition.pixelUm > 0 ? definition.pixelUm : null;
  const px = (micrometres: number, fallback: number, max: number) => um ? Math.min(max, Math.max(1, Math.round(micrometres / um))) : fallback;
  return {
    engine: "cytellect-nucleolar-v2" as const, protocol_version: definition.source === "marker" ? "2.1.0" as const : "2.0.0" as const,
    source: definition.source === "marker" ? "marker" as const : "dapi_poor" as const,
    smoothing_sigma_px: definition.source === "marker" ? 0.7 : (um ? Math.min(20, Math.round(0.35 / um * 10) / 10) : 2),
    rim_exclusion_px: px(0.6, 4, 100),
    relative_threshold: definition.relative,
    marker_fraction: 0.4,
    background_radius_px: px(1.0, 10, 200),
    minimum_area_px: um ? Math.max(1, Math.round(0.3 / (um * um))) : 4,
    maximum_area_px: null,
    minimum_solidity: 0.6,
  };
}
