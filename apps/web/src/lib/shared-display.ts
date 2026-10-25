import type { DisplayReceipt } from "./preview-display";

/** Shared display range 1.0.0 (docs/display.md): two previews redrawn with one black and white
 * point so that equal brightness on screen means equal stored values. Display only — measurements,
 * masks and the original pixels never change. Each preview PNG is a linear 8-bit map of its own
 * [black, white] range; values outside a preview's own range were already clipped by it. */
export interface PlaneRange { black: number; white: number }
export type SharedRange = { status: "shared"; black: number; white: number } | { status: "unavailable"; reason: "receipt" | "composite" };

export function planeRange(receipt: DisplayReceipt | undefined): PlaneRange | null {
  if (receipt?.status !== "verified" || receipt.value.composite || receipt.value.planes.length !== 1) return null;
  const plane = receipt.value.planes[0];
  return {black: plane.display_black_value, white: plane.display_white_value};
}

/** The union of the planes' own ranges; refused when any plane lacks a verified receipt. */
export function sharedRange(receipts: Array<DisplayReceipt | undefined>): SharedRange {
  if (receipts.some(receipt => receipt?.status === "verified" && receipt.value.composite)) return {status: "unavailable", reason: "composite"};
  const ranges = receipts.map(planeRange);
  if (!ranges.length || ranges.some(range => range === null)) return {status: "unavailable", reason: "receipt"};
  const known = ranges as PlaneRange[];
  return {status: "shared", black: Math.min(...known.map(range => range.black)), white: Math.max(...known.map(range => range.white))};
}

/** 8-bit lookup table from a preview's own range to the shared range. */
export function remapTable(own: PlaneRange, shared: {black: number; white: number}): Uint8Array {
  const table = new Uint8Array(256), span = shared.white - shared.black;
  for (let value = 0; value < 256; value++) {
    const stored = own.black + value / 255 * (own.white - own.black);
    const scaled = span > 0 ? (stored - shared.black) / span : 0;
    table[value] = Math.round(255 * Math.min(1, Math.max(0, scaled)));
  }
  return table;
}

/** Redraws a grayscale preview through the table; returns an object URL the caller revokes. */
export async function remappedPreview(src: string, table: Uint8Array): Promise<string> {
  const image = new Image();
  image.decoding = "async";
  image.src = src;
  await image.decode();
  const canvas = document.createElement("canvas");
  canvas.width = image.naturalWidth;
  canvas.height = image.naturalHeight;
  const context = canvas.getContext("2d", {willReadFrequently: true});
  if (!context) throw new Error("shared_display_unavailable");
  context.drawImage(image, 0, 0);
  const pixels = context.getImageData(0, 0, canvas.width, canvas.height);
  const data = pixels.data;
  for (let index = 0; index < data.length; index += 4) {
    data[index] = table[data[index]];
    data[index + 1] = table[data[index + 1]];
    data[index + 2] = table[data[index + 2]];
  }
  context.putImageData(pixels, 0, 0);
  const blob = await new Promise<Blob | null>(resolve => canvas.toBlob(resolve, "image/png"));
  if (!blob) throw new Error("shared_display_unavailable");
  return URL.createObjectURL(blob);
}
