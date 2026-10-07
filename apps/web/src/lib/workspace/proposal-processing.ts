/** Apply only locally validated, registered settings. This module never starts a job. */
import { nuclearRecipe, type Recipe, type ValidatedProposal } from "./api-adapter";
import type { ChannelDefinition } from "./grouping";

export interface NuclearProcessingDetector {
  engine: "fiji-stardist-2d"; model: "Versatile (fluorescent nuclei)";
  probability: number; nms: number; percentile_low: number; percentile_high: number;
}
export interface SignalProcessingDetector {
  engine: "fiji-positive-regions"; protocol_version: "1.0.0";
  threshold_method: "otsu" | "manual"; threshold: number | null;
  smoothing_sigma_px: number; minimum_area_px: number; split_touching: boolean;
}
export interface LegacyNucleolarProcessingDetector {
  engine: "fiji-nucleolar-compartments"; protocol_version: "1.1.0";
  threshold_method: "otsu" | "manual"; threshold: number | null;
  smoothing_sigma_px: number; minimum_area_px: number; maximum_area_px: number | null; split_touching: boolean;
}
export interface NucleolarProcessingDetector {
  engine: "cytellect-nucleolar-v2"; protocol_version: "2.0.0" | "2.1.0"; source: "dapi_poor" | "marker";
  smoothing_sigma_px: number; rim_exclusion_px: number; relative_threshold: number; marker_fraction: number;
  background_radius_px: number; minimum_area_px: number; maximum_area_px: number | null; minimum_solidity: number;
}
export interface ProposalProcessing {
  version: "1.0.0";
  nuclei: {channel: string; detection_max_side_px: number | null; detector: NuclearProcessingDetector} | null;
  nucleoli: {channel: string; detector: LegacyNucleolarProcessingDetector | NucleolarProcessingDetector} | null;
  signal: {channel: string; detector: SignalProcessingDetector} | null;
}

/** Unknown roles stay pending; accepting a proposal is not acquisition confirmation. */
export function applicableProcessing(proposal: ValidatedProposal, channels: ChannelDefinition[]): ProposalProcessing | null {
  const processing = proposal.draft.processing;
  if (!processing || processing.version !== "1.0.0") return null;
  for (const operation of [processing.nuclei, processing.nucleoli, processing.signal]) {
    if (operation && (!channels.some(channel => channel.token === operation.channel)
      || proposal.needs_confirmation.includes(operation.channel))) return null;
  }
  if (processing.nuclei && !channels.some(channel => channel.token === processing.nuclei!.channel && channel.role === "nuclear")) return null;
  return structuredClone(processing);
}

export function proposalNuclearRecipe(channel: ChannelDefinition, processing: ProposalProcessing): Recipe {
  const settings = processing.nuclei;
  if (!settings || settings.channel !== channel.token) throw new Error("核検出のチャンネルが一致しません");
  return {...nuclearRecipe(channel, settings.detection_max_side_px), detector: settings.detector};
}

/** Resolve live adopted parent IDs only at execution; the LLM never supplies revision IDs. */
export function proposalNucleolarRecipe(processing: ProposalProcessing, nuclear: {revision: string; channel: string}): Recipe {
  const settings = processing.nucleoli;
  if (!settings || processing.nuclei?.channel !== nuclear.channel) throw new Error("核小体の親となる核を選択してください");
  return {id: "region-2d", version: "1.4.0", region_set_id: "nucleoli", label: "核小体",
    source: "fiji_nuclear_compartment", compartment: "nucleoli", nuclear_revision_id: nuclear.revision,
    nuclear_channel_id: nuclear.channel, defining_channel_id: settings.channel, detector: settings.detector};
}

export function proposalSignalRecipe(processing: ProposalProcessing, target: "gfp" | "ncl"): Recipe {
  const settings = processing.signal;
  if (!settings) throw new Error("陽性領域の設定がありません");
  return {id: "region-2d", version: "1.3.0", region_set_id: `${target}_positive`, label: "陽性領域",
    source: "fiji_positive_regions", defining_channel_id: settings.channel, detector: settings.detector};
}

/** Restore settings from adopted revisions without resurrecting an old conversation or starting a job. */
export function savedProcessing(nuclear?: Recipe, nucleolar?: Recipe, signal?: Recipe): ProposalProcessing | null {
  if (!nuclear || nuclear.source !== "stardist_nuclear") return null;
  const nucleus = nuclear.detector;
  const child = nucleolar?.source === "fiji_nuclear_compartment" ? nucleolar.detector : null;
  const positive = signal?.source === "fiji_positive_regions" ? signal.detector : null;
  return {version:"1.0.0",nuclei:{channel:nuclear.defining_channel_id,detection_max_side_px:nuclear.detection_max_side_px ?? null,
    detector:nucleus?.engine === "fiji-stardist-2d" ? nucleus : {engine:"fiji-stardist-2d",model:"Versatile (fluorescent nuclei)",probability:0.5,nms:0.3,percentile_low:1,percentile_high:99.8}},
    nucleoli:nucleolar && (child?.engine === "cytellect-nucleolar-v2" || (child?.engine === "fiji-nucleolar-compartments" && child.protocol_version === "1.1.0"))
      ? {channel:nucleolar.defining_channel_id,detector:child as NucleolarProcessingDetector | LegacyNucleolarProcessingDetector} : null,
    signal:signal && positive?.engine === "fiji-positive-regions" ? {channel:signal.defining_channel_id,detector:positive} : null};
}

/** Visible controls are authoritative; retain only compatible, otherwise hidden AI parameters. */
export function withProcessingSettings(recipe: Recipe, processing: ProposalProcessing | null, calibrationChanged = false): Recipe {
  if (!processing) return recipe;
  if (recipe.source === "stardist_nuclear" && processing.nuclei?.channel === recipe.defining_channel_id) {
    return {...recipe, detector: processing.nuclei.detector};
  }
  if (recipe.source === "fiji_positive_regions" && processing.signal?.channel === recipe.defining_channel_id) {
    const current = recipe.detector;
    if (!current || !("threshold_method" in current)) return recipe;
    return {...recipe, label: "陽性領域", detector: {...processing.signal.detector,
      threshold_method: current.threshold_method ?? "otsu", threshold: current.threshold ?? null}};
  }
  if (recipe.source === "fiji_nuclear_compartment" && processing.nucleoli?.channel === recipe.defining_channel_id) {
    const current = recipe.detector, proposed = processing.nucleoli.detector;
    if (!current) return recipe;
    if ("source" in current && "source" in proposed && current.source === proposed.source && !calibrationChanged) {
      return {...recipe, detector: {...proposed, relative_threshold: current.relative_threshold}};
    }
    if (current.engine === "fiji-nucleolar-compartments" && proposed.engine === "fiji-nucleolar-compartments") {
      return {...recipe, detector: {...proposed, ...current}};
    }
  }
  return recipe;
}
