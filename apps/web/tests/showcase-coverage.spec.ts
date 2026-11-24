import fs from "node:fs";
import path from "node:path";
import {expect, test, type Page} from "@playwright/test";
import {SUBJECT_METRICS} from "../src/lib/workspace/metric-catalog";

/**
 * Every condition the statistics side panel offers in each scene of the public demo opens its recorded result, and
 * the demo offers every metric the product lists for the scene's regions (genellect/cytellect#257 SR-05; NS-06 for
 * the description of the runs). Run like showcase.spec.ts, against the public build with the published demo files.
 */
const PUBLISHED = fs.existsSync(path.resolve("public/showcase/seed.zip"));
const live = 240_000;
interface Scene {id: string; workspaceId: string; regions: string[]; gateChannels?: string[]}
const SCENES: Scene[] = (() => {
  try {return (JSON.parse(fs.readFileSync(path.resolve("public/showcase/snapshot/scenes.json"), "utf8")) as {scenes: Scene[]}).scenes;}
  catch {return [];}
})();
const NOT_RECORDED = "この操作の結果は公開デモに記録していません。";
const SUBJECTS: Record<string, string> = {nuclei: "核", nucleoli: "核小体", nucleoplasm: "核質"};

test.describe.configure({mode: "serial"});
test.beforeEach(() => {
  test.skip(!PUBLISHED || !SCENES.length, "The public demo files (apps/web/public/showcase) are not built.");
  test.skip(process.env.CYTELLECT_EXPECT_UNCONFIGURED !== "1", "The demo exists only in the public build without an analysis API.");
});

const side = (page: Page) => page.getByRole("complementary", {name: "解析対象"});
const results = (page: Page) => page.getByRole("region", {name: "測定結果の統計解析"});
const values = (page: Page, name: string | RegExp, root = side(page)) =>
  root.getByRole("combobox", {name, exact: typeof name === "string"}).locator("option:not([disabled])")
    .evaluateAll(options => options.map(option => (option as HTMLOptionElement).value).filter(Boolean));

/** The product's list of a subject (metric-catalog.ts), each entry by its first variant. The positive count and fraction
 * are listed only in a scene that classifies nuclei by a stain (scene.gateChannels); the cell ROI is not a subject of the
 * demo's images. */
function expectedEntries(subject: string, classifies: boolean): string[] {
  return SUBJECT_METRICS[subject as keyof typeof SUBJECT_METRICS].flatMap(group => group.metrics.map(metric => metric.variants[0].id))
    .filter(id => classifies || !id.startsWith("positive_"));
}

/** Waits until the chosen condition shows a result; fails when the demo answers with its notice instead. */
async function shows(page: Page, what: string) {
  const card = results(page).getByRole("region", {name: "選択中の条件"});
  await expect(card, `${what}: no result`).toHaveCount(0, {timeout: live});
  await expect(results(page).getByText(NOT_RECORDED), what).toHaveCount(0);
  // A comparison opens on its summary; a distribution (a stain with saturated pixels offers no comparison, Q-04) on the
  // values of each run and group.
  const result = results(page).getByRole("region", {name: /^(結果のまとめ|実験回と群ごとの値)$/}).first();
  await expect(result, what).toBeVisible({timeout: live});
  // The measure is named by its stain, never by a channel identifier (SL-02; the demo's identifiers are lower case:
  // hoechst, npm1, eu5, dna, and its stains are not: Hoechst, NPM1, 5-EU).
  await expect(result.getByRole("heading", {level: 3}).first(), what).not.toHaveText(/（[a-z][a-z0-9_]*[）、]/);
}

for (const scene of SCENES) test(`${scene.id}: every offered statistics condition opens its recorded result (SR-05)`, async ({page}) => {
  test.setTimeout(3_600_000);
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto(`/demo?id=${scene.workspaceId}&step=statistics`);
  await expect(results(page).getByRole("region", {name: "結果のまとめ"}).first()).toBeVisible({timeout: live});
  const subjects = side(page).getByRole("radiogroup", {name: "対象", exact: true});
  // The subjects follow the scene's regions: nucleoli and nucleoplasm only where the scene detected them.
  const listed = Object.keys(SUBJECTS).filter(subject => scene.regions.includes(subject));
  await expect(subjects.getByRole("radio")).toHaveText(listed.map(subject => SUBJECTS[subject]));
  let conditions = 0;
  for (const subject of listed) {
    const radio = subjects.getByRole("radio", {name: SUBJECTS[subject], exact: true});
    await radio.click();
    await expect(radio).toBeChecked();
    // Every entry the product lists for the subject is offered (the nuclear shape in every scene, the largest
    // nucleolus in the nucleolar ones): the recording holds them all, independently of what it chose to record.
    const metrics = await values(page, "指標");
    expect(metrics.sort(), `${scene.id} ${subject}`).toEqual(expectedEntries(subject, !!scene.gateChannels?.length).sort());
    for (const metric of metrics) {
      await side(page).getByRole("combobox", {name: "指標", exact: true}).selectOption(metric);
      if (metric.startsWith("positive_")) {
        // Before nuclei are classified, the panel says how to classify them in 画像, as in production; the classified
        // results are offered once a classification is in effect (showcase-result-choice.spec.ts).
        await expect(results(page).getByText(/陽性率には核の分類が必要です/)).toBeVisible({timeout: live});
        await expect(results(page).getByText(NOT_RECORDED)).toHaveCount(0);
        continue;
      }
      const variants = side(page).getByRole("radiogroup", {name: /^(補正|単位)$/}).getByRole("radio");
      const variantCount = await variants.count();
      for (let variant = 0; variant < Math.max(1, variantCount); variant++) {
        if (variantCount) {
          await expect(variants.nth(variant), `${scene.id} ${subject} ${metric}: every variant is recorded`).toBeEnabled();
          await variants.nth(variant).click();
        }
        const stain = side(page).getByRole("combobox", {name: "染色", exact: true});
        const stains = await stain.count() && await stain.isEnabled() ? await values(page, "染色") : [null];
        for (const channel of stains) {
          if (channel) await stain.selectOption(channel);
          const operation = results(page).getByRole("combobox", {name: "解析", exact: true});
          for (const kind of await values(page, "解析", results(page))) {
            await operation.selectOption(kind);
            await shows(page, `${scene.id} ${subject} ${metric} variant ${variant + 1} ${channel ?? "-"} ${kind}`);
            conditions++;
          }
        }
      }
    }
  }
  expect(conditions).toBeGreaterThan(0);
  expect(errors).toEqual([]);
});

/** Classifies the nuclei by a stain in 画像 as the recording did (Otsu per imaging date), keeping one class. */
async function classify(page: Page, channel: string, values: string, keep: string) {
  const color = page.getByRole("toolbar", {name: "画像の表示"}).getByRole("combobox", {name: "色分け", exact: true});
  await expect(color).toBeVisible({timeout: live});
  await color.selectOption("positivity");
  const inspector = page.getByRole("complementary", {name: "画像解析"});
  if (!await inspector.count()) await page.locator("header").getByRole("button", {name: "設定パネル"}).click();
  const gate = inspector.getByRole("region", {name: "チャンネルによる核の分類"});
  await gate.getByRole("combobox", {name: "判定するチャンネル", exact: true}).selectOption(channel);
  await gate.getByRole("combobox", {name: "測定値", exact: true}).selectOption(values);
  await gate.getByRole("combobox", {name: "測定値の集計対象", exact: true}).selectOption(keep);
  await gate.getByRole("button", {name: "チャンネルで分類", exact: true}).click();
  await expect(gate.locator("output")).toContainText("陽性", {timeout: live});
  await expect(gate.getByRole("alert")).toHaveCount(0);
}

// With nuclei classified, every measure the panel offers for the classified nuclei opens its recorded result (SR-05):
// the choices the recording could not answer (a run without a nucleus of the kept class, a saturated stain) are not
// offered.
for (const scene of SCENES.filter(item => item.gateChannels?.length)) for (const channel of scene.gateChannels ?? [])
  for (const reading of ["raw", "corrected"]) for (const keep of ["positive", "negative"])
    test(`${scene.id}: nuclei classified by ${channel} (${reading}, ${keep} kept) open recorded results (SR-05)`, async ({page}) => {
      test.setTimeout(1_800_000);
      const errors: string[] = [];
      page.on("pageerror", error => errors.push(error.message));
      await page.goto(`/demo?id=${scene.workspaceId}&step=image`);
      await classify(page, channel, reading, keep);
      await page.locator("header").getByRole("button", {name: "統計", exact: true}).click();
      const radio = side(page).getByRole("radiogroup", {name: "対象", exact: true}).getByRole("radio", {name: "核", exact: true});
      await expect(radio).toBeVisible({timeout: live});
      await radio.click();
      let conditions = 0;
      for (const metric of await values(page, "指標")) {
        await side(page).getByRole("combobox", {name: "指標", exact: true}).selectOption(metric);
        const variants = side(page).getByRole("radiogroup", {name: /^(補正|単位)$/}).getByRole("radio");
        const variantCount = await variants.count();
        for (let variant = 0; variant < Math.max(1, variantCount); variant++) {
          if (variantCount) {
            if (!await variants.nth(variant).isEnabled()) continue;
            await variants.nth(variant).click();
          }
          const stain = side(page).getByRole("combobox", {name: "染色", exact: true});
          const stains = await stain.count() && await stain.isEnabled() ? await values(page, "染色") : [null];
          for (const measured of stains) {
            if (measured) await stain.selectOption(measured);
            const operation = results(page).getByRole("combobox", {name: "解析", exact: true});
            for (const kind of await values(page, "解析", results(page))) {
              await operation.selectOption(kind);
              // A classified measure asks, as in production, to classify again under the current experiment
              // information; the visitor does so, as the recording did.
              const again = results(page).getByRole("button", {name: "現在の実験情報で再分類", exact: true});
              await page.waitForTimeout(600);
              if (await again.count() && await again.isEnabled()) {
                await again.click();
                await expect(page.getByRole("button", {name: "分類中…"})).toHaveCount(0, {timeout: live});
              }
              await shows(page, `${scene.id} ${channel} ${reading} ${keep} ${metric} variant ${variant + 1} ${measured ?? "-"} ${kind}`);
              conditions++;
            }
          }
        }
      }
      expect(conditions).toBeGreaterThan(0);
      expect(errors).toEqual([]);
    });

/** The scenes whose recording declares a primary measure before any statistic (scenario.primary_outcome): their
 * planned opening comparison, where git shows the plan was written before measurement (implementation plan 4.5;
 * tests/test_showcase_journal_scope.py). The demo keeps the declaration in its record but shows neither the star nor
 * the 主要／探索 marks (2026-11-24, the owner's decision; implementation plan decision 26). Production shows both
 * (workspace-primary-outcome-real.spec.ts, RP-04). */
const DECLARED: Record<string, {subject: string; metric: string; channel: string | null}> = {
  "zenodo-6643470-oxaliplatin": {subject: "nucleoli", metric: "nucleolar_eccentricity", channel: null},
  "zenodo-6643470-cisplatin": {subject: "nucleoli", metric: "nucleolar_eccentricity", channel: null},
};
/** No star beside the metric and no 主要／探索 mark on the result or on any saved comparison's button. */
async function noPrimaryMark(page: Page, what: string) {
  await expect(side(page).getByRole("button", {name: "主要指標", exact: true}), what).toHaveCount(0);
  await expect(page.locator("[data-outcome-role]"), what).toHaveCount(0);
  await expect(results(page).getByText(/^(主要|探索)$/), what).toHaveCount(0);
}
for (const scene of SCENES) test(`${scene.id}: the demo shows no primary-measure star or 主要／探索 mark, also where the recording declares one (decision 26)`, async ({page}) => {
  test.setTimeout(600_000);
  const declared = DECLARED[scene.id];
  await page.goto(`/demo?id=${scene.workspaceId}&step=statistics`);
  await expect(results(page).getByRole("region", {name: "結果のまとめ"}).first()).toBeVisible({timeout: live});
  await noPrimaryMark(page, `${scene.id} opening`);
  if (declared) {
    // The declared condition, where production would fill the star and mark the result 主要. The saved comparisons
    // are on screen (in production, each button carries 主要 or 探索).
    await side(page).getByRole("radiogroup", {name: "対象", exact: true}).getByRole("radio", {name: SUBJECTS[declared.subject], exact: true}).click();
    await side(page).getByRole("combobox", {name: "指標", exact: true}).selectOption(declared.metric);
    if (declared.channel) await side(page).getByRole("combobox", {name: "染色", exact: true}).selectOption(declared.channel);
    await shows(page, `${scene.id} declared`);
    const saved = results(page).getByRole("group", {name: "保存した比較"}).getByRole("button");
    await expect(saved.first(), `${scene.id} saved comparisons`).toBeVisible({timeout: live});
    await noPrimaryMark(page, `${scene.id} declared`);
  }
  // Another measure (exploratory in production) shows no mark either.
  await side(page).getByRole("radiogroup", {name: "対象", exact: true}).getByRole("radio", {name: "核", exact: true}).click();
  await side(page).getByRole("combobox", {name: "指標", exact: true}).selectOption("area_px");
  await shows(page, `${scene.id} other measure`);
  await noPrimaryMark(page, `${scene.id} other measure`);
  // グラフ names the saved result with the same mark in production; the demo shows none.
  await page.locator("header").getByRole("button", {name: "グラフ", exact: true}).click();
  const figure = page.getByRole("region", {name: "図の作成・保存"});
  await expect(figure).toBeVisible({timeout: live});
  // The saved result is shown (its 保存 appears only then), so its label is drawn where production puts the mark.
  await expect(figure.getByRole("button", {name: "保存", exact: true})).toBeVisible({timeout: live});
  await expect(figure.getByRole("status").filter({hasText: "図を更新中"})).toHaveCount(0, {timeout: live});
  await expect(page.locator("[data-outcome-role]"), `${scene.id} figure`).toHaveCount(0);
  await expect(side(page).getByRole("button", {name: "主要指標", exact: true}), `${scene.id} figure`).toHaveCount(0);
});

for (const scene of SCENES) test(`${scene.id}: with independence unconfirmed, a comparison is the runs' description (NS-06)`, async ({page}) => {
  test.setTimeout(600_000);
  await page.goto(`/demo?id=${scene.workspaceId}&step=statistics`);
  const summary = results(page).getByRole("region", {name: "結果のまとめ"}).first();
  await expect(summary).toBeVisible({timeout: live});
  const operation = results(page).getByRole("combobox", {name: "解析", exact: true});
  await expect(operation).toHaveValue("comparison");
  // Each run's values and differences, without a test: the method is fixed to the description and no association
  // (which needs independent runs) is offered.
  await expect(summary).toContainText("記述統計");
  await expect(results(page).getByRole("combobox", {name: "方法", exact: true})).toHaveValue("none");
  await expect(operation.locator("option[value=association]")).toHaveAttribute("disabled", "");
  // Another metric of the same scene keeps the description.
  const metrics = side(page).getByRole("combobox", {name: "指標", exact: true});
  await side(page).getByRole("radiogroup", {name: "対象", exact: true}).getByRole("radio", {name: "核", exact: true}).click();
  await metrics.selectOption("area_px");
  await shows(page, `${scene.id} nuclei area`);
  await expect(results(page).getByRole("region", {name: "結果のまとめ"}).first()).toContainText("記述統計");
});
