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
export type Evidence = "ome" | "filename" | "folder" | "user";

export interface AddedFile {
  /** Relative path inside the dropped folder, or the bare file name. */
  path: string;
  size: number;
  /** Content hash when already known; used only for duplicate detection. */
  sha256?: string;
  /** OME channel name when the header provides one. */
  omeChannel?: string;
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
  | { kind: "duplicate_channel"; field: string; token: string; paths: string[] }
  | { kind: "duplicate_content"; paths: string[] }
  | { kind: "missing_channel"; field: string; token: string }
  | { kind: "channel_unidentified"; path: string };

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

function channelToken(token: string): string | null {
  const lower = token.toLowerCase();
  if (STAINS[lower] || INDEX_TOKEN.test(token)) return lower;
  return null;
}

function describe(token: string, evidence: Evidence, omeName?: string): ChannelDefinition {
  const known = STAINS[token] ?? (omeName ? STAINS[omeName.toLowerCase()] : undefined);
  return known
    ? { token, stain: known.stain, role: known.role, evidence }
    : { token, stain: null, role: null, evidence };
}

/** Group added files into fields and channels without inferring stains from indices. */
export function groupFiles(files: AddedFile[]): Grouping {
  const issues: GroupingIssue[] = [];
  const fields = new Map<string, GroupedField>();
  const channels = new Map<string, ChannelDefinition>();
  const occupied = new Map<string, string[]>();
  for (const file of files) {
    const { folders, stem } = splitPath(file.path);
    const tokens = stem.split(/[-_ .]+/).filter(Boolean);
    let token: string | null = null;
    let evidence: Evidence = "filename";
    let keyTokens = tokens;
    const matches = tokens.map(channelToken).filter((value): value is string => value !== null);
    if (file.omeChannel) {
      token = file.omeChannel.toLowerCase();
      evidence = "ome";
    } else if (matches.length === 1) {
      token = matches[0];
      keyTokens = tokens.filter((value) => channelToken(value) !== token);
    } else if (matches.length === 0 && folders.length && channelToken(folders[folders.length - 1])) {
      token = channelToken(folders[folders.length - 1]);
      evidence = "folder";
      folders.pop();
    }
    if (!token) {
      // Zero or several channel-like tokens: never guess which one is the channel.
      issues.push({ kind: "channel_unidentified", path: file.path });
      continue;
    }
    if (!channels.has(token)) channels.set(token, describe(token, evidence, file.omeChannel));
    const folder = folders.join("/");
    const key = [folder, keyTokens.join("-")].filter(Boolean).join("/");
    const field = fields.get(key) ?? { key, files: {}, candidates: candidates(keyTokens, folder) };
    const slot = `${key}\u0000${token}`;
    occupied.set(slot, [...(occupied.get(slot) ?? []), file.path]);
    field.files[token] ??= file;
    fields.set(key, field);
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
  const value = stain.trim();
  return {
    ...grouping,
    channels: grouping.channels.map((channel) => channel.token === token
      ? { ...channel, stain: value || null, evidence: "user" as const } : channel),
  };
}

export function channelName(channel: ChannelDefinition): string {
  return channel.stain ?? channel.token;
}
