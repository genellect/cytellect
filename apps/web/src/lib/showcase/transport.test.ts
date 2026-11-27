import {afterEach, describe, expect, it, vi} from "vitest";
import {fetchVerified, IntegrityError, sha256Hex} from "./digest";
import type {ShowcaseRequest, ShowcaseResponse, SnapshotIndex} from "./protocol";
import {calculationBody, createShowcaseTransport, figureSettings, journalBodyMatches, journalPathMatches, snapshotKey, type ShowcaseEngine, type ShowcaseTransport} from "./transport";
import {bootPyodideRuntime} from "./worker-runtime";

const encoder = new TextEncoder();
const json = (value: unknown) => encoder.encode(JSON.stringify(value)).buffer as ArrayBuffer;
function staticFiles(entries: Record<string, unknown> | null) {
  const index: SnapshotIndex = {version: 1, entries: {}};
  const files: Record<string, ArrayBuffer> = {};
  for (const [path, body] of Object.entries(entries ?? {})) {
    const file = `r${Object.keys(files).length}.json`;
    index.entries[snapshotKey(path)] = {status: 200, headers: [["content-type", "application/json"], ["x-recorded", "1"]], file};
    files[file] = json(body);
  }
  return vi.fn(async (url: string) => {
    if (url === "/showcase/snapshot/index.json") return entries ? new Response(JSON.stringify(index)) : new Response("missing", {status: 404});
    const name = url.replace("/showcase/snapshot/", "");
    return files[name] ? new Response(files[name]) : new Response("missing", {status: 404});
  });
}
function fakeEngine(reply: (request: ShowcaseRequest) => unknown = request => ({live: request.url})) {
  const handled: ShowcaseRequest[] = [];
  let concurrent = 0, peak = 0;
  const engine: ShowcaseEngine & {handled: ShowcaseRequest[]; peak: () => number} = {
    handled, peak: () => peak,
    start: vi.fn(async () => undefined),
    async handle(request): Promise<ShowcaseResponse> {
      concurrent += 1; peak = Math.max(peak, concurrent);
      await new Promise(resolve => setTimeout(resolve, 5));
      handled.push(request); concurrent -= 1;
      const value = reply(request);
      return typeof value === "object" && value && "status" in (value as object) ? value as ShowcaseResponse
        : {status: 200, headers: [["content-type", "application/json"]], body: json(value)};
    },
  };
  return engine;
}
const transport = (options: {entries?: Record<string, unknown> | null; engine?: ShowcaseEngine | null; capable?: boolean; record?: () => void}) => createShowcaseTransport({
  fetchStatic: staticFiles(options.entries === undefined ? {} : options.entries),
  createEngine: () => options.engine === undefined ? fakeEngine() : options.engine,
  capable: () => options.capable ?? true,
  snapshotBase: "/showcase/snapshot/",
  ...(options.record ? {record: options.record} : {}),
});

describe("showcase transport", () => {
  it("serves recorded GETs without starting the live engine", async () => {
    const engine = fakeEngine();
    const subject = transport({entries: {"/v1/session": {authenticated: true}}, engine});
    const response = await subject.fetch("/v1/session");
    expect(response.status).toBe(200);
    expect(response.headers.get("x-recorded")).toBe("1");
    expect(await response.json()).toEqual({authenticated: true});
    expect(engine.start).not.toHaveBeenCalled();
    expect(subject.state().engine).toBe("idle");
  });

  it("requests the files a workspace opens on once its settings are read, together and once each", async () => {
    const entries = {
      "/v1/session": {authenticated: true}, "/v1/workspaces/w/analysis-spec": {version: 0, spec: null},
      "/v1/workspaces/w/region-fields": [{id: "f1"}, {id: "f2"}],
      "/v1/region-fields/f1/preview?channel_id=c&gain=1": {preview: 1}, "/v1/region-fields/f2/preview?channel_id=c&gain=1": {preview: 2},
      "/v1/revisions/r1/region-masks?field_id=f1": {masks: 1}, "/v1/revisions/r1/region-measurements": {rows: 1},
    };
    const fetchStatic = staticFiles(entries);
    const subject = createShowcaseTransport({fetchStatic, createEngine: () => fakeEngine(), capable: () => true, snapshotBase: "/showcase/snapshot/"});
    const files = (paths: string[]) => paths.map(path => `/showcase/snapshot/r${Object.keys(entries).indexOf(path)}.json`);
    await subject.fetch("/v1/session");
    expect(fetchStatic.mock.calls.map(([url]) => url)).not.toContain(files(["/v1/region-fields/f1/preview?channel_id=c&gain=1"])[0]);
    await subject.fetch("/v1/workspaces/w/analysis-spec");
    await vi.waitFor(() => expect(fetchStatic.mock.calls.map(([url]) => url)).toEqual(expect.arrayContaining(files([
      "/v1/workspaces/w/region-fields", "/v1/region-fields/f1/preview?channel_id=c&gain=1", "/v1/revisions/r1/region-masks?field_id=f1", "/v1/revisions/r1/region-measurements"]))));
    expect(fetchStatic.mock.calls.map(([url]) => url)).not.toContain(files(["/v1/region-fields/f2/preview?channel_id=c&gain=1"])[0]);
    const calls = fetchStatic.mock.calls.length;
    expect(await (await subject.fetch("/v1/region-fields/f1/preview?channel_id=c&gain=1")).json()).toEqual({preview: 1});
    expect(await (await subject.fetch("/v1/region-fields/f1/preview?channel_id=c&gain=1")).json()).toEqual({preview: 1});
    expect(fetchStatic.mock.calls.length).toBe(calls);
  });

  it("opens a two-group workspace on both fields of its first run, downloaded together", async () => {
    const experiment = {version: "1.0.0", layout: "pair", control_group_id: "c", independence_confirmed: false,
      groups: [{id: "t", label: "KO"}, {id: "c", label: "NT"}], runs: [{id: "r", label: "Run1"}],
      fields: {f1: {group_id: "c", run_id: "r"}, f3: {group_id: "t", run_id: "r"}, f2: {group_id: "c", run_id: "r"}}};
    const entries = {
      "/v1/workspaces/w/analysis-spec": {version: 1, spec: {experiment}}, "/v1/workspaces/w/region-fields": [{id: "f1"}, {id: "f2"}, {id: "f3"}],
      "/v1/region-fields/f1/preview?channel_id=c&gain=1": {preview: 1}, "/v1/region-fields/f2/preview?channel_id=c&gain=1": {preview: 2},
      "/v1/region-fields/f3/preview?channel_id=c&gain=1": {preview: 3},
    };
    const files = staticFiles(entries), name = (path: string) => `/showcase/snapshot/r${Object.keys(entries).indexOf(path)}.json`;
    // Image files arrive only when released, so the test sees which downloads run at the same time.
    const waiting = new Map<string, () => void>();
    const fetchStatic = vi.fn(async (url: string) => {
      if (/preview/.test(Object.keys(entries)[Number(/r(\d+)\.json$/.exec(url)?.[1] ?? -1)] ?? "")) await new Promise<void>(resolve => waiting.set(url, resolve));
      return files(url);
    });
    const subject = createShowcaseTransport({fetchStatic, createEngine: () => fakeEngine(), capable: () => true, snapshotBase: "/showcase/snapshot/"});
    await subject.fetch("/v1/workspaces/w/analysis-spec");
    await vi.waitFor(() => expect([...waiting.keys()].sort()).toEqual([name("/v1/region-fields/f1/preview?channel_id=c&gain=1"), name("/v1/region-fields/f3/preview?channel_id=c&gain=1")].sort()));
    const first = subject.fetch("/v1/region-fields/f1/preview?channel_id=c&gain=1"), second = subject.fetch("/v1/region-fields/f3/preview?channel_id=c&gain=1");
    // The second answer does not wait for the first image: releasing it alone answers it.
    waiting.get(name("/v1/region-fields/f3/preview?channel_id=c&gain=1"))!();
    expect(await (await second).json()).toEqual({preview: 3});
    waiting.get(name("/v1/region-fields/f1/preview?channel_id=c&gain=1"))!();
    expect(await (await first).json()).toEqual({preview: 1});
    expect(waiting.has(name("/v1/region-fields/f2/preview?channel_id=c&gain=1"))).toBe(false);
  });

  it("answers anything unrecorded at once with a notice, never with the in-browser API", async () => {
    const engine = fakeEngine();
    const subject = transport({entries: {"/v1/session": {authenticated: true}}, engine});
    const read = await subject.fetch("/v1/workspaces/w/jobs?x=1");
    expect(read.status).toBe(409);
    expect(await read.json()).toEqual({detail: "showcase_action_not_recorded"});
    expect(await (await subject.fetch("/v1/workspaces", {method: "POST", body: "{}"})).json()).toEqual({detail: "showcase_action_not_recorded"});
    expect(engine.start).not.toHaveBeenCalled();
    expect(subject.state().engine).toBe("idle");
  });

  it("routes the recorder's requests live after the first change, in order and one at a time", async () => {
    const engine = fakeEngine();
    const subject = transport({entries: {"/v1/workspaces/w/selection": {version: 1}}, engine, record: vi.fn()});
    expect(await (await subject.fetch("/v1/workspaces/w/selection")).json()).toEqual({version: 1});
    const changed = subject.fetch("/v1/workspaces/w/selection", {method: "POST", body: JSON.stringify({version: 1}), headers: {"X-Cytellect-Request": "1"}});
    const reread = subject.fetch("/v1/workspaces/w/selection");
    await Promise.all([changed, reread]);
    expect(engine.handled.map(request => `${request.method} ${request.url}`)).toEqual(["POST /v1/workspaces/w/selection", "GET /v1/workspaces/w/selection"]);
    expect(new TextDecoder().decode(engine.handled[0].body!)).toBe('{"version":1}');
    expect(engine.handled[0].headers).toContainEqual(["x-cytellect-request", "1"]);
    expect(engine.handled[1].body).toBeNull();
    expect(engine.peak()).toBe(1);
  });

  it("never starts the API in the background: recorded results answer", async () => {
    const engine = fakeEngine();
    const subject = transport({entries: {"/v1/session": {authenticated: true}}, engine});
    subject.prepare();
    await new Promise(resolve => setTimeout(resolve, 20));
    expect(engine.start).not.toHaveBeenCalled();
    expect(await (await subject.fetch("/v1/session")).json()).toEqual({authenticated: true});
  });

  it("reports an unpublished demo and a failed boot without throwing", async () => {
    const unpublished = transport({entries: null, engine: null});
    expect(await (await unpublished.fetch("/v1/session")).json()).toEqual({detail: "showcase_unavailable"});
    const broken = fakeEngine();
    broken.start = vi.fn(async () => {throw new Error("showcase_integrity_failed");});
    const failed = transport({entries: {}, engine: broken, record: vi.fn()});
    expect(await (await failed.fetch("/v1/workspaces", {method: "POST"})).json()).toEqual({detail: "showcase_engine_unavailable"});
    expect(failed.state()).toEqual({engine: "unavailable", reason: "failed"});
  });

  it("never uploads files in the demo", async () => {
    const engine = fakeEngine();
    const response = await transport({engine}).fetch("/v1/workspaces/w/region-fields", {method: "POST", body: new FormData()});
    expect(response.status).toBe(403);
    expect(await response.json()).toEqual({detail: "showcase_upload_disabled"});
    expect(engine.start).not.toHaveBeenCalled();
  });

  it("returns the engine's API errors unchanged for the client to interpret", async () => {
    const engine = fakeEngine(() => ({status: 409, headers: [["content-type", "application/json"]], body: json({detail: "showcase_detection_not_recorded"})}));
    const response = await transport({engine, record: vi.fn()}).fetch("/v1/workspaces/w/runs", {method: "POST", body: "{}"});
    expect(response.status).toBe(409);
    expect(await response.json()).toEqual({detail: "showcase_detection_not_recorded"});
  });
});

describe("recorded tour", () => {
  const entry = (method: string, path: string, body: string | null, file: string | null, status = 200) =>
    ({method, path, body, status, headers: [["content-type", "application/json"]] as Array<[string, string]>, file});
  function tour(capable: boolean, engine = fakeEngine(), split = false) {
    const files: Record<string, unknown> = {
      "index.json": {version: 1, entries: {[snapshotKey("/v1/workspaces/w/jobs/j")]: {status: 200, headers: [], file: "s0.json"}}},
      "s0.json": {state: "snapshot"},
      "journal.json": {version: 1, entries: [
        entry("POST", "/v1/workspaces/w/statistics", JSON.stringify({request_id: "*", metric: "area"}), "a.json", 202),
        entry("GET", "/v1/workspaces/w/jobs/j", null, "b.json"),
        entry("GET", "/v1/workspaces/w/jobs/j", null, "c.json"),
        entry("PUT", "/v1/workspaces/w/selection", null, "d.json"),
        entry("GET", "/v1/workspaces/w/jobs/j", null, "e.json"),
      ]},
      "a.json": {job: "j"}, "b.json": {state: "running"}, "c.json": {state: "done"}, "d.json": {version: 2}, "e.json": {state: "after"},
    };
    if (split) {
      // The same tour in parts, as a tour of several scenes is published (one part per scene, docs/showcase.md).
      const entries = (files["journal.json"] as {entries: unknown[]}).entries;
      files["journal-first.json"] = {version: 1, entries: entries.slice(0, 2)};
      files["journal-second.json"] = {version: 1, entries: entries.slice(2)};
      files["journal.json"] = {version: 2, parts: ["journal-first.json", "journal-second.json"]};
    }
    const fetchStatic = vi.fn(async (url: string) => {
      const name = url.replace("/showcase/snapshot/", "");
      return name in files ? new Response(JSON.stringify(files[name])) : new Response("missing", {status: 404});
    });
    return {engine, subject: createShowcaseTransport({fetchStatic, createEngine: () => engine, capable: () => capable, snapshotBase: "/showcase/snapshot/"})};
  }
  const post = (subject: ReturnType<typeof tour>["subject"], metric: string) =>
    subject.fetch("/v1/workspaces/w/statistics", {method: "POST", body: JSON.stringify({metric, request_id: crypto.randomUUID()})});

  it("answers a recorded change and the reads after it on a device without the engine", async () => {
    const {subject, engine} = tour(false);
    expect(await (await subject.fetch("/v1/workspaces/w/jobs/j")).json()).toEqual({state: "snapshot"});
    const started = await post(subject, "area");
    expect(started.status).toBe(202);
    expect(await started.json()).toEqual({job: "j"});
    // Reads after the change return its settled state (the job as it finished), the same each time.
    expect(await (await subject.fetch("/v1/workspaces/w/jobs/j")).json()).toEqual({state: "done"});
    expect(await (await subject.fetch("/v1/workspaces/w/jobs/j")).json()).toEqual({state: "done"});
    expect(await (await subject.fetch("/v1/workspaces/w/selection", {method: "PUT", body: "{}"})).json()).toEqual({version: 2});
    expect(await (await subject.fetch("/v1/workspaces/w/jobs/j")).json()).toEqual({state: "after"});
    expect(engine.start).not.toHaveBeenCalled();
  });

  it("answers from a tour published in parts exactly as from one file", async () => {
    const {subject, engine} = tour(false, fakeEngine(), true);
    expect(await (await post(subject, "area")).json()).toEqual({job: "j"});
    expect(await (await subject.fetch("/v1/workspaces/w/jobs/j")).json()).toEqual({state: "done"});
    expect(await (await subject.fetch("/v1/workspaces/w/selection", {method: "PUT", body: "{}"})).json()).toEqual({version: 2});
    expect(await (await subject.fetch("/v1/workspaces/w/jobs/j")).json()).toEqual({state: "after"});
    expect(await (await post(subject, "intensity")).json()).toEqual({detail: "showcase_action_not_recorded"});
    expect(engine.start).not.toHaveBeenCalled();
  });

  it("orders a read issued during a recorded change after that change", async () => {
    const {subject} = tour(false);
    const [, read] = await Promise.all([post(subject, "area"), subject.fetch("/v1/workspaces/w/jobs/j")]);
    expect(await read.json()).toEqual({state: "done"});
  });

  it("explains a change the tour does not hold, without starting the engine", async () => {
    const {subject, engine} = tour(false);
    await post(subject, "area");
    const other = await post(subject, "intensity");
    expect(other.status).toBe(409);
    expect(await other.json()).toEqual({detail: "showcase_action_not_recorded"});
    expect(engine.start).not.toHaveBeenCalled();
  });

  it("answers the same way on devices that could run the API", async () => {
    const {subject, engine} = tour(true);
    expect((await post(subject, "area")).status).toBe(202);
    expect(await (await post(subject, "intensity")).json()).toEqual({detail: "showcase_action_not_recorded"});
    expect(engine.start).not.toHaveBeenCalled();
  });

  it("finds a recorded change taken out of the recorded order", async () => {
    const {subject} = tour(false);
    expect(await (await subject.fetch("/v1/workspaces/w/selection", {method: "PUT", body: "{}"})).json()).toEqual({version: 2});
    expect((await post(subject, "area")).status).toBe(202);
    expect(await (await subject.fetch("/v1/workspaces/w/jobs/j")).json()).toEqual({state: "done"});
  });

  it("keeps the saved analysis settings on the device", async () => {
    const {subject} = tour(false);
    const saved = await subject.fetch("/v1/workspaces/w/analysis-spec", {method: "PUT", body: JSON.stringify({version: 3, spec: {target: "nucleoli"}})});
    expect(await saved.json()).toEqual({version: 4, spec: {target: "nucleoli"}});
    expect(await (await subject.fetch("/v1/workspaces/w/analysis-spec")).json()).toEqual({version: 4, spec: {target: "nucleoli"}});
  });

  it("matches recorded paths with identifiers the API generated while recording", () => {
    expect(journalPathMatches("/v1/jobs/*/figure-render", "/v1/jobs/abc/figure-render")).toBe(true);
    expect(journalPathMatches("/v1/jobs/*/figure-render", "/v1/jobs/abc/export")).toBe(false);
    expect(journalPathMatches("/v1/x?a=1", "/v1/x?a=2")).toBe(false);
  });

  it("answers a recorded run only under the settings it was measured with", async () => {
    const files: Record<string, unknown> = {
      "index.json": {version: 1, entries: {[snapshotKey("/v1/workspaces/w/analysis-spec")]: {status: 200, headers: [], file: "seed.json"}}},
      "seed.json": {version: 3, spec: {target: "nuclei", settings: {background: "raw"}}},
      "journal.json": {version: 1, entries: [
        {...entry("POST", "/v1/workspaces/w/runs", JSON.stringify({request_id: "*", target: "nuclei"}), "raw.json", 202), scene: "a"},
        {...entry("PUT", "/v1/workspaces/w/analysis-spec", JSON.stringify({version: "*", spec: {target: "nuclei", settings: {background: "automatic"}}}), null), scene: "b"},
        {...entry("POST", "/v1/workspaces/w/runs", JSON.stringify({request_id: "*", target: "nuclei"}), "automatic.json", 202), scene: "b"},
      ]},
      "raw.json": {run: "raw"}, "automatic.json": {run: "automatic"},
    };
    const fetchStatic = vi.fn(async (url: string) => {
      const name = url.replace("/showcase/snapshot/", "");
      return name in files ? new Response(JSON.stringify(files[name])) : new Response("missing", {status: 404});
    });
    const run = (subject: ReturnType<typeof createShowcaseTransport>) => subject.fetch("/v1/workspaces/w/runs", {method: "POST", body: JSON.stringify({request_id: "x", target: "nuclei"})});
    const fresh = () => createShowcaseTransport({fetchStatic, createEngine: () => null, capable: () => false, snapshotBase: "/showcase/snapshot/"});
    expect(await (await run(fresh())).json()).toEqual({run: "raw"});
    const automatic = fresh();
    await automatic.fetch("/v1/workspaces/w/analysis-spec", {method: "PUT", body: JSON.stringify({version: 3, spec: {target: "nuclei", settings: {background: "automatic"}}})});
    expect(await (await run(automatic)).json()).toEqual({run: "automatic"});
    const other = fresh();
    await other.fetch("/v1/workspaces/w/analysis-spec", {method: "PUT", body: JSON.stringify({version: 3, spec: {target: "nuclei", settings: {background: "confirmed_roi"}}})});
    expect((await run(other)).status).not.toBe(202);
  });

  it("keeps what a device already has when a change from another scene left it as it was", async () => {
    const files: Record<string, unknown> = {
      "index.json": {version: 1, entries: {[snapshotKey("/v1/workspaces/w/selection")]: {status: 200, headers: [], file: "seed.json"}}},
      "seed.json": {revision: "seed"},
      "journal.json": {version: 1, entries: [
        {...entry("POST", "/v1/workspaces/w/runs", null, "run.json", 202), scene: "measure"},
        {...entry("GET", "/v1/workspaces/w/selection", null, "measured.json"), scene: "measure"},
        {...entry("POST", "/v1/workspaces/w/proposal-drafts", null, "draft.json"), scene: "ai"},
        {...entry("GET", "/v1/workspaces/w/selection", null, "seed.json"), scene: "ai"},
        {...entry("PUT", "/v1/workspaces/w/selection", null, "saved.json"), scene: "ai"},
        {...entry("GET", "/v1/workspaces/w/selection", null, "saved.json"), scene: "ai"},
      ]},
      "run.json": {run: 1}, "measured.json": {revision: "measured"}, "draft.json": {draft: 1}, "saved.json": {revision: "saved"},
    };
    const fetchStatic = vi.fn(async (url: string) => {
      const name = url.replace("/showcase/snapshot/", "");
      return name in files ? new Response(JSON.stringify(files[name])) : new Response("missing", {status: 404});
    });
    const subject = createShowcaseTransport({fetchStatic, createEngine: () => null, capable: () => false, snapshotBase: "/showcase/snapshot/"});
    const selection = async () => (await subject.fetch("/v1/workspaces/w/selection")).json();
    expect(await selection()).toEqual({revision: "seed"});
    await subject.fetch("/v1/workspaces/w/runs", {method: "POST"});
    expect(await selection()).toEqual({revision: "measured"});
    // The AI scene was recorded from the seed and did not change the selection: the measured one stays.
    await subject.fetch("/v1/workspaces/w/proposal-drafts", {method: "POST"});
    expect(await selection()).toEqual({revision: "measured"});
    // A recorded change that does change it is shown.
    await subject.fetch("/v1/workspaces/w/selection", {method: "PUT"});
    expect(await selection()).toEqual({revision: "saved"});
  });

  it("reads back what a change wrote, from the scene's next read when none follows at once", async () => {
    const files: Record<string, unknown> = {
      "index.json": {version: 1, entries: {[snapshotKey("/v1/workspaces/w/selection")]: {status: 200, headers: [], file: "seed.json"}}},
      "seed.json": {revision: "seed"},
      "journal.json": {version: 1, entries: [
        {...entry("POST", "/v1/workspaces/w/selection", null, "written.json"), scene: "s"},
        {...entry("POST", "/v1/workspaces/w/cohorts", null, "cohort.json"), scene: "s"},
        {...entry("GET", "/v1/workspaces/w/selection", null, "written.json"), scene: "s"},
      ]},
      "written.json": {revision: "written"}, "cohort.json": {cohort: 1},
    };
    const fetchStatic = vi.fn(async (url: string) => {
      const name = url.replace("/showcase/snapshot/", "");
      return name in files ? new Response(JSON.stringify(files[name])) : new Response("missing", {status: 404});
    });
    const subject = createShowcaseTransport({fetchStatic, createEngine: () => null, capable: () => false, snapshotBase: "/showcase/snapshot/"});
    expect(await (await subject.fetch("/v1/workspaces/w/selection")).json()).toEqual({revision: "seed"});
    expect(await (await subject.fetch("/v1/workspaces/w/selection", {method: "POST"})).json()).toEqual({revision: "written"});
    expect(await (await subject.fetch("/v1/workspaces/w/selection")).json()).toEqual({revision: "written"});
  });

  it("matches recorded bodies exactly except for client-generated values", () => {
    expect(journalBodyMatches('{"a":"*","b":[1,{"c":2}]}', '{"b":[1,{"c":2}],"a":"x"}')).toBe(true);
    expect(journalBodyMatches('{"a":"*"}', '{"a":1}')).toBe(true);
    expect(journalBodyMatches('{"a":"*"}', '{}')).toBe(false);
    expect(journalBodyMatches('{"a":1}', '{"a":1,"b":2}')).toBe(false);
    expect(journalBodyMatches(null, "anything")).toBe(true);
  });

  it("hands every exchange with the engine to the build-time recorder", async () => {
    const record = vi.fn();
    const engine = fakeEngine();
    const subject = createShowcaseTransport({fetchStatic: staticFiles({}), createEngine: () => engine, capable: () => true, snapshotBase: "/showcase/snapshot/", record});
    await subject.fetch("/v1/workspaces/w/selection", {method: "PUT", body: '{"v":1}'});
    expect(record).toHaveBeenCalledWith(expect.objectContaining({method: "PUT", path: "/v1/workspaces/w/selection", body: '{"v":1}', status: 200}));
  });
});

describe("showcase notices through the API client", () => {
  afterEach(() => {vi.unstubAllEnvs(); vi.unstubAllGlobals(); vi.resetModules();});
  it("maps demo limitations to information messages, not errors", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_ORIGIN", "");
    vi.resetModules();
    vi.stubGlobal("fetch", vi.fn(async () => new Response("missing", {status: 404})));
    const api = await import("../api");
    const showcase = await import(".");
    await expect(api.request("/v1/session")).rejects.toEqual(new api.ApiError("server_not_configured", 503));
    showcase.activateShowcase();
    const error = await api.request("/v1/workspaces", {method: "POST", body: "{}"}).then(() => null, (value: unknown) => value);
    expect(error).toEqual(new api.ApiError("showcase_unavailable", 503));
    expect(showcase.isShowcaseNotice(api.errorMessage(error))).toBe(true);
    expect(showcase.isShowcaseNotice(api.errorMessage(new api.ApiError("invalid_analysis_input", 422)))).toBe(false);
    for (const code of ["showcase_detection_not_recorded", "showcase_proposal_not_recorded", "showcase_upload_disabled", "showcase_action_not_recorded"])
      expect(showcase.isShowcaseNotice(`視野 1：${api.errorCodeMessage(code)} 実行条件してください。`)).toBe(true);
    await expect(api.fetchPrivateResponse("/v1/region-fields/f/preview")).rejects.toEqual(new api.ApiError("showcase_unavailable", 503));
  });
});

describe("runtime file verification", () => {
  const bytes = encoder.encode("synthetic wheel");
  it("accepts only files whose SHA-256 matches the recorded digest", async () => {
    const digest = await sha256Hex(bytes);
    const fetcher = vi.fn(async () => new Response(bytes)) as unknown as typeof fetch;
    expect(await fetchVerified("/showcase/runtime/a.whl", digest, fetcher)).toEqual(bytes);
    await expect(fetchVerified("/showcase/runtime/a.whl", "0".repeat(64), fetcher)).rejects.toBeInstanceOf(IntegrityError);
    await expect(fetchVerified("/showcase/runtime/a.whl", "not-a-digest", fetcher)).rejects.toBeInstanceOf(IntegrityError);
  });
  it("never starts the interpreter when a self-hosted file was altered", async () => {
    const loadPyodide = vi.fn();
    const fetcher = vi.fn(async (url: string) => new Response(url.endsWith("seed.zip") ? encoder.encode("seed") : encoder.encode("altered"))) as unknown as typeof fetch;
    const config = {pyodideVersion: "0", indexURL: "https://cdn.example/pyodide/", packages: [], fonts: [],
      wheels: [{file: "cytellect_showcase-0-py3-none-any.whl", sha256: await sha256Hex(bytes)}]};
    await expect(bootPyodideRuntime(config, "https://example.org", {fetcher, loadPyodide, base: "https://example.org/showcase/"})).rejects.toBeInstanceOf(IntegrityError);
    expect(loadPyodide).not.toHaveBeenCalled();
    expect(vi.mocked(fetcher).mock.calls.map(call => call[0])).toContain(`https://example.org/showcase/runtime/cytellect_showcase-0-py3-none-any.whl?sha256=${await sha256Hex(bytes)}`);
  });
  it("does not download anything for an unpublished runtime", async () => {
    const fetcher = vi.fn() as unknown as typeof fetch;
    await expect(bootPyodideRuntime({pyodideVersion: "", indexURL: "", packages: [], wheels: [], fonts: []}, "https://example.org", {fetcher, loadPyodide: vi.fn(), base: "/"})).rejects.toThrow("showcase_runtime_missing");
    expect(fetcher).not.toHaveBeenCalled();
  });
});

describe("recorded tour across scenes", () => {
  const entry = (method: string, path: string, body: string | null, file: string | null, scene: string, pattern?: string) =>
    ({method, path, body, status: 200, headers: [["content-type", "application/json"]] as Array<[string, string]>, file, scene, ...(pattern ? {pattern} : {})});
  function subject(files: Record<string, unknown>) {
    const fetchStatic = vi.fn(async (url: string) => {
      const name = url.replace("/showcase/snapshot/", "");
      return name in files ? new Response(JSON.stringify(files[name])) : new Response("missing", {status: 404});
    });
    return createShowcaseTransport({fetchStatic, createEngine: () => null, capable: () => false, snapshotBase: "/showcase/snapshot/"});
  }
  it("finds a request recorded in another scene and answers it with this visitor's identifiers", async () => {
    const A = "aaaaaaaa-0000-4000-8000-000000000001", B = "bbbbbbbb-0000-4000-8000-000000000002", JOB = "cccccccc-0000-4000-8000-000000000003";
    const transport = subject({
      "index.json": {version: 1, entries: {}},
      "journal.json": {version: 1, entries: [
        entry("POST", "/v1/workspaces/w/region-cohorts", JSON.stringify({metric: "x"}), "cohort-a.json", "area"),
        entry("POST", `/v1/revisions/${A}/descriptive`, JSON.stringify({metric: "area"}), "area.json", "area", "/v1/revisions/*/descriptive"),
        entry("POST", "/v1/workspaces/w/region-cohorts", JSON.stringify({metric: "x"}), "cohort-b.json", "mean"),
        entry("POST", `/v1/revisions/${B}/descriptive`, JSON.stringify({metric: "mean"}), "mean.json", "mean", `/v1/revisions/*/descriptive`),
        entry("GET", `/v1/jobs/${JOB}/result`, null, "result.json", "mean"),
        entry("POST", `/v1/revisions/${B}/export`, null, "export.json", "mean", "/v1/revisions/*/export"),
        entry("POST", `/v1/jobs/${B}/figure-render`, JSON.stringify({width: 89}), "render.json", "mean", "/v1/jobs/*/figure-render"),
      ]},
      "cohort-a.json": {revision_id: A}, "cohort-b.json": {revision_id: B}, "area.json": {job_id: "area"},
      "mean.json": {job_id: JOB}, "result.json": {revision_id: B, value: 1}, "export.json": {revision_id: B, job_id: "export"}, "render.json": {job: "other"},
    });
    expect(await (await transport.fetch("/v1/workspaces/w/region-cohorts", {method: "POST", body: JSON.stringify({metric: "x"})})).json()).toEqual({revision_id: A});
    // The exact path answers first; the other scene's request is found by its pattern.
    expect(await (await transport.fetch(`/v1/revisions/${A}/descriptive`, {method: "POST", body: JSON.stringify({metric: "area"})})).json()).toEqual({job_id: "area"});
    expect(await (await transport.fetch(`/v1/revisions/${A}/descriptive`, {method: "POST", body: JSON.stringify({metric: "mean"})})).json()).toEqual({job_id: JOB});
    // That scene's answers name this visitor's cohort, and its later requests are found through it.
    expect(await (await transport.fetch(`/v1/jobs/${JOB}/result`)).json()).toEqual({revision_id: A, value: 1});
    expect(await (await transport.fetch(`/v1/revisions/${A}/export`, {method: "POST"})).json()).toEqual({revision_id: A, job_id: "export"});
    // A figure or package names no content of its own: another job's recording never answers it.
    expect((await transport.fetch(`/v1/jobs/${JOB}/figure-render`, {method: "POST", body: JSON.stringify({width: 89})})).status).toBe(409);
  });
  it("answers a request by its pattern only from the open workspace's scene, whatever was answered before", async () => {
    // Two demo scenes recorded the same request on their own cohorts: same content, only the revision differs.
    const A = "aaaaaaaa-0000-4000-8000-000000000001", B = "bbbbbbbb-0000-4000-8000-000000000002";
    const V = "dddddddd-0000-4000-8000-000000000004";
    const body = JSON.stringify({metric: "mean"});
    const files = {
      "index.json": {version: 1, entries: {}},
      "journal.json": {version: 1, entries: [
        entry("POST", "/v1/workspaces/wa/region-cohorts", null, "cohort-a.json", "first:walk-1"),
        entry("POST", `/v1/revisions/${A}/descriptive`, body, "first.json", "first:walk-1"),
        entry("POST", "/v1/workspaces/wb/region-cohorts", null, "cohort-b.json", "second:walk-1"),
        entry("POST", `/v1/revisions/${B}/descriptive`, body, "second.json", "second:walk-1"),
      ]},
      "cohort-a.json": {revision_id: A}, "cohort-b.json": {revision_id: B}, "first.json": {scene: "first"}, "second.json": {scene: "second"},
    };
    const ask = async (transport: ReturnType<typeof subject>) =>
      (await (await transport.fetch(`/v1/revisions/${V}/descriptive`, {method: "POST", body})).json()) as {scene: string};
    // The second scene's workspace is open after the first scene's change was answered: its own record answers.
    const after = subject(files);
    await after.fetch("/v1/workspaces/wa/region-cohorts", {method: "POST"});
    await after.fetch("/v1/workspaces/wb/selection");
    expect(await ask(after)).toEqual({scene: "second"});
    // And the other way, with the first scene's workspace open after the second's change.
    const before = subject(files);
    await before.fetch("/v1/workspaces/wb/region-cohorts", {method: "POST"});
    await before.fetch("/v1/workspaces/wa/selection");
    expect(await ask(before)).toEqual({scene: "first"});
    // A request is answered for the workspace open when it was made, even when the visitor has switched before its
    // answer is decided (decisions follow request order).
    const switched = subject(files);
    await switched.fetch("/v1/workspaces/wa/selection");
    const asked = ask(switched);
    void switched.fetch("/v1/workspaces/wb/selection");
    expect(await asked).toEqual({scene: "first"});
    // Without a workspace named, the scene of the change last answered decides.
    for (const [cohort, scene] of [[B, "second"], [A, "first"]]) {
      const unnamed = subject(files);
      await unnamed.fetch(`/v1/revisions/${cohort}/descriptive`, {method: "POST", body});
      expect(await ask(unnamed)).toEqual({scene});
    }
  });
  describe("the open scene's parts first", () => {
    const A = "aaaaaaaa-0000-4000-8000-000000000001", B = "bbbbbbbb-0000-4000-8000-000000000002";
    const body = JSON.stringify({metric: "mean"});
    // The open scene ("second") comes after another scene's part in the tour, which records the same statistics request.
    const first = [
      entry("POST", "/v1/workspaces/wa/runs", JSON.stringify({target: "nuclei"}), "run-a.json", "first:walk"),
      entry("GET", "/v1/workspaces/wa/runs/r", null, "done-a.json", "first:walk"),
      entry("POST", `/v1/revisions/${A}/descriptive`, body, "first.json", "first:stats"),
    ];
    const second = [
      entry("POST", "/v1/workspaces/wb/runs", JSON.stringify({target: "nuclei"}), "run-b.json", "second:walk"),
      entry("GET", "/v1/workspaces/wb/runs/r", null, "done-b.json", "second:walk"),
      entry("POST", `/v1/revisions/${B}/descriptive`, body, "second.json", "second:stats"),
    ];
    const files: Record<string, unknown> = {
      "index.json": {version: 1, entries: {}},
      "journal.json": {version: 2, parts: ["journal-first.json", "journal-second.json"], counts: [3, 3], workspaces: [["wa"], ["wb"]], revisions: [[A], [B]]},
      "journal-first.json": {version: 1, entries: first}, "journal-second.json": {version: 1, entries: second},
      "run-a.json": {run: "a"}, "done-a.json": {state: "a"}, "first.json": {scene: "first"},
      "run-b.json": {run: "b"}, "done-b.json": {state: "b"}, "second.json": {scene: "second"},
    };
    /** A transport whose part `held` arrives only when released; `tag` marks its parts' bodies as this transport's. */
    function held(name: string | null, tag = "") {
      let release = () => {};
      const arrived = new Promise<void>(resolve => {release = resolve;});
      const fetchStatic = vi.fn(async (url: string) => {
        const file = url.replace("/showcase/snapshot/", "");
        if (file === name) await arrived;
        const body = tag && /^journal-.+\.json$/.test(file) ? {...files[file] as object, tag} : files[file];
        return file in files ? new Response(JSON.stringify(body)) : new Response("missing", {status: 404});
      });
      return {release, fetchStatic, transport: createShowcaseTransport({fetchStatic, createEngine: () => null, capable: () => false, snapshotBase: "/showcase/snapshot/"})};
    }
    const json = async (response: Promise<Response>) => (await response).json();
    // The visitor opens the second scene, measures, reads the run, then asks for a statistic by a cohort of its own.
    async function walk(transport: ShowcaseTransport, release = () => {}) {
      await transport.fetch("/v1/workspaces/wb/selection");
      const measured = await json(transport.fetch("/v1/workspaces/wb/runs", {method: "POST", body: JSON.stringify({target: "nuclei"})}));
      const read = await json(transport.fetch("/v1/workspaces/wb/runs/r"));
      const statistic = transport.fetch(`/v1/revisions/${"cccccccc-0000-4000-8000-000000000003"}/descriptive`, {method: "POST", body});
      release();
      return [measured, read, await json(statistic)];
    }

    it("answers the first change of the open scene before the other parts arrive", async () => {
      const {transport, fetchStatic, release} = held("journal-first.json");
      await transport.fetch("/v1/workspaces/wb/selection");
      expect(await json(transport.fetch("/v1/workspaces/wb/runs", {method: "POST", body: JSON.stringify({target: "nuclei"})}))).toEqual({run: "b"});
      expect(await json(transport.fetch("/v1/workspaces/wb/runs/r"))).toEqual({state: "b"});
      // The open scene's part was asked for first; the other one has not arrived.
      const asked = fetchStatic.mock.calls.map(([url]) => url.replace("/showcase/snapshot/", "")).filter(name => name.startsWith("journal-"));
      expect(asked[0]).toBe("journal-second.json");
      release();
    });

    it("explains at once a change of the open workspace that its scene did not record, while the other parts are on the way", async () => {
      const {transport, release, fetchStatic} = held("journal-first.json");
      await transport.fetch("/v1/workspaces/wb/selection");
      const response = await transport.fetch("/v1/workspaces/wb/runs", {method: "POST", body: JSON.stringify({target: "nucleoli"})});
      expect(await response.json()).toEqual({detail: "showcase_action_not_recorded"});
      // The open scene's part was asked for first, then every other part (the other part is still on the way).
      const asked = fetchStatic.mock.calls.map(([url]) => url.replace("/showcase/snapshot/", "")).filter(name => name.startsWith("journal-"));
      expect(asked).toEqual(["journal-second.json", "journal-first.json"]);
      release();
    });

    it("asks for the other parts once the open scene's part has downloaded, all of them together", async () => {
      // A third part, so that "all together" means more than one.
      files["journal.json"] = {version: 2, parts: ["journal-first.json", "journal-second.json", "journal-third.json"], counts: [3, 3, 1],
        workspaces: [["wa"], ["wb"], ["wc"]], revisions: [[A], [B], []]};
      files["journal-third.json"] = {version: 1, entries: [entry("GET", "/v1/workspaces/wc/jobs", null, "done-a.json", "third:walk")]};
      try {
        const {transport, release, fetchStatic} = held("journal-second.json");
        const parts = () => fetchStatic.mock.calls.map(([url]) => url.replace("/showcase/snapshot/", "")).filter(name => name.startsWith("journal-"));
        await transport.fetch("/v1/workspaces/wb/selection");
        const change = transport.fetch("/v1/workspaces/wb/runs", {method: "POST", body: JSON.stringify({target: "nuclei"})});
        await new Promise(resolve => setTimeout(resolve, 50));
        // While the open scene's part downloads, it has the connection to itself.
        expect(parts()).toEqual(["journal-second.json"]);
        release();
        expect(await (await change).json()).toEqual({run: "b"});
        await new Promise(resolve => setTimeout(resolve, 50));
        expect(parts()).toEqual(["journal-second.json", "journal-first.json", "journal-third.json"]);
      } finally {
        files["journal.json"] = {version: 2, parts: ["journal-first.json", "journal-second.json"], counts: [3, 3], workspaces: [["wa"], ["wb"]], revisions: [[A], [B]]};
        delete files["journal-third.json"];
      }
    });

    /** The scenes whose parts a transport `held(…, tag)` has read (parsed), in order. */
    function readParts(tag: string) {
      const parse = vi.spyOn(JSON, "parse");
      return {parse, read: () => parse.mock.calls.map(([text]) => String(text)).filter(text => text.includes(`"tag":"${tag}"`))
        .flatMap(text => /"scene":"(first|second|third):/.exec(text)?.[1] ?? [])};
    }

    it("reads the other parts only once no request has been waiting for a while, so an explained change is not held back", async () => {
      vi.useFakeTimers({toFake: ["setTimeout", "Date"]});
      const {parse, read} = readParts("quiet");
      try {
        const {transport, fetchStatic} = held(null, "quiet");
        await transport.fetch("/v1/workspaces/wb/selection");
        const change = await transport.fetch("/v1/workspaces/wb/runs", {method: "POST", body: JSON.stringify({target: "nucleoli"})});
        expect(await change.json()).toEqual({detail: "showcase_action_not_recorded"});
        await vi.advanceTimersByTimeAsync(1000);
        // The other part has downloaded, but reading it would hold the page while the notice is shown.
        expect(fetchStatic.mock.calls.map(([url]) => url)).toContain("/showcase/snapshot/journal-first.json");
        expect(read()).toEqual(["second"]);
        // A request delays the reading again.
        await transport.fetch("/v1/workspaces/wb/selection");
        await vi.advanceTimersByTimeAsync(1500);
        expect(read()).toEqual(["second"]);
        await vi.advanceTimersByTimeAsync(600);
        expect(read()).toEqual(["second", "first"]);
      } finally {parse.mockRestore(); vi.useRealTimers();}
    });

    it("reads the other parts one at a time, each after a quiet moment of its own", async () => {
      vi.useFakeTimers({toFake: ["setTimeout", "Date"]});
      const {parse, read} = readParts("apart");
      files["journal.json"] = {version: 2, parts: ["journal-first.json", "journal-second.json", "journal-third.json"], counts: [3, 3, 1],
        workspaces: [["wa"], ["wb"], ["wc"]], revisions: [[A], [B], []]};
      files["journal-third.json"] = {version: 1, entries: [entry("GET", "/v1/workspaces/wc/jobs", null, "done-a.json", "third:walk")]};
      try {
        const {transport} = held(null, "apart");
        await transport.fetch("/v1/workspaces/wb/selection");
        await transport.fetch("/v1/workspaces/wb/runs", {method: "POST", body: JSON.stringify({target: "nucleoli"})});
        for (let step = 0; step < 20 && !read().includes("first"); step++) await vi.advanceTimersToNextTimerAsync();
        expect(read()).toEqual(["second", "first"]);
        // Reading a part held the page: the next one waits for another quiet moment.
        await vi.advanceTimersByTimeAsync(1500);
        expect(read()).toEqual(["second", "first"]);
        // A request in that moment puts it off again.
        await transport.fetch("/v1/workspaces/wb/selection");
        await vi.advanceTimersByTimeAsync(1500);
        expect(read()).toEqual(["second", "first"]);
        await vi.advanceTimersByTimeAsync(600);
        expect(read()).toEqual(["second", "first", "third"]);
      } finally {
        parse.mockRestore(); vi.useRealTimers();
        files["journal.json"] = {version: 2, parts: ["journal-first.json", "journal-second.json"], counts: [3, 3], workspaces: [["wa"], ["wb"]], revisions: [[A], [B]]};
        delete files["journal-third.json"];
      }
    });

    it("reads the other parts at once when an answer needs them", async () => {
      vi.useFakeTimers({toFake: ["setTimeout", "Date"]});
      const {parse, read} = readParts("needed");
      try {
        const {transport} = held(null, "needed");
        await transport.fetch("/v1/workspaces/wb/selection");
        // A statistic by a cohort of the visitor's own is found by its pattern, which the whole tour decides.
        const statistic = transport.fetch(`/v1/revisions/${"cccccccc-0000-4000-8000-000000000003"}/descriptive`, {method: "POST", body});
        // Only the recorded moment of work passes, well before the page would count as quiet.
        await vi.advanceTimersByTimeAsync(500);
        expect(await (await statistic).json()).toEqual({scene: "second"});
        expect(read()).toEqual(["second", "first"]);
      } finally {parse.mockRestore(); vi.useRealTimers();}
    });

    it("explains at once an edit of one of the open scene's analysis versions that its scene did not record", async () => {
      const {transport, release} = held("journal-first.json");
      await transport.fetch("/v1/workspaces/wb/selection");
      // The edit names an analysis version of the open scene (the index lists it there), not the workspace.
      const response = await transport.fetch(`/v1/revisions/${B}/region-edits`, {method: "POST", body: JSON.stringify({operation: "delete"})});
      expect(await response.json()).toEqual({detail: "showcase_action_not_recorded"});
      // An opening version no part names (the tour never edited it) is the open scene's too.
      const opening = await transport.fetch("/v1/revisions/eeeeeeee-0000-4000-8000-000000000005/region-edits", {method: "POST", body: JSON.stringify({operation: "delete"})});
      expect(await opening.json()).toEqual({detail: "showcase_action_not_recorded"});
      // A version another scene's part names waits for the whole tour.
      let answered = false;
      const other = transport.fetch(`/v1/revisions/${A}/region-edits`, {method: "POST", body: JSON.stringify({operation: "delete"})}).then(value => {answered = true; return value;});
      await new Promise(resolve => setTimeout(resolve, 50));
      expect(answered).toBe(false);
      release();
      expect(await (await other).json()).toEqual({detail: "showcase_action_not_recorded"});
    });

    it("does not use a tour whose parts disagree with the counts of its index", async () => {
      const saved = files["journal.json"];
      files["journal.json"] = {version: 2, parts: ["journal-first.json", "journal-second.json"], counts: [2, 3], workspaces: [["wa"], ["wb"]]};
      try {
        const {transport} = held(null);
        await transport.fetch("/v1/workspaces/wb/selection");
        // The open scene's part sits at another position than the index says: nothing is answered from the tour.
        const statistic = await transport.fetch(`/v1/revisions/${B}/descriptive`, {method: "POST", body});
        expect(await statistic.json()).toEqual({detail: "showcase_action_not_recorded"});
      } finally {files["journal.json"] = saved;}
    });

    it("answers the same whether the other parts arrive late or at once", async () => {
      const late = held("journal-first.json"), atOnce = held(null);
      const answers = await walk(late.transport, late.release);
      expect(answers).toEqual(await walk(atOnce.transport));
      // A statistic by a pattern waits for the whole tour, and is answered by the open scene's walk.
      expect(answers).toEqual([{run: "b"}, {state: "b"}, {scene: "second"}]);
    });
  });
  it("keeps listing a job another scene gave this visitor, so a reused cohort is still found", async () => {
    const transport = subject({
      "index.json": {version: 1, entries: {[snapshotKey("/v1/workspaces/w/jobs")]: {status: 200, headers: [], file: "seed.json"}}},
      "journal.json": {version: 1, entries: [
        entry("POST", "/v1/workspaces/w/region-cohorts", JSON.stringify({sources: "nucleoplasm"}), "cohort-a.json", "count"),
        entry("GET", "/v1/workspaces/w/jobs", null, "jobs-a.json", "count"),
        entry("POST", "/v1/workspaces/w/region-cohorts", JSON.stringify({sources: "nucleoli"}), "cohort-b.json", "mean"),
        entry("GET", "/v1/workspaces/w/jobs", null, "jobs-b.json", "mean"),
      ]},
      "seed.json": [{id: "seed", state: "succeeded"}],
      "cohort-a.json": {job_id: "a"}, "jobs-a.json": [{id: "seed", state: "succeeded"}, {id: "a", state: "succeeded"}],
      "cohort-b.json": {job_id: "b"}, "jobs-b.json": [{id: "seed", state: "succeeded"}, {id: "b", state: "succeeded"}],
    });
    const ids = async () => ((await (await transport.fetch("/v1/workspaces/w/jobs")).json()) as Array<{id: string}>).map(job => job.id);
    expect(await ids()).toEqual(["seed"]);
    await transport.fetch("/v1/workspaces/w/region-cohorts", {method: "POST", body: JSON.stringify({sources: "nucleoplasm"})});
    expect(await ids()).toEqual(["seed", "a"]);
    await transport.fetch("/v1/workspaces/w/region-cohorts", {method: "POST", body: JSON.stringify({sources: "nucleoli"})});
    // Scene "mean" recorded no job "a"; the API would still list it, and the client may reuse it.
    expect(await ids()).toEqual(["seed", "b", "a"]);
  });
  it("reads after a scene's last change never come from the next scene's opening", async () => {
    const transport = subject({
      "index.json": {version: 1, entries: {[snapshotKey("/v1/workspaces/w/selection")]: {status: 200, headers: [], file: "seed.json"}}},
      "journal.json": {version: 1, entries: [
        entry("POST", "/v1/jobs/j/figure-render", JSON.stringify({width: 89}), "render.json", "a"),
        entry("GET", "/v1/workspaces/w/selection", null, "other.json", "b"),
        entry("POST", "/v1/workspaces/w/proposal-drafts", JSON.stringify({goal: "x"}), "draft.json", "b"),
      ]},
      "seed.json": {version: 1}, "other.json": {version: 14}, "render.json": {job: "r"}, "draft.json": {draft: true},
    });
    expect(await (await transport.fetch("/v1/workspaces/w/selection")).json()).toEqual({version: 1});
    await transport.fetch("/v1/jobs/j/figure-render", {method: "POST", body: JSON.stringify({width: 89})});
    // Scene "b" read another adoption before its own first change; this device keeps its own.
    expect(await (await transport.fetch("/v1/workspaces/w/selection")).json()).toEqual({version: 1});
  });
  it("answers with the visitor's cohort the request names, when two of them stand for one recorded cohort", async () => {
    const R = "aaaaaaaa-0000-4000-8000-000000000001", V1 = "bbbbbbbb-0000-4000-8000-000000000002", V2 = "cccccccc-0000-4000-8000-000000000003";
    const transport = subject({
      "index.json": {version: 1, entries: {}},
      "journal.json": {version: 1, entries: [
        entry("POST", "/v1/workspaces/w/region-cohorts", JSON.stringify({sources: "x"}), "c1.json", "m1"),
        entry("POST", "/v1/workspaces/w/region-cohorts", JSON.stringify({sources: "y"}), "c2.json", "m2"),
        entry("POST", `/v1/revisions/${R}/descriptive`, JSON.stringify({metric: "a"}), "job.json", "s", "/v1/revisions/*/descriptive"),
        entry("GET", "/v1/jobs/j/result", null, "result.json", "s"),
      ]},
      "c1.json": {revision_id: V1}, "c2.json": {revision_id: V2}, "job.json": {job_id: "j"}, "result.json": {revision_id: R},
    });
    const describe = async (cohort: string) => {
      await transport.fetch(`/v1/revisions/${cohort}/descriptive`, {method: "POST", body: JSON.stringify({metric: "a"})});
      return (await (await transport.fetch("/v1/jobs/j/result")).json() as {revision_id: string}).revision_id;
    };
    await transport.fetch("/v1/workspaces/w/region-cohorts", {method: "POST", body: JSON.stringify({sources: "x"})});
    expect(await describe(V1)).toBe(V1);
    await transport.fetch("/v1/workspaces/w/region-cohorts", {method: "POST", body: JSON.stringify({sources: "y"})});
    expect(await describe(V2)).toBe(V2);
    expect(await describe(V1)).toBe(V1);
  });
  it("keeps the device's document when the answered change left the scene's one as the scene wrote it", async () => {
    const transport = subject({
      "index.json": {version: 1, entries: {[snapshotKey("/v1/workspaces/w/selection")]: {status: 200, headers: [], file: "seed.json"}}},
      "journal.json": {version: 1, entries: [
        entry("GET", "/v1/workspaces/w/selection", null, "s1.json", "a"),
        entry("POST", "/v1/workspaces/w/selection", JSON.stringify({version: "*"}), "s2.json", "a"),
        entry("POST", "/v1/jobs/j/figure-render", JSON.stringify({width: 89}), "render.json", "a"),
        entry("GET", "/v1/workspaces/w/selection", null, "s2.json", "a"),
      ]},
      "seed.json": {version: 1}, "s1.json": {version: 1}, "s2.json": {version: 2}, "render.json": {job: "r"},
    });
    expect(await (await transport.fetch("/v1/workspaces/w/selection")).json()).toEqual({version: 1});
    await transport.fetch("/v1/jobs/j/figure-render", {method: "POST", body: JSON.stringify({width: 89})});
    // The figure changed no adoption; the scene's own adoption before it is not this device's.
    expect(await (await transport.fetch("/v1/workspaces/w/selection")).json()).toEqual({version: 1});
  });
  it("switches a field to a revision it already adopted on the device, and nothing else", async () => {
    const selection = {version: 4, entries: [{id: "e1", field_id: "f1", revision_id: "nuc", exclusion_reason: null, target_revisions: {nuclei: "nuc", nucleoli: "nol"}}]};
    const transport = subject({
      "index.json": {version: 1, entries: {[snapshotKey("/v1/workspaces/w/selection")]: {status: 200, headers: [], file: "selection.json"}}},
      "selection.json": selection, "journal.json": {version: 1, entries: []},
    });
    const write = (revision: string, version = 4) => transport.fetch("/v1/workspaces/w/selection", {method: "POST", body: JSON.stringify({version, entries: [{...selection.entries[0], revision_id: revision}]})});
    const adopted = await write("nol");
    expect(adopted.status).toBe(200);
    const value = await adopted.json();
    expect(value).toEqual({version: 5, entries: [{...selection.entries[0], revision_id: "nol"}]});
    expect(await (await transport.fetch("/v1/workspaces/w/selection")).json()).toEqual(value);
    // A revision the field never adopted, or a stale version, is not decided here.
    expect((await write("other", 5)).status).toBe(409);
    expect((await write("nuc", 4)).status).toBe(409);
  });
});

describe("adoption after a recorded change", () => {
  it("keeps the device's adoption over the reads recorded for the change before it", async () => {
    const before = {version: 4, entries: [{id: "e1", field_id: "f1", revision_id: "nuc", exclusion_reason: null, target_revisions: {nuclei: "nuc", nucleoli: "nol"}}]};
    const measured = {version: 5, entries: [{...before.entries[0], revision_id: "nol"}]};
    const files: Record<string, unknown> = {
      "index.json": {version: 1, entries: {[snapshotKey("/v1/workspaces/w/selection")]: {status: 200, headers: [], file: "before.json"}}},
      "before.json": before, "measured.json": measured, "accept.json": {ok: true},
      "journal.json": {version: 1, entries: [
        {method: "POST", path: "/v1/workspaces/w/runs/r/accept", body: null, status: 200, headers: [], file: "accept.json", scene: "measure"},
        {method: "GET", path: "/v1/workspaces/w/selection", body: null, status: 200, headers: [], file: "measured.json", scene: "measure"},
      ]},
    };
    const fetchStatic = vi.fn(async (url: string) => {
      const name = url.replace("/showcase/snapshot/", "");
      return name in files ? new Response(JSON.stringify(files[name])) : new Response("missing", {status: 404});
    });
    const transport = createShowcaseTransport({fetchStatic, createEngine: () => null, capable: () => false, snapshotBase: "/showcase/snapshot/"});
    await transport.fetch("/v1/workspaces/w/runs/r/accept", {method: "POST"});
    expect(await (await transport.fetch("/v1/workspaces/w/selection")).json()).toEqual(measured);
    const adopted = await (await transport.fetch("/v1/workspaces/w/selection", {method: "POST", body: JSON.stringify({version: 5, entries: [{...measured.entries[0], revision_id: "nuc"}]})})).json();
    expect(adopted.version).toBe(6);
    expect(await (await transport.fetch("/v1/workspaces/w/selection")).json()).toEqual(adopted);
  });
});

describe("figures drawn from the recorded results", () => {
  const S = "11111111-1111-4111-8111-111111111111", R = "22222222-2222-4222-8222-222222222222";
  const base = {width_inches: 183 / 25.4, height_inches: 100 / 25.4, font_size: 7, x_label: "", y_label: "", group_order: [], kind: "superplot",
    preset: "custom", language: "en", axes: {version: "1.0.0", x_scale: "linear", y_scale: "linear", x_min: null, x_max: null, x_tick_step: null},
    y_tick_step: null, point_size: 18, style: {version: "1.0.0", series_colors: {}, show_legend: true}, y_min: null, y_max: null,
    presentation: {version: "1.0.0", annotation: "value", size: "panel", composition: "quantification", outlines: true}};
  const stars = {...base, presentation: {...base.presentation, annotation: "stars"}};
  function figures() {
    const files: Record<string, unknown> = {
      "index.json": {version: 1, entries: {}},
      "journal.json": {version: 1, entries: [
        {scene: "s:a", method: "POST", path: `/v1/revisions/${R}/common-statistics`, body: JSON.stringify({mode: "m", plot: {kind: "superplot"}}), status: 202, headers: [["content-type", "application/json"]], file: "a.json"},
        {scene: "s:a", method: "GET", path: "/v1/workspaces/w/jobs", body: null, status: 200, headers: [["content-type", "application/json"]], file: "l.json"},
        {scene: "s:a", method: "GET", path: `/v1/jobs/${S}/common-statistics`, body: null, status: 200, headers: [["content-type", "application/json"]], file: "r.json"},
      ]},
      "a.json": {job_id: S}, "l.json": [{id: S, state: "succeeded"}], "r.json": {revision_id: R, estimates: {p: 0.01}, spec: {plot: {kind: "superplot"}, test: "paired-t"}, figure: {old: true}},
      "figures.json": {version: 1, sources: {[S]: {group: "g", workspace: "w", revision: R}}, packages: [],
        groups: {g: {observations: "points", opening: {plot: base, figure: {opening: true}, files: {"figure.svg": "open.svg"}},
          figures: [{plot: base, figure: {drawn: "base"}, files: {"figure.svg": "base.svg"}}, {plot: stars, figure: {drawn: "stars"}, files: {"figure.svg": "stars.svg", "figure-legend.md": "legend.md"}}]}}},
    };
    const raw: Record<string, string> = {"open.svg": "<svg>opening</svg>", "base.svg": "<svg>base</svg>", "stars.svg": "<svg>stars</svg>", "legend.md": "# Legend"};
    const fetchStatic = vi.fn(async (url: string) => {
      const name = url.replace("/showcase/snapshot/", "");
      if (name in raw) return new Response(raw[name]);
      return name in files ? new Response(JSON.stringify(files[name])) : new Response("missing", {status: 404});
    });
    return createShowcaseTransport({fetchStatic, createEngine: () => fakeEngine(), capable: () => false, snapshotBase: "/showcase/snapshot/"});
  }
  const render = (subject: ReturnType<typeof figures>, plot: unknown) =>
    subject.fetch(`/v1/jobs/${S}/figure-render`, {method: "POST", body: JSON.stringify({request_id: crypto.randomUUID(), plot})});

  it("reads a figure request by what it draws: defaults a request leaves out are the result's", () => {
    const explicit = {...base, presentation: {...base.presentation, observations: "points", color_by: "run"}};
    expect(figureSettings(explicit, "points")).toBe(figureSettings(base, "points"));
    expect(figureSettings({...base, width_inches: 3}, "points")).toBe(figureSettings(base, "points"));
    expect(figureSettings({...base, presentation: {...base.presentation, observations: "box"}}, "points")).not.toBe(figureSettings(base, "points"));
    const page = {...base, kind: "distribution", presentation: undefined};
    expect(figureSettings({...page, width_inches: 89 / 25.4}, "points")).not.toBe(figureSettings(page, "points"));
  });

  it("matches a recorded calculation whatever figure settings it names", () => {
    expect(calculationBody("/v1/revisions/r/common-statistics", JSON.stringify({mode: "m", plot: {kind: "box"}})))
      .toBe(calculationBody("/v1/revisions/r/common-statistics", JSON.stringify({mode: "m", plot: {kind: "superplot", presentation: {}}})));
    expect(calculationBody("/v1/workspaces/w/selection", "{\"plot\":1}")).toBe("{\"plot\":1}");
  });

  it("calculates from the tour and shows the result with the figure drawn for it", async () => {
    const subject = figures();
    const accepted = await subject.fetch(`/v1/revisions/${R}/common-statistics`, {method: "POST", body: JSON.stringify({mode: "m", plot: base})});
    expect(await accepted.json()).toEqual({job_id: S});
    const result = await (await subject.fetch(`/v1/jobs/${S}/common-statistics`)).json();
    expect(result.estimates).toEqual({p: 0.01});
    expect(result.figure).toEqual({opening: true});
    expect(result.spec).toEqual({plot: base, test: "paired-t"});
    expect(await (await subject.fetch(`/v1/jobs/${S}/files/figure.svg`)).text()).toBe("<svg>opening</svg>");
  });

  it("answers a figure setting with its drawing, listed as a finished job", async () => {
    const subject = figures();
    const accepted = await render(subject, {...stars, presentation: {...stars.presentation, color_by: "run"}});
    expect(accepted.status).toBe(202);
    const {job_id: job} = await accepted.json();
    expect(await (await subject.fetch(`/v1/jobs/${job}/figure-render`)).json()).toEqual({source_job_id: S, figure: {drawn: "stars"}});
    expect(await (await subject.fetch(`/v1/jobs/${job}/files/figure.svg`)).text()).toBe("<svg>stars</svg>");
    const legend = await subject.fetch(`/v1/jobs/${job}/files/figure-legend.md`);
    expect(legend.headers.get("content-type")).toContain("text/markdown");
    expect(await legend.text()).toBe("# Legend");
    await subject.fetch(`/v1/revisions/${R}/common-statistics`, {method: "POST", body: JSON.stringify({mode: "m", plot: base})});
    const listed = await (await subject.fetch("/v1/workspaces/w/jobs")).json() as Array<{id: string; state: string; kind?: string}>;
    expect(listed.find(item => item.id === job)).toMatchObject({state: "succeeded", kind: "figure-render", revision_id: R});
  });

  it("explains a figure setting it holds no drawing for", async () => {
    const subject = figures();
    const other = await render(subject, {...base, presentation: {...base.presentation, size: "double-column"}});
    expect(other.status).toBe(409);
    expect(await other.json()).toEqual({detail: "showcase_action_not_recorded"});
  });
});

describe("saved results and figures of the seed", () => {
  it("shows a saved result and a saved figure with their drawings from figures.json", async () => {
    const S = "33333333-3333-4333-8333-333333333333", F = "44444444-4444-4444-8444-444444444444";
    const index = {version: 1, entries: {
      [snapshotKey(`/v1/jobs/${S}/result`)]: {status: 200, headers: [["content-type", "application/json"]], file: "s.json"},
      [snapshotKey(`/v1/jobs/${F}/result`)]: {status: 200, headers: [["content-type", "application/json"]], file: "f.json"},
    }};
    const files: Record<string, string> = {
      "index.json": JSON.stringify(index), "journal.json": JSON.stringify({version: 1, entries: []}),
      "s.json": JSON.stringify({revision_id: "r", estimates: {p: 0.2}, spec: {plot: {kind: "superplot"}}, figure: {old: 1}}),
      "f.json": JSON.stringify({revision_id: "r", source_job_id: S, spec: {plot: {kind: "box"}}, figure: {old: 2}}),
      "figures.json": JSON.stringify({version: 1, packages: [], sources: {[S]: {group: "g", workspace: "w", revision: "r", seed: true}},
        groups: {g: {observations: "points", opening: {plot: {kind: "superplot", presentation: null}, figure: {drawn: "opening"}, files: {"figure.svg": "o.svg"}}, figures: []}},
        saved: {[F]: {source: S, plot: {kind: "box"}, figure: {drawn: "saved"}, files: {"figure.svg": "b.svg"}}}}),
      "o.svg": "<svg>opening</svg>", "b.svg": "<svg>saved</svg>",
    };
    const fetchStatic = vi.fn(async (url: string) => {
      const name = url.replace("/showcase/snapshot/", "");
      return name in files ? new Response(files[name]) : new Response("missing", {status: 404});
    });
    const subject = createShowcaseTransport({fetchStatic, createEngine: () => fakeEngine(), capable: () => false, snapshotBase: "/showcase/snapshot/"});
    const result = await (await subject.fetch(`/v1/jobs/${S}/result`)).json();
    expect(result).toMatchObject({estimates: {p: 0.2}, figure: {drawn: "opening"}});
    expect(await (await subject.fetch(`/v1/jobs/${S}/files/figure.svg`)).text()).toBe("<svg>opening</svg>");
    expect(await (await subject.fetch(`/v1/jobs/${F}/result`)).json()).toMatchObject({source_job_id: S, figure: {drawn: "saved"}});
    expect(await (await subject.fetch(`/v1/jobs/${F}/figure-render`)).json()).toEqual({source_job_id: S, figure: {drawn: "saved"}});
    expect(await (await subject.fetch(`/v1/jobs/${F}/files/figure.svg`)).text()).toBe("<svg>saved</svg>");
  });
});
