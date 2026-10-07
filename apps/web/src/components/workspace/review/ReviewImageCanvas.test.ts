import {describe, expect, it} from "vitest";
import {reviewImageFit, reviewImagePoint, reviewImageSelection, reviewImageZoom, reviewViewportCamera} from "./ReviewImageCanvas";

describe("review image geometry", () => {
  it.each([[1920, 900, 2048, 2048], [1280, 440, 1024, 2048], [280, 300, 4096, 1024]])("fits %s×%s without distorting native coordinates", (vw, vh, width, height) => {
    const camera = reviewImageFit({width, height}, {width: vw, height: vh});
    expect(camera.x).toBeGreaterThanOrEqual(0);
    expect(camera.y).toBeGreaterThanOrEqual(0);
    expect(camera.x + width * camera.scale).toBeLessThanOrEqual(vw);
    expect(camera.y + height * camera.scale).toBeLessThanOrEqual(vh);
    expect(Math.min(camera.x, camera.y)).toBe(0);
  });
  it("keeps the pixel below the cursor fixed during zoom", () => {
    const before = {scale: 0.2, x: 120, y: 0};
    const anchor = {x: 255, y: 180};
    const after = reviewImageZoom(before, 0.4, anchor);
    expect((anchor.x - after.x) / after.scale).toBeCloseTo((anchor.x - before.x) / before.scale);
    expect((anchor.y - after.y) / after.scale).toBeCloseTo((anchor.y - before.y) / before.scale);
  });
  it("translates a drawn point into the same native coordinate after pan and zoom", () => {
    const native = [231.5, 876.25];
    for (const camera of [{scale: 0.17, x: 143, y: 0}, {scale: 2, x: -310, y: -880}]) {
      const result = reviewImagePoint(camera, {x: native[0] * camera.scale + camera.x, y: native[1] * camera.scale + camera.y});
      expect(result[0]).toBeCloseTo(native[0], 10);
      expect(result[1]).toBeCloseTo(native[1], 10);
    }
  });
  it("synchronizes native image center between different channel viewport sizes", () => {
    const shared = {scale: 2, centerX: 500, centerY: 700};
    for (const size of [{width: 400, height: 600}, {width: 800, height: 450}]) {
      const camera = reviewViewportCamera(shared, size);
      expect(reviewImagePoint(camera, {x: size.width / 2, y: size.height / 2})).toEqual([500, 700]);
    }
  });
  it("selects unique region identities, not duplicated hole contours, in both directions", () => {
    const contours = [8, 2, 2, 21];
    expect(reviewImageSelection(contours, undefined, 1)).toBe(2);
    expect(reviewImageSelection(contours, 2, 1)).toBe(8);
    expect(reviewImageSelection(contours, 2, -1)).toBe(21);
    expect(reviewImageSelection([], 2, 1)).toBeUndefined();
  });
});
