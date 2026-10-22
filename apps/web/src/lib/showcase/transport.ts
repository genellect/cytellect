/**
 * Serverless transport of the public demo (docs/showcase.md).
 *
 * 1. Recorded initial GET responses (snapshot) paint the workspace at once.
 * 2. The first change, or a GET without a recording, starts the real API inside a
 *    Web Worker (Pyodide), booted from the same seed as the snapshot. Once it has
 *    received a request, every later request goes to it, one at a time.
 *
 * The transport only returns Responses; `lib/api.ts` keeps its own error handling.
 */
import type {HeaderList, ShowcaseNoticeCode, ShowcaseRequest, ShowcaseResponse, SnapshotIndex} from "./protocol";

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
}

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
  let queue: Promise<unknown> = Promise.resolve();
  const listeners = new Set<() => void>();
  const publish = (next: ShowcaseState) => {state = next; listeners.forEach(listener => listener());};

  function snapshot() {
    index ??= dependencies.fetchStatic(`${dependencies.snapshotBase}index.json`)
      .then(async response => {
        if (!response.ok) {await response.text(); return null;}
        const value = await response.json() as SnapshotIndex;
        return value?.version === 1 && value.entries && typeof value.entries === "object" ? value : null;
      }).catch(() => null);
    return index;
  }
  async function recorded(path: string): Promise<Response | null> {
    const entry = (await snapshot())?.entries[snapshotKey(path)];
    if (!entry || !/^[A-Za-z0-9._-]+$/.test(entry.file)) return null;
    const response = await dependencies.fetchStatic(`${dependencies.snapshotBase}${entry.file}`).catch(() => null);
    if (!response?.ok) {await response?.text().catch(() => ""); return null;}
    const body = nullBody(entry.status) ? null : await response.arrayBuffer();
    return new Response(body, {status: entry.status, headers: entry.headers});
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
    /** Background start after the first paint; silently does nothing on incapable devices. */
    prepare() {if (dependencies.capable() && state.engine === "idle") void ensureEngine().catch(() => undefined);},
    async fetch(path: string, init: RequestInit = {}): Promise<Response> {
      const signal = init.signal;
      if (signal?.aborted) throw abortError();
      const method = (init.method || "GET").toUpperCase();
      if (typeof FormData !== "undefined" && init.body instanceof FormData) return noticeResponse("showcase_upload_disabled", 403);
      const reading = method === "GET" || method === "HEAD";
      if (reading && !live && !active) {
        const hit = await recorded(path);
        if (signal?.aborted) throw abortError();
        if (hit) return hit;
      }
      // After the first change, later reads must observe it: route them all live.
      if (!reading) live = true;
      // Queued at call time, so the engine sees requests in the order the client issued them.
      const response = await serialized(async (): Promise<ShowcaseResponse | ShowcaseNoticeCode> => {
        let running: ShowcaseEngine;
        try {running = await ensureEngine();}
        catch (error) {return (error as Error).message === "showcase_unavailable" ? "showcase_unavailable" : "showcase_engine_unavailable";}
        const request: ShowcaseRequest = {method, url: path, headers: headerList(init.headers), body: reading ? null : await bodyBytes(init.body)};
        return running.handle(request);
      }).catch(() => "showcase_engine_unavailable" as const);
      if (typeof response === "string") return noticeResponse(response, 503);
      if (signal?.aborted) throw abortError();
      return new Response(nullBody(response.status) ? null : response.body, {status: response.status, headers: response.headers});
    },
  };
}
export type ShowcaseTransport = ReturnType<typeof createShowcaseTransport>;
