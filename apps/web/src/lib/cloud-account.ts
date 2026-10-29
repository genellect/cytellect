/**
 * Sign-in for the cloud features of a local installation (GPU inference and analysis proposals).
 *
 * The browser talks only to the local API (`/v1/account/*`); the local API holds the device
 * token and calls the cloud service. Nothing here ever sees the token. Local analysis never
 * depends on these calls.
 */
import {API, LOCAL_MODE} from "./api";

export type AccountState = "signed_out" | "code_sent" | "pending_approval" | "allowed" | "revoked" | "expired" | "offline";
export type Allowance = {gpu_seconds_month: number | null; proposal_usd_month: number | null};
export type Usage = {gpu_seconds: number | null; proposal_usd: number | null};
export type Account = {
  state: AccountState; email?: string | null; limits?: Allowance; usage?: Usage; resets_at?: string;
  retry_after_seconds?: number; attempts_left?: number | null; requested_at?: number | null; approved?: boolean;
};
export type GpuState = {
  state: "idle" | "unconfigured" | "starting" | "ready" | "timeout" | "quota_exceeded" | "revoked" | "rejected" | "auth_required" | "offline" | "disabled" | "failed";
  resets_at?: string; scope?: "user" | "global"; busy?: boolean;
};
export type UpdateInfo = {available: boolean; latest?: string};

export class AccountRequestError extends Error {
  constructor(public code: string, public status: number, public retryAfterSeconds?: number, public attemptsLeft?: number | null) {super(code);}
}

const loopback = () => typeof window === "undefined" || ["localhost", "127.0.0.1", "[::1]", "::1"].includes(window.location.hostname);

/** Same-origin JSON request that keeps the documented extra fields of an error (retry time, attempts left). */
export async function accountRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  if (!LOCAL_MODE || !loopback()) throw new AccountRequestError("local_host_required", 403);
  const headers = new Headers(init.headers);
  if (init.body) headers.set("Content-Type", "application/json");
  if (init.method && init.method !== "GET") headers.set("X-Cytellect-Request", "1");
  let response: Response;
  try {response = await fetch(API + path, {...init, headers, credentials: "include", cache: "no-store"});}
  catch {throw new AccountRequestError("local_api_unreachable", 0);}
  if (!response.ok) {
    let body: Record<string, unknown> = {};
    try {body = await response.json();} catch {}
    const code = typeof body.detail === "string" ? body.detail : "request_failed";
    const retry = typeof body.retry_after_seconds === "number" ? body.retry_after_seconds : undefined;
    const left = typeof body.attempts_left === "number" ? body.attempts_left : undefined;
    throw new AccountRequestError(code, response.status, retry, left);
  }
  return response.json() as Promise<T>;
}
const send = <T,>(path: string, body?: unknown) => accountRequest<T>(path, {method: "POST", body: body === undefined ? undefined : JSON.stringify(body)});

export const accountApi = {
  get: () => accountRequest<Account>("/v1/account"),
  sendCode: (email: string) => send<Account>("/v1/account/code", {email}),
  verify: (code: string) => send<Account>("/v1/account/verify", {code}),
  logout: () => send<Account>("/v1/account/logout"),
  gpu: () => accountRequest<GpuState>("/v1/account/gpu"),
  startGpu: () => send<GpuState>("/v1/account/gpu"),
  firstRun: () => accountRequest<{first_run: boolean}>("/v1/local/first-run"),
  /** The installer's update route; an installation without it (404) shows nothing. */
  async update(): Promise<UpdateInfo | null> {
    try {return await accountRequest<UpdateInfo>("/v1/app/update");}
    catch (error) {if (error instanceof AccountRequestError && [404, 405].includes(error.status)) return null; throw error;}
  },
  applyUpdate: () => send<unknown>("/v1/app/update"),
};

/** Japanese date of a reset or request, in the PC's time zone unless one is given (tests). */
export function formatDate(value: string | number | null | undefined, timeZone?: string, withTime = false): string {
  if (value === null || value === undefined || value === "") return "";
  const date = new Date(typeof value === "number" ? value * 1000 : value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString("ja-JP", {month: "long", day: "numeric", ...(withTime ? {hour: "2-digit", minute: "2-digit"} : {}), timeZone});
}

export const normalizeEmail = (value: string) => value.trim().toLowerCase();
export const plausibleEmail = (value: string) => /^[^@\s]{1,64}@[^@\s.][^@\s]*\.[^@\s.]{2,63}$/.test(normalizeEmail(value)) && normalizeEmail(value).length <= 254;
export const plausibleCode = (value: string) => /^\d{6}$/.test(value.trim());

/** The month's GPU allowance is used up (the service refuses further detection until it resets). */
export function gpuQuotaReached(account: Account | null | undefined): boolean {
  const limit = account?.limits?.gpu_seconds_month, used = account?.usage?.gpu_seconds;
  return account?.state === "allowed" && typeof limit === "number" && typeof used === "number" && used >= limit;
}

/** The sentence for a used-up GPU allowance, with the date it resumes. */
export function gpuQuotaText(account: Account, timeZone?: string): string {
  const date = formatDate(account.resets_at, timeZone);
  return `今月の GPU の利用上限に達しました。${date ? `${date}から` : "来月から"}再び使えます。それまでも、このPCでの解析は使えます。`;
}

/** The header's short label. */
export function accountLabel(account: Account | null | undefined, timeZone?: string): {label: string; detail?: string} {
  switch (account?.state) {
    case "allowed": {
      const date = formatDate(account.resets_at, timeZone);
      return {label: account.email || "ログイン中", detail: gpuQuotaReached(account) ? `GPU：今月の上限${date ? `（${date}に再開）` : ""}` : "GPU・解析提案：利用可"};
    }
    case "pending_approval": return {label: account.approved ? "承認されました" : "承認待ち"};
    case "code_sent": return {label: "コードの入力待ち"};
    case "revoked": return {label: "クラウド機能：停止中"};
    case "expired": return {label: "ログイン", detail: "もう一度ログインしてください"};
    case "offline": return {label: account.email || "オフライン", detail: "クラウドに接続できません"};
    default: return {label: "ログイン"};
  }
}

/** Monthly usage beside the limits, e.g. "GPU 2 / 60 分 · 解析提案 0.40 / 5.00 ドル". */
export function usageText(account: Account): string {
  const parts: string[] = [];
  const minutes = (seconds: number | null | undefined) => seconds === null || seconds === undefined ? "–" : String(Math.ceil(seconds / 60));
  const dollars = (value: number | null | undefined) => value === null || value === undefined ? "–" : value.toFixed(2);
  if (account.limits || account.usage) {
    parts.push(`GPU ${minutes(account.usage?.gpu_seconds)} / ${minutes(account.limits?.gpu_seconds_month)} 分`);
    parts.push(`解析提案 ${dollars(account.usage?.proposal_usd)} / ${dollars(account.limits?.proposal_usd_month)} ドル`);
  }
  return parts.join(" · ");
}

const accountMessages: Record<string, string> = {
  account_email_invalid: "メールアドレスの形式を確認してください。",
  account_cloud_unreachable: "クラウドに接続できません。ネットワークを確認してもう一度試してください。",
  account_cloud_failed: "クラウドで処理できませんでした。時間をおいてもう一度試してください。",
  account_mail_failed: "メールを送れませんでした。時間をおいてもう一度試してください。",
  account_cloud_unavailable: "クラウドのログインが一時的に使えません。時間をおいてもう一度試してください。このPCでの解析は使えます。",
  account_cloud_misconfigured: "クラウドの接続先の設定が正しくありません。Cytellect をインストールし直してください。",
  account_code_expired: "コードの有効期限が切れました。「コードを再送」を押して、新しいコードを受け取ってください。",
  account_code_attempts_exhausted: "入力できる回数を超えました。「コードを再送」を押して、新しいコードを受け取ってください。",
  account_code_format_invalid: "メールに書かれた 6 桁の数字を入力してください。",
  account_code_not_requested: "コードの受け取りからやり直してください。",
  account_already_signed_in: "すでにログインしています。",
  session_required: "作業画面の接続が切れました。画面を開き直してください。",
  local_api_unreachable: "Cytellect に接続できません。起動・停止の画面が開いているか確認してください。",
};

/** "約 N 秒後"／"約 N 分後"／"約 N 時間後" for a wait of up to a day. */
export function waitText(seconds: number): string {
  if (seconds < 120) return `約 ${Math.max(1, Math.ceil(seconds))} 秒後`;
  if (seconds < 3600) return `約 ${Math.ceil(seconds / 60)} 分後`;
  return `約 ${Math.ceil(seconds / 3600)} 時間後`;
}

/** The researcher-facing sentence; the code itself is shown only under 詳細. */
export function accountErrorText(error: unknown): string {
  if (!(error instanceof AccountRequestError)) return accountMessages.local_api_unreachable;
  if (error.code === "account_rate_limited") return `しばらくしてからもう一度試してください（${waitText(error.retryAfterSeconds ?? 60)}）。このPCでの解析は続けて使えます。`;
  if (error.code === "account_code_invalid") return error.attemptsLeft === null || error.attemptsLeft === undefined
    ? "コードが一致しません。メールの 6 桁の数字を確かめてください。"
    : `コードが一致しません。あと ${error.attemptsLeft} 回入力できます。`;
  return accountMessages[error.code] || "処理できませんでした。もう一度試してください。";
}
export const errorDetail = (error: unknown) => error instanceof AccountRequestError ? error.code : "";

export type Notice = {text: string; action?: {kind: "retry" | "login"; label: string}; tone: "progress" | "ready" | "problem" | "info"};

/** What the GPU is doing and what to press next. Null when there is nothing to say. */
export function gpuNotice(gpu: GpuState | null | undefined, timeZone?: string): Notice | null {
  switch (gpu?.state) {
    case "starting": return gpu.busy ? {text: "GPU を準備しています。前の検出が終わると始まります。", tone: "progress"}
      : {text: "GPU を起動しています。止まっていた場合は 1〜2 分かかります（起動を待つ時間も利用時間に数えます）。", tone: "progress"};
    case "ready": return {text: "GPU の準備ができました。", tone: "ready"};
    case "timeout": return {text: "GPU の起動が 2 分以内に終わりませんでした。", action: {kind: "retry", label: "もう一度試す"}, tone: "problem"};
    case "quota_exceeded": {
      const date = formatDate(gpu.resets_at, timeZone);
      const whose = gpu.scope === "global" ? "クラウド GPU 全体の今月の利用上限" : "今月の GPU の利用上限";
      return {text: `${whose}に達しました。${date ? `${date}から` : "来月から"}再び使えます。それまでも、このPCでの解析は使えます。`, tone: "problem"};
    }
    case "revoked": return {text: "クラウド機能の利用が停止されています。オーナーにお問い合わせください。このPCでの解析は続けて使えます。", tone: "problem"};
    case "auth_required": return {text: "ログインの有効期限が切れました。もう一度ログインしてください。", action: {kind: "login", label: "ログイン"}, tone: "problem"};
    case "disabled": return {text: "クラウド GPU は現在停止しています。時間をおいてもう一度試してください。このPCでの解析は使えます。", action: {kind: "retry", label: "もう一度試す"}, tone: "problem"};
    case "rejected": case "failed": return {text: "GPU に接続できませんでした。", action: {kind: "retry", label: "もう一度試す"}, tone: "problem"};
    case "offline": return {text: "クラウドに接続できません。", action: {kind: "retry", label: "ネットワークを確認してもう一度試す"}, tone: "problem"};
    case "unconfigured": return {text: "Cellpose の検出は GPU で行います。使うには、クラウド機能を有効にしてください。", action: {kind: "login", label: "ログイン"}, tone: "info"};
    default: return null;
  }
}

/** The header's phase while a Cellpose detection runs. */
export function inferencePhase(gpu: GpuState | null | undefined, running: boolean): string | null {
  if (!running) return null;
  if (gpu?.state === "starting") return gpu.busy ? "GPU を準備しています" : "GPU を起動しています";
  return "検出しています";
}

/** The top banner while an access request waits for the owner. */
export function pendingNotice(account: Account | null | undefined, timeZone?: string): Notice | null {
  if (account?.state !== "pending_approval") return null;
  if (account.approved) return {text: "承認されました。ログインを続けると、GPU と解析提案が使えます。", action: {kind: "login", label: "承認されました。ログインを続ける"}, tone: "ready"};
  const when = formatDate(account.requested_at ?? null, timeZone, true);
  return {text: `承認待ち${when ? `（${when} に申請）` : ""}。オーナーが承認するとメールでお知らせします。それまでも、このPCでの解析は使えます。`, tone: "info"};
}

/** Account notices other than pending approval (revoked, expired). */
export function accountNotice(account: Account | null | undefined): Notice | null {
  if (account?.state === "revoked") return {text: "クラウド機能の利用が停止されています。オーナーにお問い合わせください。このPCでの解析は続けて使えます。", tone: "problem"};
  if (account?.state === "expired") return {text: "クラウド機能を使うには、もう一度ログインしてください。", action: {kind: "login", label: "ログイン"}, tone: "info"};
  return null;
}

/** Seconds until 「コードを再送」 is enabled. */
export const resendWait = (retryAt: number, now: number) => Math.max(0, Math.ceil((retryAt - now) / 1000));

/** Poll interval for a pending request: 45 s, within the 30–60 s the owner's approval needs. */
export const PENDING_POLL_MS = 45_000;
/** Shown beside the usage: the cloud counts the wait for the GPU to start as GPU time. */
export const GPU_TIME_NOTE = "GPU の起動を待つ時間も、GPU の利用時間に数えます。";
export const GPU_POLL_MS = 3_000;
export const FIRST_RUN_KEY = "cytellect.first-run.dismissed";
