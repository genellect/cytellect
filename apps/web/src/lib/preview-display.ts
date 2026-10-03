import type { components } from "./generated";

export const PREVIEW_DISPLAY_HEADER = "X-Cytellect-Preview-Display";
export type PreviewDisplay = components["schemas"]["PreviewDisplayMetadata"];
export type PreviewIdentity = { fieldId: string; channel: string; gain: number; composite: boolean };
export type DisplayReceipt = { status: "verified"; value: PreviewDisplay } | { status: "missing" | "invalid" };

const finite = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value);

/** Validate the response identity before showing any range next to decoded pixels. */
export function readPreviewDisplay(header: string | null, expected: PreviewIdentity): DisplayReceipt {
 if (header === null) return {status:"missing"};
 try {
  if (header.length > 12000) return {status:"invalid"};
  const value = JSON.parse(header) as PreviewDisplay;
  if (!value || value.version !== "1.0.0" || value.field_id !== expected.fieldId || value.requested_channel !== expected.channel || value.composite !== expected.composite || value.gain !== expected.gain || value.scope !== "whole-plane" || value.mode !== "per-plane-percentile" || !finite(value.low_percentile) || !finite(value.high_percentile) || value.low_percentile < 0 || value.high_percentile > 100 || value.low_percentile >= value.high_percentile || !Array.isArray(value.planes) || value.planes.length < 1 || value.planes.length > 3) return {status:"invalid"};
  if (!expected.composite && (value.planes.length !== 1 || value.planes[0].channel_id !== expected.channel)) return {status:"invalid"};
  const ids = new Set<string>();
  for (const plane of value.planes) {
   if (!plane || typeof plane.channel_id !== "string" || ids.has(plane.channel_id) || (expected.composite && !["ncl","gfp","dapi"].includes(plane.channel_id)) || typeof plane.dtype !== "string" || !["native-grayscale","legacy-imported"].includes(plane.value_basis) || typeof plane.constant_plane !== "boolean") return {status:"invalid"};
   const numbers = [plane.source_min,plane.source_max,plane.percentile_low_value,plane.percentile_high_value,plane.normalization_span,plane.display_black_value,plane.display_white_value];
   if (!numbers.every(finite) || plane.source_min > plane.source_max || plane.percentile_low_value > plane.percentile_high_value || plane.normalization_span < 1 || plane.display_white_value <= plane.display_black_value || plane.constant_plane !== (plane.source_min === plane.source_max)) return {status:"invalid"};
   ids.add(plane.channel_id);
  }
  return {status:"verified",value};
 } catch { return {status:"invalid"}; }
}
