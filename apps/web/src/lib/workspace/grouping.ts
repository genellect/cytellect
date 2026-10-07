/**
 * Field/channel grouping for added files (workspace redesign U02).
 *
 * An unknown stain is not a problem to resolve: the channel keeps its token as
 * its name. The only decision a run can need is which channel detects nuclei.
 *
 * Evidence comes only from OME channel names, file names and folder names.
 * File order never pairs files, `c1`/`c2`-style tokens never establish a stain,
 * and folders never become independent experimental units. Ambiguity is
 * reported as an issue instead of being resolved silently.
 */

export type ChannelRole = "nuclear" | "measure";
export type Evidence = "ome" | "filename" | "folder" | "user" | "registered_source";

export interface AddedFile {
  /** Relative path inside the dropped folder, or the bare file name. */
  path: string;
  size: number;
  /** Content hash when already known; used only for duplicate detection. */
  sha256?: string;
  inputMode?: "native" | "display-rgb";
  /** OME channel name when the header provides one (one channel per file). */
  omeChannel?: string;
  /** Channel names of a multi-channel OME-TIFF, read by the import API. */
  omeChannels?: string[];
}

export interface ChannelDefinition {
  token: string;
  /** Actual stain name; null when the evidence does not establish it. */
  stain: string | null;
  role: ChannelRole | null;
  evidence: Evidence;
}

export interface GroupedField {
  key: string;
  files: Record<string, AddedFile>;
  candidates: { well?: string; date?: string; folder?: string };
}

export type GroupingIssue =
  | { kind: "channel_range_reference"; path: string; channels: string[] }
  | { kind: "duplicate_channel"; field: string; token: string; paths: string[] }
  | { kind: "duplicate_content"; paths: string[] }
  | { kind: "missing_channel"; field: string; token: string }
  | { kind: "channel_unidentified"; path: string }
  /** Multi-channel OME-TIFF whose channel names are read on import; kept, never dropped. */
  | { kind: "channels_pending"; path: string };

export interface Grouping {
  fields: GroupedField[];
  channels: ChannelDefinition[];
  issues: GroupingIssue[];
}

interface KnownStain { stain: string; role: ChannelRole }

const STAINS: Record<string, KnownStain> = {
  dapi: { stain: "DAPI", role: "nuclear" },
  hoechst: { stain: "Hoechst", role: "nuclear" },
  draq: { stain: "DRAQ", role: "nuclear" },
  draq5: { stain: "DRAQ5", role: "nuclear" },
  draq7: { stain: "DRAQ7", role: "nuclear" },
  gfp: { stain: "GFP", role: "measure" },
  egfp: { stain: "EGFP", role: "measure" },
  ncl: { stain: "NCL", role: "measure" },
  nucleolin: { stain: "NCL", role: "measure" },
  fibrillarin: { stain: "Fibrillarin", role: "measure" },
  ubf: { stain: "UBF", role: "measure" },
  rfp: { stain: "RFP", role: "measure" },
  mcherry: { stain: "mCherry", role: "measure" },
};
/** Index-only channel tokens: they identify a channel, never a stain. */
const INDEX_TOKEN = /^(?:c|ch|channel|w)\d{1,2}$/i;
/** An index glued to the end of a name, e.g. xy01c1 → xy01 + c1. */
const GLUED_INDEX = /^(.*\d)(c|ch|w)(\d{1,2})$/i;
/** A known stain, optionally followed by a dye or wavelength number (Hoechst33342, DAPI405). */
const STAIN_TOKEN = new RegExp(`^(${Object.keys(STAINS).sort((a, b) => b.length - a.length).join("|")})(\\d{0,5})$`, "i");
const WELL_TOKEN = /^[A-P]\d{1,2}$/;
const DATE_TOKEN = /^(20\d{2})-?(\d{2})-?(\d{2})$/;
const IMAGE_EXTENSION = /\.(?:ome\.tiff?|tiff?)$/i;

export function isSupportedImage(path: string): boolean {
  return IMAGE_EXTENSION.test(path);
}

function splitPath(path: string): { folders: string[]; stem: string } {
  const parts = path.replaceAll("\\", "/").split("/").filter(Boolean);
  const name = parts.pop() ?? "";
  return { folders: parts, stem: name.replace(/\.(?:ome\.tiff?|tiff?|bmp|png)$/i, "") };
}

/** Known stain for a token, keeping a dye/wavelength number in the name. */
export function stainOf(token: string): KnownStain | null {
  const match = STAIN_TOKEN.exec(token.trim());
  if (!match) return null;
  const known = STAINS[match[1].toLowerCase()];
  return { stain: `${known.stain}${match[2]}`, role: known.role };
}

function describe(token: string, evidence: Evidence, name?: string): ChannelDefinition {
  const known = stainOf(token) ?? (name ? stainOf(name) : null);
  return known
    ? { token, stain: known.stain, role: known.role, evidence }
    : { token, stain: null, role: null, evidence };
}

interface ChannelMatch { token: string; keyTokens: string[]; evidence: Evidence; folderUsed: boolean }

/**
 * One channel per file. A named stain wins over an index token; index tokens
 * are channel numbers and are removed from the field key. Several stains, or
 * several indices without a stain, are ambiguous and never guessed.
 */
function matchChannel(tokens: string[], folders: string[]): ChannelMatch | null {
  const stains = tokens.filter((token) => stainOf(token));
  const indices = tokens.filter((token) => INDEX_TOKEN.test(token));
  const rest = tokens.filter((token) => !stainOf(token) && !INDEX_TOKEN.test(token));
  if (stains.length === 1) return { token: stains[0].toLowerCase(), keyTokens: rest, evidence: "filename", folderUsed: false };
  if (stains.length > 1) return null;
  if (indices.length === 1) return { token: indices[0].toLowerCase(), keyTokens: rest, evidence: "filename", folderUsed: false };
  if (indices.length > 1) return null;
  const last = tokens.at(-1);
  const glued = last ? GLUED_INDEX.exec(last) : null;
  if (glued) {
    return { token: `${glued[2]}${glued[3]}`.toLowerCase(), keyTokens: [...tokens.slice(0, -1), glued[1]], evidence: "filename", folderUsed: false };
  }
  const folder = folders.at(-1);
  if (folder && (stainOf(folder) || INDEX_TOKEN.test(folder))) {
    return { token: folder.toLowerCase(), keyTokens: tokens, evidence: "folder", folderUsed: true };
  }
  return null;
}

/** Group added files into fields and channels without inferring stains from indices. */
export function groupFiles(files: AddedFile[], mode: "automatic" | "single" = "automatic"): Grouping {
  const issues: GroupingIssue[] = [];
  const fields = new Map<string, GroupedField>();
  const channels = new Map<string, ChannelDefinition>();
  const occupied = new Map<string, string[]>();
  const place = (file: AddedFile, folders: string[], keyTokens: string[], token: string, definition: ChannelDefinition) => {
    if (!channels.has(token)) channels.set(token, definition);
    const folder = folders.join("/");
    const key = [folder, keyTokens.join("-")].filter(Boolean).join("/");
    const field = fields.get(key) ?? { key, files: {}, candidates: candidates(keyTokens, folder) };
    const slot = `${key}\u0000${token}`;
    occupied.set(slot, [...(occupied.get(slot) ?? []), file.path]);
    field.files[token] ??= file;
    fields.set(key, field);
  };
  for (const file of files) {
    const { folders, stem } = splitPath(file.path);
    const tokens = stem.split(/[-_ .]+/).filter(Boolean);
    if (file.omeChannels?.length) {
      // A multi-channel container is one field; its channels come from the OME header.
      file.omeChannels.forEach((name, index) => {
        const token = name.trim() ? name.trim().toLowerCase() : `c${index + 1}`;
        place(file, folders, tokens, token, describe(token, "ome", name));
      });
      continue;
    }
    if (file.omeChannel) {
      const token = file.omeChannel.trim().toLowerCase();
      place(file, folders, tokens, token, describe(token, "ome", file.omeChannel));
      continue;
    }
    // A range suffix is not a single channel. With all matching component
    // files present, use those planes and report the range image separately.
    // This never identifies a biological stain or decomposes RGB intensities.
    const range = mode === "automatic" ? /^(.*?)[_ .-](c|ch|channel)(\d+)-(?:c|ch|channel)?(\d+)$/i.exec(stem) : null;
    if (range && Number(range[4]) > Number(range[3]) && Number(range[4]) - Number(range[3]) < 16) {
      const channelIds = Array.from({length:Number(range[4]) - Number(range[3]) + 1}, (_, index) => `${range[2].toLowerCase()}${Number(range[3]) + index}`);
      const companions = files.filter(candidate => {
        const part = splitPath(candidate.path);
        return part.folders.join("/") === folders.join("/") && channelIds.some(id => part.stem.toLowerCase() === `${range[1]}_${id}`.toLowerCase() || part.stem.toLowerCase() === `${range[1]}-${id}`.toLowerCase());
      });
      if (channelIds.every(id => companions.some(candidate => splitPath(candidate.path).stem.toLowerCase().endsWith(`_${id}`) || splitPath(candidate.path).stem.toLowerCase().endsWith(`-${id}`)))) {
        issues.push({kind:"channel_range_reference", path:file.path, channels:channelIds});
        continue;
      }
      // Without individual planes, retain the image independently instead of
      // turning c1-4 into a misleading c1 channel of another field.
      place(file, folders, [stem], "image", {token:"image",stain:null,role:null,evidence:"user"});
      continue;
    }
    const match = mode === "single" ? null : matchChannel(tokens, folders);
    if (!match) {
      // Preserve unnamed planes independently, without guessing biological pairing.
      place(file, folders, [stem], "c1", {token: "c1", stain: null, role: null, evidence: "user"});
      continue;
    }
    const keyFolders = match.folderUsed ? folders.slice(0, -1) : folders;
    place(file, keyFolders, match.keyTokens, match.token, describe(match.token, match.evidence));
  }
  for (const [slot, paths] of occupied) {
    if (paths.length > 1) {
      const [field, token] = slot.split("\u0000");
      issues.push({ kind: "duplicate_channel", field, token, paths });
      // Two candidates for one slot stay unresolved; neither is used.
      delete fields.get(field)!.files[token];
    }
  }
  const byHash = new Map<string, string[]>();
  for (const file of files) {
    if (file.sha256) byHash.set(file.sha256, [...(byHash.get(file.sha256) ?? []), file.path]);
  }
  for (const paths of byHash.values()) if (paths.length > 1) issues.push({ kind: "duplicate_content", paths });
  const tokens = [...channels.keys()].sort();
  for (const field of fields.values()) {
    for (const token of tokens) {
      if (!field.files[token] && !issues.some((issue) => issue.kind === "duplicate_channel" && issue.field === field.key && issue.token === token)) {
        issues.push({ kind: "missing_channel", field: field.key, token });
      }
    }
  }
  return {
    fields: [...fields.values()].sort((a, b) => a.key.localeCompare(b.key, "en", { numeric: true })),
    channels: tokens.map((token) => channels.get(token)!),
    issues,
  };
}

function candidates(tokens: string[], folder: string): GroupedField["candidates"] {
  const result: GroupedField["candidates"] = {};
  const well = tokens.find((token) => WELL_TOKEN.test(token));
  if (well) result.well = well;
  for (const token of tokens) {
    const match = DATE_TOKEN.exec(token);
    if (match) result.date = `${match[1]}-${match[2]}-${match[3]}`;
  }
  if (folder) result.folder = folder;
  return result;
}

/**
 * The one channel decision a run may need: which channel detects nuclei.
 * Recorded as the user's statement; stains are not inferred from it.
 */
export function chooseNuclearChannel(grouping: Grouping, token: string): Grouping {
  if (!grouping.channels.some((channel) => channel.token === token)) throw new Error("channel_unknown");
  return {
    ...grouping,
    channels: grouping.channels.map((channel) => channel.token === token
      ? { ...channel, role: "nuclear" as const, evidence: "user" as const }
      : channel.role === "nuclear" ? { ...channel, role: "measure" as const, evidence: "user" as const } : channel),
  };
}

/** Optional display/stain name; an empty name returns the channel to unknown stain. */
export function nameChannel(grouping: Grouping, token: string, stain: string): Grouping {
  // Known stains are written one way (ncl → NCL), so recipes recognise them.
  const value = stainOf(stain)?.stain ?? stain.trim();
  return {
    ...grouping,
    channels: grouping.channels.map((channel) => channel.token === token
      ? { ...channel, stain: value || null, evidence: "user" as const } : channel),
  };
}

export function channelName(channel: ChannelDefinition): string {
  return channel.stain ?? channel.token;
}

/** Restore the union: incomplete fields need not contain every channel. */
export function restoredChannels(fields: Array<{image_info: {channels: Array<{channel_id: string; label: string; stain: string | null}>}}>): ChannelDefinition[] {
  const known = new Map<string, {label: string; channel: ChannelDefinition}>();
  for (const field of fields) for (const spec of field.image_info.channels) {
    const previous = known.get(spec.channel_id);
    if (previous && (previous.label !== spec.label || previous.channel.stain !== spec.stain)) throw new Error("保存されたチャンネル情報が一致しません。");
    known.set(spec.channel_id, {label: spec.label, channel: {token: spec.channel_id, stain: spec.stain, role: null, evidence: "registered_source"}});
  }
  return [...known.values()].map(value => value.channel).sort((a, b) => a.token.localeCompare(b.token));
}
