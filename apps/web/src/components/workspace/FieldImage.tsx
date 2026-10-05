"use client";
import type { Outline } from "@/lib/workspace/model";
import styles from "./analysis-workspace.module.css";

export interface OutlineView { outline: Outline; state: "included" | "excluded" | "deleted" }

/** Display-only image with region outlines; preview pixels are never measured. */
export function FieldImage({ src, size, outlines, analyzed, selected, onSelect, label }: {
  src: string | null;
  size: { width: number; height: number } | null;
  outlines: OutlineView[];
  analyzed: boolean;
  selected?: number;
  onSelect: (region: number) => void;
  label: string;
}) {
  if (!src || !size) {
    return <div className={styles.imageEmpty}><p>プレビューなし</p></div>;
  }
  return (
    <div className={styles.imageFrame}>
      <svg className={styles.imageSvg} viewBox={`0 0 ${size.width} ${size.height}`} role="img" aria-label={label}>
        <image href={src} width={size.width} height={size.height} preserveAspectRatio="none" />
        {outlines.map(({ outline, state }) => {
          if (state === "deleted") return null;
          const id = Number(outline.id);
          const points = outline.points.map(([x, y]) => `${x},${y}`).join(" ");
          const className = [styles.outline, state === "excluded" ? styles.outlineExcluded : "", id === selected ? styles.outlineSelected : ""].join(" ");
          return (
            <polygon key={outline.id} points={points} className={className} data-region={outline.id}
              onClick={() => onSelect(id)}>
              <title>{`領域 ${outline.id}${state === "excluded" ? "（除外）" : ""}`}</title>
            </polygon>
          );
        })}
      </svg>
      {analyzed && !outlines.length && <p className={styles.imageNote}>輪郭データなし（測定値は表・グラフで確認）</p>}
    </div>
  );
}
