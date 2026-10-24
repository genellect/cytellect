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
import type {HeaderList, Journal, JournalEntry, ShowcaseNoticeCode, ShowcaseRequest, ShowcaseResponse, SnapshotIndex} from "./protocol";

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
/** Recorded change paths use "*" for an identifier the API generated while recording. */
export function journalPathMatches(recorded: string, actual: string): boolean {
  const [path, query = ""] = recorded.split("?"), [other, otherQuery = ""] = actual.split("?");
  const left = path.split("/"), right = other.split("/");
  return query === otherQuery && left.length === right.length && left.every((segment, index) => segment === right[index] || (segment === "*" && right[index] !== ""));
}
const SETTINGS = /^\/v1\/workspaces\/[^/?]+\/analysis-spec$/;
const RUNS = /^\/v1\/workspaces\/[^/?]+\/runs$/;
const SELECTION = /^\/v1\/workspaces\/[^/?]+\/selection$/;
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
  let journal: Promise<Journal | null> | null = null, journaled = false, cursor = -1;
  let gate: Promise<unknown> = Promise.resolve();
  // The saved analysis settings, kept on the device while the tour answers (they hold no result).
  let settings: {version: number; spec: unknown} | null = null;
  // What this device was last given for each read, as a recorded file (snapshot or tour).
  const seen = new Map<string, JournalEntry | "snapshot" | {device: unknown; at: number}>();
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
        const keep = (key: string) => {
          const file = value.entries[key]?.file;
          if (file && /^[A-Za-z0-9._-]+$/.test(file) && !opening.has(file)) opening.set(file, read(file));
          return file ? opening.get(file)! : null;
        };
        for (const key of Object.keys(value.entries)) if (OPENING.test(key)) keep(key);
        void openingField(value, keep);
        return value;
      }).catch(() => null);
    return index;
  }
  /** The first field opens first: its previews, masks and measurements are requested with the records. */
  async function openingField(value: SnapshotIndex, keep: (key: string) => Promise<ArrayBuffer | null> | null) {
    const keys = Object.keys(value.entries), listing = keys.find(key => /^GET \/v1\/workspaces\/[^/?]+\/region-fields$/.test(key));
    const bytes = listing ? await keep(listing) : null;
    let first: string | undefined;
    try {first = (JSON.parse(new TextDecoder().decode(bytes ?? undefined)) as Array<{id?: string}>)[0]?.id;} catch {return;}
    if (!first) return;
    const field = encodeURIComponent(first), revisions = new Set<string>();
    for (const key of keys) {
      if (!key.includes(`/region-fields/${field}/preview?`) && !key.endsWith(`field_id=${field}`)) continue;
      keep(key);
      const revision = /^GET \/v1\/revisions\/([^/?]+)\/region-masks\?/.exec(key)?.[1];
      if (revision) revisions.add(revision);
    }
    for (const revision of revisions) keep(`GET /v1/revisions/${revision}/region-measurements`);
  }
  async function recorded(path: string): Promise<Response | null> {
    const entry = (await snapshot())?.entries[snapshotKey(path)];
    if (!entry || !/^[A-Za-z0-9._-]+$/.test(entry.file)) return null;
    const bytes = await (opening.get(entry.file) ?? read(entry.file));
    if (!bytes) return null;
    // Each caller reads its own copy; the cached bytes stay intact.
    return new Response(nullBody(entry.status) ? null : bytes.slice(0), {status: entry.status, headers: entry.headers});
  }
  async function fromSnapshot(path: string) {
    const response = await recorded(path);
    if (response) seen.set(path, "snapshot");
    return response;
  }
  function loadJournal() {
    journal ??= dependencies.fetchStatic(`${dependencies.snapshotBase}journal.json`)
      .then(async response => {
        if (!response.ok) {await response.text(); return null;}
        const value = await response.json() as Journal;
        return value?.version === 1 && Array.isArray(value.entries) ? value : null;
      }).catch(() => null);
    return journal;
  }
  // Identifiers another scene's recording generated for what this visitor already has (its cohort,
  // its job): recorded -> visitor, and back. Answers from that scene read with the visitor's ones.
  const aliases = new Map<string, string>(), reverse = new Map<string, string>();
  const UUIDS = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/g;
  const recordedIds = (text: string) => reverse.size ? text.replace(UUIDS, id => reverse.get(id) ?? id) : text;
  function learn(recorded: string, visitor: string) {
    const left = recorded.split("/"), right = visitor.split("/");
    left.forEach((segment, index) => {
      if (segment !== right[index] && /^[0-9a-f-]{36}$/.test(segment) && /^[0-9a-f-]{36}$/.test(right[index] ?? "")) {
        aliases.set(segment, right[index]); reverse.set(right[index], segment);
      }
    });
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
  async function fromJournal(method: string, path: string, body: string | null): Promise<Response | null> {
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
    const entries = (await loadJournal())?.entries;
    if (!entries) return null;
    if (!reading(method)) {
      // Switching which adopted revision a field shows is answered by the device first: a recorded
      // adoption matches any revision the recording generated, and would bring that scene's state.
      if (method === "POST" && SELECTION.test(path)) {const adopted = await adoptOnDevice(path, body); if (adopted) return adopted;}
      // The next matching change, else the first one: scenes of the tour each start from the seed.
      // A run is measured under the saved settings, which its request does not carry: a recorded
      // run answers only when the settings it was recorded under are the visitor's.
      const current = RUNS.test(path) ? JSON.stringify(conditions(settings?.spec ?? await seedSettings())) : null;
      const matches = (entry: JournalEntry, position: number, recorded = entry.path, requested = path) => entry.method === method && !SETTINGS.test(entry.path)
        && journalPathMatches(recorded, requested) && journalBodyMatches(entry.body, body)
        && (current === null || journalBodyMatches(JSON.stringify(conditions(recordedSettings(entries, position) ?? seed)), current));
      const seed = current === null ? null : await seedSettings();
      let index = entries.findIndex((entry, position) => position > cursor && matches(entry, position));
      if (index < 0) index = entries.findIndex((entry, position) => matches(entry, position));
      // A request naming what another scene's answer gave this visitor is that scene's request.
      const translated = recordedIds(path);
      if (index < 0 && translated !== path) index = entries.findIndex((entry, position) => position > cursor && matches(entry, position, entry.path, translated));
      if (index < 0 && translated !== path) index = entries.findIndex((entry, position) => matches(entry, position, entry.path, translated));
      // Identifiers the API generated while recording (a cohort, a job) differ between scenes: the
      // same request recorded in another scene is found by its pattern, only when no path matches.
      const patterned = (entry: JournalEntry, position: number) => {
        const pattern = analysisPattern(entry.path);
        return !!pattern && matches(entry, position, pattern);
      };
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
    const next = entries.findIndex((entry, position) => position > cursor && !reading(entry.method));
    const end = next < 0 ? entries.length : next;
    const translated = recordedIds(path);
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
      // document the answered change left as it was keeps what this device already has.
      const scene = entries[cursor].scene;
      let before: {file: string | null; status: number} | null = null;
      for (let index = cursor - 1; index >= 0 && !before && entries[index].scene === scene; index--) if (read(index)) before = entries[index];
      before ??= (await snapshot())?.entries[snapshotKey(path)] ?? null;
      const unchanged = before !== null && before.file === entries[after].file && before.status === entries[after].status;
      if (!(unchanged && previous)) return remember(path, entries[after]);
    }
    if (previous) return heldRead(path);
    // Else the scene's next read of it (what the change wrote), else the latest recorded read before,
    // else one recorded later (a resource another scene created).
    for (let index = end; index < entries.length && entries[index].scene === entries[cursor].scene; index++) if (read(index)) return remember(path, entries[index]);
    for (let index = end - 1; index >= 0; index--) if (read(index)) return remember(path, entries[index]);
    for (let index = end; index < entries.length; index++) if (read(index)) return remember(path, entries[index]);
    return null;
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
      void loadJournal();
    },
    async fetch(path: string, init: RequestInit = {}): Promise<Response> {
      const signal = init.signal;
      if (signal?.aborted) throw abortError();
      const method = (init.method || "GET").toUpperCase();
      if (typeof FormData !== "undefined" && init.body instanceof FormData) return noticeResponse("showcase_upload_disabled", 403);
      const isRead = reading(method);
      const text = async () => isRead || init.body === undefined || init.body === null ? null : new TextDecoder().decode((await bodyBytes(init.body)) ?? undefined);
      if (!dependencies.record) {
        // Decisions are taken in request order, so a read issued after a change sees that change.
        const decided = gate.then(async () => await fromJournal(method, path, await text()) ?? (isRead ? await fromSnapshot(path) : null));
        gate = decided.catch(() => null);
        const answered = await decided;
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
