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
const SUBJECTS: Record<string, string> = {nuclei: "核", nucleoli: "核小体", nucleoplasm: "核質"};
const subjectRadio = (page: Page, subject: string) => side(page).getByRole("radiogroup", {name: "対象", exact: true}).getByRole("radio", {name: SUBJECTS[subject], exact: true});
/** The subject first (it sets the region), then its metric and stain (M-01). */
async function choose(page: Page, subject: string, metric: string, channel: string | null) {
  await subjectRadio(page, subject).click();
  await expect(subjectRadio(page, subject)).toBeChecked();
  await side(page).getByRole("combobox", {name: "指標", exact: true}).selectOption(metric);
  if (channel) await side(page).getByRole("combobox", {name: "染色", exact: true}).selectOption(channel);
}
interface Recorded {region: string; metric: string; channel: string | null; gate?: string | null}
/** The recorded statistics of the opening scene (what the side panel may offer). */
const RECORDED: Recorded[] = (() => {
  try {return (JSON.parse(fs.readFileSync(path.resolve("public/showcase/snapshot/recorded-statistics.json"), "utf8")) as {scenes: Record<string, Recorded[]>}).scenes[OPENING?.id ?? ""] ?? [];}
  catch {return [];}
})();
/** The region set a metric of a subject reads (the per-nucleus nucleolar summaries, the largest nucleolus's fraction
 * among them, come from the nucleoplasm set: metric-catalog.ts, docs/methods.md). */
const regionOf = (metric: string, subject: string) => /^(nucleolar_|log2_|largest_nucleolus_fraction)/.test(metric) ? "nucleoplasm" : /^(nucleus_|positive_)/.test(metric) ? "nuclei" : subject;
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
  await subjectRadio(page, "nuclei").click();
  await expect(subjectRadio(page, "nuclei")).toBeChecked();
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
  await expect(page.getByRole("checkbox", {name: "群の間で撮影・画素条件を比べられる"})).toHaveCount(0);
  expect(errors).toEqual([]);
});

test("each subject offers only the recorded combinations of metric, region and stain (M-01, #257 D-1)", async ({page}) => {
  test.setTimeout(600_000);
  test.skip(!RECORDED.length, "The demo publishes no recorded statistics index.");
  const errors = await open(page, "step=statistics");
  const metric = side(page).getByRole("combobox", {name: "指標", exact: true});
  await expect(metric).toBeVisible({timeout: live});
  const all = (gate: string | null) => RECORDED.filter(item => (item.gate ?? null) === gate || item.metric.startsWith("positive_"));
  const subjects = await side(page).getByRole("radiogroup", {name: "対象", exact: true}).getByRole("radio").allTextContents();
  expect(subjects.length).toBeGreaterThan(1);
  for (const [subject, label] of Object.entries(SUBJECTS)) {
    if (!subjects.includes(label)) {
      // A subject without a recorded metric is not offered at all.
      expect(all(null).some(item => item.region === subject || (subject === "nucleoli" && /^nucleolar_/.test(item.metric)))).toBe(false);
      continue;
    }
    await subjectRadio(page, subject).click();
    await expect(subjectRadio(page, subject)).toBeChecked();
    const offered = await metric.locator("option:not([disabled])").evaluateAll(options => options.map(option => (option as HTMLOptionElement).value));
    expect(offered.length).toBeGreaterThan(0);
    for (const id of offered) expect(all(null).some(item => item.metric === id && item.region === regionOf(id, subject)), `${subject} ${id}`).toBe(true);
    // Each offered metric brings only recorded stains, and its switch only recorded variants.
    for (const id of offered) {
      await metric.selectOption(id);
      const stain = side(page).getByRole("combobox", {name: "染色", exact: true});
      if (await stain.count()) for (const channel of await stain.locator("option").evaluateAll(options => options.map(option => (option as HTMLOptionElement).value)))
        expect(all(null).some(item => item.metric === id && item.region === regionOf(id, subject) && item.channel === channel), `${subject} ${id} ${channel}`).toBe(true);
      const variants = side(page).getByRole("radiogroup", {name: /^(補正|単位)$/}).getByRole("radio");
      for (const name of await variants.allTextContents()) {
        const variant = name === "背景補正" ? id.replace(/_corrected$/, "") + "_corrected" : name === "µm²" ? id.replace(/_px$/, "_um2") : id.replace(/_corrected$/, "").replace(/_um2$/, "_px");
        expect(all(null).some(item => item.metric === variant && item.region === regionOf(variant, subject)), `${subject} ${variant}`).toBe(true);
      }
    }
  }
  expect(errors).toEqual([]);
});

test("a chosen condition shows its own recorded result at once, named as chosen (SR-01)", async ({page}) => {
  test.setTimeout(600_000);
  test.skip(!RECORDED.some(item => item.region === "nucleoli" && item.metric === "mean" && item.channel === "npm1" && !item.gate), "The tour recorded no nucleolar NPM1 mean.");
  const errors = await open(page, "step=statistics");
  const results = page.getByRole("region", {name: "測定結果の統計解析"});
  const summary = results.getByRole("region", {name: "結果のまとめ"});
  await expect(summary).toBeVisible({timeout: live});
  await choose(page, "nucleoli", "mean", "npm1");
  // No 計算 and no confirmation: the recorded result of the chosen condition replaces the previous one.
  await expect(results.getByRole("button", {name: "計算", exact: true})).toHaveCount(0);
  await expect(pendingCard(page)).toHaveCount(0, {timeout: live});
  await expect(summary.getByRole("heading", {level: 3})).toContainText("核小体の平均輝度（NPM1）", {timeout: live});
  await choose(page, "nucleoli", "nucleolar_count", null);
  await expect(summary.getByRole("heading", {level: 3})).toContainText("核小体数", {timeout: live});
  expect(errors).toEqual([]);
});

test("a subject chosen before the opening result arrives stays chosen (M-01)", async ({page}) => {
  test.setTimeout(600_000);
  const errors = await open(page, "step=statistics");
  // The subject shown before the opening result (核) and another one (核質), each chosen before that result arrives.
  for (const subject of ["nuclei", "nucleoplasm"]) {
    await page.goto(url("step=statistics"));
    await expect(subjectRadio(page, subject)).toBeVisible({timeout: live});
    await subjectRadio(page, subject).click();
    // The chosen condition's result (a comparison, or the per-run values where a comparison is not possible).
    await expect(page.getByRole("region", {name: "測定結果の統計解析"}).getByRole("heading", {level: 3}).first()).toBeVisible({timeout: live});
    await page.waitForLoadState("networkidle");
    // Neither the opening comparison nor the move to a recorded region takes the researcher's subject back.
    await expect(subjectRadio(page, subject)).toBeChecked();
  }
  expect(errors).toEqual([]);
});
