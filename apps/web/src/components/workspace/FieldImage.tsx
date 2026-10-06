"use client";
import {useEffect, useRef, useState} from "react";
import type { Outline } from "@/lib/workspace/model";
import styles from "./analysis-workspace.module.css";

export interface OutlineView { outline: Outline; state: "included" | "excluded" | "deleted" }

/** Display-only image with region outlines; preview pixels are never measured. */
export function FieldImage({ src, size, outlines, analyzed, selected, onSelect, label, controlledZoom, onZoomChange }: {
  src: string | null;
  size: { width: number; height: number } | null;
  outlines: OutlineView[];
  analyzed: boolean;
  selected?: number;
  onSelect: (region: number) => void;
  label: string;
  controlledZoom?: number | null;
  onZoomChange?: (value: number | null) => void;
}) {
  const viewport = useRef<HTMLDivElement>(null);
  const [localZoom, setLocalZoom] = useState<number | null>(null);
  const manualZoom = controlledZoom === undefined ? localZoom : controlledZoom;
  const setZoom = (value: number | null | ((previous: number | null) => number | null)) => {
    const next = typeof value === "function" ? value(manualZoom) : value;
    if (onZoomChange) onZoomChange(next); else setLocalZoom(next);
  };
  const [fitZoom, setFitZoom] = useState(1);
  const zoom = manualZoom ?? fitZoom;
  const imageWidth = size?.width;
  const imageHeight = size?.height;
  useEffect(() => {
    const element = viewport.current;
    if (!element || !imageWidth || !imageHeight || !src) return;
    const resize = () => setFitZoom(Math.max(0.01, Math.min(element.clientWidth / imageWidth, element.clientHeight / imageHeight)));
    const observer = new ResizeObserver(resize); observer.observe(element); resize();
    return () => observer.disconnect();
  }, [imageWidth, imageHeight, src]);
  const [showOutlines, setShowOutlines] = useState(true);
  if (!src || !size) {
    return <div className={styles.imageEmpty}><p>プレビューなし</p></div>;
  }
  return (
    <div className={styles.imageFrame}>
      <div className={styles.zoomToolbar}>
        <button type="button" onClick={() => setZoom(value => Math.max(0.1, (value ?? fitZoom) / 1.5))} aria-label="縮小">−</button>
        <button type="button" onClick={() => setZoom(1)} aria-label="原寸で表示">{Math.round(zoom * 100)}%</button>
        <button type="button" onClick={() => setZoom(value => Math.min(8, (value ?? fitZoom) * 1.5))} aria-label="拡大">＋</button>
        <button type="button" onClick={() => {setZoom(null);}}>全体を表示</button>
        {analyzed && <button type="button" aria-pressed={showOutlines} onClick={() => setShowOutlines(value => !value)}>検出領域 {outlines.filter(value => value.state !== "deleted").length}</button>}
      </div>
      <div ref={viewport} className={styles.imageViewport}>
      <svg className={styles.imageSvg} style={{width: size.width * zoom, height: size.height * zoom, minWidth: size.width * zoom}} viewBox={`0 0 ${size.width} ${size.height}`} role="img" aria-label={label}>
        <image href={src} width={size.width} height={size.height} preserveAspectRatio="xMidYMid meet" />
        {showOutlines && outlines.map(({ outline, state }) => {
          if (state === "deleted") return null;
          const id = Number(outline.id);
          const points = outline.points.map(([x, y]) => `${x},${y}`).join(" ");
          const className = [styles.outline, state === "excluded" ? styles.outlineExcluded : "", id === selected ? styles.outlineSelected : ""].join(" ");
          return (
            <polygon key={outline.id} points={points} className={className} data-region={outline.id}
              role="button" tabIndex={0} aria-label={`領域 ${id}`} onKeyDown={event => {if (event.key === "Enter" || event.key === " ") {event.preventDefault(); onSelect(id);}}} onClick={() => onSelect(id)}>
              <title>{`領域 ${outline.id}${state === "excluded" ? "（除外）" : ""}`}</title>
            </polygon>
          );
        })}
      </svg>
      </div>
      {analyzed && !outlines.length && <p className={styles.imageNote}>輪郭データなし（測定値は表・グラフで確認）</p>}
    </div>
  );
}
