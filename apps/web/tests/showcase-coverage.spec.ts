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

/** The product's list of a subject (metric-catalog.ts), each entry by its first variant, without the positive count
 * and fraction (offered once nuclei are classified) and the cell ROI (no cell outlines in the demo's images). */
function expectedEntries(subject: string): string[] {
  return SUBJECT_METRICS[subject as keyof typeof SUBJECT_METRICS].flatMap(group => group.metrics.map(metric => metric.variants[0].id))
    .filter(id => !id.startsWith("positive_"));
}

/** Waits until the chosen condition shows a result; fails when the demo answers with its notice instead. */
async function shows(page: Page, what: string) {
  const card = results(page).getByRole("region", {name: "選択中の条件"});
  await expect(card, `${what}: no result`).toHaveCount(0, {timeout: live});
  await expect(results(page).getByText(NOT_RECORDED), what).toHaveCount(0);
  await expect(results(page).getByRole("region", {name: "結果のまとめ"}).first(), what).toBeVisible({timeout: live});
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
    expect(metrics.sort(), `${scene.id} ${subject}`).toEqual(expectedEntries(subject).sort());
    for (const metric of metrics) {
      await side(page).getByRole("combobox", {name: "指標", exact: true}).selectOption(metric);
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

/** The scenes whose recording declares a primary measure before any statistic (scenario.primary_outcome): their
 * planned opening comparison, where git shows the plan was written before measurement (implementation plan 4.5,
 * NS-06; tests/test_showcase_journal_scope.py). */
const DECLARED: Record<string, {subject: string; metric: string; channel: string | null}> = {
  "zenodo-6643470-oxaliplatin": {subject: "nucleoli", metric: "nucleolar_eccentricity", channel: null},
  "zenodo-6643470-cisplatin": {subject: "nucleoli", metric: "nucleolar_eccentricity", channel: null},
};
const role = (page: Page) => results(page).locator("[data-outcome-role]");
for (const scene of SCENES.filter(item => DECLARED[item.id])) test(`${scene.id}: the recorded primary measure stays declared while exploratory measures are chosen (NS-06)`, async ({page}) => {
  test.setTimeout(600_000);
  const declared = DECLARED[scene.id];
  await page.goto(`/demo?id=${scene.workspaceId}&step=statistics`);
  await expect(results(page).getByRole("region", {name: "結果のまとめ"}).first()).toBeVisible({timeout: live});
  const star = side(page).getByRole("button", {name: "主要指標", exact: true});
  // The declared condition: the star is filled and cannot be pressed (a visitor cannot declare after the results).
  await side(page).getByRole("radiogroup", {name: "対象", exact: true}).getByRole("radio", {name: SUBJECTS[declared.subject], exact: true}).click();
  await side(page).getByRole("combobox", {name: "指標", exact: true}).selectOption(declared.metric);
  if (declared.channel) await side(page).getByRole("combobox", {name: "染色", exact: true}).selectOption(declared.channel);
  await shows(page, `${scene.id} declared`);
  await expect(star).toBeDisabled();
  await expect(star).toHaveAttribute("aria-pressed", "true");
  await expect(role(page)).toHaveText("主要");
  // Any other measure is exploratory, and the declaration is kept.
  await side(page).getByRole("radiogroup", {name: "対象", exact: true}).getByRole("radio", {name: "核", exact: true}).click();
  await side(page).getByRole("combobox", {name: "指標", exact: true}).selectOption("area_px");
  await shows(page, `${scene.id} exploratory`);
  await expect(star).toBeDisabled();
  await expect(star).toHaveAttribute("aria-pressed", "false");
  await expect(role(page)).toHaveText("探索");
});

for (const scene of SCENES.filter(item => !DECLARED[item.id])) test(`${scene.id}: a scene without a recorded declaration shows no primary mark`, async ({page}) => {
  test.setTimeout(600_000);
  await page.goto(`/demo?id=${scene.workspaceId}&step=statistics`);
  await expect(results(page).getByRole("region", {name: "結果のまとめ"}).first()).toBeVisible({timeout: live});
  await expect(side(page).getByRole("button", {name: "主要指標", exact: true})).toHaveCount(0);
  await expect(role(page)).toHaveCount(0);
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
