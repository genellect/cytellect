"use client";

import {useEffect, useId, useRef, useState} from "react";
import styles from "./review-plot.module.css";

export interface PlotObservation {
  fieldId: string;
  fieldLabel: string;
  regionId: number;
  value: number;
}

interface Props {
  points: PlotObservation[];
  yLabel: string;
  xLabel: string;
  yMin?: number;
  yMax?: number;
  onSelect?: (point: PlotObservation) => void;
  selected?: {fieldId: string; regionId: number};
}

function offset(point: PlotObservation) {
  let hash = 2166136261;
  for (const char of `${point.fieldId}:${point.regionId}`) hash = Math.imul(hash ^ char.charCodeAt(0), 16777619);
  return ((hash >>> 0) / 4294967295 - 0.5) * 36;
}

const number = (value: number) => Number(value.toPrecision(4)).toLocaleString("en-US", {maximumSignificantDigits: 4});

/** Inspection preview of saved observations; no aggregation or statistical inference. */
export function ReviewMeasurementPlot({points, yLabel, xLabel, yMin, yMax, onSelect, selected}: Props) {
  const host = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({width: 640, height: 400});
  const [focus, setFocus] = useState(0);
  const clip = useId().replaceAll(":", "");
  useEffect(() => {
    const element = host.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => {
      if (entry.contentRect.width > 0 && entry.contentRect.height > 0) {
        setSize({width: entry.contentRect.width, height: entry.contentRect.height});
      }
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const valid = points.filter(point => Number.isFinite(point.value));
  const fields = [...new Map(valid.map(point => [point.fieldId, point.fieldLabel])).entries()];
  let low = Infinity, high = -Infinity;
  for (const point of valid) {low = Math.min(low, point.value); high = Math.max(high, point.value);}
  const padding = high > low ? (high - low) * 0.08 : Math.max(Math.abs(low) * 0.08, 1);
  const minimum = yMin ?? (low - padding);
  const maximum = yMax ?? (high + padding);
  const axisValid = Number.isFinite(minimum) && Number.isFinite(maximum) && minimum < maximum;
  const shown = axisValid ? valid.filter(point => point.value >= minimum && point.value <= maximum) : [];
  const width = Math.max(size.width, 180 + fields.length * 104);
  const height = Math.max(size.height, 300);
  const left = 86, right = width - 26, top = 24, bottom = height - 90;
  const x = (id: string) => left + (fields.findIndex(([field]) => field === id) + 0.5) * (right - left) / fields.length;
  const y = (value: number) => bottom - (value - minimum) / (maximum - minimum) * (bottom - top);
  const focusedIndex = Math.min(focus, Math.max(0, shown.length - 1));

  return <div ref={host} className={styles.root}>
    {!valid.length ? <p className={styles.empty}>この項目の測定値はありません</p>
      : !axisValid ? <p className={styles.empty}>Y軸の最小値を最大値より小さくしてください</p>
      : <div className={styles.scroll}>
        <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className={styles.figure} aria-label={`${yLabel}・視野別の測定値`}>
          <title>{yLabel}・視野別の測定値</title>
          <desc>各点は保存された1領域の測定値です。左右の矢印キーで点を移動し、Enterで元の領域を表示します。</desc>
          <defs><clipPath id={clip}><rect x={left} y={top} width={right - left} height={bottom - top}/></clipPath></defs>
          {[0, 1, 2, 3, 4].map(index => {
            const value = minimum + (maximum - minimum) * index / 4;
            return <g key={index}><line className={styles.tick} x1={left - 5} y1={y(value)} x2={left} y2={y(value)}/><text className={styles.tickLabel} x={left - 10} y={y(value)} textAnchor="end" dominantBaseline="middle">{number(value)}</text></g>;
          })}
          <path className={styles.axis} d={`M ${left} ${top} V ${bottom} H ${right}`}/>
          {fields.map(([id, label]) => <g key={id}><line className={styles.tick} x1={x(id)} y1={bottom} x2={x(id)} y2={bottom + 5}/><text className={styles.tickLabel} x={x(id)} y={bottom + 23} textAnchor="middle"><title>{label}</title>{label.length > 13 ? `${label.slice(0, 12)}…` : label}</text></g>)}
          <text className={styles.axisLabel} x={(left + right) / 2} y={height - 17} textAnchor="middle">{xLabel}</text>
          <text className={styles.axisLabel} transform={`translate(20 ${(top + bottom) / 2}) rotate(-90)`} textAnchor="middle">{yLabel}</text>
          <g clipPath={`url(#${clip})`}>
            {shown.map((point, index) => {
              const active = selected?.fieldId === point.fieldId && selected.regionId === point.regionId;
              return <circle key={`${point.fieldId}:${point.regionId}`} cx={x(point.fieldId) + offset(point)} cy={y(point.value)} r={active ? 5 : 3.5}
                className={`${styles.point} ${active ? styles.selected : ""}`} role={onSelect ? "button" : undefined}
                tabIndex={onSelect && index === focusedIndex ? 0 : -1} aria-label={`${point.fieldLabel}・領域 ${point.regionId}・${yLabel} ${point.value}`}
                aria-pressed={onSelect ? !!active : undefined} onClick={() => onSelect?.(point)} onFocus={() => setFocus(index)}
                onKeyDown={event => {
                  if (!onSelect) return;
                  if (event.key === "Enter" || event.key === " ") {event.preventDefault(); onSelect(point);}
                  if (event.key === "ArrowRight" || event.key === "ArrowLeft") {
                    event.preventDefault();
                    const next = (index + (event.key === "ArrowRight" ? 1 : -1) + shown.length) % shown.length;
                    setFocus(next);
                    const sibling = event.currentTarget.parentElement?.children[next] as SVGElement | undefined;
                    sibling?.focus();
                  }
                }}><title>{point.fieldLabel} · 領域 {point.regionId} · {point.value}</title></circle>;
            })}
          </g>
        </svg>
      </div>}
    {(valid.length !== points.length || (axisValid && shown.length !== valid.length)) && <p className={styles.note}>
      {valid.length !== points.length && `非数値 ${points.length - valid.length} 件`}
      {valid.length !== points.length && axisValid && shown.length !== valid.length && " · "}
      {axisValid && shown.length !== valid.length && `表示範囲外 ${valid.length - shown.length} 件`}
    </p>}
  </div>;
}
