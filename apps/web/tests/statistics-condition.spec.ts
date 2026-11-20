import fs from "node:fs";
import path from "node:path";
import {expect, test, type Page} from "@playwright/test";

/**
 * The statistics view follows the side panel's choice (Issue #257, requirements SR-01–SR-04): a chosen condition's saved
 * result opens without another action; a condition without one shows, where the result will appear, its name, what the
 * calculation still needs and 計算; confirmations stay through other metrics and regions; an analysis the view changes
 * says why; the figure view says when its figure is not the chosen condition's. Run on the public demo build (no analysis
 * API) with the published demo files, like showcase.spec.ts; the demo's fully recorded opening scene (oxaliplatin) is used.
 */
const PUBLISHED = fs.existsSync(path.resolve("public/showcase/seed.zip"));
const live = 240_000;
interface Scene {id: string; workspaceId: string; regions: string[]}
const SCENES: Scene[] = (() => {
  try {return (JSON.parse(fs.readFileSync(path.resolve("public/showcase/snapshot/scenes.json"), "utf8")) as {scenes: Scene[]}).scenes;}
  catch {return [];}
})();
const OPENING = SCENES[0];

test.describe.configure({mode: "serial"});
test.beforeEach(() => {
  test.skip(!PUBLISHED, "The public demo files (apps/web/public/showcase/seed.zip) are not built.");
  test.skip(process.env.CYTELLECT_EXPECT_UNCONFIGURED !== "1", "The demo exists only in the public build without an analysis API.");
  test.skip(!!OPENING && !OPENING.regions.includes("nucleoli"), "The opening scene has no nucleoli.");
});

async function open(page: Page) {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto(OPENING ? `/demo?id=${OPENING.workspaceId}&step=statistics` : "/demo?step=statistics");
  const results = page.getByRole("region", {name: "測定結果の統計解析"});
  await expect(results.getByRole("region", {name: "結果のまとめ"})).toBeVisible({timeout: live});
  const side = page.getByRole("complementary", {name: "解析対象"});
  const choose = async (metric: string, region?: string, stain?: string) => {
    // The subject first, then its metric and stain (B-1).
    if (region) await side.getByRole("combobox", {name: "対象", exact: true}).selectOption(region);
    await side.getByRole("combobox", {name: "指標", exact: true}).selectOption(metric);
    if (stain) await side.getByRole("combobox", {name: "染色", exact: true}).selectOption(stain);
  };
  return {results, side, choose, errors};
}

test("a chosen condition shows its saved result, or its name, what is missing and 計算 where the result will appear", async ({page}) => {
  test.setTimeout(600_000);
  const {results, choose, errors} = await open(page);
  const summary = results.getByRole("region", {name: "結果のまとめ"});
  const pending = results.getByRole("region", {name: "選択中の条件"});
  const calculate = results.getByRole("button", {name: "計算", exact: true});
  // Saved comparisons are named by region, metric and stain, never by a channel identifier (SL-02).
  const saved = results.getByRole("group", {name: "保存した比較"}).getByRole("button");
  await expect(saved.first()).toBeVisible();
  for (const name of await saved.allTextContents()) expect(name).not.toMatch(/·|eu5|npm1|hoechst/);

  // SR-01: a condition with a saved result opens it without 計算.
  await choose("mean", "nucleoli", "eu5");
  await expect(summary.getByRole("heading", {level: 3})).toContainText("核小体の平均輝度（5-EU）");
  await expect(pending).toHaveCount(0);
  await expect(results.locator("[class*=current]").first()).toHaveText("計算する条件：核小体の平均輝度（5-EU）");

  // SR-02, SR-03: a condition without one shows no other condition's result; it names the condition and what is missing.
  await choose("mean", "nucleoli", "npm1");
  await expect(pending.getByRole("heading", {level: 3})).toHaveText("核小体の平均輝度（NPM1）");
  await expect(summary).toHaveCount(0);
  await expect(pending.getByRole("img")).toHaveCount(0);
  await expect(calculate).toBeDisabled();
  await expect(pending).toContainText("計算に必要なこと：");
  await expect(pending).toContainText("測定領域と採用する視野の確認");
  for (const name of ["実験回の定義、撮影・画素条件、採否と欠測の扱いを確認済み", "測定領域と採用する視野を確認済み"]) await pending.getByLabel(name, {exact: true}).check();
  const keep = pending.getByLabel("この一覧を確認し、欠測として残して計算する", {exact: true});
  if (await keep.count()) await keep.check();
  await expect(pending).not.toContainText("計算に必要なこと：");
  await calculate.click();
  await expect(summary.getByRole("heading", {level: 3})).toContainText("核小体の平均輝度（NPM1）", {timeout: live});
  await expect(pending).toHaveCount(0);

  // D-3: another region asks only for its own review; the design's confirmation stays. Back on the nucleoli, the
  // calculated result is shown at once and the confirmations are still given.
  await choose("mean", "nucleoplasm", "npm1");
  await expect(pending.getByRole("heading", {level: 3})).toHaveText("核質の平均輝度（NPM1）");
  await expect(pending.getByLabel("実験回の定義、撮影・画素条件、採否と欠測の扱いを確認済み", {exact: true})).toBeChecked();
  await expect(pending.getByLabel("測定領域と採用する視野を確認済み", {exact: true})).not.toBeChecked();
  await choose("mean", "nucleoli", "npm1");
  await expect(summary.getByRole("heading", {level: 3})).toContainText("核小体の平均輝度（NPM1）");
  await expect(results.getByLabel("測定領域と採用する視野を確認済み", {exact: true})).toBeChecked();
  await expect(calculate).toBeEnabled();
  expect(errors).toEqual([]);
});

test("an analysis the measure cannot have is changed with its reason, and the figure view says when its figure is another condition's", async ({page}) => {
  test.setTimeout(600_000);
  const {results, choose, errors} = await open(page);
  const operation = results.getByRole("combobox", {name: "解析", exact: true});
  await expect(operation).toHaveValue("comparison");
  // SR-04: groups with saturated nuclear-stain pixels cannot be compared; the view says why it shows the distribution.
  await choose("mean", "nuclei", "hoechst");
  await expect(operation).toHaveValue("distribution");
  await expect(results.getByRole("status").filter({hasText: "飽和した画素を含む群があり、群間比較ができないため、分布に切り替えました。"})).toBeVisible();
  // The reason belongs to that measure: another stain no longer shows it.
  await choose("mean", "nuclei", "npm1");
  await expect(results.getByRole("status").filter({hasText: "切り替えました"})).toHaveCount(0);
  // The figure view: the chosen condition has no figure yet, so the shown figure is named and 統計で計算 opens statistics.
  await choose("area_px", "nucleoli");
  await page.locator("header").getByRole("button", {name: "グラフ", exact: true}).click();
  const figure = page.getByRole("region", {name: "図の作成・保存"});
  await expect(figure.getByRole("status").filter({hasText: "選択中の「核小体の面積（px²）」の図はまだありません。"})).toBeVisible({timeout: live});
  await figure.getByRole("button", {name: "統計で計算", exact: true}).click();
  await expect(page.getByRole("region", {name: "測定結果の統計解析"}).getByRole("region", {name: "選択中の条件"})).toContainText("核小体の面積（px²）");
  expect(errors).toEqual([]);
});

test("the subject comes first: only its metrics are listed, by what one observation is, and one sentence states both", async ({page}) => {
  test.setTimeout(300_000);
  const {side, errors} = await open(page);
  const subject = side.getByRole("combobox", {name: "対象", exact: true});
  const metric = side.getByRole("combobox", {name: "指標", exact: true});
  // SL-01 on the nucleoli: per-nucleolus measures, the per-nucleus summaries and the partition; no nucleus counts.
  await subject.selectOption("nucleoli");
  await expect(metric.locator("optgroup")).toHaveCount(3);
  await expect(metric.locator("optgroup").first()).toHaveAttribute("label", "核小体ごと");
  await expect(metric.locator("option[value=nucleolar_eccentricity]")).toHaveCount(1);
  await expect(metric.locator("option[value=nucleus_count]")).toHaveCount(0);
  await metric.selectOption("nucleolar_eccentricity");
  await expect(side.getByTestId("metric-definition")).toContainText("対象：核小体。観測の単位：核ごと（その核の核小体をまとめた値）。");
  // On the nuclei a metric of another subject is replaced by the first of the nuclei, which the sentence names.
  await subject.selectOption("nuclei");
  await expect(metric.locator("option[value=nucleolar_eccentricity]")).toHaveCount(0);
  await expect(side.getByTestId("metric-definition")).toContainText("対象：核。観測の単位：");
  // A per-region metric stays when the subject changes; its observation follows the subject.
  await metric.selectOption("mean");
  await subject.selectOption("nucleoli");
  await expect(metric).toHaveValue("mean");
  await expect(side.getByTestId("metric-definition")).toContainText("観測の単位：核小体ごと。");
  expect(errors).toEqual([]);
});
