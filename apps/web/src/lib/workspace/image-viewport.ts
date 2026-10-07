import type {Outline} from "./model";

type Contour = {outline: Outline; state: "included" | "excluded" | "deleted"};
export type RegionAnnotation = {id: number; x: number; y: number};

/** CSS-pixel fit with a small rounding allowance. Scientific coordinates are untouched. */
export function imageFit(width: number, height: number, viewportWidth: number, viewportHeight: number) {
  if (Math.min(width, height, viewportWidth, viewportHeight) <= 0) return 1;
  return Math.max(0.001, Math.min(Math.max(1, viewportWidth - 2) / width, Math.max(1, viewportHeight - 2) / height));
}

/** Label anchors use even-odd interior spans, so holes do not acquire cell numbers. */
export function regionAnnotations(contours: readonly Contour[]): RegionAnnotation[] {
  const groups = new Map<number, Outline[]>();
  for (const {outline, state} of contours) {
    if (state === "deleted" || outline.points.length < 3) continue;
    const id = Number(outline.id);
    if (!Number.isFinite(id)) continue;
    groups.set(id, [...(groups.get(id) ?? []), outline]);
  }
  return [...groups].flatMap(([id, rings]) => {
    const ys = rings.flatMap(ring => ring.points.map(point => point[1]));
    const lo = Math.min(...ys), hi = Math.max(...ys);
    let best: RegionAnnotation | undefined;
    let widest = 0;
    for (const fraction of [0.5, 0.35, 0.65, 0.2, 0.8]) {
      const y = lo + (hi - lo) * fraction;
      const crossings: number[] = [];
      for (const ring of rings) for (let index = 0; index < ring.points.length; index++) {
        const [x1, y1] = ring.points[index], [x2, y2] = ring.points[(index + 1) % ring.points.length];
        if ((y1 > y) !== (y2 > y)) crossings.push(x1 + (y - y1) * (x2 - x1) / (y2 - y1));
      }
      crossings.sort((a, b) => a - b);
      for (let index = 0; index + 1 < crossings.length; index += 2) {
        const width = crossings[index + 1] - crossings[index];
        if (width > widest) {widest = width; best = {id, x: (crossings[index] + crossings[index + 1]) / 2, y};}
      }
    }
    return best ? [best] : [];
  });
}

/** Prioritize the selected number and omit overlapping labels at the displayed scale. */
export function visibleRegionAnnotations(annotations: readonly RegionAnnotation[], zoom: number, selected?: number) {
  const ordered = [...annotations].sort((a, b) => Number(b.id === selected) - Number(a.id === selected));
  const visible: RegionAnnotation[] = [];
  for (const annotation of ordered) {
    if (visible.length >= 60) break;
    if (visible.some(other => Math.abs(annotation.x - other.x) * zoom < 14 + 4 * Math.max(String(annotation.id).length, String(other.id).length) && Math.abs(annotation.y - other.y) * zoom < 36)) continue;
    visible.push(annotation);
  }
  return visible;
}

export function scrollToRegion(anchor: RegionAnnotation, zoom: number, viewport: {width:number;height:number;left:number;top:number}, image: {width:number;height:number}) {
  const x = anchor.x * zoom + Math.max(0, (viewport.width - image.width * zoom) / 2);
  const y = anchor.y * zoom;
  const margin = Math.min(32, viewport.width / 4, viewport.height / 4);
  return {
    left: x < viewport.left + margin || x > viewport.left + viewport.width - margin ? Math.max(0, x - viewport.width / 2) : viewport.left,
    top: y < viewport.top + margin || y > viewport.top + viewport.height - margin ? Math.max(0, y - viewport.height / 2) : viewport.top,
  };
}
