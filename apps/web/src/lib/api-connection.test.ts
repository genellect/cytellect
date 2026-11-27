/** The local build's three connection failures and the one session renewal (#284 W9). */
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";
import {readFileSync} from "node:fs";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), {status, headers: {"Content-Type": "application/json"}});
type Call = [string, RequestInit & {headers?: Headers | Record<string, string>}];

/** The local client after one answered request of this page (a session in use), unless `fresh`. */
async function localApi(answers: Array<Response | Error | ((path: string, init: RequestInit) => Response | Promise<Response>)>, {fresh = false} = {}) {
  vi.stubEnv("NEXT_PUBLIC_CYTELLECT_WEB_MODE", "local");
  vi.stubGlobal("window", {location: {hostname: "127.0.0.1"}});
  const queue = [...(fresh ? [] : [json(200, [])]), ...answers];
  const fetch = vi.fn(async (path: string, init: RequestInit) => {
    const next = queue.shift();
    if (!next) throw new Error(`unexpected request ${path}`);
    if (next instanceof Error) throw next;
    return typeof next === "function" ? next(path, init) : next;
  });
  vi.stubGlobal("fetch", fetch);
  const api = await import("./api");
  const connection = await import("./local-connection");
  if (!fresh) {await api.request("/v1/workspaces"); fetch.mockClear();}
  return {api, connection, fetch, calls: () => fetch.mock.calls as unknown as Call[]};
}
const header = (init: RequestInit, name: string) => new Headers(init.headers).get(name);

beforeEach(() => vi.resetModules());
afterEach(() => {vi.unstubAllGlobals(); vi.unstubAllEnvs(); vi.resetModules();});

describe("local connection failures", () => {
  it("no answer (unsent, or the answer was lost) is api_unreachable with status 0, never the browser's text", async () => {
    const {api, connection, calls} = await localApi([new TypeError("Failed to fetch"), json(200, {ok: true})]);
    const failure = await api.post("/v1/workspaces/w/region-fields", {}).catch((error: unknown) => error);
    expect(failure).toEqual(new api.ApiError("api_unreachable", 0));
    expect(api.errorMessage(failure)).toBe(api.LOCAL_UNREACHABLE_TEXT);
    expect(connection.localConnection()).toBe("unreachable");
    expect(calls()).toHaveLength(1); // a request without an answer is never repeated: it may have been accepted
    // The next answer means the service is back.
    expect(await api.request("/v1/local/setup")).toEqual({ok: true});
    expect(connection.localConnection()).toBe("connected");
  });
  it("an ended session (401) opens a new session once and sends the same request again", async () => {
    const body = new FormData();
    const {api, connection, calls} = await localApi([json(401, {detail: "session_required"}), json(200, {authenticated: true}), json(200, {id: "f1"})]);
    expect(await api.request("/v1/workspaces/w/region-fields", {method: "POST", body})).toEqual({id: "f1"});
    const [first, renewal, again] = calls();
    expect(renewal[0]).toBe("/v1/local/session");
    expect(renewal[1]).toMatchObject({method: "POST", credentials: "include", cache: "no-store"});
    expect(header(renewal[1], "X-Cytellect-Request")).toBe("1");
    expect(again[0]).toBe(first[0]);
    expect(again[1].body).toBe(body);
    expect(again[1].method).toBe("POST");
    expect(connection.localConnection()).toBe("connected");
  });
  it("retries only once: a second 401 is reported as an ended session", async () => {
    const {api, connection, calls} = await localApi([json(401, {detail: "session_required"}), json(200, {authenticated: true}), json(401, {detail: "session_required"})]);
    await expect(api.request("/v1/workspaces")).rejects.toEqual(new api.ApiError("session_required", 401));
    expect(calls().map(([path]) => path)).toEqual(["/v1/workspaces", "/v1/local/session", "/v1/workspaces"]);
    expect(connection.localConnection()).toBe("session");
    expect(api.errorMessage(new api.ApiError("session_required", 401))).toContain("デスクトップの「Cytellect」");
  });
  it("a refused renewal does not send the request again", async () => {
    const {api, connection, calls} = await localApi([json(401, {detail: "session_required"}), json(403, {detail: "local_origin_required"})]);
    await expect(api.request("/v1/workspaces")).rejects.toMatchObject({code: "session_required", status: 401});
    expect(calls()).toHaveLength(2);
    expect(connection.localConnection()).toBe("session");
  });
  it("requests that meet a 401 together share one renewal", async () => {
    let renewals = 0;
    const answer = (path: string) => {
      if (path === "/v1/local/session") {renewals += 1; return json(200, {authenticated: true});}
      return json(renewals ? 200 : 401, renewals ? {ok: true} : {detail: "session_required"});
    };
    const {api} = await localApi([answer, answer, answer, answer, answer]);
    await Promise.all([api.request("/v1/workspaces"), api.request("/v1/workspaces/w")]);
    expect(renewals).toBe(1);
  });
  it("routes that open or end a session, and other 401s, are not renewed", async () => {
    const ended = () => json(401, {detail: "session_required"});
    const {api, calls} = await localApi([ended(), ended(), ended(), json(401, {detail: "invitation_invalid"})]);
    await expect(api.post("/v1/local/session")).rejects.toMatchObject({status: 401});
    await expect(api.request("/v1/session", {method: "DELETE"})).rejects.toMatchObject({status: 401}); // an explicit end stays ended
    await expect(api.post("/v1/desktop/session")).rejects.toMatchObject({status: 401});
    await expect(api.request("/v1/workspaces")).rejects.toMatchObject({code: "invitation_invalid"});
    expect(calls()).toHaveLength(4);
  });
  it("a page that has used no session yet is not renewed: it starts one from its own screen", async () => {
    const {api, connection, calls} = await localApi([json(200, {ready: true}), json(401, {detail: "session_required"})], {fresh: true});
    await api.request("/v1/local/setup"); // answers without a session
    await expect(api.request("/v1/session")).rejects.toMatchObject({code: "session_required", status: 401});
    expect(calls().map(([path]) => path)).toEqual(["/v1/local/setup", "/v1/session"]);
    expect(connection.localConnection()).toBe("session");
  });
  it("an explicit end of the session is not undone by the next request", async () => {
    const {api, calls} = await localApi([json(200, {}), json(401, {detail: "session_required"})]);
    await api.request("/v1/session", {method: "DELETE"});
    await expect(api.request("/v1/workspaces")).rejects.toMatchObject({status: 401});
    expect(calls()).toHaveLength(2);
  });
  it("the workspace's own session check is renewed like any reading", async () => {
    const {api, calls} = await localApi([json(401, {detail: "session_required"}), json(200, {authenticated: true}), json(200, {authenticated: true})]);
    expect(await api.request("/v1/session")).toEqual({authenticated: true});
    expect(calls().map(([path]) => path)).toEqual(["/v1/session", "/v1/local/session", "/v1/session"]);
  });
  it("the wrong origin (403 local_origin_required) is reported as such and never retried", async () => {
    const {api, connection, calls} = await localApi([json(403, {detail: "local_origin_required"})]);
    await expect(api.request("/v1/workspaces")).rejects.toEqual(new api.ApiError("local_origin_required", 403));
    expect(calls()).toHaveLength(1);
    expect(connection.localConnection()).toBe("origin");
    expect(api.errorMessage(new api.ApiError("local_origin_required", 403))).toBe("作業画面には、デスクトップの「Cytellect」から開いた画面が必要です。");
  });
  it("a page outside the PC's own address is the wrong origin before any request", async () => {
    const {api, connection, fetch} = await localApi([]);
    vi.stubGlobal("window", {location: {hostname: "example.com"}});
    await expect(api.request("/v1/workspaces")).rejects.toMatchObject({code: "local_host_required"});
    expect(fetch).not.toHaveBeenCalled();
    expect(connection.localConnection()).toBe("origin");
  });
  it("an aborted request stays an abort", async () => {
    const {api, connection} = await localApi([new DOMException("aborted", "AbortError")]);
    await expect(api.request("/v1/workspaces")).rejects.toMatchObject({name: "AbortError"});
    expect(connection.localConnection()).toBe("connected");
  });
  it("private images renew an ended session the same way", async () => {
    const {api, calls} = await localApi([json(401, {detail: "session_required"}), json(200, {authenticated: true}), new Response("png", {status: 200})]);
    expect(await (await api.fetchPrivateResponse("/v1/region-fields/f/preview")).text()).toBe("png");
    expect(calls().map(([path]) => path)).toEqual(["/v1/region-fields/f/preview", "/v1/local/session", "/v1/region-fields/f/preview"]);
  });
  it("the hosted build keeps its own session rules: no renewal, no connection notice", async () => {
    vi.stubEnv("NEXT_PUBLIC_CYTELLECT_WEB_MODE", "web");vi.stubEnv("NEXT_PUBLIC_API_ORIGIN", "https://api.example.test");
    const fetch = vi.fn().mockResolvedValueOnce(json(401, {detail: "session_required"})).mockRejectedValueOnce(new TypeError("Failed to fetch"));
    vi.stubGlobal("fetch", fetch);
    const api = await import("./api"), connection = await import("./local-connection");
    await expect(api.request("/v1/workspaces")).rejects.toMatchObject({code: "session_required"});
    await expect(api.request("/v1/workspaces")).rejects.toMatchObject({code: "api_unreachable", status: 0});
    expect(fetch).toHaveBeenCalledTimes(2);
    expect(connection.localConnection()).toBe("connected");
  });
});

describe("connection notice text", () => {
  it("gives each failure its own state, reason and button (UC-02, UC-03)", async () => {
    const {connectionNotice} = await import("./local-connection");
    expect(connectionNotice("connected")).toBeNull();
    expect(connectionNotice("unreachable")).toEqual({status: "ローカルのサービス：接続なし", reason: "再開には、デスクトップの「Cytellect」の起動が必要です。", action: "再接続"});
    expect(connectionNotice("unreachable", true)?.status).toBe("ローカルのサービス：再接続中");
    expect(connectionNotice("session")).toEqual({status: "作業画面のセッション：終了", reason: null, action: "再接続"});
    expect(connectionNotice("origin")).toEqual({status: "ローカルのサービス：接続の拒否", reason: "作業画面には、デスクトップの「Cytellect」から開いた画面が必要です。", action: null});
  });
  it("names an abnormal previous stop in one line, with the launcher's labels", async () => {
    const {previousStopText, STOP_LABELS} = await import("./local-connection");
    expect(previousStopText({abnormal: false, reason: null, time: null})).toBeNull();
    expect(previousStopText({abnormal: true, reason: "unrecorded", time: null})).toBe("前回の停止：理由の記録なし");
    const at = Date.UTC(2026, 10, 23, 9, 28) / 1000;
    expect(previousStopText({abnormal: true, reason: "local_worker_stopped", time: at}, "Asia/Tokyo")).toBe("前回の停止：計算処理の停止 · 11月23日 18:28");
    const source = readFileSync(new URL("../../../../services/api/src/cytellect_api/local.py", import.meta.url), "utf8");
    const block = source.slice(source.indexOf("STOP_LABELS = {"), source.indexOf("}", source.indexOf("STOP_LABELS = {")));
    const launcher = Object.fromEntries([...block.matchAll(/"([a-z_]+)": "([^"]+)"/g)].map(match => [match[1], match[2]]));
    expect(launcher).toEqual(STOP_LABELS);
  });
});
