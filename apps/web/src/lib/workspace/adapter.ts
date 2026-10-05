/**
 * Communication boundary of the single workspace.
 *
 * The prototype adapter replays recorded public BBBC013 outputs so that the
 * interaction can be reviewed before the API is connected (redesign step 1–2).
 * It performs no detection or measurement; its summaries stand in for API
 * responses and are display values for the prototype only.
 */
import type { AddedFile } from "./grouping";
import type { FieldResult, Region, WorkspaceState } from "./model";
import { regionState } from "./model";

export interface ExportLink { label: string; href?: string; detail?: string; reason?: string }

export interface WorkspaceAdapter {
  kind: "prototype" | "api";
  loadSample(): Promise<{ name: string; files: AddedFile[]; attribution: string }>;
  preview(field: string, token: string): string | null;
  size(field: string): { width: number; height: number } | null;
  run(field: string): Promise<FieldResult>;
  exports(state: WorkspaceState): ExportLink[];
  label(field: string): string;
}

interface SampleChannel { source_name: string; stain: string; preview: string; recorded_role: string }
interface SampleField {
  well: string; width: number; height: number; channels: SampleChannel[];
  measurements: { region_id: number; area_px: number; gfp_mean_raw: number; gfp_integral_raw: number }[]; outlines: { id: string; points: [number, number][] }[] | null;
}
interface Sample { dataset: string; attribution: string; source: string; license: string; fields: SampleField[] }

const SAMPLE_URL = "/prototype/bbbc013/fields.json";
const FOLDER = "BBBC013";

function channelToken(channel: SampleChannel): string {
  return channel.source_name.split(/[-_ .]+/)[0].toLowerCase();
}

function fieldKey(sourceName: string): string {
  // Mirrors grouping: "Channel1-01-A-01.BMP" → folder + "01-A-01".
  const stem = sourceName.replace(/\.[^.]+$/, "");
  return `${FOLDER}/${stem.split(/[-_ .]+/).filter((token) => !/^channel\d+$/i.test(token)).join("-")}`;
}

export function createPrototypeAdapter(options: { delayMs?: number; fetcher?: typeof fetch } = {}): WorkspaceAdapter {
  const delay = options.delayMs ?? 1400;
  const fetcher = options.fetcher ?? fetch;
  let sample: Sample | null = null;
  const byKey = new Map<string, SampleField>();
  const ensure = async () => {
    if (!sample) {
      const response = await fetcher(SAMPLE_URL);
      if (!response.ok) throw new Error("公開画像を読み込めません");
      sample = await response.json() as Sample;
      for (const field of sample.fields) byKey.set(fieldKey(field.channels[0].source_name), field);
    }
    return sample;
  };
  return {
    kind: "prototype",
    async loadSample() {
      const data = await ensure();
      const files = data.fields.flatMap((field) => field.channels.map((channel) => ({
        path: `${FOLDER}/${channel.source_name}`, size: 0,
      })));
      return { name: "解析例（BBBC013）", files, attribution: `${data.attribution} ${data.license}` };
    },
    preview(field, token) {
      return byKey.get(field)?.channels.find((item) => channelToken(item) === token)?.preview ?? null;
    },
    size(field) {
      const sampleField = byKey.get(field);
      return sampleField ? { width: sampleField.width, height: sampleField.height } : null;
    },
    label(field) {
      const sampleField = byKey.get(field);
      return sampleField ? `ウェル ${sampleField.well}` : field.split("/").pop() ?? field;
    },
    async run(field) {
      await ensure();
      await new Promise((resolve) => setTimeout(resolve, delay));
      const sampleField = byKey.get(field);
      if (!sampleField) throw new Error("この画像はプロトタイプでは解析できません");
      // Recorded values are keyed by the channel token the grouping produced.
      const measured = sampleField.channels.find((item) => item.recorded_role === "gfp");
      const token = measured ? channelToken(measured) : null;
      const measurements = sampleField.measurements.map((row) => {
        const values: Region = { region_id: row.region_id, area_px: row.area_px };
        if (token) {
          values[`${token}:mean_raw`] = row.gfp_mean_raw;
          values[`${token}:integral_raw`] = row.gfp_integral_raw;
        }
        return values;
      });
      return { measurements, outlines: sampleField.outlines };
    },
    exports(state) {
      const corrected = state.corrections.length > 0;
      const reason = corrected ? "修正後の書き出しはプロトタイプでは未対応" : undefined;
      return [
        { label: "SVG", detail: "編集可能なグラフ", href: corrected ? undefined : "/marketing/figure-public.svg", reason },
        { label: "CSV", detail: "全領域の測定値", href: corrected ? undefined : "/marketing/figure-public.csv", reason },
        { label: "図の説明", detail: "凡例・解析条件", href: corrected ? undefined : "/marketing/figure-caption.md", reason },
        { label: "PDF", reason: "プロトタイプでは未対応" },
      ];
    },
  };
}

export interface DistributionPoint { field: string; region: number; value: number; state: "included" | "excluded" }
export interface FieldSummary { field: string; n: number; excluded: number; median: number | null; q1: number | null; q3: number | null }

function quantile(sorted: number[], p: number): number {
  // Linear interpolation h=(n−1)p, matching the API's descriptive protocol.
  const h = (sorted.length - 1) * p;
  const low = Math.floor(h);
  return sorted[low] + (h - low) * ((sorted[Math.ceil(h)] ?? sorted[low]) - sorted[low]);
}

/** Prototype stand-in for the API's saved descriptive summary of existing values. */
export function fieldDistribution(state: WorkspaceState, metric: string): { points: DistributionPoint[]; summaries: FieldSummary[] } {
  const points: DistributionPoint[] = [];
  const summaries: FieldSummary[] = [];
  const order = state.figure.order.length ? state.figure.order : Object.keys(state.results);
  for (const field of order) {
    const result = state.results[field];
    if (!result) continue;
    const values: number[] = [];
    let excluded = 0;
    for (const row of result.measurements) {
      const value = row[metric];
      if (typeof value !== "number" || !Number.isFinite(value)) continue;
      const status = regionState(state, field, row.region_id);
      if (status === "deleted") continue;
      if (status === "excluded") excluded += 1; else values.push(value);
      points.push({ field, region: row.region_id, value, state: status });
    }
    values.sort((a, b) => a - b);
    summaries.push({ field, n: values.length, excluded, median: values.length ? quantile(values, .5) : null,
      q1: values.length ? quantile(values, .25) : null, q3: values.length ? quantile(values, .75) : null });
  }
  return { points, summaries };
}
