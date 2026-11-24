/**
 * Serverless transport of the public demo (docs/showcase.md).
 *
 * Visitors see recorded results only, on every device, without waiting:
 * 1. Recorded GET responses (snapshot) paint the workspace and answer what it shows.
 * 2. The recorded tour (`snapshot/journal.json`) answers changes: one that matches a recorded
 *    change returns its recorded response, and later reads return what the API returned after
 *    it; the saved analysis settings are kept on the device.
 * 3. Anything else is answered at once with a notice (`showcase_action_not_recorded`).
 *
 * The real API inside a Web Worker (Pyodide), booted from the same seed, runs only for the
 * build-time recorder (`record`), which produces 2 through it.
 *
 * The transport only returns Responses; `lib/api.ts` keeps its own error handling.
 */
import type {FigureCatalog, HeaderList, Journal, JournalEntry, JournalIndex, ShowcaseNoticeCode, ShowcaseRequest, ShowcaseResponse, SnapshotIndex} from "./protocol";
import {openingPair, type ExperimentDesign} from "../workspace/experiment-design";

export type EngineState = "idle" | "preparing" | "active" | "unavailable";
export interface ShowcaseState {engine: EngineState; reason: "device" | "failed" | "unpublished" | null}
export interface ShowcaseEngine {start(): Promise<void>; handle(request: ShowcaseRequest): Promise<ShowcaseResponse>}
export interface TransportDependencies {
  /** Same-origin static files (snapshot index and bodies). */
  fetchStatic: (url: string) => Promise<Response>;
  /** Null when no runtime is published for this build. */
  createEngine: () => ShowcaseEngine | null;
  /** Whether this device should run the in-browser API. */
  capable: () => boolean;
  snapshotBase: string;
  /** Build-time recorder of the tour (services/showcase journal.mjs); unset for visitors. */
  record?: (exchange: RecordedExchange) => void;
}
export interface RecordedExchange {method: string; path: string; body: string | null; status: number; headers: HeaderList; bytes: ArrayBuffer}

const noticeResponse = (code: ShowcaseNoticeCode, status: number) =>
  new Response(JSON.stringify({detail: code}), {status, headers: {"content-type": "application/json"}});
const abortError = () => new DOMException("The operation was aborted.", "AbortError");
const nullBody = (status: number) => status === 204 || status === 205 || status === 304;

async function bodyBytes(body: RequestInit["body"]): Promise<ArrayBuffer | null> {
  if (body === undefined || body === null) return null;
  if (typeof body === "string") return new TextEncoder().encode(body).buffer as ArrayBuffer;
  if (body instanceof ArrayBuffer) return body.slice(0);
  if (ArrayBuffer.isView(body)) return new Uint8Array(body.buffer, body.byteOffset, body.byteLength).slice().buffer;
  if (body instanceof Blob) return body.arrayBuffer();
  if (body instanceof URLSearchParams) return new TextEncoder().encode(body.toString()).buffer as ArrayBuffer;
  throw new Error("showcase_body_unsupported");
}
function headerList(headers: RequestInit["headers"]): HeaderList {
  const list: HeaderList = [];
  new Headers(headers).forEach((value, name) => list.push([name, value]));
  return list;
}
/** A recorded body matches when equal, with "*" in the recording standing for any value the client generates or counts. */
/** How long after the first paint the recorded tour starts loading (it competes with the opening images). */
const JOURNAL_DELAY_MS = 6000;

export function journalBodyMatches(recorded: string | null, actual: string | null): boolean {
  if (recorded === null) return true;
  if (actual === null) return false;
  let left: unknown, right: unknown;
  try {left = JSON.parse(recorded); right = JSON.parse(actual);} catch {return recorded === actual;}
  const same = (a: unknown, b: unknown): boolean => {
    if (a === "*") return b !== undefined;
    if (Array.isArray(a)) return Array.isArray(b) && a.length === b.length && a.every((value, index) => same(value, b[index]));
    if (a && typeof a === "object") {
      if (!b || typeof b !== "object" || Array.isArray(b)) return false;
      const keys = Object.keys(a as object), other = Object.keys(b as object);
      return keys.length === other.length && keys.every(key => key in (b as object) && same((a as Record<string, unknown>)[key], (b as Record<string, unknown>)[key]));
    }
    return a === b;
  };
  return same(left, right);
}
/** A calculation's figure settings only say how its result is drawn, and the demo draws every result from
 * `figures.json`: a recorded calculation answers whatever figure the request names. */
const CALCULATION = /\/(?:descriptive|common-statistics)$/;
export function calculationBody(path: string, text: string | null): string | null {
  if (text === null || !CALCULATION.test(path)) return text;
  try {
    const value = JSON.parse(text) as unknown;
    if (!value || typeof value !== "object" || Array.isArray(value)) return text;
    const rest: Record<string, unknown> = {...value as Record<string, unknown>};
    delete rest.plot;
    return JSON.stringify(rest);
  } catch {return text;}
}
/**
 * What a figure request draws (ConnectedResults.tsx `plot()`): every setting a figure depends on, with
 * the defaults a request may leave out written in (`observations`: the result's opening form). The size
 * of a publication figure is its `size`; a width and height count only for a custom size or a page figure.
 */
export function figureSettings(plot: unknown, observations: string): string {
  const value = (plot && typeof plot === "object" ? plot : {}) as Record<string, unknown>;
  const presentation = (value.presentation && typeof value.presentation === "object" ? value.presentation : null) as Record<string, unknown> | null;
  const axes = (value.axes && typeof value.axes === "object" ? value.axes : {}) as Record<string, unknown>;
  const style = (value.style && typeof value.style === "object" ? value.style : {}) as Record<string, unknown>;
  const sized = !presentation || presentation.size === "custom";
  const mm = (inches: unknown) => typeof inches === "number" ? Math.round(inches * 254) / 10 : null;
  const images = presentation?.composition === "images-quantification";
  return JSON.stringify({
    kind: value.kind ?? null, font_size: value.font_size ?? null, x_label: value.x_label ?? "", y_label: value.y_label ?? "",
    y_min: value.y_min ?? null, y_max: value.y_max ?? null, y_tick_step: value.y_tick_step ?? null, point_size: value.point_size ?? null,
    group_order: value.group_order ?? [], series_colors: style.series_colors ?? {}, show_legend: style.show_legend ?? true,
    axes: [axes.x_scale ?? "linear", axes.y_scale ?? "linear", axes.x_min ?? null, axes.x_max ?? null, axes.x_tick_step ?? null],
    width: sized ? mm(value.width_inches) : null, height: sized ? mm(value.height_inches) : null,
    presentation: presentation ? [presentation.size ?? "panel", presentation.annotation ?? "value", presentation.composition ?? "quantification",
      presentation.color_by ?? "run", value.kind === "superplot" ? presentation.observations ?? observations : null,
      images ? presentation.image_fields ?? {} : {}, images ? presentation.outlines ?? true : true] : null,
  });
}
/** Recorded change paths use "*" for an identifier the API generated while recording. */
export function journalPathMatches(recorded: string, actual: string): boolean {
  const [path, query = ""] = recorded.split("?"), [other, otherQuery = ""] = actual.split("?");
  const left = path.split("/"), right = other.split("/");
  return query === otherQuery && left.length === right.length && left.every((segment, index) => segment === right[index] || (segment === "*" && right[index] !== ""));
}
const SETTINGS = /^\/v1\/workspaces\/([^/?]+)\/analysis-spec$/;
const RUNS = /^\/v1\/workspaces\/[^/?]+\/runs$/;
const SELECTION = /^\/v1\/workspaces\/[^/?]+\/selection$/;
const JOBS = /^\/v1\/workspaces\/[^/?]+\/jobs$/;
const WORKSPACE = /^\/v1\/workspaces\/([^/?]+)/;
const FIGURE_RENDER = /^\/v1\/jobs\/([^/?]+)\/figure-render$/;
const JOB_FILE = /^\/v1\/jobs\/([^/?]+)\/files\/([^/?]+)$/;
const PACKAGE = /^\/v1\/jobs\/([^/?]+)\/publication-package$/;
const RESULT = /^\/v1\/jobs\/([^/?]+)\/(?:result|common-statistics)$/;
const FILE_TYPES: Record<string, string> = {".svg": "image/svg+xml", ".png": "image/png", ".md": "text/markdown; charset=utf-8",
  ".zip": "application/zip", ".json": "application/json", ".pdf": "application/pdf", ".csv": "text/csv"};
/** Statistics of an analysis version (a cohort): the request names what it calculates, so the same
 * request on another cohort of identical content is the same calculation. Figures and packages are
 * not: their request does not say which result they draw or package. */
const ANALYSIS = /^\/v1\/revisions\/[0-9a-f-]{36}\/(?:review|descriptive|common-statistics)$/;
const analysisPattern = (path: string) => ANALYSIS.test(path) ? path.replace(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/, "*") : undefined;
/** The parts of the saved settings a measurement depends on. */
export function conditions(spec: unknown): unknown {
  const value = spec as Record<string, unknown> | null;
  if (!value || typeof value !== "object") return null;
  return Object.fromEntries(["target", "settings", "processing", "measurement", "backgrounds", "confirmed_channel_ids"].map(key => [key, value[key] ?? null]));
}
/** The settings the scene of entry `position` had saved before it, or undefined when it saved none. */
function recordedSettings(entries: JournalEntry[], position: number): unknown {
  for (let index = position - 1; index >= 0 && entries[index].scene === entries[position].scene; index--) {
    const entry = entries[index];
    if (entry.method === "PUT" && SETTINGS.test(entry.path)) {try {return (JSON.parse(entry.body ?? "null") as {spec?: unknown})?.spec;} catch {return undefined;}}
  }
  return undefined;
}
const reading = (method: string) => method === "GET" || method === "HEAD";
const pause = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

/** Snapshot keys use the path and query exactly as the client requests them. */
export function snapshotKey(path: string) {
  const url = new URL(path, "http://showcase.invalid");
  return `GET ${url.pathname}${url.search}`;
}

export function createShowcaseTransport(dependencies: TransportDependencies) {
  let state: ShowcaseState = {engine: "idle", reason: null};
  let index: Promise<SnapshotIndex | null> | null = null;
  let engine: Promise<ShowcaseEngine> | null = null;
  let live = false, active = false;
  // Recorded tour: `cursor` is the last change it answered.
  let journal: Promise<Journal | null> | null = null, journaled = false, cursor = -1, complete = false;
  // The workspace the visitor has open: the last one a request named, in request order. Each request keeps the one
  // open when it was made, since its answer is decided after the requests before it.
  let openWorkspace: string | null = null;
  let gate: Promise<unknown> = Promise.resolve();
  // The saved analysis settings, kept on the device while the tour answers (they hold no result).
  let settings: {version: number; spec: unknown} | null = null;
  // What this device was last given for each read, as a recorded file (snapshot or tour).
  const seen = new Map<string, JournalEntry | "snapshot" | {device: unknown; at: number}>();
  // Every job a workspace's job list has shown this device, by list path and job id.
  const jobs = new Map<string, Map<string, unknown>>();
  let queue: Promise<unknown> = Promise.resolve();
  const listeners = new Set<() => void>();
  const publish = (next: Partial<ShowcaseState>) => {state = {...state, ...next}; listeners.forEach(listener => listener());};

  // The small workspace records the opening view walks through one after another are requested
  // together as soon as the index arrives, and kept; other recorded bodies are read when asked.
  const opening = new Map<string, Promise<ArrayBuffer | null>>();
  const read = (file: string) => dependencies.fetchStatic(`${dependencies.snapshotBase}${file}`)
    .then(async response => {if (!response.ok) {await response.text(); return null;} return response.arrayBuffer();})
    .catch(() => null);
  const OPENING = /^GET \/v1\/(session|workspaces(\?|$)|workspaces\/[^/?]+(\/(region-fields|revisions|jobs|selection|channel-assignments|field-links|analysis-spec))?$)/;
  function snapshot() {
    index ??= dependencies.fetchStatic(`${dependencies.snapshotBase}index.json`)
      .then(async response => {
        if (!response.ok) {await response.text(); return null;}
        const value = await response.json() as SnapshotIndex;
        if (value?.version !== 1 || !value.entries || typeof value.entries !== "object") return null;
        for (const key of Object.keys(value.entries)) if (OPENING.test(key)) keep(value, key);
        return value;
      }).catch(() => null);
    return index;
  }
  /** Starts loading a recorded file once; later reads of it take the same bytes. */
  function keep(value: SnapshotIndex, key: string) {
    const file = value.entries[key]?.file;
    if (file && /^[A-Za-z0-9._-]+$/.test(file) && !opening.has(file)) opening.set(file, read(file));
    return file ? opening.get(file)! : null;
  }
  const opened = new Set<string>();
  /** What a workspace shows first loads first: once its saved settings are read, the fields it opens on
   * (a two-group design: the first run's field of each group; else its first field) have their previews,
   * masks and measurements requested together, before the client asks for them one by one. */
  async function openingFields(workspace: string) {
    if (opened.has(workspace)) return;
    opened.add(workspace);
    const value = await snapshot();
    if (!value) return;
    const parse = async (key: string) => {try {return JSON.parse(new TextDecoder().decode((await keep(value, key)) ?? undefined)) as unknown;} catch {return null;}};
    const [settings, listing] = await Promise.all([parse(`GET /v1/workspaces/${workspace}/analysis-spec`), parse(`GET /v1/workspaces/${workspace}/region-fields`)]);
    const pair = openingPair((settings as {spec?: {experiment?: ExperimentDesign | null} | null} | null)?.spec?.experiment ?? null);
    const first = Array.isArray(listing) ? (listing[0] as {id?: unknown} | undefined)?.id : undefined;
    const fields = pair.length > 1 ? pair : typeof first === "string" ? [first] : [];
    const keys = Object.keys(value.entries), revisions = new Set<string>();
    for (const id of fields) {
      const field = encodeURIComponent(id);
      for (const key of keys) {
        if (!key.includes(`/region-fields/${field}/preview?`) && !key.endsWith(`field_id=${field}`)) continue;
        keep(value, key);
        const revision = /^GET \/v1\/revisions\/([^/?]+)\/region-masks\?/.exec(key)?.[1];
        if (revision) revisions.add(revision);
      }
    }
    for (const revision of revisions) keep(value, `GET /v1/revisions/${revision}/region-measurements`);
  }
  async function recorded(path: string): Promise<Response | null> {
    const later = await recordedLater(path);
    return later ? later() : null;
  }
  /** The opening snapshot's answer for a read, decided now; its file is requested now and read when awaited. */
  async function recordedLater(path: string): Promise<(() => Promise<Response | null>) | null> {
    const entry = (await snapshot())?.entries[snapshotKey(path)];
    if (!entry || !/^[A-Za-z0-9._-]+$/.test(entry.file)) return null;
    const pending = opening.get(entry.file) ?? read(entry.file);
    return async () => {
      const bytes = await pending;
      if (!bytes) return null;
      // Each caller reads its own copy; the cached bytes stay intact.
      return new Response(nullBody(entry.status) ? null : bytes.slice(0), {status: entry.status, headers: entry.headers});
    };
  }
  async function fromSnapshot(path: string) {
    const response = await recorded(path);
    if (response) seen.set(path, "snapshot");
    return response;
  }
  // The figures of the tour's results (figures.json), and the figure and package jobs this device was given.
  let catalog: Promise<FigureCatalog | null> | null = null;
  const settingsOf = new Map<string, string[]>();
  const drawn = new Map<string, {source: string; group: string; index: number; workspace: string; revision: string}>();
  const packaged = new Map<string, string>();
  function loadFigures() {
    catalog ??= dependencies.fetchStatic(`${dependencies.snapshotBase}figures.json`)
      .then(async response => {
        if (!response.ok) {await response.text(); return null;}
        const value = await response.json() as FigureCatalog;
        return value?.version === 1 && value.groups && value.sources ? value : null;
      }).catch(() => null);
    return catalog;
  }
  const staticFile = async (file: string, status = 200): Promise<Response | null> => {
    if (!/^[A-Za-z0-9._-]+$/.test(file)) return null;
    const response = await dependencies.fetchStatic(`${dependencies.snapshotBase}${file}`).catch(() => null);
    if (!response?.ok) {await response?.text().catch(() => ""); return null;}
    return new Response(await response.arrayBuffer(), {status, headers: {"content-type": FILE_TYPES[file.slice(file.lastIndexOf("."))] ?? "application/octet-stream"}});
  };
  const jsonResponse = (value: unknown, status = 200) => new Response(JSON.stringify(value), {status, headers: {"content-type": "application/json"}});
  /** A job this device was given, listed as the API lists a finished one. */
  function listJob(workspace: string, record: {id: string; revision_id: string; kind: string}) {
    const path = `/v1/workspaces/${workspace}/jobs`;
    const known = jobs.get(path) ?? new Map<string, unknown>();
    jobs.set(path, known);
    known.set(record.id, {...record, state: "succeeded", created: Date.now() / 1000, error: null, attempts: 1, analysis_mode: null, analysis_version: null});
  }
  const recordedId = (id: string) => reverse.get(id) ?? id;
  /** A figure request, its drawing and package, answered from figures.json; undefined when it is no figure request of a recorded result. */
  async function fromFigures(method: string, path: string, body: string | null): Promise<Response | null | undefined> {
    const render = FIGURE_RENDER.exec(path), file = JOB_FILE.exec(path), pack = PACKAGE.exec(path);
    if (!render && !file && !pack) return undefined;
    const value = await loadFigures();
    if (!value) return undefined;
    if (render && method === "POST") {
      const source = value.sources[recordedId(render[1])], group = source && value.groups[source.group];
      if (!source || !group) return undefined;
      let plot: unknown;
      try {plot = (JSON.parse(body ?? "null") as {plot?: unknown} | null)?.plot;} catch {return null;}
      let known = settingsOf.get(source.group);
      if (!known) {known = group.figures.map(item => figureSettings(item.plot, group.observations)); settingsOf.set(source.group, known);}
      const index = known.indexOf(figureSettings(plot, group.observations));
      if (index < 0) return null;
      const id = crypto.randomUUID();
      drawn.set(id, {source: render[1], group: source.group, index, workspace: source.workspace, revision: source.revision});
      listJob(source.workspace, {id, revision_id: source.revision, kind: "figure-render"});
      await pause(450);
      return jsonResponse({job_id: id}, 202);
    }
    if (render && method === "GET") {
      const held = drawn.get(render[1]), saved = value.saved?.[render[1]];
      if (held) return jsonResponse({source_job_id: held.source, figure: value.groups[held.group].figures[held.index].figure});
      return saved ? jsonResponse({source_job_id: saved.source, figure: saved.figure}) : undefined;
    }
    if (pack && method === "POST") {
      const held = drawn.get(pack[1]);
      if (!held) return undefined;
      let analysis: unknown;
      try {analysis = (JSON.parse(body ?? "null") as {analysis_job_id?: unknown} | null)?.analysis_job_id;} catch {return null;}
      const found = typeof analysis === "string" ? value.packages.find(item => item.figure === held.index && item.analysis === recordedId(analysis)
        && value.sources[item.source]?.group === held.group) : undefined;
      if (!found?.files["publication.zip"]) return null;
      const id = crypto.randomUUID();
      packaged.set(id, found.files["publication.zip"]);
      listJob(held.workspace, {id, revision_id: held.revision, kind: "publication-package"});
      await pause(450);
      return jsonResponse({job_id: id}, 202);
    }
    if (file && method === "GET") {
      const name = decodeURIComponent(file[2]), held = drawn.get(file[1]), zip = packaged.get(file[1]);
      if (held) {const stored = value.groups[held.group].figures[held.index].files[name]; return stored ? staticFile(stored) : null;}
      if (zip) return name === "publication.zip" ? staticFile(zip) : null;
      const source = value.sources[recordedId(file[1])], saved = value.saved?.[file[1]];
      const stored = saved ? saved.files[name] : source && value.groups[source.group]?.opening.files[name];
      return stored ? staticFile(stored) : undefined;
    }
    return undefined;
  }
  /** A result read back (calculated in the tour, or saved in the seed): its figure is the one figures.json draws for it. */
  async function withFigure(path: string, response: Response | null): Promise<Response | null> {
    const found = RESULT.exec(path);
    if (!found || !response?.ok) return response;
    const value = await loadFigures(), source = value?.sources[recordedId(found[1])];
    const opening = value?.saved?.[found[1]] ?? (source ? value?.groups[source.group]?.opening : undefined);
    if (!opening) return response;
    let result: {figure?: unknown; spec?: Record<string, unknown>};
    try {result = await response.json();} catch {return null;}
    return jsonResponse({...result, figure: opening.figure, ...(result.spec ? {spec: {...result.spec, plot: opening.plot}} : {})}, response.status);
  }
  /** One journal file: the whole tour (version 1), or its index of parts (version 2). */
  async function journalFile(name: string): Promise<Journal | JournalIndex | null> {
    const response = await dependencies.fetchStatic(`${dependencies.snapshotBase}${name}`);
    if (!response.ok) {await response.text(); return null;}
    const value = await response.json() as Journal | JournalIndex;
    if (value?.version === 1 && Array.isArray(value.entries)) return value;
    return value?.version === 2 && Array.isArray(value.parts) ? value : null;
  }
  let tourIndex: Promise<Journal | JournalIndex | null> | null = null;
  const tourParts = new Map<string, Promise<Journal | JournalIndex | null>>();
  const indexFile = () => tourIndex ??= journalFile("journal.json").catch(() => null);
  const partFile = (name: string) => {
    if (!tourParts.has(name)) tourParts.set(name, journalFile(name).catch(() => null));
    return tourParts.get(name)!;
  };
  /** The parts that hold the recorded scene of a workspace, by the index; none when the index does not say. */
  function partsOf(index: JournalIndex, workspace: string | null): string[] {
    const {parts, counts, workspaces} = index;
    if (!workspace || !counts || !workspaces || counts.length !== parts.length || workspaces.length !== parts.length) return [];
    return parts.filter((_, position) => workspaces[position]?.includes(workspace));
  }
  /** The recorded tour. A tour split into parts (one per scene, docs/showcase.md) is read whole, in order, so it
   *  answers exactly as the same tour in one file. The parts of the open workspace's scene are read first; the
   *  others follow together. */
  function loadJournal() {
    journal ??= indexFile()
      .then(async value => {
        if (value?.version !== 2) return value;
        if (!value.parts.every(part => /^journal-[a-z0-9-]+\.json$/.test(part))) return null;
        await Promise.all(partsOf(value, openWorkspace).map(partFile));
        const parts = await Promise.all(value.parts.map(partFile));
        if (!parts.every(part => part?.version === 1)) return null;
        return {version: 1, entries: (parts as Journal[]).flatMap(part => part.entries)} as Journal;
      })
      .then(value => {complete = !!value; return value;})
      .catch(() => null);
    return journal;
  }
  // A position of the tour whose part has not arrived: it matches no request and belongs to no walk.
  const PENDING: JournalEntry = {scene: "\u0000", method: "", path: "", body: null, status: 0, headers: [], file: null};
  const sceneTours = new Map<string, Promise<{entries: JournalEntry[]; holds: (position: number) => boolean} | null>>();
  /**
   * The tour with only the parts of a workspace's scene in place, every other position pending: the same positions
   * as the whole tour, so what it answers is what the whole tour answers when the answer lies in that scene.
   */
  function sceneTour(workspace: string) {
    if (!sceneTours.has(workspace)) sceneTours.set(workspace, (async () => {
      const index = await indexFile();
      if (index?.version !== 2) return null;
      const names = partsOf(index, workspace);
      if (!names.length) return null;
      void loadJournal();
      const parts = await Promise.all(names.map(partFile));
      const counts = index.counts!;
      const entries: JournalEntry[] = new Array(counts.reduce((total, count) => total + count, 0)).fill(PENDING);
      const ranges: Array<[number, number]> = [];
      let offset = 0;
      for (const [position, name] of index.parts.entries()) {
        const at = names.indexOf(name);
        if (at >= 0) {
          const part = parts[at];
          if (part?.version !== 1 || part.entries.length !== counts[position]) return null;
          part.entries.forEach((entry, item) => {entries[offset + item] = entry;});
          ranges.push([offset, offset + counts[position]]);
        }
        offset += counts[position];
      }
      return {entries, holds: (position: number) => ranges.some(([start, end]) => position >= start && position < end)};
    })().catch(() => null));
    return sceneTours.get(workspace)!;
  }
  /**
   * The open scene's tour, when it alone decides the answer: a change naming the open workspace (a recorded path names
   * a workspace only in that workspace's scene, journal_files.py), or a read after a change answered in that scene.
   */
  async function earlyTour(method: string, path: string, opened: string | null): Promise<JournalEntry[] | null> {
    if (complete || !opened) return null;
    if (!reading(method) && !path.startsWith(`/v1/workspaces/${opened}/`)) return null;
    const tour = await sceneTour(opened);
    if (!tour || (reading(method) && !(cursor >= 0 && tour.holds(cursor)))) return null;
    return tour.entries;
  }
  /** A decision the open scene's tour cannot take alone: it waits for the whole tour. */
  const WHOLE = Symbol("whole tour");
  // Identifiers another scene's recording generated for what this visitor already has (its cohort,
  // its job): recorded -> visitor, and back. Answers from that scene read with the visitor's ones.
  const aliases = new Map<string, string>(), reverse = new Map<string, string>();
  const UUIDS = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/g;
  const recordedIds = (text: string) => reverse.size ? text.replace(UUIDS, id => reverse.get(id) ?? id) : text;
  /**
   * The recorded form of a requested path. Several of this visitor's cohorts of identical content
   * can stand for one recorded cohort; the one this request names is the one answers name.
   */
  function recordedPath(path: string) {
    const translated = recordedIds(path);
    if (translated !== path) for (const id of path.match(UUIDS) ?? []) {const original = reverse.get(id); if (original) aliases.set(original, id);}
    return translated;
  }
  function learn(recorded: string, visitor: string) {
    const left = recorded.split("/"), right = visitor.split("/");
    left.forEach((segment, index) => {
      if (segment !== right[index] && /^[0-9a-f-]{36}$/.test(segment) && /^[0-9a-f-]{36}$/.test(right[index] ?? "")) {
        aliases.set(segment, right[index]); reverse.set(right[index], segment);
      }
    });
  }
  /** The demo scene an entry belongs to: its scene's name before the walk (`<scene>:<walk>`, docs/showcase.md). */
  const demoScene = (entry: JournalEntry) => (entry.scene ?? "").split(":")[0];
  // The workspace each demo scene of the tour was recorded in, from the workspace paths it requested.
  const sceneWorkspaces = new WeakMap<JournalEntry[], Map<string, string>>();
  function workspaceOf(entries: JournalEntry[], entry: JournalEntry) {
    let workspaces = sceneWorkspaces.get(entries);
    if (!workspaces) {
      workspaces = new Map();
      for (const item of entries) {
        const named = WORKSPACE.exec(item.path)?.[1], scene = demoScene(item);
        if (named && !workspaces.has(scene)) workspaces.set(scene, named);
      }
      sceneWorkspaces.set(entries, workspaces);
    }
    return workspaces.get(demoScene(entry));
  }
  async function answer(entry: JournalEntry): Promise<Response | null> {
    let body: ArrayBuffer | null = null;
    if (entry.file !== null && !nullBody(entry.status)) {
      if (!/^[A-Za-z0-9._-]+$/.test(entry.file)) return null;
      const response = await dependencies.fetchStatic(`${dependencies.snapshotBase}${entry.file}`).catch(() => null);
      if (!response?.ok) {await response?.text().catch(() => ""); return null;}
      body = await response.arrayBuffer();
      if (aliases.size && entry.file.endsWith(".json")) {
        const text = new TextDecoder().decode(body).replace(UUIDS, id => aliases.get(id) ?? id);
        body = new TextEncoder().encode(text).buffer as ArrayBuffer;
      }
    }
    return new Response(body, {status: entry.status, headers: entry.headers});
  }
  let seedSpec: Promise<unknown> | null = null;
  /** The published workspace's saved settings (the opening snapshot). */
  function seedSettings() {
    seedSpec ??= snapshot().then(async value => {
      const key = Object.keys(value?.entries ?? {}).find(name => SETTINGS.test(name.slice(4)));
      const response = key ? await recorded(key.slice(4)) : null;
      return response ? ((await response.json()) as {spec?: unknown}).spec ?? null : null;
    }).catch(() => null);
    return seedSpec;
  }
  /** The recorded tour's answer, or null when the tour holds none for this request. */
  async function fromJournal(method: string, path: string, body: string | null, opened: string | null = null): Promise<Response | null> {
    if (SETTINGS.test(path) && (method === "PUT" || (method === "GET" && settings))) {
      if (method === "PUT") {
        let written: {version?: unknown; spec?: unknown} | null = null;
        try {written = JSON.parse(body ?? "null");} catch {return null;}
        if (!written || typeof written.version !== "number" || written.spec === undefined) return null;
        settings = {version: written.version + 1, spec: written.spec};
      }
      return new Response(JSON.stringify(settings), {status: 200, headers: {"content-type": "application/json"}});
    }
    // Until a change has been answered, reads come from the opening snapshot without the tour.
    if (reading(method) && !journaled) {const held = seen.get(path); return held && typeof held === "object" && "device" in held ? heldRead(path) : null;}
    const early = await earlyTour(method, path, opened);
    if (early) {
      const decided = await decide(early, method, path, body, opened, true);
      if (decided !== WHOLE) return decided;
    }
    const entries = (await loadJournal())?.entries;
    if (!entries) return null;
    const decided = await decide(entries, method, path, body, opened, false);
    return decided === WHOLE ? null : decided;
  }
  /** The answer from the tour (`partial`: only the open scene's parts are in place). */
  async function decide(entries: JournalEntry[], method: string, path: string, body: string | null, opened: string | null,
    partial: boolean): Promise<Response | null | typeof WHOLE> {
    if (!reading(method)) {
      // Switching which adopted revision a field shows is answered by the device first: a recorded
      // adoption matches any revision the recording generated, and would bring that scene's state.
      if (method === "POST" && SELECTION.test(path)) {const adopted = await adoptOnDevice(path, body); if (adopted) return adopted;}
      // The next matching change, else the first one: scenes of the tour each start from the seed.
      // A run is measured under the saved settings, which its request does not carry: a recorded
      // run answers only when the settings it was recorded under are the visitor's.
      const current = RUNS.test(path) ? JSON.stringify(conditions(settings?.spec ?? await seedSettings())) : null;
      const matches = (entry: JournalEntry, position: number, recorded = entry.path, requested = path) => entry.method === method && !SETTINGS.test(entry.path)
        && journalPathMatches(recorded, requested) && journalBodyMatches(calculationBody(entry.path, entry.body), calculationBody(path, body))
        && (current === null || journalBodyMatches(JSON.stringify(conditions(recordedSettings(entries, position) ?? seed)), current));
      const seed = current === null ? null : await seedSettings();
      let index = entries.findIndex((entry, position) => position > cursor && matches(entry, position));
      if (index < 0) index = entries.findIndex((entry, position) => matches(entry, position));
      // A request naming what another scene's answer gave this visitor is that scene's request.
      const translated = recordedPath(path);
      if (index < 0 && translated !== path) index = entries.findIndex((entry, position) => position > cursor && matches(entry, position, entry.path, translated));
      if (index < 0 && translated !== path) index = entries.findIndex((entry, position) => matches(entry, position, entry.path, translated));
      // Identifiers the API generated while recording (a cohort, a job) differ between scenes: the
      // same request recorded in another walk is found by its pattern, only when no path matches. Only
      // walks of the open workspace's scene answer: another scene's cohort of the same request holds
      // other images. Without a workspace named yet, the scene of the change last answered stands for it;
      // a scene that named no workspace is not told apart.
      const scope = opened ?? (cursor >= 0 ? workspaceOf(entries, entries[cursor]) : undefined);
      const patterned = (entry: JournalEntry, position: number) => {
        const pattern = analysisPattern(entry.path);
        return !!pattern && (scope === undefined || (workspaceOf(entries, entry) ?? scope) === scope) && matches(entry, position, pattern);
      };
      // A pattern can match another scene's walk (its scope is not a path): the whole tour decides it.
      if (index < 0 && partial) return WHOLE;
      if (index < 0) index = entries.findIndex((entry, position) => position > cursor && patterned(entry, position));
      if (index < 0) index = entries.findIndex(patterned);
      if (index < 0) return null;
      if (!journalPathMatches(entries[index].path, path) && !journalPathMatches(entries[index].path, translated)) learn(entries[index].path, path);
      cursor = index; journaled = true;
      // The device now holds what this change wrote, not what it read before.
      seen.delete(path);
      // A recorded change returns as the API would, after a moment of work.
      await pause(450);
      return answer(entries[index]);
    }
    if (!journaled) return null;
    // The answered change's reads end at the scene's next change, or where the next scene begins.
    let end = cursor + 1;
    while (end < entries.length && reading(entries[end].method) && entries[end].scene === entries[cursor].scene) end++;
    const translated = recordedPath(path);
    const read = (index: number) => entries[index].method === "GET" && (entries[index].path === path || entries[index].path === translated);
    const previous = seen.get(path);
    // What this device wrote after the last recorded change is newer than anything recorded for it.
    if (previous && typeof previous === "object" && "device" in previous && previous.at === cursor) return heldRead(path);
    // The last recorded read of this path after the answered change and before the next one (a job
    // has finished, a document is settled), so repeated reads agree.
    let after = -1;
    for (let index = end - 1; index > cursor && after < 0; index--) if (read(index)) after = index;
    if (after >= 0) {
      // Scenes start from the seed, so a visitor's earlier changes may come from another scene. A
      // document the answered change left as it was keeps what this device already has. The scene's
      // document before the change is its last read, or a write answered with the document itself.
      const scene = entries[cursor].scene;
      const wrote = (index: number) => !reading(entries[index].method) && entries[index].path === entries[after].path && entries[index].file === entries[after].file;
      let before: {file: string | null; status: number} | null = null;
      for (let index = cursor - 1; index >= 0 && !before && entries[index].scene === scene; index--) if (read(index) || wrote(index)) before = entries[index];
      before ??= (await snapshot())?.entries[snapshotKey(path)] ?? null;
      const unchanged = before !== null && before.file === entries[after].file && before.status === entries[after].status;
      if (!(unchanged && previous)) return remember(path, entries[after]);
    }
    if (previous) return heldRead(path);
    // Else the scene's next read of it (what the change wrote), else the latest recorded read before,
    // else one recorded later (a resource another scene created).
    for (let index = end; index < entries.length && entries[index].scene === entries[cursor].scene; index++) if (read(index)) return remember(path, entries[index]);
    if (partial) return WHOLE;
    for (let index = end - 1; index >= 0; index--) if (read(index)) return remember(path, entries[index]);
    for (let index = end; index < entries.length; index++) if (read(index)) return remember(path, entries[index]);
    return null;
  }
  /**
   * The API keeps every job of a workspace, and a client may reuse a job it was given earlier (the
   * same cohort for another measure of the same revisions). A list recorded in another scene lacks
   * the jobs of this visitor's earlier scenes, so the jobs it showed this device stay listed.
   */
  async function withKnownJobs(path: string, response: Response | null): Promise<Response | null> {
    if (!response?.ok || !JOBS.test(path)) return response;
    let listed: unknown;
    try {listed = await response.json();} catch {return null;}
    if (!Array.isArray(listed)) return null;
    const known = jobs.get(path) ?? new Map<string, unknown>();
    jobs.set(path, known);
    const ids = new Set<string>();
    for (const job of listed as Array<{id?: unknown}>) if (typeof job?.id === "string") {ids.add(job.id); known.set(job.id, job);}
    const merged = [...listed, ...[...known].filter(([id]) => !ids.has(id)).map(([, job]) => job)];
    return new Response(JSON.stringify(merged), {status: response.status, headers: {"content-type": "application/json"}});
  }
  /** What this device already has for a read: the opening snapshot, a recorded read, or its own adoption. */
  function heldRead(path: string): Promise<Response | null> {
    const value = seen.get(path);
    if (value === "snapshot") return recorded(path);
    if (value && "device" in value) return Promise.resolve(new Response(JSON.stringify(value.device), {status: 200, headers: {"content-type": "application/json"}}));
    return value ? answer(value) : Promise.resolve(null);
  }
  /**
   * Adoption is bookkeeping of which adopted revision each field shows; it measures nothing. When no
   * recorded adoption matches (the visitor's measurements and analyses came in another order), the
   * device applies the API's rule for the one case the replay can: each field switches to a revision
   * it has already adopted for some target, with the same fields, identities and exclusions.
   */
  async function adoptOnDevice(path: string, body: string | null): Promise<Response | null> {
    const held = await heldRead(path) ?? (journaled ? null : await recorded(path));
    if (!held || !held.ok) return null;
    type Entry = {id?: string; field_id?: string; revision_id?: string | null; exclusion_reason?: string | null; target_revisions?: Record<string, string>};
    let current: {version: number; entries: Entry[]}, written: {version?: unknown; entries?: Entry[]};
    try {current = await held.json(); written = JSON.parse(body ?? "null");} catch {return null;}
    if (!written || written.version !== current.version || !Array.isArray(written.entries) || written.entries.length !== current.entries.length) return null;
    const entries: Entry[] = [];
    for (const [index, before] of current.entries.entries()) {
      const after = written.entries[index];
      if (after.id !== before.id || after.field_id !== before.field_id || (after.exclusion_reason ?? null) !== (before.exclusion_reason ?? null)) return null;
      const adopted = Object.values(before.target_revisions ?? {});
      if (after.revision_id !== before.revision_id && !adopted.includes(after.revision_id ?? "")) return null;
      entries.push({...before, revision_id: after.revision_id});
    }
    const next = {version: current.version + 1, entries};
    seen.set(path, {device: next, at: cursor});
    return new Response(JSON.stringify(next), {status: 200, headers: {"content-type": "application/json"}});
  }
  function remember(path: string, entry: JournalEntry) {
    seen.set(path, entry);
    return answer(entry);
  }
  function ensureEngine(): Promise<ShowcaseEngine> {
    if (engine) return engine;
    const capable = dependencies.capable(), created = capable ? dependencies.createEngine() : null;
    if (!created) {
      publish({engine: "unavailable", reason: capable ? "unpublished" : "device"});
      engine = Promise.reject(new Error(capable ? "showcase_unavailable" : "showcase_engine_unavailable"));
    } else {
      publish({engine: "preparing", reason: null});
      engine = created.start().then(() => {active = true; publish({engine: "active", reason: null}); return created;},
        () => {publish({engine: "unavailable", reason: "failed"}); throw new Error("showcase_engine_unavailable");});
    }
    engine.catch(() => undefined);
    return engine;
  }
  function serialized<T>(task: () => Promise<T>): Promise<T> {
    const result = queue.then(task, task);
    queue = result.catch(() => undefined);
    return result;
  }

  return {
    state: () => state,
    subscribe(listener: () => void) {listeners.add(listener); return () => {listeners.delete(listener);};},
    /** After the first paint: the recorded tour is loaded; the API starts only when an operation needs it. */
    prepare() {
      // The build-time recorder runs every operation through the API, so it starts the API at once.
      if (dependencies.record) {void ensureEngine().catch(() => undefined); return;}
      // The opening images go first; a change before this loads the recording on demand.
      setTimeout(() => {void loadJournal(); void loadFigures();}, JOURNAL_DELAY_MS);
    },
    async fetch(path: string, init: RequestInit = {}): Promise<Response> {
      const signal = init.signal;
      if (signal?.aborted) throw abortError();
      const method = (init.method || "GET").toUpperCase();
      if (typeof FormData !== "undefined" && init.body instanceof FormData) return noticeResponse("showcase_upload_disabled", 403);
      const isRead = reading(method);
      const text = async () => isRead || init.body === undefined || init.body === null ? null : new TextDecoder().decode((await bodyBytes(init.body)) ?? undefined);
      if (!dependencies.record) {
        // Decisions are taken in request order, so a read issued after a change sees that change. A read
        // the opening snapshot answers is decided in order too, but its file (an image, masks) downloads
        // alongside the next requests instead of holding them (the two opening images load together).
        const workspace = SETTINGS.exec(path)?.[1];
        if (isRead && workspace) void openingFields(workspace);
        const opened = openWorkspace = WORKSPACE.exec(path)?.[1] ?? openWorkspace;
        const decided = gate.then(async (): Promise<Response | null | (() => Promise<Response | null>)> => {
          const body = await text();
          // Figures are drawn from the recorded results (figures.json), not recorded with the tour.
          const figured = await fromFigures(method, path, body);
          if (figured !== undefined) return figured;
          const journaled = await fromJournal(method, path, body, opened);
          if (journaled || !isRead) return isRead ? withFigure(path, await withKnownJobs(path, journaled)) : journaled;
          if (JOBS.test(path)) return withKnownJobs(path, await fromSnapshot(path));
          if (RESULT.test(path)) return withFigure(path, await fromSnapshot(path));
          const later = await recordedLater(path);
          if (later) seen.set(path, "snapshot");
          return later;
        });
        gate = decided.catch(() => null);
        const decision = await decided;
        const answered = typeof decision === "function" ? await decision() : decision;
        if (signal?.aborted) throw abortError();
        if (answered) return answered;
        return (await snapshot()) ? noticeResponse("showcase_action_not_recorded", 409) : noticeResponse("showcase_unavailable", 503);
      }
      // The recorder: the opening reads come from the snapshot, everything else from the API.
      if (isRead && !live && !active) {
        const hit = await recorded(path);
        if (signal?.aborted) throw abortError();
        if (hit) return hit;
      }
      if (!isRead) live = true;
      // Queued at call time, so the engine sees requests in the order the client issued them.
      const response = await serialized(async (): Promise<ShowcaseResponse | ShowcaseNoticeCode> => {
        let running: ShowcaseEngine;
        try {running = await ensureEngine();}
        catch (error) {return (error as Error).message === "showcase_unavailable" ? "showcase_unavailable" : "showcase_engine_unavailable";}
        const request: ShowcaseRequest = {method, url: path, headers: headerList(init.headers), body: isRead ? null : await bodyBytes(init.body)};
        return running.handle(request);
      }).catch(() => "showcase_engine_unavailable" as const);
      if (typeof response === "string") return noticeResponse(response, 503);
      if (dependencies.record) {
        const body = isRead || init.body === undefined || init.body === null ? null : new TextDecoder().decode((await bodyBytes(init.body)) ?? undefined);
        dependencies.record({method, path, body, status: response.status, headers: response.headers, bytes: response.body.slice(0)});
      }
      if (signal?.aborted) throw abortError();
      return new Response(nullBody(response.status) ? null : response.body, {status: response.status, headers: response.headers});
    },
  };
}
export type ShowcaseTransport = ReturnType<typeof createShowcaseTransport>;
