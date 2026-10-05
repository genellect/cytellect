"use client";
import type { DistributionPoint, FieldSummary } from "@/lib/workspace/adapter";
import styles from "./analysis-workspace.module.css";

const SCALE = 4; // SVG units per millimetre for the on-screen preview.

function ticks(min: number, max: number, count = 5): number[] {
  if (!(max > min)) return [min];
  const raw = (max - min) / count;
  const magnitude = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 5, 10].map((factor) => factor * magnitude).find((value) => value >= raw) ?? raw;
  const result: number[] = [];
  for (let value = Math.ceil(min / step) * step; value <= max + step * 1e-9; value += step) result.push(Number(value.toPrecision(12)));
  return result;
}

/** Display-only jitter from the region identity; values and selection are unchanged. */
function jitter(region: number): number {
  return (((region * 2654435761) >>> 0) % 1000) / 1000 - 0.5;
}

function format(value: number): string {
  return Math.abs(value) >= 1000 ? value.toFixed(0) : Number(value.toPrecision(3)).toString();
}

export function FieldFigure({ points, summaries, labels, metricLabel, widthMm, heightMm, yLabel, selected, onSelect }: {
  points: DistributionPoint[];
  summaries: FieldSummary[];
  labels: Record<string, string>;
  metricLabel: string;
  widthMm: number;
  heightMm: number;
  yLabel: string;
  selected?: { field: string; region: number };
  onSelect: (field: string, region: number) => void;
}) {
  const width = widthMm * SCALE;
  const height = heightMm * SCALE;
  const margin = { left: 58, right: 12, top: 14, bottom: 46 };
  const values = points.map((point) => point.value);
  const low = values.length ? Math.min(0, ...values) : 0;
  const high = values.length ? Math.max(...values) : 1;
  const axis = ticks(low, high);
  const top = Math.max(high, axis.at(-1) ?? high);
  const y = (value: number) => margin.top + (height - margin.top - margin.bottom) * (1 - (value - low) / ((top - low) || 1));
  const band = (width - margin.left - margin.right) / Math.max(summaries.length, 1);
  const x = (index: number) => margin.left + band * (index + 0.5);
  const position = new Map(summaries.map((summary, index) => [summary.field, index]));
  return (
    <figure className={styles.figure} style={{ maxWidth: `${widthMm * 6 + 34}px` }}>
      <svg viewBox={`0 0 ${width} ${height}`} className={styles.figureSvg} role="img"
        aria-label={`${metricLabel}の視野ごとの分布。1点は1領域です。`}>
        <line x1={margin.left} x2={margin.left} y1={margin.top} y2={height - margin.bottom} className={styles.axis} />
        {axis.map((value) => (
          <g key={value}>
            <line x1={margin.left - 4} x2={margin.left} y1={y(value)} y2={y(value)} className={styles.axis} />
            <text x={margin.left - 7} y={y(value) + 3.5} textAnchor="end" className={styles.tick}>{format(value)}</text>
          </g>
        ))}
        <text transform={`translate(14 ${(height - margin.bottom + margin.top) / 2}) rotate(-90)`} textAnchor="middle" className={styles.axisLabel}>
          {yLabel || metricLabel}
        </text>
        {summaries.map((summary, index) => (
          <g key={summary.field}>
            <text x={x(index)} y={height - margin.bottom + 16} textAnchor="middle" className={styles.tick}>{labels[summary.field] ?? summary.field}</text>
            <text x={x(index)} y={height - margin.bottom + 30} textAnchor="middle" className={styles.count}>n = {summary.n}{summary.excluded ? `（除外 ${summary.excluded}）` : ""}</text>
            {summary.q1 !== null && summary.q3 !== null && (
              <rect x={x(index) - band * 0.28} width={band * 0.56} y={y(summary.q3)} height={Math.max(1, y(summary.q1) - y(summary.q3))} className={styles.iqr} />
            )}
            {summary.median !== null && <line x1={x(index) - band * 0.32} x2={x(index) + band * 0.32} y1={y(summary.median)} y2={y(summary.median)} className={styles.median} />}
          </g>
        ))}
        {points.map((point) => {
          const index = position.get(point.field) ?? 0;
          const isSelected = selected?.field === point.field && selected.region === point.region;
          return (
            <circle key={`${point.field}:${point.region}`} cx={x(index) + jitter(point.region) * band * 0.5} cy={y(point.value)} r={isSelected ? 5 : 2.4}
              className={[styles.point, point.state === "excluded" ? styles.pointExcluded : "", isSelected ? styles.pointSelected : ""].join(" ")}
              data-field={point.field} data-region={point.region} onClick={() => onSelect(point.field, point.region)}>
              <title>{`${labels[point.field] ?? point.field} · 領域 ${point.region}: ${format(point.value)}`}</title>
            </circle>
          );
        })}
      </svg>
      <figcaption>1点は1領域です。帯は四分位範囲、横線は視野内の中央値です。視野数・領域数は独立した実験反復数ではありません。</figcaption>
    </figure>
  );
}
