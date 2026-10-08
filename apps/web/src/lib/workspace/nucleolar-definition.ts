/** Researcher-selected nucleolar definition (DAPI protocol 2.0.0 / marker protocol 2.1.0, see docs/nucleolar-compartments.md). */
export type NucleolarSource = "dapi_poor" | "marker" | "ncl";
export type NucleolarDefinition = {source: NucleolarSource; marker: string; pixelUm: number | null; relative: number};

export const nucleolarSourceText: Record<NucleolarSource, {label: string; description: string}> = {
  dapi_poor: {label: "DAPI の暗い部分", description: "核小体は DNA が少ないため核染色で暗く写ります。NCL が移動しても使えます。"},
  marker: {label: "核小体マーカー（UBF／FBL など）", description: "核小体の中心部を示すマーカーで決めます。マーカーの染色を確認したうえで使います。"},
  ncl: {label: "NCL の明るい部分（旧方式）", description: "以前の解析の再現用です。NCL がストレスで移動すると核小体を誤ります。"},
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
