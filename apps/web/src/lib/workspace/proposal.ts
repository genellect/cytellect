/**
 * Rule-based analysis proposal from confirmed channel roles (workspace redesign).
 *
 * A proposal combines registered recipes only. It never invents a channel, never
 * treats an index token as a stain and never proposes inference without
 * experimental units. The optional LLM service may later draft the same shape;
 * the API remains the owner of validation and execution.
 */
import type { ChannelDefinition, Grouping } from "./grouping";
import { unresolvedChannels } from "./grouping";

export type RecipeId = "nuclear-intensity" | "nuclear-ncl" | "supplied-regions" | "measured-table";

export interface Metric { key: string; label: string; unit: string; channel?: string }

export interface ProposedFigure {
  id: string;
  kind: "field-distribution" | "unit-comparison";
  metric: string;
  /** What one point represents; always stated on the figure. */
  point: "region" | "experimental unit";
}

export interface Proposal {
  recipe: RecipeId | null;
  fieldCount: number;
  nuclearChannel: ChannelDefinition | null;
  measuredChannels: ChannelDefinition[];
  regions: string[];
  metrics: Metric[];
  background: "raw-only" | "automatic-candidate" | "user-roi";
  statistics: { kind: "descriptive" } | { kind: "comparison"; test: "welch-t" | "welch-anova" };
  figures: ProposedFigure[];
  unresolved: string[];
  notes: string[];
}

export interface DesignInfo {
  /** Condition per field key; absent when unknown. */
  conditions: Record<string, string | undefined>;
  /** Independent experimental unit per field key; absent when unknown. */
  units: Record<string, string | undefined>;
}

const AREA: Metric = { key: "area_px", label: "核面積", unit: "px²" };

export function buildProposal(grouping: Grouping, design: DesignInfo = { conditions: {}, units: {} }): Proposal {
  const unresolved: string[] = [];
  const notes: string[] = [];
  for (const channel of unresolvedChannels(grouping)) unresolved.push(`チャンネル「${channel.token}」の染色と役割`);
  const nuclear = grouping.channels.filter((channel) => channel.role === "nuclear");
  const measured = grouping.channels.filter((channel) => channel.role === "measure" && channel.stain);
  if (nuclear.length > 1) unresolved.push("核検出に使うチャンネルを1つに指定");
  const nuclearChannel = nuclear.length === 1 ? nuclear[0] : null;
  const hasNcl = measured.some((channel) => channel.stain === "NCL");
  let recipe: RecipeId | null = null;
  const regions: string[] = [];
  const metrics: Metric[] = [];
  if (nuclearChannel && !unresolved.length) {
    recipe = hasNcl ? "nuclear-ncl" : "nuclear-intensity";
    regions.push("核");
    metrics.push(AREA);
    if (hasNcl) {
      regions.push("核小体候補", "核質");
      const ncl = measured.find((channel) => channel.stain === "NCL")!;
      metrics.push({ key: `${ncl.token}:log2_nucleoplasm_over_nucleoli`, label: "NCL 核質/核小体 log₂比", unit: "", channel: ncl.token });
      notes.push("核小体候補はNCL自身から定義します。条件ごとの検出率と核小体面積を併せて表示します。");
    }
    for (const channel of measured) {
      if (channel.stain === "NCL") continue;
      metrics.push({ key: `${channel.token}:mean_raw`, label: `${channel.stain} 平均輝度（補正前）`, unit: "", channel: channel.token });
    }
  } else if (!nuclearChannel && !unresolved.length) {
    unresolved.push("核染色チャンネル、または既存の領域マスク");
  }
  const known = grouping.fields.every((field) => design.conditions[field.key] && design.units[field.key]);
  const conditions = new Set(grouping.fields.map((field) => design.conditions[field.key]).filter(Boolean));
  const statistics: Proposal["statistics"] = known && conditions.size >= 2
    ? { kind: "comparison", test: conditions.size === 2 ? "welch-t" : "welch-anova" }
    : { kind: "descriptive" };
  if (statistics.kind === "descriptive") notes.push("群と独立した実験単位が未設定のため、視野ごとの分布を作成します。比較はグラフから設定できます。");
  const figures: ProposedFigure[] = metrics.map((metric) => ({
    id: `distribution:${metric.key}`, kind: "field-distribution", metric: metric.key, point: "region",
  }));
  if (statistics.kind === "comparison") {
    figures.push(...metrics.map((metric) => ({
      id: `comparison:${metric.key}`, kind: "unit-comparison" as const, metric: metric.key, point: "experimental unit" as const,
    })));
  }
  return {
    recipe, fieldCount: grouping.fields.length, nuclearChannel, measuredChannels: measured, regions, metrics,
    background: "raw-only", statistics, figures, unresolved, notes,
  };
}
