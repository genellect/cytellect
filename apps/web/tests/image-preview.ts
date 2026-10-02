import { expect, type Page } from "@playwright/test";

/** The square GFP fixture occupies over 30% of the canvas at the tested viewport. */
export async function expectGfpPreview(page: Page) {
 await expect.poll(async () => page.locator('[data-testid="image-canvas"] canvas').first().evaluate(element => {
  const canvas = element as HTMLCanvasElement;
  const pixels = canvas.getContext("2d")!.getImageData(0, 0, canvas.width, canvas.height).data;
  let opaque = 0, samples = 0;
  for (let i = 3; i < pixels.length; i += 64) { samples++; if (pixels[i] > 250) opaque++; }
  // Mask outlines and canvas loading text alone cannot satisfy this image-area check.
  return opaque / samples;
 }), { timeout: 30000 }).toBeGreaterThan(.3);
}
