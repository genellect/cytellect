import type {ReviewField} from "@/lib/workspace/review-preview";

const NUCLEAR = "#3f86ff";
/** One colour per other stain, in channel order. */
const STAINS = ["#ff4fb3", "#4fd36a", "#ffc23d", "#3fd9e6"];

/**
 * The colour merge (重ねて表示) of a field's grayscale previews, display only: the nuclear stain of the adopted
 * nuclei (else the channel assigned to nuclear detection) is blue and every other stain has its own colour.
 * A channel assigned 「使用しない」 and a preview not yet loaded are left out; measurements never use these colours.
 */
export function compositeLayers(field: Pick<ReviewField, "channels" | "previews" | "nuclearChannelId">): Array<{channel: string; src: string; color: string}> {
  const nuclear = field.nuclearChannelId ?? field.channels.find(channel => channel.role === "nuclear")?.id;
  let other = 0;
  return field.channels.filter(channel => channel.role !== "unused" && field.previews[channel.id])
    .map(channel => ({channel: channel.id, src: field.previews[channel.id], color: channel.id === nuclear ? NUCLEAR : STAINS[other++ % STAINS.length]}));
}
