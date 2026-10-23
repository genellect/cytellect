export type PaidFeature = { enabled: boolean; used: number; limit: number };
export type PaidAccess = {
  activated: boolean; service_configured: boolean; reachable: boolean | null; revoked: boolean;
  label: string | null; month: string | null; cellpose: PaidFeature | null; proposals: PaidFeature | null;
};

/** One line per paid feature for the local "有料機能" card. */
export function featureText(feature: PaidFeature | null, unit: string): string {
  if (!feature) return "確認できません";
  if (!feature.enabled) return "現在は提供されていません";
  const left = Math.max(0, feature.limit - feature.used);
  return left ? `利用できます（今月の残り ${left} ${unit}）` : `今月の上限に達しました（${feature.limit} ${unit}）`;
}
