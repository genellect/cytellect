import {afterEach, describe, expect, it, vi} from "vitest";
import {
  AccountRequestError, restartGpuAfterSignIn, accountErrorText, accountLabel, accountNotice, formatDate, gpuNotice, gpuQuotaReached, gpuQuotaText, inferencePhase,
  followUpdate, pendingNotice, plausibleCode, plausibleEmail, resendWait, safeNotesUrl, updateNotice, updateSignature, usageText,
} from "./cloud-account";

afterEach(() => {vi.unstubAllGlobals(); vi.unstubAllEnvs(); vi.resetModules();});

describe("cloud account display", () => {
  it("labels each account state for the header", () => {
    expect(accountLabel(null)).toEqual({label: "ログイン"});
    expect(accountLabel({state: "allowed", email: "researcher@example.org"})).toEqual({label: "researcher@example.org", detail: "GPU・解析提案：利用可"});
    expect(accountLabel({state: "pending_approval", email: "a@example.org"}).label).toBe("承認待ち");
    expect(accountLabel({state: "pending_approval", approved: true}).label).toBe("承認されました");
    expect(accountLabel({state: "expired"}).label).toBe("ログイン");
    const used = {state: "allowed" as const, email: "a@example.org", resets_at: "2026-11-01T00:00:00Z",
      limits: {gpu_seconds_month: 3600, proposal_usd_month: 5}, usage: {gpu_seconds: 3600, proposal_usd: 1}};
    expect(gpuQuotaReached(used)).toBe(true);
    expect(accountLabel(used, "UTC").detail).toBe("GPU：今月の上限（11月1日に再開）");
    expect(gpuQuotaText(used, "UTC")).toContain("11月1日から再び使えます");
    expect(gpuQuotaReached({...used, usage: {gpu_seconds: 10, proposal_usd: 0}})).toBe(false);
  });
  it("switches the pending banner to continuing the login once approved", () => {
    const waiting = pendingNotice({state: "pending_approval", requested_at: Date.UTC(2026, 9, 29, 3, 5) / 1000}, "Asia/Tokyo")!;
    expect(waiting.text).toContain("承認待ち（10月29日 12:05 に申請）");
    expect(waiting.text).toContain("このPCでの解析は使えます");
    expect(waiting.action).toBeUndefined();
    expect(pendingNotice({state: "pending_approval", approved: true})!.action?.label).toBe("承認されました。ログインを続ける");
    expect(pendingNotice({state: "allowed"})).toBeNull();
    expect(accountNotice({state: "revoked"})!.text).toContain("オーナーにお問い合わせください");
    expect(accountNotice({state: "expired"})!.text).toBe("クラウド機能を使うには、もう一度ログインしてください。");
  });
  it("names the GPU phase and the next action for each GPU state", () => {
    expect(gpuNotice({state: "starting"})!.text).toContain("GPU を起動しています");
    expect(inferencePhase({state: "starting"}, true)).toBe("GPU を起動しています");
    expect(inferencePhase({state: "ready"}, true)).toBe("検出しています");
    expect(inferencePhase({state: "starting", busy: true}, true)).toBe("GPU を準備しています");
    expect(gpuNotice({state: "starting", busy: true})!.text).toContain("GPU を準備しています");
    expect(inferencePhase({state: "ready"}, false)).toBeNull();
    expect(gpuNotice({state: "quota_exceeded", resets_at: "2026-11-01T00:00:00Z"}, "UTC")!.text).toContain("11月1日から再び使えます");
    expect(gpuNotice({state: "quota_exceeded", scope: "global"})!.text).toContain("クラウド GPU 全体");
    expect(gpuNotice({state: "offline"})!.action?.label).toBe("ネットワークを確認してもう一度試す");
    expect(gpuNotice({state: "timeout"})!.action?.kind).toBe("retry");
    expect(gpuNotice({state: "auth_required"})!.action?.kind).toBe("login");
    expect(gpuNotice({state: "unconfigured"})!.action?.kind).toBe("login");
    expect(gpuNotice({state: "idle"})).toBeNull();
  });
  it("keeps error codes out of the sentence", () => {
    expect(accountErrorText(new AccountRequestError("account_code_invalid", 400, undefined, 3))).toBe("コードが一致しません。あと 3 回入力できます。");
    expect(accountErrorText(new AccountRequestError("account_rate_limited", 429, 42))).toContain("約 42 秒後");
    expect(accountErrorText(new AccountRequestError("account_rate_limited", 429, 20 * 3600))).toBe("しばらくしてからもう一度試してください（約 20 時間後）。このPCでの解析は続けて使えます。");
    expect(accountErrorText(new AccountRequestError("account_rate_limited", 429, 600))).toContain("約 10 分後");
    expect(accountErrorText(new AccountRequestError("account_mail_failed", 502))).toBe("メールを送れませんでした。時間をおいてもう一度試してください。");
    expect(accountErrorText(new AccountRequestError("unexpected_code", 500))).not.toContain("unexpected_code");
    expect(accountErrorText(new Error("network"))).toContain("Cytellect に接続できません");
  });
  it("checks inputs and counts down the resend button", () => {
    expect(plausibleEmail(" Researcher@Example.org ")).toBe(true);
    expect(plausibleEmail("researcher@example")).toBe(false);
    expect(plausibleCode("123456")).toBe(true);
    expect(plausibleCode("12345a")).toBe(false);
    expect(resendWait(61_000, 1_000)).toBe(60);
    expect(resendWait(1_000, 61_000)).toBe(0);
    expect(usageText({state: "allowed", limits: {gpu_seconds_month: 3600, proposal_usd_month: 5}, usage: {gpu_seconds: 61, proposal_usd: 0.4}}))
      .toBe("GPU 2 / 60 分 · 解析提案 0.40 / 5.00 ドル");
    expect(formatDate("not a date")).toBe("");
  });
});

describe("local account requests", () => {
  it("reads the update route's error field, such as a refusal while analyses run", async () => {
    vi.stubEnv("NEXT_PUBLIC_CYTELLECT_WEB_MODE", "local");
    vi.stubGlobal("window", {location: {hostname: "127.0.0.1"}});
    vi.stubGlobal("fetch", vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({detail: "update_jobs_running"}), {status: 409}))
      .mockResolvedValueOnce(new Response(JSON.stringify({error: "update_in_progress"}), {status: 409})));
    const {accountApi} = await import("./cloud-account");
    await expect(accountApi.applyUpdate()).rejects.toMatchObject({code: "update_jobs_running", status: 409});
    await expect(accountApi.applyUpdate()).rejects.toMatchObject({code: "update_in_progress", status: 409});
  });
  it("send the protected header, keep documented error fields and treat a missing update route as none", async () => {
    vi.stubEnv("NEXT_PUBLIC_CYTELLECT_WEB_MODE", "local");
    vi.stubGlobal("window", {location: {hostname: "127.0.0.1"}});
    const fetch = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({detail: "account_code_invalid", attempts_left: 2}), {status: 400}))
      .mockResolvedValueOnce(new Response(JSON.stringify({detail: "Not Found"}), {status: 404}))
      .mockResolvedValueOnce(new Response(JSON.stringify({available: true, latest: "0.1.0-local.22"}), {status: 200}));
    vi.stubGlobal("fetch", fetch);
    const {accountApi} = await import("./cloud-account");
    await expect(accountApi.verify("000000")).rejects.toMatchObject({code: "account_code_invalid", attemptsLeft: 2});
    expect(fetch.mock.calls[0][0]).toBe("/v1/account/verify");
    expect(fetch.mock.calls[0][1].headers.get("X-Cytellect-Request")).toBe("1");
    expect(await accountApi.update()).toBeNull();
    expect(await accountApi.update()).toEqual({available: true, latest: "0.1.0-local.22"});
  });
  it("never calls from an external host or a hosted build", async () => {
    vi.stubEnv("NEXT_PUBLIC_CYTELLECT_WEB_MODE", "local");
    vi.stubGlobal("window", {location: {hostname: "example.com"}});
    const fetch = vi.fn(); vi.stubGlobal("fetch", fetch);
    const {accountApi} = await import("./cloud-account");
    await expect(accountApi.get()).rejects.toMatchObject({code: "local_host_required"});
    expect(fetch).not.toHaveBeenCalled();
  });
});

describe("automatic GPU start after sign-in", () => {
  it("restarts only on an actual sign-in that the GPU was waiting for", () => {
    expect(restartGpuAfterSignIn(false, true, "unconfigured")).toBe(true);
    expect(restartGpuAfterSignIn(false, true, "auth_required")).toBe(true);
    // An explicit GPU key that is rejected while the account stays allowed: no loop.
    expect(restartGpuAfterSignIn(true, true, "auth_required")).toBe(false);
    expect(restartGpuAfterSignIn(null, true, "auth_required")).toBe(false);
    expect(restartGpuAfterSignIn(false, true, "ready")).toBe(false);
    expect(restartGpuAfterSignIn(false, false, "unconfigured")).toBe(false);
  });
});

describe("update banner", () => {
  it("names each update state and keeps the error code for 詳細", () => {
    expect(updateNotice({available: true, latest: "0.1.0-local.22", state: "idle"})).toMatchObject({text: "更新があります（0.1.0-local.22）。研究データと設定は引き継がれます。", action: {label: "更新する"}});
    expect(updateNotice({available: true, state: "idle"}, true)!.text).toContain("更新しています");
    expect(updateNotice({available: true, state: "downloading"})!.tone).toBe("progress");
    expect(updateNotice({available: true, state: "restarting"})!.text).toContain("再起動しています");
    expect(updateNotice({available: false, latest: "0.1.0-local.22", state: "updated"})!.text).toBe("更新が完了しました（0.1.0-local.22）。");
    const failed = updateNotice({available: true, state: "failed", error: "update_failed"})!;
    expect(failed.text).toBe("更新できませんでした。今の版のまま使えます。あとでもう一度お試しください。");
    expect(failed.error).toBe("update_failed");
    expect(failed.text).not.toContain("update_failed");
    expect(updateNotice({available: true, state: "rolled_back"})!.text).toBe("元の版で起動しました。あとでもう一度更新してください。");
    expect(updateNotice({available: false, state: "unsupported"})).toBeNull();
    expect(updateNotice({available: false, latest: "0.1.0-local.22", state: "installed"})!.text)
      .toBe("更新の準備ができました（0.1.0-local.22）。次に Cytellect を起動したときに新しい版になります。");
    // Once the new version runs, an installed state left in the record says nothing.
    expect(updateNotice({available: false, current: "0.1.0-local.22", latest: "0.1.0-local.22", state: "installed"})).toBeNull();
    expect(updateSignature({available: false, current: "a", latest: "b", state: "updated", error: null})).toBe("updated:a:b:");
    expect(updateNotice({available: false, state: "idle"})).toBeNull();
    expect(updateNotice(null)).toBeNull();
  });
  it("links release notes only on this project's GitHub releases", () => {
    expect(safeNotesUrl("https://github.com/genellect/cytellect/releases/tag/v0.1.0-local.22")).toBe("https://github.com/genellect/cytellect/releases/tag/v0.1.0-local.22");
    for (const value of ["https://github.com/genellect/cytellect/releases/download/v0.1.0-local.22/Cytellect-Setup.exe",
      "https://github.com/genellect/cytellect/releases/tag/../download/v1/x.exe",
      "https://github.com/genellect/cytellect/releases/tag/%2e%2e/download/v1/x.exe",
      "https://github.com/genellect/cytellect/releases/tag/", "https://github.com/genellect/cytellect/releases/latest","https://github.com/genellect/cytellect/releases.evil/x", "http://github.com/genellect/cytellect/releases/x",
      "javascript:alert(1)", "https://example.com/https://github.com/genellect/cytellect/releases/", null, undefined])
      expect(safeNotesUrl(value)).toBeNull();
  });
  it("follows an update through a restart until it settles, within a time limit", async () => {
    let clock = 0;
    const replies: Array<() => Promise<{available: boolean; state: "installing" | "updated"} | null>> = [
      async () => ({available: true, state: "installing"}),
      async () => {throw new Error("restarting");},
      async () => ({available: false, state: "updated"}),
    ];
    const get = vi.fn(() => replies.shift()!());
    const result = await followUpdate(get, {sleep: async ms => {clock += ms;}, now: () => clock, pollMs: 1000, limitMs: 60_000});
    expect(result).toEqual({available: false, state: "updated"});
    expect(get).toHaveBeenCalledTimes(3);
    clock = 0;
    clock = 0;
    const deferred = await followUpdate(async () => ({available: false, state: "installed"}), {sleep: async ms => {clock += ms;}, now: () => clock, pollMs: 1000, limitMs: 60_000});
    expect(deferred).toEqual({available: false, state: "installed"});
    clock = 0;
    const stuck = await followUpdate(async () => ({available: true, state: "installing"}), {sleep: async ms => {clock += ms;}, now: () => clock, pollMs: 1000, limitMs: 5000});
    expect(stuck).toBe("timeout");
    const controller = new AbortController();
    const poll = vi.fn(async () => ({available: true, state: "installing" as const}));
    const cancelled = followUpdate(poll, {sleep: async () => {controller.abort();}, pollMs: 1000, limitMs: 60_000, signal: controller.signal});
    expect(await cancelled).toBe("cancelled");
    expect(poll).not.toHaveBeenCalled();
  });
});
