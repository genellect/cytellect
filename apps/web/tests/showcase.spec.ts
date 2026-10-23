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

test.describe.configure({mode: "serial"});
test.beforeEach(() => {
  test.skip(!PUBLISHED && !DEV, "The public demo files (apps/web/public/showcase/seed.zip) are not built; set CYTELLECT_SHOWCASE_DEV_BACKEND to use the development backend.");
  test.skip(!DEV && process.env.CYTELLECT_EXPECT_UNCONFIGURED !== "1", "The demo exists only in the public build without an analysis API.");
});

interface Watch {requests: string[]; errors: string[]}
async function openDemo(page: Page, url = "/demo", {guide = false} = {}): Promise<Watch> {
  const watch: Watch = {requests: [], errors: []};
  page.on("request", request => watch.requests.push(request.url()));
  page.on("pageerror", error => watch.errors.push(error.message));
  page.on("console", message => {if (message.type() === "error") watch.errors.push(`console: ${message.text()}`);});
  // A request the page itself cancelled (a superseded preview) is not a failure.
  page.on("requestfailed", request => {if (!/ERR_ABORTED/.test(request.failure()?.errorText ?? "")) watch.errors.push(`request failed: ${request.url()} ${request.failure()?.errorText}`);});
  await page.addInitScript(dismissed => {
    try {if (dismissed) localStorage.setItem("cytellect-demo-guide", "dismissed");} catch {}
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
  }, !guide);
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
const stage = (page: Page) => page.getByRole("img").filter({has: page.locator("image")}).first();
const regions = (page: Page) => page.locator("svg path[data-region]");
async function regionBoxes(page: Page) {
  return regions(page).evaluateAll(nodes => nodes.map(node => {const box = node.getBoundingClientRect(); return {id: Number(node.getAttribute("data-region")), x: box.x, y: box.y, width: box.width, height: box.height};}));
}
/** A screen point inside the image, at least `margin` px away from every region. */
async function emptySpot(page: Page, margin = 26) {
  const image = (await page.locator("svg image").first().boundingBox())!;
  const boxes = await regionBoxes(page);
  for (let y = image.y + margin; y < image.y + image.height - margin; y += 6) for (let x = image.x + margin; x < image.x + image.width - margin; x += 6) {
    if (boxes.every(box => x < box.x - margin || x > box.x + box.width + margin || y < box.y - margin || y > box.y + box.height + margin)) return {x, y};
  }
  throw new Error("no empty image area");
}
async function draw(page: Page, center: {x: number; y: number}, radius = 7) {
  for (const [dx, dy] of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) await page.mouse.click(center.x + dx * radius, center.y + dy * radius);
  await page.getByRole("button", {name: "描画を保存", exact: true}).click();
  await idle(page);
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
async function chooseRecordedOrFill(control: Locator, preferred: string) {
  if (await control.evaluate(node => node.tagName) === "SELECT") {
    const values = await control.locator("option").evaluateAll(options => options.map(option => (option as HTMLOptionElement).value));
    const current = await control.inputValue();
    const next = values.find(value => value !== current);
    if (next !== undefined) await control.selectOption(next);
    return next !== undefined;
  }
  if (await control.isDisabled()) return false;
  await control.fill(preferred);
  return true;
}

test("demo: image, outline, measurement, statistics and figure features run without errors", async ({page}) => {
  test.setTimeout(1_200_000);
  const watch = await openDemo(page, "/demo", {guide: true});
  const header = page.locator("header");
  await expect(header.getByText("デモ", {exact: true})).toBeVisible();
  await expect(page.getByRole("link", {name: "ダウンロード", exact: true})).toHaveAttribute("href", "/#download");
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
  await noOverflow(page);

  // First-visit guide walks the real tabs.
  const guide = page.getByRole("complementary", {name: "公開デモの使い方"});
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
  await expect(header.getByText("ライブ計算：有効")).toBeAttached({timeout: live});

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
  const channels = channelBar.getByRole("button").filter({hasText: " · "});
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
  await expect(zoom).toHaveText(before!);
  await page.getByRole("button", {name: "輪郭の表示", exact: true}).first().click();
  await expect(regions(page)).toHaveCount(0);
  await page.getByRole("button", {name: "輪郭の表示", exact: true}).first().click();
  await expect(regions(page).first()).toBeAttached();

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

  // Mask corrections re-measure through the real API; undo and redo select revisions.
  const count = async () => (await regionBoxes(page)).length;
  const initial = await count();
  await selectRegion(page, (await largestRegion(page)).id);
  await page.getByRole("button", {name: "選択領域を削除", exact: true}).click();
  await idle(page);
  await expect.poll(count).toBe(initial - 1);
  await page.getByRole("button", {name: "元に戻す", exact: true}).click();
  await idle(page);
  await expect.poll(count).toBe(initial);
  await page.getByRole("button", {name: "やり直す", exact: true}).click();
  await idle(page);
  await expect.poll(count).toBe(initial - 1);
  await page.getByRole("button", {name: "領域を描く", exact: true}).click();
  await draw(page, await emptySpot(page));
  await expect.poll(count).toBe(initial);
  let target = await largestRegion(page);
  await selectRegion(page, target.id);
  await page.getByRole("button", {name: "輪郭を描き直す", exact: true}).click();
  await draw(page, {x: target.x + target.width / 2, y: target.y + target.height / 2}, Math.min(target.width, target.height) / 3);
  target = await largestRegion(page);
  await selectRegion(page, target.id);
  await page.getByRole("button", {name: "領域を分割", exact: true}).click();
  for (const [x, y] of [[target.x + target.width / 2, target.y - 3], [target.x + target.width + 3, target.y - 3], [target.x + target.width + 3, target.y + target.height + 3], [target.x + target.width / 2, target.y + target.height + 3]]) await page.mouse.click(x, y);
  await page.getByRole("button", {name: "描画を保存", exact: true}).click();
  await idle(page);
  const [a, b] = (await regionBoxes(page)).sort((left, right) => left.x - right.x || left.y - right.y);
  await selectRegion(page, a.id);
  await page.getByRole("button", {name: "領域を結合", exact: true}).click();
  await clickRegion(page, b.id);
  await page.getByRole("button", {name: "描画を保存", exact: true}).click();
  await idle(page);
  expect(await alerts(page)).toEqual([]);

  // Field exclusion is offered for fields with a recorded failure.
  const exclude = page.getByRole("button", {name: "この視野を除外", exact: true});
  if (await exclude.count()) {await exclude.click(); await idle(page); await page.getByRole("button", {name: "解析対象に戻す", exact: true}).click(); await idle(page);}

  // Compare several planes, then return to one.
  await page.getByRole("button", {name: "画像を比較", exact: true}).click();
  const picker = page.locator("input[type=checkbox]").locator("xpath=ancestor::div[1]").first();
  await picker.locator("input[type=checkbox]:not(:checked)").first().check();
  await expect.poll(async () => page.locator("svg image").count()).toBeGreaterThan(1);
  await page.getByRole("button", {name: "比較対象を閉じる", exact: true}).click();
  await channels.first().click();
  await expect(page.locator("svg image")).toHaveCount(1);

  // Image role and its reference link, restored afterwards.
  await page.locator("summary[aria-label=画像の用途]").click();
  await page.getByRole("combobox", {name: "画像の用途", exact: true}).selectOption("reference");
  await idle(page);
  const reference = page.getByRole("combobox", {name: "対応する視野", exact: true});
  await reference.selectOption({index: 1});
  await idle(page);
  await page.getByRole("combobox", {name: "画像の用途", exact: true}).selectOption("analysis");
  await idle(page);
  await page.locator("summary[aria-label=画像の用途]").click();

  // Stain assignment editor saves through the API.
  await page.getByRole("button", {name: "染色対応", exact: true}).click();
  await page.locator("[class*=assignments]").getByRole("button", {name: "保存", exact: true}).click();
  await idle(page);

  // Detection settings: recorded values only, preview, adopt the candidate.
  const inspector = page.getByRole("complementary", {name: "画像解析"});
  const openInspector = async () => {if (!(await inspector.count())) await header.getByRole("button", {name: "設定パネル"}).click(); await expect(inspector).toBeVisible();};
  await openInspector();
  await inspector.getByText("検出条件", {exact: true}).first().click();
  const probability = inspector.getByRole("spinbutton", {name: "確率閾値", exact: true}).or(inspector.getByRole("combobox", {name: "確率閾値", exact: true}));
  if (await chooseRecordedOrFill(probability, "0.6")) {
    await expect(page.getByRole("button", {name: "候補を採用", exact: true})).toBeVisible({timeout: live});
    await page.getByRole("button", {name: "候補を採用", exact: true}).click();
    await idle(page);
  }

  // Measurement for the selected field and all fields; stopping is offered while running.
  const range = header.getByLabel("測定する視野");
  for (const value of ["selected", "all"]) {
    await range.selectOption(value);
    await header.getByRole("button", {name: "測定", exact: true}).click();
    const stop = header.getByRole("button", {name: "実行を中止"});
    if (value === "all" && await stop.isVisible().catch(() => false)) await stop.click().catch(() => undefined);
    await idle(page);
  }

  // Measured regions: nucleoli, nucleoplasm and drawn cell ROIs.
  await openInspector();
  const regionSelect = inspector.getByRole("combobox", {name: "領域", exact: true});
  await range.selectOption("selected");
  for (const value of ["nucleoli", "nucleoplasm"]) {
    await openInspector();
    await regionSelect.selectOption(value);
    await header.getByRole("button", {name: "測定", exact: true}).click();
    await idle(page);
    await expect(page.locator("[class*=measureToggle] span")).toHaveText(value === "nucleoli" ? "核小体" : "核質", {timeout: live});
  }
  await regionSelect.selectOption("cell");
  await idle(page);
  const drawCell = page.getByRole("button", {name: "領域を描く", exact: true});
  if (await drawCell.isEnabled().catch(() => false)) {await drawCell.click(); await draw(page, await emptySpot(page, 30), 12);}
  await regionSelect.selectOption("nuclei");
  await idle(page);

  // Background correction: none, automatic estimate, and a drawn background ROI.
  await openInspector();
  const background = inspector.getByRole("combobox", {name: "背景補正", exact: true});
  await background.selectOption("automatic");
  await idle(page);
  await background.selectOption("confirmed_roi");
  await inspector.getByRole("button", {name: "背景を描く"}).click();
  await draw(page, await emptySpot(page, 30), 8);
  await expect(inspector.getByRole("button", {name: "選択した背景ROIを削除"})).toBeVisible();
  await inspector.getByRole("button", {name: "選択した背景ROIを削除"}).click();
  await idle(page);
  await background.selectOption("raw");
  await idle(page);

  // GFP gate when the dataset has a GFP-like measurement channel.
  await openInspector();
  await inspector.getByText("GFPによる対象選別", {exact: true}).click();
  const gfp = inspector.getByLabel("GFPチャンネル");
  const options = await gfp.locator("option").allTextContents();
  const gfpOption = options.findIndex(text => /gfp/i.test(text));
  if (gfpOption > 0) {
    await gfp.selectOption({index: gfpOption});
    await inspector.getByLabel("平均輝度のしきい値").fill("50");
    await inspector.getByRole("button", {name: "GFPで分類"}).click();
    await expect(inspector.locator("output")).toContainText("陽性", {timeout: live});
    await idle(page);
    await inspector.getByRole("button", {name: /^すべての.*を対象にする$/}).click();
    await idle(page);
  }
  expect(await alerts(page)).toEqual([]);

  // AI: recorded examples answer; other text gets the demo notice.
  const composer = page.getByLabel("AIへの指示");
  await composer.click();
  const examples = page.getByRole("group", {name: "指示の例"});
  if (await examples.count()) {
    await examples.getByRole("button").first().click();
    await idle(page);
  }
  await composer.fill("公開デモで記録されていない指示");
  await page.getByRole("button", {name: "AIへ送信"}).click();
  await expect(page.getByRole("status").filter({hasText: "記録した指示の例だけに応答します"})).toBeVisible({timeout: live});
  await page.getByRole("button", {name: "パネルを閉じる"}).click();
  expect(await alerts(page)).toEqual([]);

  // Statistics: distribution, association and group comparison with experimental metadata.
  await header.getByRole("button", {name: "統計", exact: true}).click();
  const results = page.getByRole("region", {name: "測定結果の統計解析"});
  // Area keeps the walk independent of the demo images' intensity range (saturation is reported, not compared).
  await page.getByRole("complementary", {name: "解析対象"}).getByRole("combobox", {name: "指標", exact: true}).selectOption("area_px");
  const calculate = results.getByRole("button", {name: "計算", exact: true});
  const reviewed = results.getByLabel("測定領域と採用する視野を確認した");
  await reviewed.check();
  await calculate.click();
  await expect(results.locator("table").first()).toBeVisible({timeout: live});
  const operation = results.getByRole("combobox", {name: "解析", exact: true});
  await operation.selectOption("association");
  await results.getByRole("combobox", {name: "横軸", exact: true}).selectOption("mean");
  const xChannel = results.getByRole("combobox", {name: "横軸チャンネル", exact: true});
  await xChannel.selectOption({index: await xChannel.locator("option").count() - 1});
  await results.getByRole("textbox", {name: "独立実験単位", exact: true}).fill("公開画像の視野（デモ）");
  await results.getByLabel("独立実験単位、撮影・画素条件、採否と欠測の扱いを確認した").check();
  if (!await reviewed.isChecked()) await reviewed.check();
  await calculate.click();
  await expect(results.getByRole("button", {name: "計算", exact: true})).toBeEnabled({timeout: live});
  await operation.selectOption("comparison");
  await expect(results.getByText("実験情報", {exact: true})).toBeVisible();
  const groups = results.locator("fieldset").filter({hasText: "比較する群"}).locator("input[type=checkbox]");
  // All pairs here; a subset of groups is covered by its own test below.
  for (const group of await groups.all()) await group.check();
  await results.getByLabel("独立実験単位、撮影・画素条件、採否と欠測の扱いを確認した").check();
  if (!await reviewed.isChecked()) await reviewed.check();
  await calculate.click();
  await expect(results.getByRole("button", {name: "計算", exact: true})).toBeEnabled({timeout: live});
  const notes = results.getByText("解析上の注意", {exact: true});
  if (await notes.count()) await notes.click();
  expect(await alerts(page)).toEqual([]);

  // A result row opens its source field; the workspace returns to the result.
  await results.locator("details").filter({hasText: "元の視野"}).locator("summary").click();
  await results.locator("details").filter({hasText: "元の視野"}).getByRole("button").first().click();
  await expect(header.getByRole("button", {name: "画像", exact: true})).toHaveAttribute("aria-current", "page");
  await page.getByRole("button", {name: "元の結果へ戻る"}).click();
  await expect(header.getByRole("button", {name: "統計", exact: true})).toHaveAttribute("aria-current", "page");

  // CSV tables are added in the installed versions only.
  await results.getByRole("button", {name: "CSV の数値表を解析"}).click();
  await page.getByRole("button", {name: "CSV を追加"}).click();
  await page.getByRole("dialog", {name: "数値表の追加"}).getByRole("button", {name: "閉じる"}).click();
  await page.getByRole("button", {name: "画像の測定値"}).click();

  // Figure: parts, sizes, axes, series, layouts, history and the publication package.
  await header.getByRole("button", {name: "グラフ", exact: true}).click();
  const figure = page.getByRole("region", {name: "図の作成・保存"});
  const update = figure.getByRole("button", {name: "図を更新", exact: true});
  const rendered = async () => {await update.click(); await expect(update).toBeEnabled({timeout: live}); expect(await alerts(page)).toEqual([]);};
  await figure.getByRole("combobox", {name: "図の幅", exact: true}).selectOption("89");
  await rendered();
  await figure.getByRole("button", {name: "縦軸", exact: true}).click();
  await figure.getByLabel("縦軸ラベル").fill("Area (px²)");
  await figure.getByLabel("縦軸の最小値").fill("0");
  await rendered();
  await figure.getByRole("button", {name: "横軸", exact: true}).click();
  await figure.getByLabel("横軸ラベル").fill("Condition");
  await figure.getByRole("button", {name: "系列", exact: true}).click();
  await figure.getByLabel("色", {exact: true}).fill("#d55e00");
  await figure.getByRole("button", {name: "後へ", exact: true}).click();
  await rendered();
  await figure.getByRole("button", {name: "図", exact: true}).click();
  const layout = figure.getByRole("combobox", {name: "図のレイアウト", exact: true});
  for (const value of ["box", "violin", "histogram", "distribution"]) {await layout.selectOption(value); await rendered();}
  const history = figure.getByRole("combobox", {name: "保存した図", exact: true});
  await expect.poll(async () => history.locator("option").count()).toBeGreaterThan(2);
  await history.selectOption({index: 2});
  await history.selectOption({index: 1});
  const download = page.waitForEvent("download", {timeout: live});
  await figure.getByRole("button", {name: "保存", exact: true}).click();
  expect((await download).suggestedFilename()).toBe("Cytellect-publication.zip");

  await noOverflow(page);
  await noErrors(page, watch);
});

test("deep links open the requested step without the guide", async ({page}) => {
  const watch = await openDemo(page, "/demo?step=figure", {guide: true});
  await expect(page.locator("header").getByRole("button", {name: "グラフ", exact: true})).toHaveAttribute("aria-current", "page");
  await expect(page.getByRole("complementary", {name: "公開デモの使い方"})).toHaveCount(0);
  await expect(page.getByRole("region", {name: "図の作成・保存"})).toBeVisible({timeout: live});
  // The demo opens on the latest saved result instead of an empty view.
  await expect(page.getByRole("button", {name: /^グラフを選択/}).first()).toBeVisible({timeout: live});
  await expect(page.getByText("計算した結果とグラフをここに表示します。")).toHaveCount(0);
  await noErrors(page, watch);
});

test("phones keep the recorded view and explain changes instead of failing", async ({page}) => {
  await page.addInitScript(() => Object.defineProperty(navigator, "deviceMemory", {value: 2}));
  await page.setViewportSize({width: 390, height: 844});
  const watch = await openDemo(page);
  await expect(stage(page)).toBeVisible({timeout: live});
  await expect(regions(page).first()).toBeAttached({timeout: live});
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.locator("header").getByRole("button", {name: "測定", exact: true}).click();
  await expect(page.getByRole("status").filter({hasText: "この操作はPCのブラウザで試せます"})).toBeVisible({timeout: live});
  await expect(page.locator("header").getByText("保存済みの結果を表示中")).toBeAttached();
  // Saved statistics come from the recorded responses.
  await page.goto("/demo?step=statistics");
  await expect(page.getByRole("region", {name: "測定結果の統計解析"}).locator("table").first()).toBeVisible({timeout: live});
  expect(DEV ? watch.requests.filter(url => url.endsWith("/handle")) : []).toEqual([]);
  await noOverflow(page);
  await noErrors(page, watch);
});

/** Waits for the in-browser API (every change needs it). */
async function liveEngine(page: Page) {
  await expect(page.locator("header").getByText("ライブ計算：有効")).toBeAttached({timeout: live});
}
async function openSettings(page: Page) {
  const inspector = page.getByRole("complementary", {name: "画像解析"});
  if (!(await inspector.count())) await page.locator("header").getByRole("button", {name: "設定パネル"}).click();
  await expect(inspector).toBeVisible();
  return inspector;
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
const comparisonGroups = (page: Page) => page.getByRole("region", {name: "測定結果の統計解析"}).locator("fieldset").filter({hasText: "比較する群"}).locator("label");

test("automatic background (measurement protocol 4.0.0) flows into statistics and figures", async ({page}) => {
  test.setTimeout(900_000);
  const watch = await openDemo(page);
  const header = page.locator("header");
  await expect(regions(page).first()).toBeAttached({timeout: live});
  await liveEngine(page);
  const inspector = await openSettings(page);
  await inspector.getByRole("combobox", {name: "背景補正", exact: true}).selectOption("automatic");
  await idle(page);
  await header.getByLabel("測定する視野").selectOption("all");
  await header.getByRole("button", {name: "測定", exact: true}).click();
  await idle(page);
  expect(await alerts(page)).toEqual([]);

  await header.getByRole("button", {name: "統計", exact: true}).click();
  const results = page.getByRole("region", {name: "測定結果の統計解析"});
  // NPM1, the measured channel (Hoechst saturates in some fields and its intensity comparison is refused).
  const target = page.getByRole("complementary", {name: "解析対象"});
  await target.getByRole("combobox", {name: "指標", exact: true}).selectOption("mean_corrected");
  await target.getByRole("combobox", {name: "染色", exact: true}).selectOption({label: "NPM1 · npm1"});
  const operation = results.getByRole("combobox", {name: "解析", exact: true});
  for (const value of ["distribution", "comparison", "association"]) {
    await operation.selectOption(value);
    if (value === "comparison") for (const group of await comparisonGroups(page).locator("input").all()) await group.check();
    await calculate(page);
    await expect(results.locator("table").first()).toBeVisible();
    await expect(results.getByText("核 · 平均輝度（背景補正） · npm1", {exact: true})).toBeVisible();
    await header.getByRole("button", {name: "グラフ", exact: true}).click();
    await renderFigure(page);
    await header.getByRole("button", {name: "統計", exact: true}).click();
  }
  await noErrors(page, watch);
});

test("comparing a subset of groups renders and reorders its figure; a value opens its source image", async ({page}) => {
  test.setTimeout(900_000);
  const watch = await openDemo(page, "/demo?step=statistics");
  const header = page.locator("header");
  const results = page.getByRole("region", {name: "測定結果の統計解析"});
  await expect(results).toBeVisible({timeout: live});
  await liveEngine(page);
  await results.getByRole("combobox", {name: "解析", exact: true}).selectOption("comparison");
  await results.getByRole("combobox", {name: "対応", exact: true}).selectOption({label: "独立した実験"});
  // A third group: two fields relabelled in the experimental information.
  const metadata = results.locator("details").filter({hasText: "実験情報"}).first();
  await metadata.getByLabel("視野 3 condition").fill("Third group");
  await metadata.getByLabel("視野 6 condition").fill("Third group");
  const pairs = comparisonGroups(page);
  await expect(pairs).toHaveCount(3);
  for (const box of await pairs.locator("input").all()) if (await box.isChecked()) await box.uncheck();
  await pairs.filter({hasText: /^Untreated \/ ActD/}).locator("input").check();
  await calculate(page);

  await header.getByRole("button", {name: "グラフ", exact: true}).click();
  const figure = page.getByRole("region", {name: "図の作成・保存"});
  await figure.getByRole("button", {name: "系列", exact: true}).click();
  const series = figure.locator("label", {hasText: "系列"}).locator("select");
  await expect(series.locator("option")).toHaveText(["Untreated", /^ActD/]);
  await figure.getByRole("button", {name: "後へ", exact: true}).click();
  await expect(series.locator("option")).toHaveText([/^ActD/, "Untreated"]);
  await renderFigure(page);
  await figure.getByRole("button", {name: "図", exact: true}).click();
  for (const value of ["box", "violin"]) {await figure.getByRole("combobox", {name: "図のレイアウト", exact: true}).selectOption(value); await renderFigure(page);}

  // A point of the figure lists its source fields; a field opens the image and returns to the result.
  await page.locator("[data-cytellect-source]").first().dispatchEvent("click");
  const point = page.getByRole("region", {name: "選択した点の試料・視野"});
  await expect(point).toBeVisible();
  await point.locator("tbody button").first().click();
  await expect(header.getByRole("button", {name: "画像", exact: true})).toHaveAttribute("aria-current", "page");
  await expect(stage(page)).toBeVisible({timeout: live});
  await page.getByRole("button", {name: "元の結果へ戻る"}).click();
  await expect(header.getByRole("button", {name: "グラフ", exact: true})).toHaveAttribute("aria-current", "page");
  await noErrors(page, watch);
});

test("each preset AI instruction returns a settings draft that applies like a real proposal", async ({page}) => {
  test.setTimeout(900_000);
  const watch = await openDemo(page);
  const header = page.locator("header");
  await expect(regions(page).first()).toBeAttached({timeout: live});
  await liveEngine(page);
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
  // After the visitor changes a setting, the examples still answer.
  await page.getByRole("button", {name: "パネルを閉じる"}).click();
  const inspector = await openSettings(page);
  await inspector.getByRole("combobox", {name: "背景補正", exact: true}).selectOption("automatic");
  await idle(page);
  await composer.click();
  const comparison = examples.filter({hasText: "比較"});
  await (await comparison.count() ? comparison.first() : examples.first()).click();
  await idle(page);
  await expect(notRecorded).toHaveCount(0);
  expect(await alerts(page)).toEqual([]);
  // The applied draft is what the statistics view calculates.
  await header.getByRole("button", {name: "統計", exact: true}).click();
  for (const group of await comparisonGroups(page).locator("input").all()) await group.check();
  await calculate(page);
  await header.getByRole("button", {name: "グラフ", exact: true}).click();
  await renderFigure(page);
  // Free text gets the demo notice, which the visitor can dismiss.
  await header.getByRole("button", {name: "画像", exact: true}).click();
  await composer.fill("公開デモで記録されていない指示");
  await page.getByRole("button", {name: "AIへ送信"}).click();
  await expect(notRecorded).toBeVisible({timeout: live});
  await notRecorded.getByRole("button", {name: "案内を閉じる"}).click();
  await expect(notRecorded).toHaveCount(0);
  await noErrors(page, watch);
});
