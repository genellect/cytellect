import type {ReviewField} from "@/lib/workspace/review-preview";

const NUCLEAR = "#3f86ff";
/** One colour per other stain, in channel order. */
const STAINS = ["#ff4fb3", "#4fd36a", "#ffc23d", "#3fd9e6"];

/**
 * The colour merge (重ねて表示) of a field's grayscale previews, display only: the nuclear stain of the adopted
 * nuclei (else the channel assigned to nuclear detection) is blue, and every other stain keeps the colour of its
 * channel position, so assigning the nuclear stain does not recolour the others.
 * A channel assigned 「使用しない」 and a preview not yet loaded are left out; measurements never use these colours.
 */
export function compositeLayers(field: Pick<ReviewField, "channels" | "previews" | "nuclearChannelId">): Array<{channel: string; src: string; color: string}> {
  const nuclear = field.nuclearChannelId ?? field.channels.find(channel => channel.role === "nuclear")?.id;
  return field.channels.map((channel, index) => ({channel, index})).filter(({channel}) => channel.role !== "unused" && field.previews[channel.id])
    .map(({channel, index}) => ({channel: channel.id, src: field.previews[channel.id], color: channel.id === nuclear ? NUCLEAR : STAINS[index % STAINS.length]}));
}
