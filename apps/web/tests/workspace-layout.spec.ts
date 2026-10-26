import fs from "node:fs";
import path from "node:path";
import {expect, test, type Page} from "@playwright/test";

/**
 * Layout of the analysis screen on the public demo (/demo), at the sizes researchers use: a laptop at
 * 150 % display scaling (1272 × 554 CSS px), a desktop, a small tablet and a phone. It guards what a
 * UX review found (2026-10-26): side by side, the images take the screen with their outlines and each
 * field's measurements below; nothing wraps into vertical text, is cut off, or is covered by a panel;
 * the image view carries no result card or long note; and in 統計 the result sentence comes first with
 * its figure in view. Run against the public production build with the published demo files.
 */
const PUBLISHED = fs.existsSync(path.resolve("public/showcase/seed.zip"));
interface Scene {id: string; workspaceId: string; regions: string[]; target?: string; channel?: string}
const SCENES: Scene[] = (() => {
  try {return (JSON.parse(fs.readFileSync(path.resolve("public/showcase/snapshot/scenes.json"), "utf8")) as {scenes: Scene[]}).scenes;}
  catch {return [];}
})();
const live = 240_000;
const SIZES = [
  {name: "laptop at 150 %", width: 1272, height: 554},
  {name: "desktop", width: 1440, height: 900},
  {name: "small tablet", width: 1024, height: 768},
  {name: "phone", width: 390, height: 844},
];

test.beforeEach(() => {
  test.skip(!PUBLISHED, "The public demo files (apps/web/public/showcase/seed.zip) are not built.");
  test.skip(process.env.CYTELLECT_EXPECT_UNCONFIGURED !== "1", "The demo exists only in the public build without an analysis API.");
});

/** Labels in the header and the image toolbar whose own text renders on more than one line (for
 * example Japanese words broken into vertical text). Only visible text directly inside each control
 * counts: a select's options and a closed menu's contents are not lines of the label. */
function wrappedLabels(page: Page) {
  return page.evaluate(() => [...document.querySelectorAll("header button, header a, header label, header summary, [class*=channelBar] button, [class*=channelBar] label, [class*=channelBar] summary")]
    // A closed menu's contents are not shown; its summary is.
    .filter(element => element.checkVisibility() && !element.closest("details:not([open]) > :not(summary)"))
    .flatMap(element => [...element.childNodes].filter(node => node.nodeType === Node.TEXT_NODE && node.textContent!.trim()).filter(node => {
      const range = document.createRange();
      range.selectNodeContents(node);
      return new Set([...range.getClientRects()].map(rect => Math.round(rect.top / 4))).size > 1;
    }).map(node => node.textContent!.trim())));
}
/** Header and toolbar controls whose centre is covered by something else (for example an open panel). */
function coveredControls(page: Page) {
  return page.evaluate(() => [...document.querySelectorAll("header button, header select, header a, [class*=channelBar] button, [class*=channelBar] select, [class*=channelBar] summary")]
    .filter(element => {
      const box = element.getBoundingClientRect();
      if (!box.width || !box.height || !element.checkVisibility() || element.closest("details:not([open]) > :not(summary)")) return false;
      // Controls scrolled out of the toolbar row are reachable by scrolling it, not covered.
      const bar = element.closest("[class*=channelBar]")?.getBoundingClientRect();
      const x = box.left + box.width / 2, y = box.top + box.height / 2;
      if (bar && (x < bar.left || x > bar.right)) return false;
      const hit = document.elementFromPoint(x, y);
      return !!hit && hit !== element && !element.contains(hit) && !hit.contains(element);
    }).map(element => element.getAttribute("aria-label") || element.textContent?.trim()));
}
/** Opens a toolbar popup and reports whether all of it is on top (not clipped by the scrolling toolbar). */
async function popupShown(page: Page, summary: string, panel: string) {
  const toggle = page.locator(summary);
  await toggle.scrollIntoViewIfNeeded();
  await toggle.click();
  const shown = await page.locator(panel).evaluate(element => {
    const box = element.getBoundingClientRect();
    return box.width > 0 && [[box.left + 4, box.top + 4], [box.left + box.width / 2, box.top + box.height / 2], [box.right - 4, box.bottom - 4]]
      .every(([x, y]) => {const hit = document.elementFromPoint(x, y); return !!hit && (hit === element || element.contains(hit));});
  });
  await toggle.click();
  return shown;
}
/** Per pane: the image box (between its header and table) and how much of it the drawn image covers. */
function paneImages(page: Page) {
  return page.evaluate(() => [...document.querySelectorAll("[class*=paneImage]")].map(box => {
    const frame = box.getBoundingClientRect(), image = box.querySelector("svg image")?.getBoundingClientRect();
    if (!image) return {height: frame.height, covered: 0};
    const w = Math.max(0, Math.min(frame.right, image.right) - Math.max(frame.left, image.left));
    const h = Math.max(0, Math.min(frame.bottom, image.bottom) - Math.max(frame.top, image.top));
    return {height: frame.height, covered: (w * h) / (frame.width * frame.height)};
  }));
}

for (const size of SIZES) test(`side by side on a ${size.name} (${size.width} × ${size.height}): images, outlines and measurements fill the screen`, async ({page}) => {
  test.setTimeout(300_000);
  await page.setViewportSize({width: size.width, height: size.height});
  await page.goto("/demo");
  const tables = page.getByRole("region", {name: /の測定値$/});
  await expect(tables).toHaveCount(2, {timeout: live});
  for (const table of await tables.all()) await expect(table.locator("tbody tr").first()).toBeVisible({timeout: live});
  await expect(page.locator("svg path[data-region]").first()).toBeAttached({timeout: live});
  await page.waitForTimeout(500);

  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect(await wrappedLabels(page)).toEqual([]);
  expect(await coveredControls(page)).toEqual([]);
  if (size.width > 620) expect((await page.locator("header[class*=header]").boundingBox())!.height).toBeLessThanOrEqual(60);
  // The product name is not cut by the badge next to it.
  expect(await page.locator("header [class*=brand]").evaluate(element => element.scrollWidth <= element.clientWidth + 1
    && element.getBoundingClientRect().right <= (element.nextElementSibling?.getBoundingClientRect().left ?? Infinity) + 1)).toBe(true);
  // The display range's note and the image menu open in full, above the images.
  expect(await popupShown(page, "[class*=rangeInfo] summary", "[class*=rangeInfo] p")).toBe(true);
  expect(await popupShown(page, "[class*=fieldMenu] summary", "[class*=menuPanel]")).toBe(true);

  // The images take the screen: no letterbox, and a large share of the height (a fixed height on a phone).
  const headerBottom = (await page.locator("header[class*=header]").boundingBox())!.height;
  for (const pane of await paneImages(page)) {
    expect(pane.covered).toBeGreaterThan(0.95);
    if (size.width > 620) expect(pane.height).toBeGreaterThan((size.height - headerBottom) * 0.4);
    else expect(pane.height).toBeGreaterThanOrEqual(280);
  }
  // No result card or long note in the image view; the display range is one line, opened on demand.
  await expect(page.getByRole("region", {name: "比較の結果"})).toHaveCount(0);
  await expect(page.locator("[class*=imageWork] [role=note]")).toHaveCount(0);

  // A row of a pane's table selects that outline in the same pane.
  const first = tables.first();
  const row = first.locator("tbody tr").nth(1);
  const id = (await row.locator("button").textContent())!.trim();
  await row.locator("button").click();
  await expect(page.getByRole("region", {name: /（対照）$/}).locator(`svg path[data-region="${id}"]`)).toHaveAttribute("aria-pressed", "true");
});

test("the nucleolar scene opens side by side with the same layout", async ({page}) => {
  const scene = SCENES.find(value => value.regions.includes("nucleoli"));
  test.skip(!scene, "No published scene has nucleoli.");
  await page.setViewportSize({width: 1272, height: 554});
  await page.goto(`/demo?id=${scene!.workspaceId}`);
  await expect(page.getByRole("region", {name: /の測定値$/})).toHaveCount(2, {timeout: live});
  await expect(page.locator("svg path[data-region]").first()).toBeAttached({timeout: live});
  await page.waitForTimeout(500);
  expect(await wrappedLabels(page)).toEqual([]);
  expect(await coveredControls(page)).toEqual([]);
  // It opens on the region its opening comparison measures (scenes.json target), one channel per pane:
  // no overlay toggle side by side, and the shown channel reads as chosen.
  await expect(page.locator("[class*=channelBar]").getByRole("combobox", {name: "領域", exact: true})).toHaveValue(scene!.target ?? "nuclei");
  await expect(page.getByRole("button", {name: "重ねて表示", exact: true})).toHaveCount(0);
  await expect(page.locator("[class*=channelBar] button[data-channel][aria-pressed=true]")).toHaveCount(1);
  if (scene!.channel) await expect(page.locator(`[class*=channelBar] button[data-channel="${scene!.channel}"]`)).toHaveAttribute("aria-pressed", "true");
  for (const pane of await paneImages(page)) expect(pane.covered).toBeGreaterThan(0.95);
});

for (const size of [SIZES[0], SIZES[1]]) test(`statistics on a ${size.name}: the sentence first, the source folded, the figure in view`, async ({page}) => {
  await page.setViewportSize({width: size.width, height: size.height});
  await page.goto(SCENES[0] ? `/demo?id=${SCENES[0].workspaceId}&step=statistics` : "/demo?step=statistics");
  const summary = page.getByRole("region", {name: "結果のまとめ"});
  await expect(summary).toBeVisible({timeout: live});
  await expect(summary.locator("p").first()).toContainText("比べました");
  // The source's report is there to open, not in front of the result.
  const source = summary.locator("details").filter({hasText: "出典の報告"});
  if (await source.count()) await expect(source).not.toHaveAttribute("open", "");
  const figure = page.getByRole("img", {name: "保存された解析結果のグラフ"});
  await expect(figure).toBeVisible({timeout: live});
  expect((await figure.boundingBox())!.y).toBeLessThan(size.height * 0.6);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  // The run table stays inside its card.
  const card = (await summary.boundingBox())!, runs = await summary.locator("table").first().boundingBox();
  if (runs) expect(runs.x + runs.width).toBeLessThanOrEqual(card.x + card.width + 1);
});
