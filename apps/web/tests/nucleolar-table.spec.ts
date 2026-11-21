import fs from "node:fs";
import path from "node:path";
import {expect, test} from "@playwright/test";

/**
 * On the nucleoli the image view also opens each nucleus's nucleolar summary (count, total area, area fraction, largest
 * nucleolus, eccentricity), and the next step compares what the table lists (Issue #257 A-1, A-2, requirements TB-01–TB-03).
 * The table is the saved nucleus table the nuclei already open, so nothing new is requested from the recording.
 * Run on the public demo build (no analysis API) with the published demo files, like showcase.spec.ts.
 */
const PUBLISHED = fs.existsSync(path.resolve("public/showcase/seed.zip"));
const live = 240_000;
interface Scene {id: string; workspaceId: string; regions: string[]}
const SCENES: Scene[] = (() => {
  try {return (JSON.parse(fs.readFileSync(path.resolve("public/showcase/snapshot/scenes.json"), "utf8")) as {scenes: Scene[]}).scenes;}
  catch {return [];}
})();

test.beforeEach(() => {
  test.skip(!PUBLISHED, "The public demo files (apps/web/public/showcase/seed.zip) are not built.");
  test.skip(process.env.CYTELLECT_EXPECT_UNCONFIGURED !== "1", "The demo exists only in the public build without an analysis API.");
});

for (const scene of SCENES.filter(value => value.regions.includes("nucleoli"))) test(`the nucleoli open each nucleus's nucleolar summary and the next step follows the table (${scene.id})`, async ({page}) => {
  test.setTimeout(300_000);
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto(`/demo?id=${scene.workspaceId}`);
  const bar = page.locator("[class*=channelBar]");
  await expect(bar.getByRole("combobox", {name: "領域", exact: true})).toBeVisible({timeout: live});
  await bar.getByRole("combobox", {name: "領域", exact: true}).selectOption("nucleoli");
  const views = page.getByRole("group", {name: "表の切り替え"}).first();
  // TB-01: per nucleolus, or per nucleus with the nucleoli summarised; the heading names the observation.
  await expect(views.getByRole("button", {name: "核小体ごと", exact: true})).toBeVisible({timeout: live});
  await views.getByRole("button", {name: "核小体ごと", exact: true}).click();
  const heading = page.getByRole("heading", {level: 3, name: /^(視野 \d+ · )?核小体ごと · /}).first();
  await expect(heading).toBeVisible();
  // TB-02: the table lists a stain's brightness, so the next step compares that brightness, not another metric.
  const next = page.getByRole("button", {name: /^核小体の平均輝度（.+）を群間で比較/});
  await expect(next.first()).toBeVisible();
  await views.getByRole("button", {name: "核ごと（核小体のまとめ）", exact: true}).click();
  await expect(page.getByRole("heading", {level: 3, name: /核ごと · 核小体のまとめとすべての染色$/}).first()).toBeVisible({timeout: live});
  const table = page.locator("table").filter({hasText: "核小体数"}).first();
  for (const column of ["核小体数", "核小体の面積", "核小体の面積 / 核", "最大の核小体 / 核小体全体", "離心率"]) await expect(table.getByRole("columnheader", {name: column}).first()).toBeVisible();
  // TB-03: answered from the recording, as the nuclei's own table is.
  await expect(page.getByRole("status").filter({hasText: "公開デモに記録していません"})).toHaveCount(0);
  expect(errors).toEqual([]);
});
