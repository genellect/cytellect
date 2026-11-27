import {describe, expect, it} from "vitest";
import type {Point} from "@/lib/types";
import {contextLabel, enclosedRegions, enclosingOutline, NUCLEOLUS_CONTEXT, pickEnclosedRegion, pointInPolygon, polygonCentroid} from "./context-pick";

const square = (x: number, y: number, size: number): Point[] => [[x, y], [x + size, y], [x + size, y + size], [x, y + size]];

describe("picking a nucleolus from a click on its nucleus", () => {
  const nuclei = [{id: 1, points: square(0, 0, 100)}, {id: 2, points: square(200, 0, 100)}, {id: 3, points: square(400, 0, 100)}];
  const nucleoli = [{id: 11, points: square(10, 10, 10)}, {id: 12, points: square(70, 70, 10)}, {id: 21, points: square(240, 40, 8)}];

  it("tells inside from outside, also for a concave outline", () => {
    const concave: Point[] = [[0, 0], [10, 0], [10, 10], [6, 10], [6, 4], [4, 4], [4, 10], [0, 10]];
    expect(pointInPolygon([2, 8], concave)).toBe(true);
    expect(pointInPolygon([5, 8], concave)).toBe(false);
    expect(pointInPolygon([5, 2], concave)).toBe(true);
    expect(pointInPolygon([11, 5], concave)).toBe(false);
  });
  it("uses the area centroid, whatever the winding and point spacing", () => {
    const dense: Point[] = [[0, 0], [1, 0], [2, 0], [3, 0], [10, 0], [10, 10], [0, 10]];
    for (const points of [dense, [...dense].reverse()]) {
      const [x, y] = polygonCentroid(points);
      expect(x).toBeCloseTo(5); expect(y).toBeCloseTo(5);
    }
    expect(polygonCentroid([[0, 0], [4, 0], [8, 0]])).toEqual([4, 0]);
  });
  it("picks the nucleolus of the clicked nucleus that is nearest to the click", () => {
    expect(pickEnclosedRegion([30, 30], nuclei, nucleoli)).toEqual({context: 1, region: 11});
    expect(pickEnclosedRegion([60, 60], nuclei, nucleoli)).toEqual({context: 1, region: 12});
    expect(pickEnclosedRegion([205, 95], nuclei, nucleoli)).toEqual({context: 2, region: 21});
  });
  it("never picks a nucleolus of another nucleus, however near", () => {
    // Nucleus 2's nucleolus sits at its left edge, next to a click at the right edge of nucleus 1.
    const near = [...nucleoli, {id: 22, points: square(201, 45, 6)}];
    expect(pickEnclosedRegion([99, 48], nuclei, near)).toEqual({context: 1, region: 12});
  });
  it("measures nearness to the outline, not to the centre", () => {
    // A long nucleolus whose centre is far but whose tip is beside the click, against a small one further off.
    const regions = [{id: 1, points: [[10, 48], [60, 48], [60, 52], [10, 52]] as Point[]}, {id: 2, points: square(80, 46, 8)}];
    expect(pickEnclosedRegion([66, 50], [nuclei[0]], regions)).toEqual({context: 1, region: 1});
  });
  it("reports the nucleus alone when it encloses no nucleolus", () => {
    expect(pickEnclosedRegion([450, 50], nuclei, nucleoli)).toEqual({context: 3});
  });
  it("picks nothing outside every nucleus", () => {
    expect(pickEnclosedRegion([150, 50], nuclei, nucleoli)).toBeNull();
    expect(pickEnclosedRegion([150, 50], [], nucleoli)).toBeNull();
  });
  it("takes the nucleus whose drawn line was clicked when the point is just outside its outline", () => {
    expect(pickEnclosedRegion([-0.4, 30], nuclei, nucleoli)).toBeNull();
    expect(pickEnclosedRegion([-0.4, 30], nuclei, nucleoli, 1)).toEqual({context: 1, region: 11});
    expect(pickEnclosedRegion([400.2, -0.3], nuclei, nucleoli, 3)).toEqual({context: 3});
    // Inside an outline, the geometry decides, not the element that took the click.
    expect(pickEnclosedRegion([205, 95], nuclei, nucleoli, 1)).toEqual({context: 2, region: 21});
    expect(pickEnclosedRegion([150, 50], nuclei, nucleoli, 99)).toBeNull();
  });
  it("takes the smaller nucleus where outlines overlap", () => {
    const overlapping = [{id: 1, points: square(0, 0, 100)}, {id: 2, points: square(60, 60, 30)}];
    const regions = [{id: 5, points: square(10, 10, 10)}, {id: 6, points: square(70, 70, 6)}];
    expect(pickEnclosedRegion([62, 62], overlapping, regions)).toEqual({context: 2, region: 6});
    expect(pickEnclosedRegion([50, 50], overlapping, regions)).toEqual({context: 1, region: 6});
    expect(pickEnclosedRegion([24, 24], overlapping, regions)).toEqual({context: 1, region: 5});
  });
  it("keeps the lower number on a tie and skips degenerate outlines", () => {
    const regions = [{id: 9, points: square(60, 45, 10)}, {id: 4, points: square(30, 45, 10)}, {id: 1, points: [[49, 50], [51, 50]] as Point[]}];
    expect(pickEnclosedRegion([50, 50], [nuclei[0]], regions)).toEqual({context: 1, region: 4});
  });
  it("counts and finds a nucleus's nucleoli by the same rule as the pick, and states it as a value", () => {
    expect(enclosedRegions(nuclei[0], nucleoli)).toEqual([11, 12]);
    expect(enclosedRegions(nuclei[2], nucleoli)).toEqual([]);
    expect(enclosingOutline(nucleoli[2], nuclei)).toBe(2);
    // The smaller of two overlapping nuclei holds the nucleolus; one outside every nucleus has none.
    expect(enclosingOutline({id: 5, points: square(30, 30, 4)}, [nuclei[0], {id: 7, points: square(20, 20, 30)}])).toBe(7);
    expect(enclosingOutline({id: 6, points: square(150, 50, 4)}, nuclei)).toBeUndefined();
    expect(contextLabel(NUCLEOLUS_CONTEXT, 12, 3)).toBe("核 12：核小体 3");
    // A nucleolus with a hole (two rings under one id) counts once, by its outer ring, and is picked by either ring.
    const holed = [...nucleoli, {id: 13, points: square(40, 40, 20)}, {id: 13, points: square(45, 45, 5)}];
    expect(enclosedRegions(nuclei[0], holed)).toEqual([11, 12, 13]);
    expect(pickEnclosedRegion([48, 48], nuclei, holed)).toEqual({context: 1, region: 13});
    // A detached piece outside the nucleus does not make its region another nucleus's: the outer (larger) ring decides.
    const split = [{id: 31, points: square(20, 20, 30)}, {id: 31, points: square(210, 10, 4)}];
    expect(enclosedRegions(nuclei[0], split)).toEqual([31]);
    expect(enclosedRegions(nuclei[1], split)).toEqual([]);
    expect(contextLabel(NUCLEOLUS_CONTEXT, 4, 0)).toBe("核 4：核小体 0");
  });
});
