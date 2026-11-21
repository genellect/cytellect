import {metricTarget, metricUsesChannel, nucleusPositivity} from "./metric-catalog";
import type {ReviewTarget} from "./review-preview";

/** The measure declared primary before results are read (#257 RP-04, analysis spec `primary_outcome` 1.0.0).
 * The server records `declared_at` when the declared measure changes; the browser never sets it. */
export interface PrimaryOutcome {version?: "1.0.0"; metric: string; region_set_id: ReviewTarget; channel_id: string | null; declared_at?: number | null}
export interface OutcomeCondition {metric: string; regionSet: string; channel: string | null}

/** The declaration for a metric chosen on a subject: the region set its values come from, and the stain only where
 * the metric reads one. */
export function primaryOutcome(metric: string, subject: ReviewTarget, channel: string | null): PrimaryOutcome {
  return {version: "1.0.0", metric, region_set_id: metricTarget(metric, subject),
    channel_id: metricUsesChannel(metric) || nucleusPositivity(metric) ? channel : null};
}

export function samePrimary(primary: PrimaryOutcome | null | undefined, condition: OutcomeCondition | null): boolean {
  return !!primary && !!condition && primary.metric === condition.metric && primary.region_set_id === condition.regionSet
    && (primary.channel_id ?? null) === (condition.channel ?? null);
}

/** 主要 or 探索 beside a result, only when a declaration exists (none otherwise).
 * A result is primary only when it is the declared measure and the server calculated it after the declaration:
 * `calculatedAt` is the server's calculation time of the statistics (for a re-drawn figure, the original statistics),
 * `undefined` for a choice not yet calculated. A result without a recorded time is never primary.
 * `postHoc`: a result of the declared measure existed before the declaration (see declaredAfterResults); then no
 * result of that measure is primary, including one calculated again after the declaration. */
export type OutcomeRole = "primary" | "exploratory" | null;
export function outcomeRole(primary: PrimaryOutcome | null | undefined, condition: OutcomeCondition | null,
  calculatedAt?: number | null, postHoc = false): OutcomeRole {
  if (!primary) return null;
  if (!samePrimary(primary, condition) || postHoc) return "exploratory";
  if (calculatedAt === undefined) return "primary";
  return calculatedAt !== null && !!primary.declared_at && calculatedAt > primary.declared_at ? "primary" : "exploratory";
}

/** Whether the declaration came after a result of the declared measure was already calculated (or one whose time is
 * not recorded): 条件を選ぶ -> 結果 -> 宣言 -> 計算し直す must not make the declaration a prior one. */
export function declaredAfterResults(primary: PrimaryOutcome | null | undefined,
  results: Array<{condition: OutcomeCondition | null; calculatedAt: number | null}>): boolean {
  if (!primary) return false;
  return results.some(result => samePrimary(primary, result.condition)
    && (result.calculatedAt === null || !primary.declared_at || result.calculatedAt <= primary.declared_at));
}
export const OUTCOME_ROLE_LABELS: Record<"primary" | "exploratory", string> = {primary: "主要", exploratory: "探索"};
