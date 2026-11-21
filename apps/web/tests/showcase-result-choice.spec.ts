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

test("with nuclei classified by a stain, the demo offers only the measures recorded for the classified nuclei (#257 review)", async ({page}) => {
  test.setTimeout(600_000);
  const errors = await open(page, "step=image");
  const color = page.getByRole("toolbar", {name: "画像の表示"}).getByRole("combobox", {name: "色分け", exact: true});
  await expect(color).toBeVisible({timeout: live});
  await color.selectOption("positivity");
  const gate = page.getByRole("complementary", {name: "画像解析"}).getByRole("region", {name: "チャンネルによる核の分類"});
  await gate.getByRole("button", {name: "チャンネルで分類", exact: true}).click();
  await expect(gate.locator("output")).toContainText("陽性", {timeout: live});
  await page.locator("header").getByRole("button", {name: "統計", exact: true}).click();
  const metric = side(page).getByRole("combobox", {name: "指標", exact: true});
  await expect(metric).toBeVisible({timeout: live});
  const region = side(page).getByRole("combobox", {name: "領域", exact: true});
  if (await region.count()) await region.selectOption("nuclei");
  // The tour recorded the nuclear mean for classified nuclei, and the nuclear median only for all nuclei.
  const offered = await metric.locator("option").evaluateAll(options => options.map(option => (option as HTMLOptionElement).value));
  expect(offered).toContain("mean");
  expect(offered).not.toContain("median");
  expect(errors).toEqual([]);
});

test("the demo never asks the visitor for earlier work or a declaration (#257 decisions 2, 11 and 13)", async ({page}) => {
  test.setTimeout(600_000);
  const errors = await open(page, "step=statistics");
  const results = page.getByRole("region", {name: "測定結果の統計解析"});
  await expect(results.getByRole("region", {name: "結果のまとめ"}).first()).toBeVisible({timeout: live});
  // The recorded calculations carry the tour's confirmations: no confirmation and no line pointing to 画像 or 実験.
  await choose(page, "nuclei", "area_px", null);
  await expect(results.getByRole("region", {name: "選択中の条件"})).toHaveCount(0, {timeout: live});
  await expect(results.getByRole("button", {name: /^(画像|実験)：/})).toHaveCount(0);
  await expect(results.getByRole("checkbox", {name: /確認済み|欠測として残して計算する/})).toHaveCount(0);
  // The recorded public design states nothing about the acquisition settings: no mark is made up for it, and the
  // statement is not offered to the visitor.
  await page.locator("header").getByRole("button", {name: "実験", exact: true}).click();
  const status = page.getByRole("region", {name: "実験デザイン"}).getByRole("list", {name: "実験デザインの状態"});
  await expect(status.getByRole("listitem").filter({hasText: /^独立性：/})).toBeVisible({timeout: live});
  await expect(status.getByRole("listitem").filter({hasText: /^撮影条件：/})).toHaveCount(0);
  await expect(page.getByRole("checkbox", {name: "全視野を同じ撮影・画素条件で撮影した"})).toHaveCount(0);
  expect(errors).toEqual([]);
});
