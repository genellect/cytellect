import type {Point} from "@/lib/types";

type Ring = {id: number; points: Point[]};

/** The names a picked enclosing outline is stated with: 「核 12：核小体 3」 in the nucleolus view. */
export interface ContextNames {outline: string; region: string}
export const NUCLEOLUS_CONTEXT: ContextNames = {outline: "核", region: "核小体"};
/** The state of a picked enclosing outline as 「項目：値」, e.g. 核 12：核小体 3 (0 when it encloses none). */
export const contextLabel = (names: ContextNames, outline: number, regions: number) => `${names.outline} ${outline}：${names.region} ${regions}`;

function signedArea(points: readonly Point[]) {
  let sum = 0;
  for (let index = 0; index < points.length; index++) {
    const [x1, y1] = points[index], [x2, y2] = points[(index + 1) % points.length];
    sum += x1 * y2 - x2 * y1;
  }
  return sum / 2;
}

/** Even-odd test; a point on the boundary may fall on either side. */
export function pointInPolygon(point: Point, points: readonly Point[]) {
  let inside = false;
  for (let index = 0, previous = points.length - 1; index < points.length; previous = index++) {
    const [x1, y1] = points[index], [x2, y2] = points[previous];
    if ((y1 > point[1]) !== (y2 > point[1]) && point[0] < x1 + (point[1] - y1) * (x2 - x1) / (y2 - y1)) inside = !inside;
  }
  return inside;
}

/** Area centroid of an outline; the mean of its points when the outline encloses no area. */
export function polygonCentroid(points: readonly Point[]): Point {
  const area = signedArea(points);
  if (Math.abs(area) < 1e-9) return [points.reduce((sum, point) => sum + point[0], 0) / points.length, points.reduce((sum, point) => sum + point[1], 0) / points.length];
  let x = 0, y = 0;
  for (let index = 0; index < points.length; index++) {
    const [x1, y1] = points[index], [x2, y2] = points[(index + 1) % points.length];
    const cross = x1 * y2 - x2 * y1;
    x += (x1 + x2) * cross; y += (y1 + y2) * cross;
  }
  return [x / (6 * area), y / (6 * area)];
}

function distanceToOutline(point: Point, points: readonly Point[]) {
  let best = Infinity;
  for (let index = 0; index < points.length; index++) {
    const [x1, y1] = points[index], [x2, y2] = points[(index + 1) % points.length];
    const dx = x2 - x1, dy = y2 - y1, length = dx * dx + dy * dy;
    const t = length ? Math.max(0, Math.min(1, ((point[0] - x1) * dx + (point[1] - y1) * dy) / length)) : 0;
    best = Math.min(best, Math.hypot(point[0] - x1 - t * dx, point[1] - y1 - t * dy));
  }
  return best;
}

/**
 * What a click on an enclosing outline (a nucleus around nucleoli) picks. Screen-side geometry only:
 * it reads the saved outlines and never changes a mask or a measured value.
 *
 * - `context`: the enclosing outline that contains the point; the smallest one where outlines overlap.
 * - `region`: of the regions whose outline centroid lies inside that enclosing outline, the one whose
 *   outline is nearest to the point (the lower id on a tie); absent when it encloses none.
 *
 * `hit` is the enclosing outline the pointer landed on. Its drawn line is wider than the outline itself, so a
 * click on the line can fall just outside the polygon; that outline is then the one taken.
 *
 * Null when the point is outside every enclosing outline and none was hit.
 */
export function pickEnclosedRegion(point: Point, context: readonly Ring[], regions: readonly Ring[], hit?: number): {context: number; region?: number} | null {
  let enclosing: Ring | undefined, smallest = Infinity;
  for (const outline of context) {
    if (outline.points.length < 3 || !pointInPolygon(point, outline.points)) continue;
    const area = Math.abs(signedArea(outline.points));
    if (area < smallest || (area === smallest && outline.id < enclosing!.id)) {enclosing = outline; smallest = area;}
  }
  enclosing ??= hit === undefined ? undefined : context.find(outline => outline.id === hit && outline.points.length >= 3);
  if (!enclosing) return null;
  // A nucleus drawn as several rings (a hole, a detached piece) holds what its outer ring holds.
  enclosing = outerRings(context).find(outline => outline.id === enclosing!.id) ?? enclosing;
  const members = new Set(enclosedRegions(enclosing, regions));
  let region: number | undefined, nearest = Infinity;
  for (const candidate of regions) {
    if (candidate.points.length < 3 || !members.has(candidate.id)) continue;
    const distance = pointInPolygon(point, candidate.points) ? 0 : distanceToOutline(point, candidate.points);
    if (distance < nearest || (distance === nearest && candidate.id < region!)) {region = candidate.id; nearest = distance;}
  }
  return {context: enclosing.id, region};
}

/**
 * Each region's outer ring: a region with a hole or a detached part is drawn as several rings under one id, and the
 * largest of them stands for the region.
 */
export function outerRings(regions: readonly Ring[]): Ring[] {
  const outer = new Map<number, {ring: Ring; area: number}>();
  for (const ring of regions) {
    if (ring.points.length < 3) continue;
    const area = Math.abs(signedArea(ring.points)), held = outer.get(ring.id);
    if (!held || area > held.area) outer.set(ring.id, {ring, area});
  }
  return [...outer.values()].map(value => value.ring);
}

/** Whether a region's ring lies in an enclosing outline: the ring's centroid lies inside it. */
export const encloses = (outline: Ring, region: Ring) => region.points.length >= 3 && outline.points.length >= 3 && pointInPolygon(polygonCentroid(region.points), outline.points);

/** The ids of the regions an enclosing outline holds, each region once, by the centroid of its outer ring. */
export const enclosedRegions = (outline: Ring, regions: readonly Ring[]) => outerRings(regions).filter(region => encloses(outline, region)).map(region => region.id);

/** The enclosing outline that holds a region (the smallest where outlines overlap); undefined when none does. */
export function enclosingOutline(region: Ring, context: readonly Ring[]): number | undefined {
  let found: Ring | undefined, smallest = Infinity;
  for (const outline of outerRings(context)) {
    if (!encloses(outline, region)) continue;
    const area = Math.abs(signedArea(outline.points));
    if (area < smallest || (area === smallest && outline.id < found!.id)) {found = outline; smallest = area;}
  }
  return found?.id;
}
