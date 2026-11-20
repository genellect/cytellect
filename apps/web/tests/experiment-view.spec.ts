import fs from "node:fs";
import path from "node:path";
import {expect, test} from "@playwright/test";

/**
 * The 実験 view says what a run is, how values are combined and what n counts, states what is in place, and offers one
 * next step (Issue #257, requirements ED-01–ED-04). The demo's recorded design reads as text, never as disabled inputs.
 * Run on the public demo build (no analysis API) with the published demo files, like showcase.spec.ts.
 */
const PUBLISHED = fs.existsSync(path.resolve("public/showcase/seed.zip"));
const live = 240_000;
interface Scene {id: string; workspaceId: string}
const SCENES: Scene[] = (() => {
  try {return (JSON.parse(fs.readFileSync(path.resolve("public/showcase/snapshot/scenes.json"), "utf8")) as {scenes: Scene[]}).scenes;}
  catch {return [];}
})();

test.describe.configure({mode: "serial"});
test.beforeEach(() => {
  test.skip(!PUBLISHED, "The public demo files (apps/web/public/showcase/seed.zip) are not built.");
  test.skip(process.env.CYTELLECT_EXPECT_UNCONFIGURED !== "1", "The demo exists only in the public build without an analysis API.");
});

for (const scene of SCENES.length ? SCENES : [undefined]) test(`the experiment view explains runs, states what is in place and leads on${scene ? ` (${scene.id})` : ""}`, async ({page}) => {
  test.setTimeout(300_000);
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto(scene ? `/demo?id=${scene.workspaceId}` : "/demo");
  await page.locator("header").getByRole("button", {name: "実験", exact: true}).click();
  const view = page.getByRole("region", {name: "実験デザイン"});
  // C-1: the heading names the purpose; the number of screens is a supplement.
  await expect(view.getByRole("heading", {level: 1})).toHaveText(/^(対照と処理を、実験回ごとに対にして比べる|1 群の値を、実験回ごとに示す)/, {timeout: live});
  // ED-01: what a run is, why runs are kept apart, what n counts and how values are combined, in the first view.
  const explain = view.getByRole("region", {name: "実験回とまとめ方"});
  await expect(explain).toContainText("n は核や視野の数ではなく、実験回の数です");
  await expect(explain).toContainText("回ごとに分けて記録します");
  await expect(explain.getByRole("list", {name: "値のまとめ方"}).getByRole("listitem").first()).toHaveText("核ごとの値");
  await expect(explain).toBeInViewport();
  // ED-02: one line of what is in place, and one next step that leads on.
  await expect(view.getByRole("status")).toContainText(/\d+ 実験回 × \d 群、\d+ 視野を割り当て済み。/);
  const next = view.getByRole("button", {name: /^(統計で比べる|画像で検出を確認)$/});
  await expect(next).toHaveCount(1);
  // ED-03: the recorded design is text; no input is shown disabled; why independence is unconfirmed is stated.
  await expect(view.locator("input:disabled, select:disabled")).toHaveCount(0);
  await expect(view).toContainText("公開データの実験デザインです（変更できません）。");
  if (/独立性が未確認/.test(await view.getByRole("status").innerText())) await expect(view).toContainText("出典に、実験回が独立に行われたかの記載がないため");
  await expect(view.getByRole("list", {name: "統計の前の確認事項"})).not.toContainText("独立性：未確認");
  // ED-04: one name for the run on the experiment and statistics views.
  await expect(view).not.toContainText("実験単位");
  await next.click();
  const statistics = page.getByRole("region", {name: "測定結果の統計解析"});
  await expect(statistics).toBeVisible({timeout: live});
  await expect(statistics).not.toContainText("実験単位");
  expect(errors).toEqual([]);
});
