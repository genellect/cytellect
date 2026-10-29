import {afterEach, describe, expect, it, vi} from "vitest";
import {
  AccountRequestError, accountErrorText, accountLabel, accountNotice, formatDate, gpuNotice, gpuQuotaReached, gpuQuotaText, inferencePhase,
  pendingNotice, plausibleCode, plausibleEmail, resendWait, usageText,
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
    expect(accountErrorText(new AccountRequestError("account_rate_limited", 429, 42))).toContain("42 秒");
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
