import {expect, test} from "@playwright/test";
import {execFileSync} from "node:child_process";
import {existsSync} from "node:fs";
import {mkdir, readFile, writeFile} from "node:fs/promises";
import path from "node:path";

/** Goals C1: the two-group workflow through the real UI, API, worker and Fiji StarDist, on the
 * registered public JUMP Cell Painting images (cpg0016 source_13, CC0; fixtures/public/jump-plk1).
 * Requirements E-01–E-08 and N-02. It checks the workflow (entry, missing combinations, one ↔ two
 * screens, measurement, statistics), never detection accuracy or biological validity; only the
 * direction and the structure of the result are asserted. Images: scripts/public_jump_plk1.py. */
const RUNS = ["Run1", "Run2", "Run3"] as const;
const PLATES: Record<(typeof RUNS)[number], string> = {Run1: "CP-CC9-R1-01", Run2: "CP-CC9-R2-01", Run3: "CP-CC9-R3-01"};
// The batch dates of the public plates (20220914_Run1, 20221009_Run2, 20221017_Run3), entered as the researcher's record.
const PERFORMED: Record<(typeof RUNS)[number], string> = {Run1: "2022-09-14", Run2: "2022-10-09", Run3: "2022-10-17"};
const GROUPS = [{well: "A02", label: "Non-targeting"}, {well: "A23", label: "PLK1 KO"}] as const;
const SITES = [1, 2, 3, 4, 5];
// JUMP channel → file suffix (load_data URL_Orig* columns) → channel ID the grouping assigns.
const CHANNELS = [{id: "c01", suffix: "A01Z01C01", stain: "Hoechst", role: "nuclear"}, {id: "c03", suffix: "A02Z01C03", stain: "RNA", role: "measure"},
  {id: "c04", suffix: "A03Z01C04", stain: "ER", role: "measure"}, {id: "c05", suffix: "A04Z01C05", stain: "AGP", role: "measure"}] as const;

const imagesOf = (inputs: string, run: (typeof RUNS)[number], well: string) =>
  SITES.flatMap(site => CHANNELS.map(channel => path.join(inputs, `${PLATES[run]}_${well}_T0001F${String(site).padStart(3, "0")}L01${channel.suffix}.tif`)));

test("C1: two groups × three runs of public JUMP images reach a paired comparison with real Fiji", async ({page}) => {
  const inputs = process.env.CYTELLECT_JUMP_PLK1_INPUTS;
  test.skip(!inputs, "Set CYTELLECT_JUMP_PLK1_INPUTS to the images of scripts/public_jump_plk1.py");
  test.setTimeout(3_600_000);
  const python = process.env.CYTELLECT_TEST_PYTHON!, api = process.env.CYTELLECT_TEST_API_ORIGIN!, origin = process.env.CYTELLECT_WEB_URL!;
  const output = process.env.CYTELLECT_JUMP_PLK1_OUTPUT!;
  for (const value of [python, api, origin, output, process.env.CYTELLECT_TEST_DATA_DIR]) expect(value).toBeTruthy();
  const repository = path.resolve(__dirname, "../../..");
  expect(path.resolve(output).startsWith(repository + path.sep), "evidence stays outside the checkout").toBe(false);
  expect(path.resolve(inputs!).startsWith(repository + path.sep), "images stay outside the checkout").toBe(false);
  await mkdir(output, {recursive: true});

  // The images are the registered public files, byte for byte.
  const registered = JSON.parse(await readFile(path.join(repository, "fixtures/public/jump-plk1/files.json"), "utf8")) as {files: Array<{name: string; sha256: string; site: number}>};
  const used = registered.files.filter(file => SITES.includes(file.site));
  expect(used).toHaveLength(120);
  for (const file of used) expect(existsSync(path.join(inputs!, file.name)), file.name).toBe(true);
  execFileSync(python, ["-B", "-I", "-c", "import sys,json,hashlib\nfrom pathlib import Path\nroot=Path(sys.argv[1])\nfor item in json.loads(sys.argv[2]):\n assert hashlib.sha256((root/item['name']).read_bytes()).hexdigest()==item['sha256'],item['name']", inputs!, JSON.stringify(used)]);

  const token = execFileSync(python, ["-B", "-c", "import os;from pathlib import Path;from cytellect_api.db import Store;print(Store(Path(os.environ['CYTELLECT_TEST_DATA_DIR']),workspace_retention_mode=('manual' if (Path(os.environ['CYTELLECT_TEST_DATA_DIR'])/'.manual-workspace-retention').exists() else 'ttl')).invite(3600))"], {encoding: "utf8", env: process.env, stdio: ["ignore", "pipe", "ignore"]}).trim();
  expect((await page.request.post(`${api}/v1/invitations/redeem`, {headers: {Origin: origin, "X-Cytellect-Request": "1"}, data: {token}})).ok()).toBeTruthy();

  const consoleErrors: string[] = [], pageErrors: string[] = [], dialogs: string[] = [];
  page.on("console", message => {if (message.type() === "error") consoleErrors.push(message.text());});
  page.on("pageerror", error => pageErrors.push(error.message));
  page.on("dialog", dialog => {dialogs.push(dialog.message()); void dialog.dismiss();});
  const writes: string[] = [];
  page.on("request", request => {if (request.method() !== "GET") writes.push(`${request.method()} ${new URL(request.url()).pathname}`);});
  // Product alerts are inside the workspace; the empty Next.js route announcer outside it is not one.
  const noAlerts = async () => expect(await page.getByRole("main").getByRole("alert").allTextContents()).toEqual([]);

  // E-01: the first screen offers one or two screens, each with a short description.
  await page.goto("/workspace");
  const choice = page.getByRole("region", {name: "解析の形を選ぶ"});
  await expect(choice.getByRole("heading", {name: "解析の形を選ぶ", level: 1})).toBeVisible();
  await expect(choice.getByRole("button", {name: /^1 画面/})).toBeEnabled();
  await expect(choice.getByRole("button", {name: /^1 画面/})).toContainText("1 つの群を記述する");
  await expect(choice.getByRole("button", {name: /^1 画面/})).toContainText("検定はしません。");
  await expect(choice.getByRole("button", {name: /^2 画面/})).toBeEnabled();
  await expect(choice.getByRole("button", {name: /^2 画面/})).toContainText("2 つの群を比べる");
  await expect(choice.getByRole("button", {name: /^2 画面/})).toContainText("同じ実験回の 2 群を対にして比べます。");
  await choice.getByLabel("最初の実験回の実施日").fill(PERFORMED.Run1);
  await choice.getByRole("button", {name: /^2 画面/}).click();

  const setup = page.getByRole("region", {name: "実験の形"});
  await expect(setup.getByRole("heading", {name: "2 画面：2 つの群を比べる", level: 1})).toBeVisible();
  await expect(page).toHaveURL(/[?&]id=[^&]+/);
  const workspace = new URL(page.url()).searchParams.get("id")!;
  // Choosing the form saves the design only; nothing is detected or measured (requirements E-01).
  expect(writes.some(value => /\/runs|\/region-fields|\/proposal/.test(value))).toBe(false);
  const grid = setup.getByRole("table", {name: "群と実験回"});
  const issues = setup.getByRole("list", {name: "統計の前に確かめること"});

  // E-02: name the two groups and choose the control. The control is a radio choice on one group.
  const headers = grid.getByRole("columnheader");
  for (const [index, group] of GROUPS.entries()) {
    const name = headers.nth(index + 1).getByLabel("群の名前");
    await name.fill(group.label);
    await name.blur();
    await expect(headers.nth(index + 1).getByLabel("群の名前")).toHaveValue(group.label);
  }
  const controls = grid.getByRole("radio", {name: "対照"});
  await expect(controls).toHaveCount(2);
  await headers.nth(2).getByRole("radio", {name: "対照"}).check();
  await expect(headers.nth(2).getByRole("radio", {name: "対照"})).toBeChecked();
  await headers.nth(1).getByRole("radio", {name: "対照"}).check();
  await expect(headers.nth(1).getByRole("radio", {name: "対照"})).toBeChecked();
  await expect(issues).not.toContainText("どちらの群を対照にするか選んでください。");

  // E-03: the runs are shared by both screens; names and dates are the researcher's entries.
  const rows = grid.getByRole("row");
  const runName = (index: number) => rows.nth(index + 1).getByRole("rowheader").getByLabel("名前", {exact: true});
  await runName(0).fill("Run1");
  await runName(0).blur();
  for (const run of RUNS.slice(1)) {
    await setup.getByLabel("実験回を追加（実施日）").fill(PERFORMED[run]);
    await setup.getByRole("button", {name: "追加", exact: true}).click();
    const index = RUNS.indexOf(run);
    await expect(rows).toHaveCount(index + 2);
    await expect(runName(index)).toHaveValue(PERFORMED[run]);
    await runName(index).fill(run);
    await runName(index).blur();
  }
  for (const [index, run] of RUNS.entries()) {
    await expect(runName(index)).toHaveValue(run);
    await expect(rows.nth(index + 1).getByRole("rowheader").getByLabel("実施日")).toHaveValue(PERFORMED[run]);
  }
  for (const run of RUNS) await expect(issues).toContainText(`${run} に ${GROUPS.map(group => group.label).join("、")} の画像がありません。この回は対にできません。`);

  // E-03/E-04: each run × group's fields are added in its own cell. Group, run and stain come from
  // the cell and the researcher's entries, not from the plate, well or channel in the file names.
  const cell = (run: (typeof RUNS)[number], groupIndex: number) => rows.nth(RUNS.indexOf(run) + 1).getByRole("cell").nth(groupIndex);
  const add = async (run: (typeof RUNS)[number], groupIndex: number) => {
    const target = cell(run, groupIndex);
    await expect(target.getByRole("button", {name: "画像を追加", exact: true})).toBeEnabled({timeout: 120_000});
    const chooser = page.waitForEvent("filechooser");
    await target.getByRole("button", {name: "画像を追加", exact: true}).click();
    await (await chooser).setFiles(imagesOf(inputs!, run, GROUPS[groupIndex].well));
    await expect(target).toContainText(`${GROUPS[groupIndex].label} · ${SITES.length} 視野`, {timeout: 300_000});
    await expect(page.getByRole("status").filter({hasText: "画像を登録中"})).toHaveCount(0, {timeout: 120_000});
  };
  const combinations = RUNS.flatMap(run => GROUPS.map((_, groupIndex) => [run, groupIndex] as const));
  for (const [run, groupIndex] of combinations.slice(0, -1)) await add(run, groupIndex);
  // E-06: before statistics, the one missing combination is named; it disappears once added.
  await expect(issues.getByText("Run3 に PLK1 KO の画像がありません。この回は対にできません。", {exact: true})).toBeVisible();
  await expect(issues.getByText(/の画像がありません。/)).toHaveCount(1);
  await expect(cell("Run3", 1)).toContainText("PLK1 KO · 画像なし");
  await add("Run3", 1);
  await expect(issues.getByText(/の画像がありません。/)).toHaveCount(0);
  for (const [run, groupIndex] of combinations) await expect(cell(run, groupIndex)).toContainText(`${GROUPS[groupIndex].label} · ${SITES.length} 視野`);
  await expect(setup.getByRole("region", {name: "群と実験回が決まっていない視野"})).toHaveCount(0);
  // E-05: independence is the researcher's statement, never inferred from dates or plates.
  await expect(setup.getByRole("checkbox", {name: /各実験回は独立に行った/})).not.toBeChecked();
  await expect(issues).toContainText("実験回が独立に行われたこと（別々に播種・処理・染色したこと）を確認すると、群間比較の検定と信頼区間に進めます。");
  await noAlerts();

  // N-02: every field has the four channels, grouped from the file names only (no stain from names).
  const registeredFields = await (await page.request.get(`${api}/v1/workspaces/${workspace}/region-fields`)).json() as Array<{id: string; image_info: {shape: number[]; channels: Array<{channel_id: string; stain: string | null}>}}>;
  expect(registeredFields).toHaveLength(RUNS.length * GROUPS.length * SITES.length);
  for (const field of registeredFields) {
    expect(field.image_info.channels.map(channel => channel.channel_id).sort()).toEqual(CHANNELS.map(channel => channel.id));
    expect(field.image_info.channels.every(channel => channel.stain === null)).toBe(true);
  }
  const saved = await (await page.request.get(`${api}/v1/workspaces/${workspace}/analysis-spec`)).json() as {spec: {experiment: {groups: Array<{id: string; label: string}>; control_group_id: string; runs: Array<{id: string; label: string}>; fields: Record<string, {group_id: string; run_id: string}>}}};
  const design = saved.spec.experiment;
  expect(design.groups.map(group => group.label)).toEqual(GROUPS.map(group => group.label));
  expect(design.groups.find(group => group.id === design.control_group_id)?.label).toBe("Non-targeting");
  expect(design.runs.map(run => run.label)).toEqual([...RUNS]);
  expect(Object.keys(design.fields).sort()).toEqual(registeredFields.map(field => field.id).sort());

  // Stains: DNA (Hoechst) detects nuclei; the other three are measured. One save covers the set.
  await page.getByRole("navigation", {name: "作業の切替"}).getByRole("button", {name: "画像", exact: true}).click();
  const sidebar = page.getByRole("complementary", {name: "視野一覧"});
  await expect(sidebar.getByRole("button").filter({hasText: /未測定/})).toHaveCount(registeredFields.length);
  await sidebar.getByRole("button").filter({hasText: /未測定/}).first().click();
  await page.getByRole("button", {name: "染色対応", exact: true}).click();
  for (const channel of CHANNELS) {
    await page.getByLabel(`${channel.id}の染色名`, {exact: true}).fill(channel.stain);
    await page.getByLabel(`${channel.id}の役割`, {exact: true}).selectOption(channel.role);
  }
  await page.getByRole("button", {name: "保存", exact: true}).click();
  await expect(page.getByRole("button", {name: "Hoechst · c01", exact: true})).toBeVisible();

  // Measure every field with Fiji StarDist.
  await expect(page.getByRole("button", {name: "測定", exact: true})).toBeEnabled({timeout: 900_000});
  await page.getByLabel("測定する視野", {exact: true}).selectOption("all");
  const started = Date.now();
  await page.getByRole("button", {name: "測定", exact: true}).click();
  await expect(sidebar.getByRole("button").filter({hasText: /核\s+\d/})).toHaveCount(registeredFields.length, {timeout: 3_000_000});
  const measuredSeconds = Math.round((Date.now() - started) / 1000);
  await expect(page.getByRole("button", {name: "測定", exact: true})).toBeEnabled({timeout: 300_000});
  await noAlerts();
  const runs = await (await page.request.get(`${api}/v1/workspaces/${workspace}/runs`)).json() as Array<{state: string; steps: Array<{recipe?: {source?: string}}>}>;
  expect(runs.some(run => run.state === "adopted" && run.steps.length === registeredFields.length && run.steps.every(step => step.recipe?.source === "stardist_nuclear"))).toBe(true);
  await page.screenshot({path: path.join(output, "pair-measured.png")});

  // E-07: switching between two screens and one keeps the images, results and the experiment.
  const pairButton = page.getByRole("button", {name: "2 画面", exact: true});
  await expect(pairButton).toHaveAttribute("aria-pressed", "true");
  const control = page.getByRole("region", {name: "Non-targeting（対照）"}), treatment = page.getByRole("region", {name: "PLK1 KO", exact: true});
  const paneCount = async () => ({control: await control.locator("header small").textContent(), treatment: await treatment.locator("header small").textContent()});
  await expect(control.locator("header small")).toHaveText(/^5 視野 · 核 \d+$/);
  await expect(treatment.locator("header small")).toHaveText(/^5 視野 · 核 \d+$/);
  const before = await paneCount();
  const sidebarBefore = await sidebar.getByRole("button").filter({hasText: /核\s+\d/}).allTextContents();
  await pairButton.click();
  await expect(pairButton).toHaveAttribute("aria-pressed", "false");
  await expect(control).toHaveCount(0);
  await expect(page.getByRole("img", {name: /Hoechst/}).first()).toBeVisible();
  expect(await sidebar.getByRole("button").filter({hasText: /核\s+\d/}).allTextContents()).toEqual(sidebarBefore);
  await page.screenshot({path: path.join(output, "single-measured.png")});
  await pairButton.click();
  await expect(pairButton).toHaveAttribute("aria-pressed", "true");
  await expect(control.locator("header small")).toHaveText(before.control!);
  await expect(treatment.locator("header small")).toHaveText(before.treatment!);
  for (const run of RUNS) {
    await page.getByRole("combobox", {name: "実験回", exact: true}).selectOption({label: run});
    await expect(control.locator("header small")).toHaveText(/^5 視野 · 核 \d+$/);
    await expect(treatment.locator("header small")).toHaveText(/^5 視野 · 核 \d+$/);
  }
  await page.getByRole("navigation", {name: "作業の切替"}).getByRole("button", {name: "実験", exact: true}).click();
  for (const [run, groupIndex] of combinations) await expect(cell(run, groupIndex)).toContainText(`${GROUPS[groupIndex].label} · ${SITES.length} 視野`);
  for (const [index, run] of RUNS.entries()) await expect(runName(index)).toHaveValue(run);

  // Statistics: nuclei per field, compared between the groups.
  await page.getByRole("navigation", {name: "作業の切替"}).getByRole("button", {name: "統計", exact: true}).click();
  const options = page.getByRole("complementary", {name: "解析対象"});
  await options.getByRole("combobox", {name: "指標", exact: true}).selectOption("nucleus_count");
  const panel = page.getByRole("region", {name: "測定結果の統計解析"});
  await expect(panel.locator("header")).toContainText(`${registeredFields.length} 視野`);
  await panel.getByRole("combobox", {name: "解析", exact: true}).selectOption("comparison");
  // The declared pair compares treatment − control within each run.
  await expect(panel.getByRole("combobox", {name: "対応", exact: true})).toHaveValue("paired");
  await expect(panel.getByRole("checkbox", {name: "PLK1 KO − Non-targeting（処理 − 対照）"})).toBeChecked();
  // E-08: the per-field table shows the same record as the experiment, read-only here.
  const metadata = panel.locator("details").filter({has: page.getByText("実験情報", {exact: true})});
  await expect(metadata.getByText("群・試料・独立実験単位・撮影日・対応ペアは、「実験」で入力した実験の形から決まります。")).toBeVisible();
  const conditions = metadata.locator('input[aria-label$=" condition"]'), units = metadata.locator('input[aria-label$=" experimental_unit"]'), pairs = metadata.locator('input[aria-label$=" pair"]');
  await expect(conditions).toHaveCount(registeredFields.length);
  const entered: Record<string, number> = {};
  for (let index = 0; index < registeredFields.length; index++) {
    await expect(conditions.nth(index)).toHaveAttribute("readonly", "");
    const key = `${await units.nth(index).inputValue()}|${await conditions.nth(index).inputValue()}|${await pairs.nth(index).inputValue()}`;
    entered[key] = (entered[key] ?? 0) + 1;
  }
  expect(entered).toEqual(Object.fromEntries(combinations.map(([run, groupIndex]) => [`${run} · ${GROUPS[groupIndex].label}|${GROUPS[groupIndex].label}|${run}`, SITES.length])));

  await panel.getByLabel("独立実験単位、撮影・画素条件、採否と欠測の扱いを確認した", {exact: true}).check();
  await panel.getByLabel("測定領域と採用する視野を確認した", {exact: true}).check();
  // E-05: without the independence statement the comparison is descriptive: run values and differences, no test or interval.
  await expect(panel.getByRole("status").filter({hasText: "検定と信頼区間は計算せず、実験回ごとの値と差を示します。"})).toBeVisible();
  await expect(panel.getByRole("combobox", {name: "解析", exact: true}).locator("option[value=association]")).toHaveAttribute("disabled", "");
  await expect(panel.getByRole("button", {name: "計算", exact: true})).toBeEnabled();
  const described = page.waitForResponse(response => response.request().method() === "POST" && new URL(response.url()).pathname.endsWith("/common-statistics"), {timeout: 300_000});
  await panel.getByRole("button", {name: "計算", exact: true}).click();
  expect(((await described).request().postDataJSON() as {test: string}).test).toBe("none");
  const descriptive = panel.getByRole("region", {name: "結果のまとめ"});
  await expect(descriptive.getByText("実験回 n = 3（対）、検定なし（記述のみ）", {exact: true})).toBeVisible({timeout: 300_000});
  await expect(descriptive.getByText(/^3 回中、PLK1 KOが少ない回 3/)).toBeVisible();
  await expect(descriptive).not.toContainText("95% 信頼区間");
  await panel.getByRole("button", {name: "実験の形で確認する", exact: true}).first().click();
  await setup.getByRole("checkbox", {name: /各実験回は独立に行った/}).check();
  await expect(setup.getByRole("checkbox", {name: /各実験回は独立に行った/})).toBeChecked();
  await expect(issues).not.toContainText("実験回が独立に行われたこと");
  await page.getByRole("navigation", {name: "作業の切替"}).getByRole("button", {name: "統計", exact: true}).click();
  await expect(panel.getByRole("status").filter({hasText: "実験回ごとの値と差を示します"})).toHaveCount(0);
  await expect(panel.getByRole("combobox", {name: "解析", exact: true})).toHaveValue("comparison");
  if (!await panel.getByLabel("独立実験単位、撮影・画素条件、採否と欠測の扱いを確認した", {exact: true}).isChecked()) await panel.getByLabel("独立実験単位、撮影・画素条件、採否と欠測の扱いを確認した", {exact: true}).check();
  if (!await panel.getByLabel("測定領域と採用する視野を確認した", {exact: true}).isChecked()) await panel.getByLabel("測定領域と採用する視野を確認した", {exact: true}).check();
  await expect(panel.getByRole("button", {name: "計算", exact: true})).toBeEnabled();
  const accepted = page.waitForResponse(response => response.request().method() === "POST" && new URL(response.url()).pathname.endsWith("/common-statistics"), {timeout: 300_000});
  await panel.getByRole("button", {name: "計算", exact: true}).click();
  const jobId = ((await (await accepted).json()) as {job_id: string}).job_id;

  // The result sentence: PLK1 KO − control, a negative difference with its 95% CI, and the superplot.
  const summary = panel.getByRole("region", {name: "結果のまとめ"});
  await expect.poll(async () => {
    expect(await panel.getByRole("alert").allTextContents()).toEqual([]);
    return summary.count();
  }, {timeout: 300_000}).toBe(1);
  // The descriptive result above is replaced by the tested one.
  await expect(summary.getByText(/^実験回 n = 3（対）、対応のある t 検定 /)).toBeVisible({timeout: 300_000});
  const headline = (await summary.locator("p").first().textContent())!;
  expect(headline).toMatch(/^視野あたりの核数は、Non-targetingに比べPLK1 KOで [\d.]+ .*少ない値でした。$/);
  const interval = summary.getByText(/^実験回ごとの差の平均（PLK1 KO − Non-targeting）の 95% 信頼区間：/);
  await expect(interval).toBeVisible();
  await expect(summary.getByText(/^実験回 n = 3（対）、対応のある t 検定 /)).toBeVisible();
  await expect(panel.getByRole("img", {name: "保存された解析結果のグラフ"})).toBeVisible({timeout: 120_000});
  await expect.poll(() => panel.getByRole("img", {name: "保存された解析結果のグラフ"}).evaluate(image => (image as HTMLImageElement).naturalWidth), {timeout: 60_000}).toBeGreaterThan(0);
  await page.screenshot({path: path.join(output, "comparison.png"), fullPage: true});

  const jobs = await (await page.request.get(`${api}/v1/workspaces/${workspace}/jobs`)).json() as Array<{id: string; state: string; revision_id: string}>;
  const job = jobs.find(value => value.id === jobId)!;
  expect(job.state).toBe("succeeded");
  const result = await (await page.request.get(`${api}/v1/jobs/${job.id}/common-statistics`)).json() as {
    spec: {plot: {kind: string}; test?: string}; estimates: {control: string; treatment: string; design: string; n_pairs: number; difference: {estimate: number; ci_low: number; ci_high: number}; ratio: unknown; runs: Array<{pair: string; control: number; treatment: number; difference: number}>};
    comparisons: Array<{method: string; p_value: number}>; counts: unknown; field_summary: Array<Record<string, unknown>>; warnings?: string[]};
  expect(result.spec.plot.kind).toBe("superplot");
  expect(result.estimates).toMatchObject({control: "Non-targeting", treatment: "PLK1 KO", design: "paired", n_pairs: 3});
  expect(result.estimates.runs.map(run => run.pair).sort()).toEqual([...RUNS]);
  const {estimate, ci_low: low, ci_high: high} = result.estimates.difference;
  expect(estimate).toBeLessThan(0);
  expect(low).toBeLessThanOrEqual(estimate);
  expect(high).toBeGreaterThanOrEqual(estimate);
  const svg = await page.request.get(`${api}/v1/jobs/${job.id}/files/figure.svg`);
  if (svg.ok()) await writeFile(path.join(output, "figure.svg"), await svg.body());

  await noAlerts();
  expect(dialogs).toEqual([]);
  expect(pageErrors).toEqual([]);
  expect(consoleErrors).toEqual([]);
  await writeFile(path.join(output, "receipt.json"), JSON.stringify({
    scope: "Goals C1 browser workflow on registered public JUMP cpg0016 source_13 images (CC0) with real API, worker and Fiji StarDist; workflow acceptance only, not detection accuracy or biological validation",
    workspace, job: job.id, revision: job.revision_id, fields: registeredFields.length, measured_seconds: measuredSeconds,
    headline, interval: await interval.textContent(), estimates: result.estimates, comparisons: result.comparisons, counts: result.counts,
    field_summary: result.field_summary, warnings: result.warnings ?? []}, null, 2));
});

