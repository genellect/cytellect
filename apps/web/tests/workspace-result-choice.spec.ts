import {expect, test, type Page} from "@playwright/test";
import {execFileSync} from "node:child_process";
import {createHash} from "node:crypto";
import {mkdir, readFile} from "node:fs/promises";
import path from "node:path";

/** genellect/cytellect#257 SR-06: SR-01 to SR-04 in production, on the registered public BBBC007 field a9 (CC0) through
 * the real UI, API, worker and Fiji StarDist, with the flow of owner decision 11 (2026-11-21): 統計 asks for no
 * confirmation, a chosen condition is described at once, and only work left in an earlier screen is named at the
 * result. One field and one group (1 画面): it checks the screens' behaviour, never detection accuracy or biology.
 * A comparison of declared groups needs more registered fields than the CI prepares; its pointer, declaration and
 * request are covered by workspace-unresolved-nucleoli.spec.ts and workspace-api.spec.ts (transport records). */
test("#257 SR-06: the chosen condition's own result opens in 統計 and グラフ on a public workspace", async ({page}) => {
  const inputs = process.env.CYTELLECT_REAL_INPUTS, output = process.env.CYTELLECT_REAL_OUTPUT;
  const python = process.env.CYTELLECT_TEST_PYTHON, data = process.env.CYTELLECT_TEST_DATA_DIR, api = process.env.CYTELLECT_TEST_API_ORIGIN;
  if (process.env.CYTELLECT_REQUIRE_REAL_FIJI === "1") for (const value of [inputs, output, python, data, api]) expect(value).toBeTruthy();
  test.skip(!inputs || !output || !python || !data || !api, "Requires explicitly configured isolated Fiji runtime and registered public inputs");
  test.setTimeout(900_000);
  await mkdir(output!, {recursive: true});
  const manifest = JSON.parse(await readFile(path.join(inputs!, "manifest.json"), "utf8"));
  const original = ["a9-actin.tif", "a9-dna.tif"];
  const bytes = await Promise.all(original.map(name => readFile(path.join(inputs!, name))));
  bytes.forEach((value, index) => expect(createHash("sha256").update(value).digest("hex")).toBe(manifest.files[original[index]]));
  // One-use token, captured only in memory.
  const token = execFileSync(python!, ["-B", "-c", "import os;from pathlib import Path;from cytellect_api.db import Store;print(Store(Path(os.environ['CYTELLECT_TEST_DATA_DIR']),workspace_retention_mode=('manual' if (Path(os.environ['CYTELLECT_TEST_DATA_DIR'])/'.manual-workspace-retention').exists() else 'ttl')).invite(3600))"], {encoding: "utf8", env: process.env, stdio: ["ignore", "pipe", "ignore"]}).trim();
  expect((await page.request.post(`${api}/v1/invitations/redeem`, {headers: {Origin: process.env.CYTELLECT_WEB_URL!, "X-Cytellect-Request": "1"}, data: {token}})).ok()).toBeTruthy();
  const loaded = page.waitForResponse(response => new URL(response.url()).pathname === "/v1/workspaces" && response.request().method() === "GET");
  await page.goto("/workspace"); await loaded;
  await page.getByRole("button", {name: "新しいワークスペース", exact: true}).click();
  // Every description request, with what it describes.
  const described: Array<{metric?: string; channel?: string | null}> = [];
  page.on("request", request => {
    if (request.method() !== "POST" || !new URL(request.url()).pathname.endsWith("/descriptive")) return;
    const selection = (request.postDataJSON() as {selection?: {metric?: string; channel_id?: string | null}}).selection;
    described.push({metric: selection?.metric, channel: selection?.channel_id ?? null});
  });
  await page.getByTestId("file-input").setInputFiles(bytes.map((buffer, index) => ({name: `a9_c${index + 1}.tif`, mimeType: "image/tiff", buffer})));
  await page.getByRole("region",{name:"取り込みの一覧"}).getByRole("button",{name:"追加",exact:true}).click();
  // One screen: the experiment view suggests its only run and group, applied by the researcher (#284 W5, W6).
  await page.getByRole("navigation",{name:"作業の切替"}).getByRole("button",{name:"実験",exact:true}).click();
  await page.getByRole("button",{name:/^1 画面/}).click();
  await page.getByRole("region",{name:"群・実験回が未割り当ての視野"}).getByRole("button",{name:"案を適用",exact:true}).click();
  await page.getByRole("navigation",{name:"作業の切替"}).getByRole("button",{name:"画像",exact:true}).click();
  await expect(page.getByRole("toolbar", {name: "画像の表示"}).getByRole("combobox", {name: "領域", exact: true})).toBeEnabled({timeout: 120_000});
  await page.locator("summary[aria-label='画像の設定']").click();
  await page.getByRole("button", {name: "染色対応", exact: true}).click();
  await page.getByLabel("c1の染色名").fill("F-actin");
  await page.getByLabel("c1の役割").selectOption("measure");
  await page.getByLabel("c2の染色名").fill("DNA");
  await page.getByLabel("c2の役割").selectOption("nuclear");
  await page.getByRole("button", {name: "保存", exact: true}).click();
  await expect(page.getByText("核 · 検出候補", {exact: true})).toBeVisible({timeout: 300_000});

  const modes = page.getByRole("navigation", {name: "作業の切替"});
  const options = page.getByRole("complementary", {name: "解析対象"});
  const panel = page.getByRole("region", {name: "測定結果の統計解析"});
  const card = panel.getByRole("region", {name: "選択中の条件"});
  const figure = panel.getByRole("img", {name: "保存された解析結果のグラフ"});
  const earlierWork = panel.getByRole("button", {name: /^(画像|実験)：/});
  await modes.getByRole("button", {name: "統計", exact: true}).click();
  await options.getByRole("combobox", {name: "指標", exact: true}).selectOption("area_px");
  // Decision 11 and SR-02: the candidates are not adopted yet. The result's place keeps the condition's name and names the
  // one piece of earlier work; there is no confirmation to tick, no figure and no request.
  await expect(card.getByRole("heading", {level: 3})).toContainText("面積");
  await expect(card.getByRole("button", {name: "画像：未測定 1 視野", exact: true})).toBeVisible();
  await expect(panel.getByRole("checkbox", {name: /確認済み|欠測として残して計算する/})).toHaveCount(0);
  await expect(figure).toHaveCount(0);
  expect(described).toEqual([]);
  await card.getByRole("button", {name: "画像：未測定 1 視野", exact: true}).click();
  await expect(modes.getByRole("button", {name: "画像", exact: true})).toHaveAttribute("aria-current", "page");
  await page.getByRole("button", {name: "候補を採用", exact: true}).click();
  await expect(page.getByText("核 · 検出候補", {exact: true})).toHaveCount(0);
  await expect(page.getByRole("button", {name: "測定", exact: true})).toBeEnabled({timeout: 120_000});

  // Adopted in 画像, the chosen area is described as soon as 統計 is shown (D-5): no 計算, no confirmation.
  await modes.getByRole("button", {name: "統計", exact: true}).click();
  await expect.poll(() => described.filter(value => value.metric === "area_px").length, {timeout: 240_000}).toBe(1);
  await expectResult(page, figure);
  await expect(earlierWork).toHaveCount(0);

  // SR-02: another condition without a result. The area's figure leaves the main display at once; the card names the
  // new condition until its own description arrives.
  await options.getByRole("combobox", {name: "指標", exact: true}).selectOption("mean");
  await options.getByRole("combobox", {name: "染色", exact: true}).selectOption("c1");
  await expect(card.getByRole("heading", {level: 3})).toContainText(/平均輝度.*F-actin/);
  await expect(figure).toHaveCount(0);
  await expect.poll(() => described.filter(value => value.metric === "mean" && value.channel === "c1").length, {timeout: 240_000}).toBe(1);
  await expectResult(page, figure);
  // SR-03: the adoption and the measure's change hold; nothing earlier is asked for again.
  await expect(earlierWork).toHaveCount(0);
  await expect(panel.getByRole("checkbox", {name: /確認済み/})).toHaveCount(0);

  // SR-01: back to the area, its saved result opens without another request or press.
  const requests = described.length;
  await options.getByRole("combobox", {name: "指標", exact: true}).selectOption("area_px");
  await expect(card).toHaveCount(0);
  await expectResult(page, figure);
  await page.waitForTimeout(1500);
  expect(described.length).toBe(requests);
  await page.screenshot({path: path.join(output!, "sr06-statistics.png"), fullPage: true});

  // SR-04: グラフ follows the side panel's choice, and a saved figure chosen there sets the side panel.
  await modes.getByRole("button", {name: "グラフ", exact: true}).click();
  const saved = page.getByRole("combobox", {name: "保存した図", exact: true});
  await expect(saved.locator("option:checked")).toContainText("面積");
  const mean = saved.locator("option").filter({hasText: /平均輝度/});
  await expect(mean).toHaveCount(1);
  await saved.selectOption({label: (await mean.textContent())!});
  await expect(options.getByRole("combobox", {name: "指標", exact: true})).toHaveValue("mean");
  await expect(saved.locator("option:checked")).toContainText("平均輝度");
  expect(described.length).toBe(requests);
  // The automatic change of the analysis and its one-line reason needs a design the public field cannot make here
  // (saturated pairs, an association of unconfirmed runs); it is checked on the public demo (showcase-result-choice.spec.ts).
});

/** The shown result: its figure has loaded and no condition card stands in its place. */
async function expectResult(page: Page, figure: ReturnType<Page["getByRole"]>) {
  const panel = page.getByRole("region", {name: "測定結果の統計解析"});
  await expect(panel.getByRole("region", {name: "選択中の条件"})).toHaveCount(0, {timeout: 240_000});
  await expect(figure.first()).toBeVisible({timeout: 120_000});
  await expect.poll(() => figure.first().evaluate(image => (image as HTMLImageElement).naturalWidth), {timeout: 60_000}).toBeGreaterThan(0);
  expect(await panel.getByRole("alert").allTextContents()).toEqual([]);
}
