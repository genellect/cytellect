import {afterEach, describe, expect, it, vi} from "vitest";
import {fetchVerified, IntegrityError, sha256Hex} from "./digest";
import type {ShowcaseRequest, ShowcaseResponse, SnapshotIndex} from "./protocol";
import {createShowcaseTransport, journalBodyMatches, journalPathMatches, snapshotKey, type ShowcaseEngine} from "./transport";
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

  it("requests the opening records and the first field's files together, once each", async () => {
    const entries = {
      "/v1/session": {authenticated: true}, "/v1/workspaces/w/region-fields": [{id: "f1"}, {id: "f2"}],
      "/v1/region-fields/f1/preview?channel_id=c&gain=1": {preview: 1}, "/v1/region-fields/f2/preview?channel_id=c&gain=1": {preview: 2},
      "/v1/revisions/r1/region-masks?field_id=f1": {masks: 1}, "/v1/revisions/r1/region-measurements": {rows: 1},
    };
    const fetchStatic = staticFiles(entries);
    const subject = createShowcaseTransport({fetchStatic, createEngine: () => fakeEngine(), capable: () => true, snapshotBase: "/showcase/snapshot/"});
    await subject.fetch("/v1/session");
    const files = (paths: string[]) => paths.map(path => `/showcase/snapshot/r${Object.keys(entries).indexOf(path)}.json`);
    await vi.waitFor(() => expect(fetchStatic.mock.calls.map(([url]) => url)).toEqual(expect.arrayContaining(files([
      "/v1/workspaces/w/region-fields", "/v1/region-fields/f1/preview?channel_id=c&gain=1", "/v1/revisions/r1/region-masks?field_id=f1", "/v1/revisions/r1/region-measurements"]))));
    expect(fetchStatic.mock.calls.map(([url]) => url)).not.toContain(files(["/v1/region-fields/f2/preview?channel_id=c&gain=1"])[0]);
    const calls = fetchStatic.mock.calls.length;
    expect(await (await subject.fetch("/v1/region-fields/f1/preview?channel_id=c&gain=1")).json()).toEqual({preview: 1});
    expect(await (await subject.fetch("/v1/region-fields/f1/preview?channel_id=c&gain=1")).json()).toEqual({preview: 1});
    expect(fetchStatic.mock.calls.length).toBe(calls);
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
  function tour(capable: boolean, engine = fakeEngine()) {
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
      expect(showcase.isShowcaseNotice(`視野 1：${api.errorCodeMessage(code)} 実行条件を確認してください。`)).toBe(true);
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
  it("finds a request recorded in another scene under that scene's generated identifier", async () => {
    const transport = subject({
      "index.json": {version: 1, entries: {}},
      "journal.json": {version: 1, entries: [
        entry("POST", "/v1/workspaces/w/region-cohorts", JSON.stringify({metric: "x"}), "cohort-a.json", "area"),
        entry("POST", "/v1/revisions/rev-a/descriptive", JSON.stringify({metric: "area"}), "area.json", "area", "/v1/revisions/*/descriptive"),
        entry("POST", "/v1/workspaces/w/region-cohorts", JSON.stringify({metric: "x"}), "cohort-b.json", "mean"),
        entry("POST", "/v1/revisions/rev-b/descriptive", JSON.stringify({metric: "mean"}), "mean.json", "mean", "/v1/revisions/*/descriptive"),
      ]},
      "cohort-a.json": {revision_id: "rev-a"}, "cohort-b.json": {revision_id: "rev-b"}, "area.json": {job: "area"}, "mean.json": {job: "mean"},
    });
    expect(await (await transport.fetch("/v1/workspaces/w/region-cohorts", {method: "POST", body: JSON.stringify({metric: "x"})})).json()).toEqual({revision_id: "rev-a"});
    // The exact path answers first; the other scene's request is found by its pattern.
    expect(await (await transport.fetch("/v1/revisions/rev-a/descriptive", {method: "POST", body: JSON.stringify({metric: "area"})})).json()).toEqual({job: "area"});
    expect(await (await transport.fetch("/v1/revisions/rev-a/descriptive", {method: "POST", body: JSON.stringify({metric: "mean"})})).json()).toEqual({job: "mean"});
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
