import fs from "node:fs";
import path from "node:path";
import {expect, test, type Locator, type Page} from "@playwright/test";

/**
 * Public demo (/demo): the production workspace on the serverless transport (docs/showcase.md).
 * Run against the public production build (no analysis API) with the published demo files, or
 * against a build with NEXT_PUBLIC_SHOWCASE_DEV_BACKEND and scripts/dev_showcase_backend.py
 * (set CYTELLECT_SHOWCASE_DEV_BACKEND to the same origin). The dev backend's threshold detection
 * is a stand-in: these checks cover interaction and error handling, never scientific values.
 */
const DEV = process.env.CYTELLECT_SHOWCASE_DEV_BACKEND?.replace(/\/$/, "") || "";
const PUBLISHED = fs.existsSync(path.resolve("public/showcase/seed.zip"));
const live = 240_000;

/** The published scenes (snapshot/scenes.json); a single-scene demo reads as one scene without an id. */
interface Scene {id: string; label: string; workspaceId: string; regions: string[]; assistantScope?: string; fields: unknown[]}
const SCENES: Scene[] = (() => {
  try {return (JSON.parse(fs.readFileSync(path.resolve("public/showcase/snapshot/scenes.json"), "utf8")) as {scenes: Scene[]}).scenes;}
  catch {return [];}
})();
const sceneUrl = (scene: Scene | undefined, query = "") => scene ? `/demo?id=${scene.workspaceId}${query ? `&${query}` : ""}` : `/demo${query ? `?${query}` : ""}`;
const OPENING = SCENES[0];
/** The scene with nucleoli and a measured stain besides the nuclear one, for the nucleolar checks. */
const NUCLEOLAR = SCENES.find(scene => scene.regions.includes("nucleoli"));
const scopeText = (scene: Scene | undefined) => (scene?.assistantScope ?? "このデモは、記録した公開画像の解析だけに答えます。").slice(0, 20);

test.describe.configure({mode: "serial"});
test.beforeEach(() => {
  test.skip(!PUBLISHED && !DEV, "The public demo files (apps/web/public/showcase/seed.zip) are not built; set CYTELLECT_SHOWCASE_DEV_BACKEND to use the development backend.");
  test.skip(!DEV && process.env.CYTELLECT_EXPECT_UNCONFIGURED !== "1", "The demo exists only in the public build without an analysis API.");
});

interface Watch {requests: string[]; errors: string[]}
async function openDemo(page: Page, url = "/demo"): Promise<Watch> {
  const watch: Watch = {requests: [], errors: []};
  page.on("request", request => watch.requests.push(request.url()));
  page.on("pageerror", error => watch.errors.push(error.message));
  page.on("console", message => {if (message.type() === "error") watch.errors.push(`console: ${message.text()}`);});
  // A request the page itself cancelled (a superseded preview) is not a failure.
  page.on("requestfailed", request => {if (!/ERR_ABORTED/.test(request.failure()?.errorText ?? "")) watch.errors.push(`request failed: ${request.url()} ${request.failure()?.errorText}`);});
  await page.addInitScript(() => {
    const seen: string[] = [];
    (window as unknown as {__alerts: string[]}).__alerts = seen;
    const record = (node: Node) => {
      if (!(node instanceof Element)) return;
      for (const element of [node, ...node.querySelectorAll("[role=alert]")]) {
        if (element.getAttribute("role") === "alert" && element.id !== "__next-route-announcer__" && element.textContent?.trim()) seen.push(element.textContent.trim());
      }
    };
    new MutationObserver(changes => changes.forEach(change => {
      if (change.type === "characterData") record(change.target.parentElement as Node);
      change.addedNodes.forEach(record);
      if (change.type === "attributes") record(change.target);
    })).observe(document, {subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ["role"]});
  });
  await page.goto(url);
  return watch;
}
const alerts = (page: Page) => page.evaluate(() => (window as unknown as {__alerts: string[]}).__alerts);
async function noErrors(page: Page, watch: Watch) {
  expect(await alerts(page)).toEqual([]);
  expect(watch.errors).toEqual([]);
  const forbidden = watch.requests.filter(url => {
    const parsed = new URL(url);
    if (DEV && parsed.origin === DEV) return !/^\/(boot|handle|snapshot\/[A-Za-z0-9._-]+)$/.test(parsed.pathname);
    return parsed.pathname.startsWith("/v1/") || ["localhost", "127.0.0.1"].includes(parsed.hostname) && parsed.port === "8000";
  });
  expect(forbidden).toEqual([]);
}
async function idle(page: Page) {
  await page.waitForTimeout(800);
  await expect(page.locator("header").getByRole("status").first()).toHaveText("", {timeout: live});
}
async function noOverflow(page: Page) {
  for (const width of [1440, 390]) {
    await page.setViewportSize({width, height: width > 500 ? 1000 : 844});
    await page.waitForTimeout(300);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  }
  await page.setViewportSize({width: 1440, height: 1000});
}
const notRecorded = (page: Page) => page.getByRole("status").filter({hasText: "公開デモに記録していません"});
// A shown result table: the experiment details above the results start folded once an experiment exists.
const shownTable = (region: Locator) => region.locator("table").filter({visible: true}).first();
const stage = (page: Page) => page.getByRole("group").filter({has: page.locator("image")}).first();
const regions = (page: Page) => page.locator("svg path[data-region]");
async function regionBoxes(page: Page) {
  return regions(page).evaluateAll(nodes => nodes.map(node => {const box = node.getBoundingClientRect(); return {id: Number(node.getAttribute("data-region")), x: box.x, y: box.y, width: box.width, height: box.height};}));
}
/** The region nearest the image centre, away from the floating toolbars. */
async function centralRegion(page: Page) {
  const image = (await page.locator("svg image").first().boundingBox())!;
  const cx = image.x + image.width / 2, cy = image.y + image.height / 2;
  return (await regionBoxes(page)).sort((a, b) => Math.hypot(a.x + a.width / 2 - cx, a.y + a.height / 2 - cy) - Math.hypot(b.x + b.width / 2 - cx, b.y + b.height / 2 - cy))[0];
}
async function largestRegion(page: Page) {
  const boxes = (await regionBoxes(page)).filter(box => box.width > 14 && box.height > 14);
  return boxes.sort((a, b) => b.width * b.height - a.width * a.height)[0];
}
/** A pointer click on the region's own outline area, as a researcher clicks it. */
async function clickRegion(page: Page, id: number) {
  const point = await page.locator(`svg path[data-region="${id}"]`).evaluate((node: SVGPathElement) => {
    const svg = node.ownerSVGElement!, box = node.getBoundingClientRect();
    for (let y = box.top + box.height / 2, step = 0; step < 40; step++) for (const x of [box.left + box.width / 2, box.left + box.width * (step % 10) / 10]) {
      const hit = document.elementFromPoint(x, y + ((step % 5) - 2) * box.height / 6);
      if (hit === node && svg.contains(hit)) return {x, y: y + ((step % 5) - 2) * box.height / 6};
    }
    return {x: box.left + box.width / 2, y: box.top + box.height / 2};
  });
  await page.mouse.click(point.x, point.y);
}
async function selectRegion(page: Page, id: number) {
  await clickRegion(page, id);
  await expect(page.locator(`svg path[data-region="${id}"]`)).toHaveAttribute("aria-pressed", "true");
}

test("demo: image, outline, measurement, statistics and figure features run without errors", async ({page}) => {
  test.setTimeout(1_200_000);
  const watch = await openDemo(page, "/demo");
  const header = page.locator("header");
  await expect(header.getByText("デモ", {exact: true})).toBeVisible();
  await expect(page.getByRole("link", {name: "ダウンロード", exact: true})).toHaveAttribute("href", "/#download");
  // Uploads are unavailable here, so the demo never offers an empty new workspace.
  await expect(page.getByRole("button", {name: "新しいワークスペース", exact: true})).toHaveCount(0);
  // Image source and limits (snapshot/dataset.json) open from the badge when published.
  await expect(stage(page)).toBeVisible({timeout: live});
  const credit = header.locator("summary", {hasText: "デモ"});
  if (await credit.count()) {
    await credit.click();
    await expect(header.getByRole("link", {name: "出典"})).toHaveAttribute("href", /^https:\/\//);
    await credit.click();
  }
  await expect(stage(page)).toBeVisible({timeout: live});
  await expect(regions(page).first()).toBeAttached({timeout: live});
  // The demo opens on nuclei, two groups side by side, each image with its outlines and measurements,
  // without starting the in-browser API. The comparison's sentence and figure are one tab away (統計).
  await expect(page.locator("[class*=channelBar]").getByRole("combobox", {name: "領域", exact: true})).toHaveValue("nuclei");
  const merge = page.getByRole("button", {name: "重ねて表示", exact: true});
  if (await merge.count()) await expect(merge).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("button", {name: "2 画面", exact: true})).toHaveAttribute("aria-pressed", "true");
  const paneTables = page.getByRole("region", {name: /の測定値$/});
  await expect(paneTables).toHaveCount(2, {timeout: live});
  for (const table of await paneTables.all()) await expect(table.locator("tbody tr").first()).toBeVisible({timeout: live});
  await expect(page.getByRole("region", {name: "比較の結果"})).toHaveCount(0);
  await expect(header.locator("[data-showcase-engine=idle]")).toBeAttached();
  if (SCENES.length > 1) await expect(header.getByRole("combobox", {name: "場面"})).toHaveValue(OPENING.id);
  // The rest of this walk uses one field at a time.
  await page.getByRole("button", {name: "2 画面", exact: true}).click();
  await noOverflow(page);

  // The guide stays closed so the image and results show at once; 「使い方」 walks the real tabs.
  const guide = page.getByRole("complementary", {name: "公開デモの使い方"});
  await expect(guide).toHaveCount(0);
  await header.getByRole("button", {name: "使い方", exact: true}).click();
  await expect(guide).toBeVisible();
  await guide.getByRole("button", {name: "次へ"}).click();
  await expect(page.getByRole("button", {name: /^測定値/})).toHaveAttribute("aria-expanded", "true");
  await guide.getByRole("button", {name: "次へ"}).click();
  await expect(header.getByRole("button", {name: "統計", exact: true})).toHaveAttribute("aria-current", "page");
  await guide.getByRole("button", {name: "次へ"}).click();
  await expect(header.getByRole("button", {name: "グラフ", exact: true})).toHaveAttribute("aria-current", "page");
  await guide.getByRole("button", {name: "了解"}).click();
  await expect(guide).toHaveCount(0);
  await header.getByRole("button", {name: "画像", exact: true}).click();
  await page.getByRole("button", {name: /^測定値/}).click();

  // Image intake is explained, never attempted.
  const fieldList = page.getByRole("complementary", {name: "視野一覧"});
  for (const name of ["画像", "フォルダ"]) {
    await fieldList.getByRole("button", {name, exact: true}).click();
    const dialog = page.getByRole("dialog", {name: "画像の追加"});
    await expect(dialog.getByRole("link", {name: "ダウンロードの案内"})).toHaveAttribute("href", "/#download");
    await dialog.getByRole("button", {name: "閉じる"}).click();
    await expect(dialog).toHaveCount(0);
  }
  const transfer = await page.evaluateHandle(() => {const value = new DataTransfer(); value.items.add(new File(["x"], "synthetic.tif", {type: "image/tiff"})); return value;});
  await page.locator("main").dispatchEvent("dragover", {dataTransfer: transfer});
  await page.locator("main").dispatchEvent("drop", {dataTransfer: transfer});
  await page.getByRole("dialog", {name: "画像の追加"}).getByRole("button", {name: "閉じる"}).click();

  // Channels, zoom, fit, pan and outlines.
  const channelBar = page.getByRole("button", {name: "染色対応", exact: true}).locator("..");
  const channels = channelBar.locator("button[data-channel]");
  const channelCount = await channels.count();
  await channels.nth(channelCount - 1).click();
  await expect(channels.nth(channelCount - 1)).toHaveAttribute("aria-pressed", "true");
  await channels.first().click();
  const zoom = page.locator("[role=toolbar] span").first();
  // The fitted scale exists once the viewer has measured its viewport (until then it shows "–").
  await expect(zoom).toHaveText(/^\d+%$/);
  const before = await zoom.textContent();
  await page.getByRole("button", {name: "拡大", exact: true}).first().click();
  await expect(zoom).not.toHaveText(before!);
  const box = (await page.locator("svg image").first().boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down(); await page.mouse.move(box.x + box.width / 2 + 60, box.y + box.height / 2 + 40, {steps: 5}); await page.mouse.up();
  await page.getByRole("button", {name: "画像全体を表示", exact: true}).first().click();
  // The demo opens magnified on a group of cells; 画像全体を表示 shows the whole field (smaller scale).
  await expect.poll(async () => parseInt(await zoom.textContent() || "0", 10)).toBeLessThan(parseInt(before!, 10));
  await page.getByRole("button", {name: "輪郭の表示", exact: true}).first().click();
  await expect(regions(page)).toHaveCount(0);
  await page.getByRole("button", {name: "輪郭の表示", exact: true}).first().click();
  await expect(regions(page).first()).toBeAttached();

  await page.getByRole("button", {name: "画像全体を表示", exact: true}).first().click();

  // Region selection is shared by the image and the table.
  const drawer = page.getByRole("button", {name: /^測定値/});
  if (await drawer.getAttribute("aria-expanded") !== "true") await drawer.click();
  const first = await centralRegion(page);
  await selectRegion(page, first.id);
  await expect(page.locator("tr[aria-selected=true]").first()).toContainText(String(first.id));
  const tableButton = page.locator("table").first().locator("tbody button").nth(4);
  const tableId = Number(await tableButton.textContent());
  await tableButton.click();
  await expect(page.locator(`svg path[data-region="${tableId}"]`)).toHaveAttribute("aria-pressed", "true");

  // A correction the visitor draws is not recorded: it is explained at once, never waited for.
  const count = async () => (await regionBoxes(page)).length;
  const initial = await count();
  await selectRegion(page, (await largestRegion(page)).id);
  const started = Date.now();
  await page.getByRole("button", {name: "選択領域を削除", exact: true}).click();
  await expect(notRecorded(page)).toBeVisible({timeout: 5000});
  expect(Date.now() - started).toBeLessThan(5000);
  expect(await count()).toBe(initial);

  // Compare several planes, then return to one.
  await page.getByRole("button", {name: "画像を比較", exact: true}).click();
  const picker = page.locator("input[type=checkbox]").locator("xpath=ancestor::div[1]").first();
  await picker.locator("input[type=checkbox]:not(:checked)").first().check();
  await expect.poll(async () => page.locator("svg image").count()).toBeGreaterThan(1);
  await page.getByRole("button", {name: "比較対象を閉じる", exact: true}).click();
  await channels.first().click();

  // Measurement of the selected field and of all fields: recorded results.
  await openSettings(page);
  const range = header.getByLabel("測定する視野");
  for (const value of ["selected", "all"]) {
    await range.selectOption(value);
    await header.getByRole("button", {name: "測定", exact: true}).click();
    await idle(page);
  }
  await expect(notRecorded(page)).toHaveCount(0);
  expect(await alerts(page)).toEqual([]);

  // AI: a recorded example answers; a request this dataset cannot answer is told what it can.
  const composer = page.getByLabel("AIへの指示");
  await composer.click();
  await page.getByRole("group", {name: "指示の例"}).getByRole("button").first().click();
  await idle(page);
  await composer.fill("ミトコンドリアを数えたい");
  await page.getByRole("button", {name: "AIへ送信"}).click();
  await expect(page.getByText(scopeText(OPENING))).toBeVisible({timeout: live});
  await page.getByRole("button", {name: "パネルを閉じる"}).click();
  expect(await alerts(page)).toEqual([]);

  // Statistics: the opening result and its group comparison, then their figures.
  await header.getByRole("button", {name: "統計", exact: true}).click();
  const results = page.getByRole("region", {name: "測定結果の統計解析"});
  await expect(shownTable(results)).toBeVisible({timeout: live});
  await calculate(page);
  await results.getByRole("combobox", {name: "解析", exact: true}).selectOption("comparison");
  await calculate(page);
  await expect(shownTable(results)).toBeVisible();
  await expect(notRecorded(page)).toHaveCount(0);
  await header.getByRole("button", {name: "グラフ", exact: true}).click();
  await renderFigure(page);
  await page.getByRole("region", {name: "図の作成・保存"}).getByRole("combobox", {name: "図のレイアウト", exact: true}).selectOption("box");
  await renderFigure(page);
  await expect(notRecorded(page)).toHaveCount(0);

  await noOverflow(page);
  await noErrors(page, watch);
});

test("the scene switcher opens each scene's own images and examples", async ({page}) => {
  test.skip(SCENES.length < 2, "The published demo has one scene.");
  const watch = await openDemo(page);
  const header = page.locator("header");
  await expect(regions(page).first()).toBeAttached({timeout: live});
  for (const scene of SCENES.slice(1).concat(SCENES[0])) {
    await header.getByRole("combobox", {name: "場面"}).selectOption(scene.id);
    await expect(page).toHaveURL(new RegExp(`id=${scene.workspaceId}`));
    await expect(regions(page).first()).toBeAttached({timeout: live});
    await expect(page.locator("[class*=fieldCard]")).toHaveCount(scene.fields.length, {timeout: live});
  }
  await noErrors(page, watch);
});

/** The fields each pane can show for the run on screen (the panes' field choices). */
async function paneFields(page: Page) {
  const panes = page.getByRole("combobox", {name: / の視野$/});
  await expect(panes).toHaveCount(2, {timeout: live});
  return Promise.all((await panes.all()).map(select => select.locator("option").evaluateAll(options => options.map(option => (option as HTMLOptionElement).value))));
}
test("the selected field drives the pair: a figure's source opens on its run and pane, the list on its pane", async ({page}) => {
  const watch = await openDemo(page, sceneUrl(OPENING));
  const panes = page.getByRole("combobox", {name: / の視野$/});
  const [control] = await paneFields(page);
  // A field chosen in the list shows in its group's pane, also after another field was chosen in that pane.
  await panes.first().selectOption(control[1]);
  await expect(panes.first()).toHaveValue(control[1]);
  const label = (await panes.first().locator(`option[value="${control[0]}"]`).textContent())!.trim();
  await page.locator("[class*=fieldCard]").filter({hasText: label}).first().click();
  await expect(panes.first()).toHaveValue(control[0]);
  // A point of the saved figure from another run lists its fields; opening one shows it on its run, in its pane.
  const runs = page.getByRole("combobox", {name: "実験回", exact: true});
  const first = (await runs.locator("option:checked").textContent())!.trim();
  await page.locator("header").getByRole("button", {name: "グラフ", exact: true}).click();
  await expect(page.getByRole("button", {name: /^グラフを選択/}).first()).toBeVisible({timeout: live});
  const units = await page.locator("[data-cytellect-source]").evaluateAll(elements => elements.map(element => {
    try {return (JSON.parse(element.getAttribute("data-cytellect-source") ?? "") as {experimental_unit?: string}).experimental_unit ?? "";} catch {return "";}
  }));
  const other = units.findIndex(unit => unit && !unit.startsWith(`${first} `));
  expect(other).toBeGreaterThanOrEqual(0);
  const run = units[other].split(" ")[0];
  await page.locator("[data-cytellect-source]").nth(other).dispatchEvent("click");
  const listed = page.getByRole("region", {name: "選択した点の試料・視野"}).locator("tbody button").first();
  const opened = (await listed.textContent())!.trim();
  await listed.click();
  await expect(page.locator("header").getByRole("button", {name: "画像", exact: true})).toHaveAttribute("aria-current", "page");
  await expect(runs.locator("option:checked")).toHaveText(run, {timeout: live});
  await expect(page.getByRole("combobox", {name: / の視野$/}).locator("option:checked", {hasText: opened})).toHaveCount(1);
  await expect(page.getByRole("button", {name: "元の結果へ戻る"})).toBeVisible();
  expect(await alerts(page)).toEqual([]);
  await noErrors(page, watch);
});
test("deep links open the requested step without the guide", async ({page}) => {
  const watch = await openDemo(page, sceneUrl(OPENING, "step=figure"));
  await expect(page.locator("header").getByRole("button", {name: "グラフ", exact: true})).toHaveAttribute("aria-current", "page");
  await expect(page.getByRole("complementary", {name: "公開デモの使い方"})).toHaveCount(0);
  await expect(page.getByRole("region", {name: "図の作成・保存"})).toBeVisible({timeout: live});
  // The demo opens on the latest saved result instead of an empty view.
  await expect(page.getByRole("button", {name: /^グラフを選択/}).first()).toBeVisible({timeout: live});
  await expect(page.getByText("計算した結果とグラフをここに表示します。")).toHaveCount(0);
  await noErrors(page, watch);
});

test("phones run the guided operations from the recorded tour", async ({page}) => {
  test.skip(!!DEV, "The recorded tour is part of the published demo files.");
  await page.addInitScript(() => Object.defineProperty(navigator, "deviceMemory", {value: 2}));
  await page.setViewportSize({width: 390, height: 844});
  const watch = await openDemo(page);
  const header = page.locator("header");
  await expect(stage(page)).toBeVisible({timeout: live});
  await expect(regions(page).first()).toBeAttached({timeout: live});
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  // Measuring the opened field returns as it did in the browser API, without starting it here.
  const measure = header.getByRole("button", {name: "測定", exact: true});
  await measure.click();
  // The narrow header has no progress text; the run is over when measuring can start again.
  await page.waitForTimeout(800);
  await expect(measure).toBeEnabled({timeout: live});
  await expect(page.getByRole("status").filter({hasText: "公開デモ"})).toHaveCount(0);
  await expect(header.locator("[data-showcase-engine=idle]")).toBeAttached();
  expect(await alerts(page)).toEqual([]);

  // Statistics, its figure and the publication package, as 「使い方」 leads.
  await page.goto(sceneUrl(OPENING, "step=statistics"));
  const results = page.getByRole("region", {name: "測定結果の統計解析"});
  await expect(shownTable(results)).toBeVisible({timeout: live});
  // The opening comparison asks for both confirmations, given once every field has loaded.
  await calculate(page);
  await header.getByRole("button", {name: "グラフ", exact: true}).click();
  const figure = page.getByRole("region", {name: "図の作成・保存"});
  const update = figure.getByRole("button", {name: "図を更新", exact: true});
  await update.click();
  await expect(update).toBeEnabled({timeout: live});
  const download = page.waitForEvent("download", {timeout: live});
  await figure.getByRole("button", {name: "保存", exact: true}).click();
  expect((await download).suggestedFilename()).toBe("Cytellect-publication.zip");
  expect(await alerts(page)).toEqual([]);

  // Free figure sizes cannot be recorded, so the demo offers the recorded widths only.
  await expect(figure.getByRole("combobox", {name: "図の幅", exact: true}).locator("option[value=custom]")).toHaveCount(0);
  await expect(figure.getByRole("spinbutton", {name: "幅 / mm"})).toBeDisabled();
  // The phone never downloaded the in-browser API.
  expect(watch.requests.filter(url => /\/showcase\/(runtime\/|seed\.zip)/.test(url))).toEqual([]);
  await noErrors(page, watch);
});

async function openSettings(page: Page) {
  const inspector = page.getByRole("complementary", {name: "画像解析"});
  if (!(await inspector.count())) await page.locator("header").getByRole("button", {name: "設定パネル"}).click();
  await expect(inspector).toBeVisible();
  return inspector;
}
/** A metric of a fixed region (such as nucleolar count) hides the region choice; area brings it back. */
async function chooseMetric(page: Page, region: string, metric: string, channel: string | null) {
  const side = page.getByRole("complementary", {name: "解析対象"});
  const choice = side.getByRole("combobox", {name: "領域", exact: true});
  if (!await choice.count()) await side.getByRole("combobox", {name: "指標", exact: true}).selectOption("area_px");
  await choice.selectOption(region);
  await side.getByRole("combobox", {name: "指標", exact: true}).selectOption(metric);
  if (channel) await side.getByRole("combobox", {name: "染色", exact: true}).selectOption(channel);
}
async function fillIfEmpty(control: Locator, value: string) {
  if (await control.count() && !await control.inputValue()) await control.fill(value);
}
async function calculate(page: Page) {
  const results = page.getByRole("region", {name: "測定結果の統計解析"});
  await fillIfEmpty(results.getByRole("textbox", {name: "独立実験単位", exact: true}), "公開画像の反復（デモ）");
  await fillIfEmpty(results.getByRole("textbox", {name: "対応の根拠", exact: true}), "同じ反復（Rep）内の 2 条件");
  const confirm = results.getByLabel("独立実験単位、撮影・画素条件、採否と欠測の扱いを確認した");
  if (await confirm.count() && !await confirm.isChecked()) await confirm.check();
  const reviewed = results.getByLabel("測定領域と採用する視野を確認した");
  if (!await reviewed.isChecked()) await reviewed.check();
  await results.getByRole("button", {name: "計算", exact: true}).click();
  await expect(results.getByRole("button", {name: "計算", exact: true})).toBeEnabled({timeout: live});
  await expect(results.getByText("測定結果または解析条件が変わりました。再計算してください。")).toHaveCount(0);
  expect(await alerts(page)).toEqual([]);
}
async function renderFigure(page: Page) {
  const update = page.getByRole("region", {name: "図の作成・保存"}).getByRole("button", {name: "図を更新", exact: true});
  await update.click();
  await expect(update).toBeEnabled({timeout: live});
  await expect(page.getByRole("button", {name: /^グラフを選択/}).first()).toBeVisible({timeout: live});
  expect(await alerts(page)).toEqual([]);
}

for (const scene of SCENES.length ? SCENES : [undefined]) test(`every field, region and channel shows recorded results${scene ? ` (${scene.id})` : ""}`, async ({page}) => {
  test.setTimeout(900_000);
  const watch = await openDemo(page, sceneUrl(scene));
  const header = page.locator("header");
  await expect(regions(page).first()).toBeAttached({timeout: live});
  const pair = page.getByRole("button", {name: "2 画面", exact: true});
  if (await pair.getAttribute("aria-pressed") === "true") await pair.click();
  const cards = page.locator("[class*=fieldCard]");
  const total = scene ? scene.fields.length : 6;
  await expect(cards).toHaveCount(total, {timeout: live});
  const inspector = await openSettings(page);
  const region = inspector.getByRole("combobox", {name: "領域", exact: true});
  const channels = page.getByRole("button", {name: "染色対応", exact: true}).locator("..").locator("button[data-channel]");
  for (let index = 0; index < total; index++) {
    await cards.nth(index).click();
    for (const value of scene?.regions ?? ["nuclei", "nucleoli", "nucleoplasm"]) {
      await region.selectOption(value);
      for (let channel = 0; channel < await channels.count(); channel++) await channels.nth(channel).click();
      await expect(regions(page).first()).toBeAttached({timeout: 10_000});
    }
  }
  await header.getByRole("button", {name: "統計", exact: true}).click();
  await expect(shownTable(page.getByRole("region", {name: "測定結果の統計解析"}))).toBeVisible({timeout: live});
  await header.getByRole("button", {name: "グラフ", exact: true}).click();
  const history = page.getByRole("region", {name: "図の作成・保存"}).getByRole("combobox", {name: "保存した図", exact: true});
  for (const value of await history.locator("option:not([disabled])").evaluateAll(options => options.map(option => (option as HTMLOptionElement).value))) {
    await history.selectOption(value);
    await expect(page.getByRole("button", {name: /^グラフを選択/}).first()).toBeVisible({timeout: 10_000});
    expect(await alerts(page)).toEqual([]);
  }
  await expect(notRecorded(page)).toHaveCount(0);
  await expect(header.locator("[data-showcase-engine=idle]")).toBeAttached();
  await noErrors(page, watch);
});

test("measuring nucleoli or nucleoplasm, then statistics of the nuclei, shows recorded results", async ({page}) => {
  test.setTimeout(600_000);
  test.skip(SCENES.length > 0 && !NUCLEOLAR, "No published scene has nucleoli.");
  for (const [target, label] of [["nucleoli", "核小体"], ["nucleoplasm", "核質"]]) {
    const watch = await openDemo(page, sceneUrl(NUCLEOLAR));
    const header = page.locator("header");
    await expect(regions(page).first()).toBeAttached({timeout: live});
    const inspector = await openSettings(page);
    const region = inspector.getByRole("combobox", {name: "領域", exact: true});
    await region.selectOption(target);
    // The toolbar shows the region chosen in the panel, and each pane counts its objects.
    await expect(page.locator("[class*=channelBar]").getByRole("combobox", {name: "領域", exact: true})).toHaveValue(target);
    await expect(page.locator("[class*=paneHead] small").first()).toContainText(label);
    await header.getByLabel("測定する視野").selectOption("all");
    await header.getByRole("button", {name: "測定", exact: true}).click();
    await idle(page);
    await page.locator("[class*=fieldCard]").first().click();
    await region.selectOption("nuclei");
    await idle(page);
    await header.getByRole("button", {name: "統計", exact: true}).click();
    const results = page.getByRole("region", {name: "測定結果の統計解析"});
    await expect(shownTable(results)).toBeVisible({timeout: live});
    await calculate(page);
    await results.getByRole("combobox", {name: "解析", exact: true}).selectOption("comparison");
    await calculate(page);
    await header.getByRole("button", {name: "グラフ", exact: true}).click();
    await renderFigure(page);
    await expect(notRecorded(page)).toHaveCount(0);
    await noErrors(page, watch);
  }
});

test("operations the recording does not hold are explained at once, without the in-browser API", async ({page}) => {
  const watch = await openDemo(page);
  const header = page.locator("header");
  await expect(regions(page).first()).toBeAttached({timeout: live});
  const inspector = await openSettings(page);
  // Conditions the recording cannot cover are shown as the recorded settings, with a note, not as
  // controls that cannot answer.
  await expect(inspector.getByRole("combobox", {name: "背景補正", exact: true})).toHaveCount(0);
  await expect(inspector.getByRole("combobox", {name: "核染色", exact: true})).toHaveCount(0);
  await expect(inspector.getByText(/記録した条件で検出しています/)).toBeVisible();
  const recorded = inspector.locator("dl").filter({hasText: "確率閾値"});
  await expect(recorded).toContainText("Hoechst · ");
  await expect(recorded).toContainText("0.5");
  await expect(inspector.locator("dl").filter({hasText: "背景補正"})).toContainText("自動推定");
  await expect(inspector.getByRole("combobox", {name: "領域", exact: true}).locator("option[value=cell]")).toHaveCount(0);
  // A hand correction of an outline, made one field at a time, is explained at once.
  const pair = page.getByRole("button", {name: "2 画面", exact: true});
  if (await pair.getAttribute("aria-pressed") === "true") await pair.click();
  await expect(regions(page).first()).toBeAttached({timeout: live});
  await selectRegion(page, (await largestRegion(page)).id);
  const started = Date.now();
  await page.getByRole("button", {name: "選択領域を削除", exact: true}).click();
  await expect(notRecorded(page)).toBeVisible({timeout: 5000});
  expect(Date.now() - started).toBeLessThan(5000);
  await expect(header.locator("[data-showcase-engine=idle]")).toBeAttached();
  expect(watch.requests.filter(url => /\/showcase\/(runtime\/|seed\.zip)/.test(url))).toEqual([]);
  await noErrors(page, watch);
});

test("statistics of nucleoli, nucleoplasm and nucleolar measures show results, descriptively while independence is unconfirmed", async ({page}) => {
  test.setTimeout(600_000);
  test.skip(SCENES.length > 0 && !NUCLEOLAR, "No published scene has nucleoli.");
  const watch = await openDemo(page, sceneUrl(NUCLEOLAR));
  const header = page.locator("header");
  await expect(regions(page).first()).toBeAttached({timeout: live});
  await header.getByRole("button", {name: "統計", exact: true}).click();
  const results = page.getByRole("region", {name: "測定結果の統計解析"});
  await expect(shownTable(results)).toBeVisible({timeout: live});
  // Both changes the source reports, recorded before measurement, are one click apart (goals C7).
  const recorded = results.getByRole("group", {name: "記録した比較"});
  await expect(recorded.getByRole("button")).toHaveCount(2, {timeout: live});
  const sentence = results.getByRole("region", {name: "結果のまとめ"}).locator("p").first();
  // The opening comparison names its region and channel, and the side panel already agrees with it.
  await expect(sentence).toContainText("核小体の平均輝度（eu5）");
  await expect(results.getByRole("status").filter({hasText: /前の結果|記録した結果/})).toHaveCount(0);
  await recorded.getByRole("button", {name: /離心率/}).click();
  await expect(sentence).toContainText("離心率");
  await expect(page.getByRole("complementary", {name: "解析対象"}).getByRole("combobox", {name: "指標", exact: true})).toHaveValue("nucleolar_eccentricity");
  await recorded.getByRole("button", {name: /eu5/}).click();
  await expect(sentence).toContainText("平均輝度");
  await expect(results.getByRole("status").filter({hasText: /前の結果|記録した結果/})).toHaveCount(0);
  const operation = results.getByRole("combobox", {name: "解析", exact: true});
  const cases: Array<[string, string, string | null, string]> = [
    ["nucleoli", "area_px", null, "distribution"], ["nucleoli", "mean", "npm1", "comparison"],
    ["nucleoplasm", "mean", "npm1", "distribution"], ["nuclei", "nucleolar_count", null, "comparison"],
    ["nuclei", "nucleolar_area_fraction", null, "distribution"], ["nuclei", "log2_nucleoplasm_over_nucleolus", "npm1", "comparison"],
    ["nucleoli", "mean", "eu5", "comparison"],
  ];
  for (const [region, metric, channel, kind] of cases) {
    await chooseMetric(page, region, metric, channel);
    await operation.selectOption(kind);
    await calculate(page);
    await expect(shownTable(results)).toBeVisible();
    await expect(notRecorded(page)).toHaveCount(0);
  }
  // Without confirmed independence the comparison is descriptive and an association is not offered (E-05).
  await expect(results.getByRole("region", {name: "結果のまとめ"})).toContainText("検定なし（記述のみ）");
  await expect(operation.locator("option[value=association]")).toHaveAttribute("disabled", "");
  // The last result's figure.
  await header.getByRole("button", {name: "グラフ", exact: true}).click();
  await renderFigure(page);
  await noErrors(page, watch);
});

test("an AI example on another field, then measuring and statistics of each region, keep showing results", async ({page}) => {
  test.setTimeout(900_000);
  test.skip(SCENES.length > 0 && !NUCLEOLAR, "No published scene has nucleoli.");
  const watch = await openDemo(page, sceneUrl(NUCLEOLAR));
  const header = page.locator("header");
  await expect(regions(page).first()).toBeAttached({timeout: live});
  const results = page.getByRole("region", {name: "測定結果の統計解析"});
  const statistics = async (region: string, metric: string, channel: string | null, kind: string) => {
    await header.getByRole("button", {name: "統計", exact: true}).click();
    await expect(shownTable(results)).toBeVisible({timeout: live});
    await chooseMetric(page, region, metric, channel);
    await results.getByRole("combobox", {name: "解析", exact: true}).selectOption(kind);
    await calculate(page);
    await expect(notRecorded(page)).toHaveCount(0);
  };
  const measure = async (target: string, range: "all" | "selected") => {
    await header.getByRole("button", {name: "画像", exact: true}).click();
    const inspector = await openSettings(page);
    await inspector.getByRole("combobox", {name: "領域", exact: true}).selectOption(target);
    await header.getByLabel("測定する視野").selectOption(range);
    await header.getByRole("button", {name: "測定", exact: true}).click();
    await idle(page);
    await expect(notRecorded(page)).toHaveCount(0);
    expect(await alerts(page)).toEqual([]);
  };
  // The example previews the nuclei of the field shown; it is adopted as after a real proposal.
  await page.locator("[class*=fieldCard]").nth(2).click();
  await idle(page);
  await page.getByLabel("AIへの指示").click();
  await page.getByRole("group", {name: "指示の例"}).getByRole("button").first().click();
  await idle(page);
  const adopt = page.getByRole("button", {name: "候補を採用", exact: true});
  if (await adopt.isVisible()) {await adopt.click(); await idle(page);}
  await expect(notRecorded(page)).toHaveCount(0);
  await page.getByRole("button", {name: "パネルを閉じる"}).click();
  // Measuring under the example's settings, and statistics after one cohort and another.
  await measure("nucleoli", "all");
  await statistics("nucleoplasm", "mean", "npm1", "comparison");
  // The recorded experiment information is shown as recorded.
  await expect(results.locator("details").filter({hasText: "実験情報"}).locator("input").first()).toHaveAttribute("readonly", "");
  await statistics("nucleoli", "area_px", null, "distribution");
  await measure("nuclei", "selected");
  await statistics("nuclei", "area_px", null, "comparison");
  await statistics("nucleoplasm", "mean_corrected", "npm1", "distribution");
  await header.getByRole("button", {name: "グラフ", exact: true}).click();
  await renderFigure(page);
  // An example choosing rank-based methods: the statistics that follow keep them.
  await header.getByRole("button", {name: "画像", exact: true}).click();
  await page.getByLabel("AIへの指示").click();
  await page.getByRole("group", {name: "指示の例"}).getByRole("button").nth(2).click();
  await idle(page);
  if (await adopt.isVisible()) {await adopt.click(); await idle(page);}
  await page.getByRole("button", {name: "パネルを閉じる"}).click();
  await statistics("nucleoli", "nucleolar_area_fraction", null, "comparison");
  await statistics("nucleoplasm", "mean", "npm1", "comparison");
  await header.getByRole("button", {name: "グラフ", exact: true}).click();
  await renderFigure(page);
  await noErrors(page, watch);
});

for (const scene of SCENES.length ? SCENES : [undefined]) test(`each preset AI instruction returns a settings draft that applies like a real proposal${scene ? ` (${scene.id})` : ""}`, async ({page}) => {
  test.setTimeout(900_000);
  const watch = await openDemo(page, sceneUrl(scene));
  const header = page.locator("header");
  await expect(regions(page).first()).toBeAttached({timeout: live});
  const notRecorded = page.getByRole("status").filter({hasText: "記録した指示の例だけに応答します"});
  const composer = page.getByLabel("AIへの指示");
  await composer.click();
  const ai = page.getByRole("complementary", {name: "AI"});
  const examples = ai.getByRole("group", {name: "指示の例"}).getByRole("button");
  const count = await examples.count();
  expect(count).toBeGreaterThan(0);
  for (let index = 0; index < count; index++) {
    const instruction = await examples.nth(index).getAttribute("title");
    await examples.nth(index).click();
    await idle(page);
    await expect(notRecorded).toHaveCount(0);
    await expect(composer).toHaveValue(instruction!);
    await expect(ai.getByRole("button", {name: "AIによる設定変更を戻す"})).toBeVisible();
    // The draft's detection preview is offered for adoption, as after a real proposal.
    const adopt = page.getByRole("button", {name: "候補を採用", exact: true});
    if (await adopt.isVisible()) {await adopt.click(); await idle(page);}
    expect(await alerts(page)).toEqual([]);
  }
  // Free text this dataset cannot answer is told what it can, without a notice or an error.
  await header.getByRole("button", {name: "画像", exact: true}).click();
  await composer.fill("ミトコンドリアを数えたい");
  await page.getByRole("button", {name: "AIへ送信"}).click();
  await expect(page.getByText(scopeText(scene))).toBeVisible({timeout: live});
  await expect(notRecorded).toHaveCount(0);
  await noErrors(page, watch);
});
