/**
 * Serverless transport of the public demo (docs/showcase.md).
 *
 * 1. Recorded initial GET responses (snapshot) paint the workspace at once.
 * 2. The first change, or a GET without a recording, starts the real API inside a
 *    Web Worker (Pyodide), booted from the same seed as the snapshot. Once it has
 *    received a request, every later request goes to it, one at a time.
 *
 * 3. On devices that cannot run that API (phones, little memory, a failed start), the
 *    recorded tour (`snapshot/journal.json`) answers instead: a change that matches a
 *    recorded one returns its recorded response, and later reads return what the API
 *    returned after it; the saved analysis settings are kept on the device. Desktops wait
 *    for their own API, so its state never diverges from the tour's.
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
  // Recorded tour: `cursor` is the last change it answered; `served` the last read answered per path.
  let journal: Promise<Journal | null> | null = null, journaled = false, cursor = -1;
  let gate: Promise<unknown> = Promise.resolve();
  // The saved analysis settings, kept on the device while the tour answers (they hold no result).
  let settings: {version: number; spec: unknown} | null = null;
  const served = new Map<string, number>();
  let queue: Promise<unknown> = Promise.resolve();
  const listeners = new Set<() => void>();
  const publish = (next: ShowcaseState) => {state = next; listeners.forEach(listener => listener());};

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
  function loadJournal() {
    journal ??= dependencies.fetchStatic(`${dependencies.snapshotBase}journal.json`)
      .then(async response => {
        if (!response.ok) {await response.text(); return null;}
        const value = await response.json() as Journal;
        return value?.version === 1 && Array.isArray(value.entries) ? value : null;
      }).catch(() => null);
    return journal;
  }
  async function answer(entry: JournalEntry): Promise<Response | null> {
    let body: ArrayBuffer | null = null;
    if (entry.file !== null && !nullBody(entry.status)) {
      if (!/^[A-Za-z0-9._-]+$/.test(entry.file)) return null;
      const response = await dependencies.fetchStatic(`${dependencies.snapshotBase}${entry.file}`).catch(() => null);
      if (!response?.ok) {await response?.text().catch(() => ""); return null;}
      body = await response.arrayBuffer();
    }
    return new Response(body, {status: entry.status, headers: entry.headers});
  }
  /** The recorded tour's answer, or null when the tour holds none for this request. */
  async function fromJournal(method: string, path: string, body: string | null): Promise<Response | null> {
    // Until a change has been answered, reads come from the opening snapshot without the tour.
    if (reading(method) && !journaled) return null;
    const entries = (await loadJournal())?.entries;
    if (!entries) return null;
    if (SETTINGS.test(path) && (method === "PUT" || (method === "GET" && settings))) {
      if (method === "PUT") {
        const written = JSON.parse(body ?? "null") as {version?: unknown; spec?: unknown} | null;
        if (!written || typeof written.version !== "number" || written.spec === undefined) return null;
        settings = {version: written.version + 1, spec: written.spec}; journaled = true;
      }
      return new Response(JSON.stringify(settings), {status: 200, headers: {"content-type": "application/json"}});
    }
    if (!reading(method)) {
      // The next matching change, else the first one: scenes of the tour each start from the seed.
      const matches = (entry: JournalEntry) => entry.method === method && journalPathMatches(entry.path, path) && journalBodyMatches(entry.body, body);
      let index = entries.findIndex((entry, position) => position > cursor && matches(entry));
      if (index < 0) index = entries.findIndex(matches);
      if (index < 0) return null;
      cursor = index; journaled = true;
      // A recorded change returns as the API would, after a moment of work.
      await pause(450);
      return answer(entries[index]);
    }
    if (!journaled) return null;
    const next = entries.findIndex((entry, position) => position > cursor && !reading(entry.method));
    const end = next < 0 ? entries.length : next;
    const from = Math.max(cursor, served.get(path) ?? -1);
    // The next recorded read of this path before the next change (e.g. a job finishing), else the
    // latest one before it, else one recorded later (a resource another scene created).
    const read = (index: number) => entries[index].method === "GET" && entries[index].path === path;
    for (let index = from + 1; index < end; index++) if (read(index)) {served.set(path, index); return answer(entries[index]);}
    for (let index = Math.min(from, end - 1); index >= 0; index--) if (read(index)) return answer(entries[index]);
    for (let index = end; index < entries.length; index++) if (read(index)) return answer(entries[index]);
    return null;
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
    /** Background start after the first paint; devices that do not run the API load the recorded tour instead. */
    prepare() {
      if (!dependencies.capable()) {void loadJournal(); return;}
      if (state.engine === "idle") void ensureEngine().catch(() => undefined);
    },
    async fetch(path: string, init: RequestInit = {}): Promise<Response> {
      const signal = init.signal;
      if (signal?.aborted) throw abortError();
      const method = (init.method || "GET").toUpperCase();
      if (typeof FormData !== "undefined" && init.body instanceof FormData) return noticeResponse("showcase_upload_disabled", 403);
      const isRead = reading(method);
      // The recorded tour answers before the in-browser API is running, and keeps answering once used.
      // Decisions are taken in request order, so a read issued after a change sees that change.
      const decided = gate.then(async (): Promise<Response | "notice" | null> => {
        if (live || (!journaled && dependencies.capable() && state.reason !== "failed")) return null;
        const text = isRead || init.body === undefined || init.body === null ? null : new TextDecoder().decode((await bodyBytes(init.body)) ?? undefined);
        const hit = await fromJournal(method, path, text);
        return hit ?? (journaled && !isRead ? "notice" : null);
      });
      gate = decided.catch(() => null);
      const recordedTour = await decided;
      if (signal?.aborted) throw abortError();
      if (recordedTour === "notice") return noticeResponse("showcase_action_not_recorded", 409);
      if (recordedTour) return recordedTour;
      // While the tour answers, the engine (whose state lacks its changes) is never used.
      if (isRead && (journaled || (!live && !active))) {
        const hit = await recorded(path);
        if (signal?.aborted) throw abortError();
        if (hit || journaled) return hit ?? noticeResponse("showcase_action_not_recorded", 409);
      }
      // After the first change, later reads must observe it: route them all live.
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
