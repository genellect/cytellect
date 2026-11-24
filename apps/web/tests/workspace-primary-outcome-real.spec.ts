import {expect, test, type Page} from "@playwright/test";
import {execFileSync} from "node:child_process";
import {createHash} from "node:crypto";
import {mkdir, readFile} from "node:fs/promises";
import path from "node:path";

/** genellect/cytellect#257 RP-04 (implementation plan §4.5, Issue E) in the order a researcher works, on the registered
 * public BBBC007 field a9 (CC0) through the real UI, API, worker and Fiji StarDist. No time is supplied by the test:
 * the declaration time is the server's (analysis-spec PUT) and a result's time is the server's creation of its
 * statistics job (`calculated_at`). primary-outcome.spec.ts covers the same rules on fixed transport records.
 * - A: a condition without a result is declared with the star, and its result comes afterwards -> 主要.
 * - B: a condition is chosen, its result is described at once (owner decisions 9 and 11), and the star is pressed only
 *   afterwards -> 探索 stays (a declaration after the result is not a prior one).
 * One field: it checks the screens' behaviour, never detection accuracy or biology. */
test("#257 RP-04: a declaration before the result marks it 主要, one after it stays 探索", async ({page}) => {
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

  // What the server recorded: each description request with its job, each job's kind and calculation time, and the
  // declaration the analysis-spec PUT returned.
  const described: Array<{metric?: string; channel: string | null; job?: string}> = [];
  const jobs = new Map<string, {kind: string; calculated_at: number | null}>();
  const declarations: Array<{metric: string; region_set_id: string; channel_id: string | null; declared_at: number}> = [];
  page.on("request", request => {
    if (request.method() !== "POST" || !new URL(request.url()).pathname.endsWith("/descriptive")) return;
    const selection = (request.postDataJSON() as {selection?: {metric?: string; channel_id?: string | null}}).selection;
    described.push({metric: selection?.metric, channel: selection?.channel_id ?? null});
  });
  page.on("response", async response => {
    const {pathname} = new URL(response.url()), method = response.request().method();
    if (!response.ok()) return;
    try {
      if (method === "POST" && pathname.endsWith("/descriptive")) {
        const job = (await response.json() as {job_id: string}).job_id;
        const entry = described.findLast(value => !value.job);
        if (entry) entry.job = job;
      } else if (method === "GET" && /^\/v1\/workspaces\/[^/]+\/jobs$/.test(pathname)) {
        for (const job of await response.json() as Array<{id: string; kind: string; calculated_at?: number | null}>)
          jobs.set(job.id, {kind: job.kind, calculated_at: job.calculated_at ?? null});
      } else if (method === "PUT" && pathname.endsWith("/analysis-spec")) {
        const primary = (await response.json() as {spec?: {primary_outcome?: typeof declarations[number]}}).spec?.primary_outcome;
        if (primary) declarations.push(primary);
      }
    } catch { /* a response the page navigated away from */ }
  });

  await page.getByTestId("file-input").setInputFiles(bytes.map((buffer, index) => ({name: `a9_c${index + 1}.tif`, mimeType: "image/tiff", buffer})));
  await page.getByRole("button", {name: /^1 画面/}).click();
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
  const star = options.getByRole("button", {name: "主要指標", exact: true});
  const panel = page.getByRole("region", {name: "測定結果の統計解析"});
  const card = panel.getByRole("region", {name: "選択中の条件"});
  const figure = panel.getByRole("img", {name: "保存された解析結果のグラフ"});
  // The mark beside the shown condition's name (the first line in the settings that carries one).
  const shownRole = panel.locator("p:has(> [data-outcome-role])").first().locator("[data-outcome-role]");

  // A: the area is chosen while 画像 still holds its candidates, so it has no result yet, and is declared at once.
  await modes.getByRole("button", {name: "統計", exact: true}).click();
  await options.getByRole("combobox", {name: "指標", exact: true}).selectOption("area_px");
  await expect(card.getByRole("button", {name: "画像：未測定 1 視野", exact: true})).toBeVisible();
  await expect(panel.locator("[data-outcome-role]")).toHaveCount(0);
  await expect(star).toHaveAttribute("aria-pressed", "false");
  await star.click();
  await expect(star).toHaveAttribute("aria-pressed", "true");
  await expect.poll(() => declarations.at(-1)?.metric).toBe("area_px");
  const area = declarations.at(-1)!;
  expect(area).toMatchObject({region_set_id: "nuclei", channel_id: null});
  expect(described).toEqual([]);
  // The declaration changes neither detection nor measurement, so the candidates detected before it stay and are adopted
  // in 画像 as they are; the area is described when 統計 is shown again.
  await card.getByRole("button", {name: "画像：未測定 1 視野", exact: true}).click();
  await expect(modes.getByRole("button", {name: "画像", exact: true})).toHaveAttribute("aria-current", "page");
  await expect(page.getByText("核 · 検出候補", {exact: true})).toBeVisible();
  const accepted = page.waitForResponse(response => /\/runs\/[^/]+\/accept$/.test(new URL(response.url()).pathname));
  await page.getByRole("button", {name: "候補を採用", exact: true}).click();
  expect((await accepted).status()).toBe(200);
  await expect(page.getByText("核 · 検出候補", {exact: true})).toHaveCount(0);
  await expect(page.getByRole("button", {name: "測定", exact: true})).toBeEnabled({timeout: 120_000});
  expect(described).toEqual([]);
  await modes.getByRole("button", {name: "統計", exact: true}).click();
  await expect.poll(() => described.filter(value => value.metric === "area_px" && value.job).length, {timeout: 240_000}).toBe(1);
  await expectResult(page, figure);
  const areaJob = described.find(value => value.metric === "area_px")!.job!;
  await expect.poll(() => jobs.get(areaJob)?.calculated_at ?? null, {timeout: 60_000}).not.toBeNull();
  expect(jobs.get(areaJob)!.kind).toBe("statistics");
  expect(jobs.get(areaJob)!.calculated_at!).toBeGreaterThan(area.declared_at);
  // Judged only once the result is shown: before it, a pending choice of the declared measure reads 主要 by its measure.
  await expect(shownRole).toHaveText("主要");
  await expect(shownRole).toHaveAttribute("data-outcome-role", "primary");
  await page.screenshot({path: path.join(output!, "rp04-primary.png"), fullPage: true});

  // B: another condition without a result is chosen in the ready workspace. It is described at once, without any press.
  await options.getByRole("combobox", {name: "指標", exact: true}).selectOption("mean");
  await options.getByRole("combobox", {name: "染色", exact: true}).selectOption("c1");
  await expect.poll(() => described.filter(value => value.metric === "mean" && value.channel === "c1" && value.job).length, {timeout: 240_000}).toBe(1);
  const mean = described.find(value => value.metric === "mean" && value.channel === "c1")!;
  // Described while the area was still the declared measure: the star was not pressed for the mean before its result.
  expect(declarations.at(-1)?.metric).toBe("area_px");
  await expectResult(page, figure);
  await expect(shownRole).toHaveText("探索");
  await expect(star).toHaveAttribute("aria-pressed", "false");
  // The star is pressed after the result: the declaration moves to the mean, recorded after its statistics.
  await star.click();
  await expect(star).toHaveAttribute("aria-pressed", "true");
  await expect.poll(() => declarations.at(-1)?.metric).toBe("mean");
  const declaredMean = declarations.at(-1)!;
  expect(declaredMean).toMatchObject({region_set_id: "nuclei", channel_id: "c1"});
  await expect.poll(() => jobs.get(mean.job!)?.calculated_at ?? null, {timeout: 60_000}).not.toBeNull();
  expect(jobs.get(mean.job!)!.kind).toBe("statistics");
  expect(jobs.get(mean.job!)!.calculated_at!).toBeLessThan(declaredMean.declared_at);
  // The declared measure's own result, shown, stays 探索; the declaration asks for no description of its own.
  await expect(shownRole).toHaveText("探索");
  await expect(shownRole).toHaveAttribute("data-outcome-role", "exploratory");
  const requests = described.length;
  await page.waitForTimeout(1500);
  expect(described.length).toBe(requests);
  await expect(shownRole).toHaveText("探索");
  await page.screenshot({path: path.join(output!, "rp04-exploratory.png"), fullPage: true});
});

/** The shown result: its figure has loaded and no condition card stands in its place. */
async function expectResult(page: Page, figure: ReturnType<Page["getByRole"]>) {
  const panel = page.getByRole("region", {name: "測定結果の統計解析"});
  await expect(panel.getByRole("region", {name: "選択中の条件"})).toHaveCount(0, {timeout: 240_000});
  await expect(figure.first()).toBeVisible({timeout: 120_000});
  await expect.poll(() => figure.first().evaluate(image => (image as HTMLImageElement).naturalWidth), {timeout: 60_000}).toBeGreaterThan(0);
  expect(await panel.getByRole("alert").allTextContents()).toEqual([]);
}
