import {measureLabel, metricTarget, metricUsesChannel, nucleusPositivity} from "./metric-catalog";
import type {ReviewTarget} from "./review-preview";

/** The measure declared primary before results are read (#257 RP-04, analysis spec `primary_outcome` 1.0.0).
 * The server records `declared_at` when the declared measure changes. */
export interface PrimaryOutcome {version?: "1.0.0"; metric: string; region_set_id: ReviewTarget; channel_id: string | null; declared_at?: number | null}

/** The declaration for a metric chosen on a subject: the region set the values come from, and the stain only where the
 * metric reads one. */
export function primaryOutcome(metric: string, subject: ReviewTarget, channel: string | null): PrimaryOutcome {
  return {version: "1.0.0", metric, region_set_id: metricTarget(metric, subject), channel_id: metricUsesChannel(metric) || nucleusPositivity(metric) ? channel : null};
}

/** How a result relates to the declaration: the primary measure, a primary measure computed before it was declared,
 * or an exploratory one (any other measure, or every measure when nothing is declared). */
export type OutcomeRole = "primary" | "primary-after" | "exploratory";
export function outcomeRole(primary: PrimaryOutcome | null | undefined, condition: {metric: string; regionSet: string; channel: string | null} | null,
  created?: number): OutcomeRole {
  if (!primary || !condition) return "exploratory";
  const same = primary.metric === condition.metric && primary.region_set_id === condition.regionSet && (primary.channel_id ?? null) === (condition.channel ?? null);
  if (!same) return "exploratory";
  return primary.declared_at && created && created < primary.declared_at ? "primary-after" : "primary";
}

/** The words of a role beside a result. */
export function outcomeRoleText(role: OutcomeRole, primaryName: string | null): string {
  if (role === "primary") return "主要指標";
  if (role === "primary-after") return "主要指標（この結果は宣言より前に計算）";
  return primaryName ? `探索的な指標（主要指標：${primaryName}）` : "探索的な指標（主要指標は未宣言）";
}

/** The declared measure in the label used everywhere else (SL-02). */
export function primaryName(primary: PrimaryOutcome | null | undefined, stainName: (channel: string) => string): string | null {
  return primary ? measureLabel(primary.metric, primary.region_set_id, primary.channel_id ? stainName(primary.channel_id) : null) : null;
}
