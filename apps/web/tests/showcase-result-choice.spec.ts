import fs from "node:fs";
import path from "node:path";
import {expect, test, type Page} from "@playwright/test";

/**
 * The statistics and figure views follow the side panel's choice in the public demo (genellect/cytellect#257
 * SR-01–SR-04, owner decisions 9 and 15, 2026-11-21): a condition shows its own result, a design of two groups is
 * compared, and グラフ never shows another condition's figure. Run like showcase.spec.ts, against the public build.
 */
const PUBLISHED = fs.existsSync(path.resolve("public/showcase/seed.zip"));
const live = 240_000;
interface Scene {id: string; workspaceId: string; regions: string[]}
const SCENES: Scene[] = (() => {
  try {return (JSON.parse(fs.readFileSync(path.resolve("public/showcase/snapshot/scenes.json"), "utf8")) as {scenes: Scene[]}).scenes;}
  catch {return [];}
})();
const OPENING = SCENES[0];
const url = (query: string) => OPENING ? `/demo?id=${OPENING.workspaceId}&${query}` : `/demo?${query}`;

test.describe.configure({mode: "serial"});
test.beforeEach(() => {
  test.skip(!PUBLISHED, "The public demo files (apps/web/public/showcase/seed.zip) are not built.");
  test.skip(process.env.CYTELLECT_EXPECT_UNCONFIGURED !== "1", "The demo exists only in the public build without an analysis API.");
  test.skip(!!OPENING && !OPENING.regions.includes("nucleoli"), "The opening scene has no nucleoli.");
});

async function open(page: Page, query: string) {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto(url(query));
  return errors;
}
const side = (page: Page) => page.getByRole("complementary", {name: "解析対象"});
async function choose(page: Page, region: string, metric: string, channel: string | null) {
  const choice = side(page).getByRole("combobox", {name: "領域", exact: true});
  if (!await choice.count()) await side(page).getByRole("combobox", {name: "指標", exact: true}).selectOption("area_px");
  await choice.selectOption(region);
  await side(page).getByRole("combobox", {name: "指標", exact: true}).selectOption(metric);
  if (channel) await side(page).getByRole("combobox", {name: "染色", exact: true}).selectOption(channel);
}
const pendingCard = (page: Page) => page.getByRole("region", {name: "選択中の条件"});

test("two groups are compared: 分布 is not an analysis of the opening scene, and each condition opens its own result", async ({page}) => {
  test.setTimeout(600_000);
  const errors = await open(page, "step=statistics");
  const results = page.getByRole("region", {name: "測定結果の統計解析"});
  const operation = results.getByRole("combobox", {name: "解析", exact: true});
  await expect(operation).toBeVisible({timeout: live});
  for (const [region, metric, channel] of [["nucleoli", "area_px", null], ["nucleoplasm", "mean", "npm1"], ["nuclei", "area_px", null]] as const) {
    await choose(page, region, metric, channel);
    await expect(operation).toHaveValue("comparison");
    await expect(operation.locator("option[value=distribution]")).toHaveCount(0);
    // The recorded result opens without 計算; the condition's card does not stay in its place.
    await expect(pendingCard(page)).toHaveCount(0, {timeout: live});
    await expect(results.getByRole("region", {name: "結果のまとめ"})).toBeVisible();
  }
  expect(errors).toEqual([]);
});

test("グラフ follows the side panel both ways and never shows another condition's figure (SR-04)", async ({page}) => {
  test.setTimeout(600_000);
  const errors = await open(page, "step=figure");
  const figure = page.getByRole("region", {name: "図の作成・保存"});
  const history = figure.getByRole("combobox", {name: "保存した図", exact: true});
  await expect(history).toBeVisible({timeout: live});
  // A condition chosen in the side panel opens its figure.
  await choose(page, "nuclei", "area_px", null);
  await expect(pendingCard(page)).toHaveCount(0, {timeout: live});
  await expect(history.locator("option:checked")).toHaveText(/面積/);
  await expect(page.getByRole("button", {name: /^グラフを選択/}).first()).toBeVisible({timeout: live});
  // A saved figure chosen in グラフ sets the side panel.
  const options = await history.locator("option:not([disabled])").allTextContents();
  const other = options.find(text => /離心率/.test(text));
  test.skip(!other, "The demo holds no saved figure of the nucleolar eccentricity.");
  await history.selectOption({label: other!});
  await expect(side(page).getByRole("combobox", {name: "指標", exact: true})).toHaveValue("nucleolar_eccentricity");
  await expect(pendingCard(page)).toHaveCount(0, {timeout: live});
  expect(errors).toEqual([]);
});
