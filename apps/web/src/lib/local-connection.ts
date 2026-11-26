/**
 * The local build's connection to the PC's own service (#284 W9). The API client reports what each
 * request met; the workspace shows one notice for it and re-reads what was saved once it is back.
 *
 * - `unreachable`: no answer at all (the request failed before or after it was sent; the launcher may be closed).
 * - `session`: the service answered 401 and a new session did not resolve it (one renewal per request).
 * - `origin`: the page is not the PC's own address (403 `local_origin_required`, or not loopback).
 */
export type LocalConnection = "connected" | "unreachable" | "session" | "origin";

let current: LocalConnection = "connected";
const listeners = new Set<() => void>();

export function reportConnection(next: LocalConnection) {
  if (next === current) return;
  current = next;
  for (const listener of [...listeners]) listener();
}
export const localConnection = () => current;
export function subscribeConnection(listener: () => void) {
  listeners.add(listener);
  return () => {listeners.delete(listener);};
}

/** While the service does not answer, the workspace checks again at this interval (and on 「再接続」). */
export const RECONNECT_INTERVAL_MS = 5000;

/** What the connection notice says: a state (UC-02), at most one reason sentence, and the button if one helps. */
export function connectionNotice(state: LocalConnection, checking = false): {status: string; reason: string | null; action: "再接続" | null} | null {
  switch (state) {
    case "unreachable": return {status: `ローカルのサービス：${checking ? "再接続中" : "接続なし"}`,
      reason: "再開には、デスクトップの「Cytellect」の起動が必要です。", action: "再接続"};
    case "session": return {status: `作業画面のセッション：${checking ? "再接続中" : "終了"}`, reason: null, action: "再接続"};
    case "origin": return {status: "ローカルのサービス：接続の拒否",
      reason: "作業画面には、デスクトップの「Cytellect」から開いた画面が必要です。", action: null};
    default: return null;
  }
}

/** `GET /v1/local/previous-stop`: the previous launcher run's end, when it was abnormal. */
export type PreviousStop = {abnormal: boolean; reason: string | null; time: number | null};
/** The launcher's reason labels (`STOP_LABELS` in services/api/src/cytellect_api/local.py); a test keeps them equal. */
export const STOP_LABELS: Record<string, string> = {
  local_worker_stopped: "計算処理の停止", local_worker_start_failed: "計算処理の起動失敗",
  parent_process_gone: "起動元のプロセスの終了", server_stopped: "サービスの停止",
  unhandled_exception: "予期しないエラー", unrecorded: "理由の記録なし",
};
/** One line about an abnormal previous stop, in the PC's time zone unless one is given (tests); null otherwise. */
export function previousStopText(value: PreviousStop | null | undefined, timeZone?: string): string | null {
  if (!value?.abnormal) return null;
  const line = `前回の停止：${STOP_LABELS[value.reason ?? ""] ?? STOP_LABELS.unrecorded}`;
  if (!value.time) return line;
  const parts = Object.fromEntries(new Intl.DateTimeFormat("ja-JP", {month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit", hourCycle: "h23", timeZone})
    .formatToParts(new Date(value.time * 1000)).map(part => [part.type, part.value]));
  return `${line} · ${parts.month}月${parts.day}日 ${parts.hour}:${parts.minute}`;
}
