export const LOCAL_MODE = process.env.NEXT_PUBLIC_CYTELLECT_WEB_MODE === "local";
export const API = LOCAL_MODE ? "" : process.env.NEXT_PUBLIC_API_ORIGIN || (process.env.NODE_ENV === "development" ? "http://localhost:8000" : "");
export const API_CONFIGURED = LOCAL_MODE || !!API;
export class ApiError extends Error { constructor(public code: string, public status: number) { super(code); } }
export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
 if(!API_CONFIGURED) throw new ApiError("server_not_configured",503);
 if(LOCAL_MODE && typeof window!=="undefined" && !["localhost","127.0.0.1","[::1]","::1"].includes(window.location.hostname)) throw new ApiError("local_host_required",403);
 const headers = new Headers(options.headers);
 if (options.body && !(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
 if (options.method && !["GET", "HEAD"].includes(options.method)) headers.set("X-Cytellect-Request", "1");
 const result = await fetch(API + path, {...options, headers, credentials: "include", cache: "no-store"});
 if (!result.ok) {
   let code = "request_failed";
   try { const value = await result.json(); if (typeof value.detail === "string") code = value.detail; } catch {}
   throw new ApiError(code, result.status);
 }
 return result.json() as Promise<T>;
}
export const post = <T,>(path: string, body?: unknown) => request<T>(path, {method:"POST",body:body === undefined ? undefined : JSON.stringify(body)});
export async function fetchBlob(path: string, signal?: AbortSignal): Promise<Blob> {
 if(!API_CONFIGURED) throw new ApiError("server_not_configured",503);
 if(LOCAL_MODE && typeof window!=="undefined" && !["localhost","127.0.0.1","[::1]","::1"].includes(window.location.hostname)) throw new ApiError("local_host_required",403);
 const result = await fetch(API + path, {credentials:"include",cache:"no-store",signal});
 if (!result.ok) throw new ApiError("artifact_unavailable", result.status);
 return result.blob();
}
export async function download(path: string, name: string) {
 const blob = await fetchBlob(path); const url = URL.createObjectURL(blob);
 const anchor = document.createElement("a"); anchor.href=url;anchor.download=name;anchor.click();
 setTimeout(() => URL.revokeObjectURL(url),1000);
}
const messages:Record<string,string> = {
 local_host_required:"ローカル版はランチャーから開いたワークスペースで使用してください。",
 fiji_detection_capacity_exceeded:"この画像は現在の自動検出の上限を超えています（1辺2048 px、270万画素）。原画像は変更されていません。",
 recipe_required_channels_missing:"このレシピに必要なチャンネルが不足しています。NCL解析には核染色とNCL、GFP解析には核染色とGFPが必要です。",
 outcome_cannot_be_its_own_gfp_covariate:"GFPを目的変数と説明変数の両方に指定できません。独立実験単位での比較を選択してください。",
 invitation_invalid:"招待コードが無効、期限切れ、または使用済みです。",
 session_required:"セッションが失効しました。新しい招待で接続してください。",
 too_many_attempts:"試行が多いため、1分後にお試しください。",
 confirm_background_for_every_field:"すべての視野で背景ROIを描いて確認してください。",
 demo_accepts_synthetic_only:"この環境は合成データ専用です。",
 unsupported_or_invalid_image:"画像の軸・bit深度・サイズ・チャンネルの対応を確認してください。",
 stale_revision:"別の解析版が採用されています。最新の版へ戻って修正してください。",
 review_required:"品質確認を完了してから統計を実行してください。",
 nucleolar_resegmentation_required:"核の修正後、核小体候補を再検出して確認してください。",
 resolve_or_explicitly_exclude_failed_fields:"失敗した視野を解決するか、理由付きで除外してください。",
 origin_or_csrf_invalid:"UIとAPIの接続元設定が一致しません。管理者に確認してください。",
 field_upload_limit:"1視野のアップロード上限を超えています。",
 workspace_limit:"作業の容量または視野数の上限を超えています。",
 invalid_analysis_input:"入力内容や領域の重なりを確認してください。",
 workspace_not_found:"作業の保存期限が切れたか、アクセス権がありません。",
 fiji_not_configured:"Fiji解析環境が未設定です。合成データでは操作を確認できます。",
};
export const errorCodeMessage = (code:string):string => messages[code] || code;
export function errorMessage(error:unknown) { return error instanceof ApiError ? (messages[error.code] || `処理できませんでした（${error.code}）。入力条件を確認してください。`) : "APIに接続できません。解析サーバーの起動と接続先を確認してください。"; }
