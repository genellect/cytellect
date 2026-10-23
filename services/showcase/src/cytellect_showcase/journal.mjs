// Record the demo tour (snapshot/journal.json) through the in-browser API of a built /demo
// page: each scene starts from the seed in a fresh page, performs the guided operations a
// researcher makes, and every exchange with the engine is kept in order. Phones and
// desktops whose engine is not running yet replay it (apps/web/src/lib/showcase/transport.ts).
// Config arrives as JSON on stdin: {web, origin, chromium, snapshot, out, only?}.
//
// A visitor's requests differ from the recorded ones only in values generated per visit, so
// changes are kept with "*" for: request identifiers and document versions, and identifiers
// the API generated while recording (any UUID absent from the seed's snapshot). The saved
// analysis settings (PUT analysis-spec) are held on the device; they are kept here only as the
// conditions later recorded runs were measured under. Each entry names its scene.
import {createHash} from "node:crypto";
import {mkdir, readdir, readFile, writeFile} from "node:fs/promises";
import {createRequire} from "node:module";
import path from "node:path";

const config = JSON.parse(await new Promise(resolve => {let text = ""; process.stdin.on("data", chunk => text += chunk); process.stdin.on("end", () => resolve(text));}));
const require = createRequire(path.join(config.web, "package.json"));
const {chromium} = require("@playwright/test");
const KEEP_HEADERS = ["content-type", "x-cytellect-preview-display", "content-disposition"];
const EXTENSIONS = {"application/json": ".json", "image/png": ".png", "image/svg+xml": ".svg", "text/csv": ".csv", "application/pdf": ".pdf", "application/zip": ".zip"};
const PER_VISIT = new Set(["request_id", "version", "spec_version"]);
const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/g;
const SETTINGS = /^\/v1\/workspaces\/[^/?]+\/analysis-spec$/;
const LIVE = 240000;

// Identifiers of the seed: everything the snapshot (the opening state) already contains.
const stable = new Set();
for (const name of await readdir(config.snapshot)) if (name.endsWith(".json")) for (const id of (await readFile(path.join(config.snapshot, name), "utf8")).match(UUID) ?? []) stable.add(id);
const generated = value => typeof value === "string" && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(value) && !stable.has(value);
function wildcard(value) {
  if (Array.isArray(value)) return value.map(wildcard);
  if (value && typeof value === "object") return Object.fromEntries(Object.entries(value).map(([key, inner]) => [key, PER_VISIT.has(key) || generated(inner) ? "*" : wildcard(inner)]));
  return generated(value) ? "*" : value;
}
const entries = [], bodies = new Map(), report = {scenes: [], alerts: [], consoleErrors: []};
function keep(exchange) {
  const bytes = Buffer.from(exchange.bytes, "base64");
  const headers = Object.fromEntries(exchange.headers.map(([name, value]) => [name.toLowerCase(), value]));
  const type = (headers["content-type"] || "").split(";")[0].trim();
  const file = bytes.length ? `${createHash("sha256").update(bytes).digest("hex").slice(0, 24)}${EXTENSIONS[type] || ".bin"}` : null;
  if (file) bodies.set(file, bytes);
  const change = !["GET", "HEAD"].includes(exchange.method);
  let body = exchange.body, where = exchange.path;
  if (change) {
    if (body !== null) {try {body = JSON.stringify(wildcard(JSON.parse(body)));} catch {}}
    const [route, query] = where.split("?");
    where = route.split("/").map(segment => generated(segment) ? "*" : segment).join("/") + (query === undefined ? "" : `?${query}`);
  }
  const settings = change && SETTINGS.test(exchange.path);
  entries.push({scene: current, method: exchange.method, path: where, body, status: exchange.status,
    headers: KEEP_HEADERS.filter(name => headers[name] !== undefined).map(name => [name, headers[name]]), file: settings ? null : file});
}

const browser = await chromium.launch({executablePath: config.chromium, headless: true});
let current = "";
async function scene(name, walk) {
  current = name;
  const context = await browser.newContext({viewport: {width: 1440, height: 900}, acceptDownloads: true});
  const page = await context.newPage();
  const start = entries.length, started = Date.now();
  await page.exposeFunction("__cytellectShowcaseRecord", keep);
  page.on("console", message => {if (message.type() === "error") report.consoleErrors.push(`${name}: ${message.text().slice(0, 300)}`);});
  page.on("pageerror", error => report.consoleErrors.push(`${name}: ${String(error).slice(0, 300)}`));
  try {
    await page.goto(`${config.origin}/demo`, {waitUntil: "domcontentloaded", timeout: LIVE});
    await page.locator("[data-showcase-engine=active]").waitFor({state: "attached", timeout: LIVE});
    await walk(page);
    await idle(page);
  } catch (error) {
    report.alerts.push(`${name}: ${String(error).split("\n")[0].slice(0, 300)}`);
    await page.screenshot({path: path.join(config.out, `failure-${name}.png`)}).catch(() => {});
  }
  for (const text of await page.getByRole("alert").allTextContents().catch(() => [])) if (text.trim() && !expected.has(text.trim().slice(0, 300))) report.alerts.push(`${name}: ${text.trim().slice(0, 300)}`);
  report.scenes.push({name, entries: entries.length - start, seconds: Math.round((Date.now() - started) / 100) / 10});
  await context.close();
}
async function idle(page) {
  await page.waitForLoadState("networkidle").catch(() => {});
  for (let index = 0; index < 120; index++) {
    const busy = await page.locator("header [role=status]").first().textContent().catch(() => "");
    if (!busy?.trim()) break;
    await page.waitForTimeout(500);
  }
  await page.waitForTimeout(800);
}
const header = page => page.locator("header");
const statistics = page => page.getByRole("region", {name: "測定結果の統計解析"});
const figure = page => page.getByRole("region", {name: "図の作成・保存"});

// The guided operations, each from the seed. Order inside a scene is the order a visitor
// following 「使い方」 takes; the replay also finds a recorded change taken out of order.
const tab = async (page, name) => {await header(page).getByRole("button", {name, exact: true}).click(); await idle(page);};
const sidebar = page => page.getByRole("complementary", {name: "解析対象"});
// Refusals the API gives every visitor for these images, recorded so a replay shows them too.
const expected = new Set();
async function calculate(page, refusal = null) {
  const results = statistics(page);
  for (const label of ["独立実験単位、撮影・画素条件、採否と欠測の扱いを確認した", "測定領域と採用する視野を確認した"]) {
    const box = results.getByLabel(label);
    if (await box.count() && !await box.isChecked()) await box.check();
  }
  const button = results.getByRole("button", {name: "計算", exact: true});
  await button.click();
  await page.waitForFunction(() => [...document.querySelectorAll("button")].some(button => button.textContent === "計算" && !button.disabled), null, {timeout: LIVE});
  await idle(page);
  const refused = (await results.getByRole("alert").allTextContents()).filter(text => text.trim());
  if (refusal && refused.length && refused.every(text => text.includes(refusal))) {expected.add(refused[0].trim().slice(0, 300)); return false;}
  if (refused.length) throw new Error(`calculation refused: ${refused.join(" / ")}`);
  return true;
}
async function render(page) {
  const update = figure(page).getByRole("button", {name: "図を更新", exact: true});
  await update.click();
  await page.waitForFunction(() => [...document.querySelectorAll("button")].some(button => button.textContent === "図を更新" && !button.disabled), null, {timeout: LIVE});
  await idle(page);
}
// Figure variants of the result just calculated, then the defaults again so the next
// calculation carries the plot a visitor's would.
async function figures(page, comparison) {
  await tab(page, "グラフ");
  const width = figure(page).getByRole("combobox", {name: "図の幅", exact: true});
  await render(page);
  if (comparison) {
    const layout = figure(page).getByRole("combobox", {name: "図のレイアウト", exact: true});
    for (const kind of ["box", "violin", "histogram"]) {await layout.selectOption(kind); await render(page);}
    await layout.selectOption("distribution");
  }
  await width.selectOption("89"); await render(page);
  await width.selectOption("183");
  await tab(page, "統計");
}
// Hoechst saturates in these images, so its brightness is described but never compared
// (the API refuses it, as it would for a visitor).
const METRICS = [["area_px", null, ["distribution", "comparison"]], ["mean", "hoechst", ["distribution"]],
  ["mean", "npm1", ["distribution", "comparison"]]];
const REFUSAL = "核小体を確定できない核";
const NUCLEOLAR = [["nucleolar_count", null, ["distribution", "comparison"]], ["nucleolar_area_fraction", null, ["distribution", "comparison"]]];
function statisticsScene(target) {
  return async page => {
    await tab(page, "統計");
    await statistics(page).waitFor({timeout: LIVE});
    await sidebar(page).getByRole("combobox", {name: "領域", exact: true}).selectOption(target);
    await idle(page);
    // Three fields hold a nucleus whose nucleolus was not found, so every statistic that reads
    // the nucleolar compartments is refused with that reason.
    if (target !== "nuclei") {
      for (const metric of ["area_px", "mean"]) {
        await sidebar(page).getByRole("combobox", {name: "指標", exact: true}).selectOption(metric);
        if (metric === "mean") await sidebar(page).getByRole("combobox", {name: "染色", exact: true}).selectOption("npm1");
        for (const kind of ["distribution", "comparison"]) {
          await statistics(page).getByRole("combobox", {name: "解析", exact: true}).selectOption(kind);
          if (await calculate(page, REFUSAL)) await figures(page, kind === "comparison");
        }
      }
      return;
    }
    const operation = statistics(page).getByRole("combobox", {name: "解析", exact: true});
    for (const [metric, channel, kinds] of [...METRICS, ...(target === "nuclei" ? NUCLEOLAR : [])]) {
      await sidebar(page).getByRole("combobox", {name: "指標", exact: true}).selectOption(metric);
      if (channel) await sidebar(page).getByRole("combobox", {name: "染色", exact: true}).selectOption(channel);
      for (const kind of kinds) {
        await operation.selectOption(kind);
        if (await calculate(page, NUCLEOLAR.some(([name]) => name === metric) ? REFUSAL : null)) await figures(page, kind === "comparison");
      }
    }
    // Size against NPM1 brightness, the relation the AI example asks for.
    await sidebar(page).getByRole("combobox", {name: "指標", exact: true}).selectOption("mean");
    await sidebar(page).getByRole("combobox", {name: "染色", exact: true}).selectOption("npm1");
    await operation.selectOption("association");
    await statistics(page).getByRole("combobox", {name: "横軸", exact: true}).selectOption("area_px");
    await calculate(page);
    await figures(page, false);
  };
}
function measureScene(target) {
  return async page => {
    const inspector = page.getByRole("complementary", {name: "画像解析"});
    if (!await inspector.count()) await header(page).getByRole("button", {name: "設定パネル"}).click();
    await inspector.getByRole("combobox", {name: "領域", exact: true}).selectOption(target);
    await idle(page);
    const range = header(page).getByLabel("測定する視野");
    const cards = page.locator("[class*=fieldCard]");
    await range.selectOption("selected");
    for (let index = 0; index < await cards.count(); index++) {
      await cards.nth(index).click(); await idle(page);
      await header(page).getByRole("button", {name: "測定", exact: true}).click(); await idle(page);
    }
    await range.selectOption("all");
    await header(page).getByRole("button", {name: "測定", exact: true}).click(); await idle(page);
  };
}
const scenes = {
  // 「使い方」 in order: the opening result, its figure and the publication package.
  async tour(page) {
    await tab(page, "統計");
    await calculate(page);
    await tab(page, "グラフ");
    await render(page);
    const download = page.waitForEvent("download", {timeout: LIVE});
    await figure(page).getByRole("button", {name: "保存", exact: true}).click();
    await download;
    await idle(page);
  },
  "statistics-nuclei": statisticsScene("nuclei"),
  "statistics-nucleoli": statisticsScene("nucleoli"),
  "statistics-nucleoplasm": statisticsScene("nucleoplasm"),
  "measure-nuclei": measureScene("nuclei"),
  "measure-nucleoli": measureScene("nucleoli"),
  "measure-nucleoplasm": measureScene("nucleoplasm"),
};
for (let index = 0; index < (config.examples ?? 3); index++) scenes[`ai-${index + 1}`] = async page => {
  await page.getByLabel("AIへの指示").click();
  await page.getByRole("group", {name: "指示の例"}).getByRole("button").nth(index).click();
  await idle(page);
  await page.screenshot({path: path.join(config.out, `ai-${index + 1}.png`)});
};
await mkdir(config.out, {recursive: true});
for (const [name, walk] of Object.entries(scenes)) if (!config.only || config.only.includes(name)) await scene(name, walk);
await browser.close();

await mkdir(path.join(config.out, "files"), {recursive: true});
for (const [file, body] of bodies) await writeFile(path.join(config.out, "files", file), body);
await writeFile(path.join(config.out, "journal.json"), JSON.stringify({version: 1, entries}, null, 1) + "\n");
report.entries = entries.length;
await writeFile(path.join(config.out, "journal-report.json"), JSON.stringify(report, null, 1) + "\n");
console.log(JSON.stringify({entries: entries.length, scenes: report.scenes, alerts: report.alerts.length, consoleErrors: report.consoleErrors.length}));
