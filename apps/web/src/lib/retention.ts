export type RetentionPolicy = {retention_mode?: "ttl" | "manual"; retention_hours: number | null};

export function retentionText(policy?: RetentionPolicy) {
  if (policy?.retention_mode === "manual") return "手動で削除するまで保持します。空き容量を確認し、別媒体にもバックアップしてください。";
  if (typeof policy?.retention_hours === "number" && Number.isFinite(policy.retention_hours)) return `保存期限は最後の明示的な操作から${policy.retention_hours}時間です。自動更新では延長されません。終了中に期限を迎えたデータは次回起動時に削除します。`;
  return "保存方針は接続後に表示します。必要な結果は別媒体にも保存してください。";
}

export function workspaceDeadline(expires: number | null | undefined) {
  if (expires === null) return "手動で削除するまで保持";
  return typeof expires === "number" && Number.isFinite(expires) ? `有効期限 ${new Date(expires * 1000).toLocaleString("ja-JP")}` : "保存期限を確認中";
}

export function workspaceNotExpired(expires: number | null | undefined, now = Date.now() / 1000) {
  return expires === null || (typeof expires === "number" && Number.isFinite(expires) && expires > now);
}
