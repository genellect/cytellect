// Record the demo tour (snapshot/journal.json) through the in-browser API of a built /demo
// page: each scene starts from the seed in a fresh page, performs the guided operations a
// researcher makes, and every exchange with the engine is kept in order. Phones and
// desktops whose engine is not running yet replay it (apps/web/src/lib/showcase/transport.ts).
// Config arrives as JSON on stdin: {web, origin, chromium, snapshot, out, only?}.
//
// A visitor's requests differ from the recorded ones only in values generated per visit, so
// change bodies are kept with "*" for: request identifiers and document versions, identifiers
// the API generated while recording (any UUID absent from the seed's snapshot), and the context
// an AI example carries (its prepared draft depends only on the instruction). Paths stay exact:
// the client addresses what the recording returned to it. The saved
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
const AI_CONTEXT = new Set(["current_processing", "previous_goal", "previous_proposal", "field_id"]);
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
const bodies = new Map(), report = {scenes: [], alerts: [], consoleErrors: []}, recorded = new Map();
// The client reads only these fields of a rendered figure; the rest repeats the statistics result.
const FIGURE_RENDER = /^\/v1\/jobs\/[^/?]+\/figure-render$/;
function keep(entries, scene, exchange) {
  let bytes = Buffer.from(exchange.bytes, "base64");
  if (exchange.method === "GET" && FIGURE_RENDER.test(exchange.path) && exchange.status === 200) {
    const value = JSON.parse(bytes.toString("utf8"));
    bytes = Buffer.from(JSON.stringify({source_job_id: value.source_job_id, figure: value.figure}));
  }
  const headers = Object.fromEntries(exchange.headers.map(([name, value]) => [name.toLowerCase(), value]));
  const type = (headers["content-type"] || "").split(";")[0].trim();
  const file = bytes.length ? `${createHash("sha256").update(bytes).digest("hex").slice(0, 24)}${EXTENSIONS[type] || ".bin"}` : null;
  if (file) bodies.set(file, bytes);
  const change = !["GET", "HEAD"].includes(exchange.method);
  let body = exchange.body, where = exchange.path;
  if (change) {
    if (body !== null) {
      try {
        const value = wildcard(JSON.parse(body));
        if (where.endsWith("/proposal-drafts") && value && typeof value === "object") for (const key of AI_CONTEXT) if (key in value) value[key] = "*";
        body = JSON.stringify(value);
      } catch {}
    }
  }
  const settings = change && SETTINGS.test(exchange.path);
  entries.push({scene, method: exchange.method, path: where, body, status: exchange.status,
    headers: KEEP_HEADERS.filter(name => headers[name] !== undefined).map(name => [name, headers[name]]), file: settings ? null : file});
}

/** The replay answers a read with the last one recorded before the next change, so only that one is kept. */
function settled(entries) {
  const kept = [];
  let segment = [];
  const flush = () => {
    const last = new Map();
    segment.forEach((entry, index) => last.set(entry.path, index));
    kept.push(...segment.filter((entry, index) => last.get(entry.path) === index));
    segment = [];
  };
  for (const entry of entries) {
    if (entry.method === "GET" || entry.method === "HEAD") {segment.push(entry); continue;}
    flush();
    kept.push(entry);
  }
  flush();
  return kept;
}

const browser = await chromium.launch({executablePath: config.chromium, headless: true});
async function scene(name, walk) {
  const entries = [];
  const context = await browser.newContext({viewport: {width: 1440, height: 900}, acceptDownloads: true});
  const page = await context.newPage();
  const started = Date.now();
  await page.exposeFunction("__cytellectShowcaseRecord", exchange => keep(entries, name, exchange));
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
  recorded.set(name, settled(entries));
  report.scenes.push({name, entries: recorded.get(name).length, seconds: Math.round((Date.now() - started) / 100) / 10});
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
// Figure variants a visitor can choose for the result just calculated: both widths and, for a
// comparison, every layout at each; then the defaults again for the next calculation.
async function figures(page, comparison) {
  await tab(page, "グラフ");
  const width = figure(page).getByRole("combobox", {name: "図の幅", exact: true});
  const layout = figure(page).getByRole("combobox", {name: "図のレイアウト", exact: true});
  for (const value of ["183", "89"]) {
    await width.selectOption(value);
    for (const kind of comparison ? ["distribution", "box", "violin", "histogram"] : [null]) {
      if (kind) await layout.selectOption(kind);
      await render(page);
    }
  }
  await width.selectOption("183");
  if (comparison) await layout.selectOption("distribution");
  await tab(page, "統計");
}
const METRICS = ["area_px", "mean", "median", "integrated", "mean_corrected", "integrated_corrected", "nucleolar_count",
  "nucleolar_area_fraction", "log2_nucleoplasm_over_nucleolus"];
const choices = select => select.locator("option:not([disabled])").evaluateAll(options => options.map(option => option.value).filter(Boolean));
// Every statistic the panel offers for one region and metric, from the seed: each stain, each
// analysis it allows and, for an association, each horizontal axis, with their figures.
function statisticsScene(region, metric) {
  return async page => {
    await tab(page, "統計");
    await statistics(page).waitFor({timeout: LIVE});
    await sidebar(page).getByRole("combobox", {name: "領域", exact: true}).selectOption(region); await idle(page);
    await sidebar(page).getByRole("combobox", {name: "指標", exact: true}).selectOption(metric); await idle(page);
    const stain = sidebar(page).getByRole("combobox", {name: "染色", exact: true});
    for (const channel of await stain.isEnabled() ? await choices(stain) : [null]) {
      if (channel) {await stain.selectOption(channel); await idle(page);}
      const operation = statistics(page).getByRole("combobox", {name: "解析", exact: true});
      for (const kind of await choices(operation)) {
        await operation.selectOption(kind); await idle(page);
        const axis = statistics(page).getByRole("combobox", {name: "横軸", exact: true});
        for (const x of kind === "association" ? await choices(axis) : [null]) {
          if (x) {await axis.selectOption(x); await idle(page);}
          await calculate(page);
          await figures(page, kind === "comparison");
        }
      }
    }
  };
}
// The saved figures the graph view lists, at each width and layout.
async function savedFigures(page) {
  await tab(page, "グラフ");
  const history = figure(page).getByRole("combobox", {name: "保存した図", exact: true});
  await history.waitFor({timeout: LIVE});
  for (const value of await choices(history)) {
    await history.selectOption(value); await idle(page);
    const comparison = await figure(page).getByRole("combobox", {name: "図のレイアウト", exact: true}).count() > 0;
    await figures(page, comparison);
    await tab(page, "グラフ");
  }
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
    // What a researcher does next: back to the first field's nuclei, then statistics and figures
    // of the new measurements.
    await cards.first().click(); await idle(page);
    if (target !== "nuclei") {await inspector.getByRole("combobox", {name: "領域", exact: true}).selectOption("nuclei"); await idle(page);}
    await tab(page, "統計");
    const operation = statistics(page).getByRole("combobox", {name: "解析", exact: true});
    for (const kind of ["distribution", "comparison"]) {
      await operation.selectOption(kind);
      if (await calculate(page)) await figures(page, kind === "comparison");
    }
    await tab(page, "画像");
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
  "saved-figures": savedFigures,
  "measure-nuclei": measureScene("nuclei"),
  "measure-nucleoli": measureScene("nucleoli"),
  "measure-nucleoplasm": measureScene("nucleoplasm"),
};
// Each example from the seed, and all of them in their listed order; the detection preview
// a draft brings is adopted, as a visitor does.
async function example(page, index) {
  await page.getByRole("group", {name: "指示の例"}).getByRole("button").nth(index).click();
  await idle(page);
  const adopt = page.getByRole("button", {name: "候補を採用", exact: true});
  if (await adopt.isVisible()) {await adopt.click(); await idle(page);}
}
for (const region of ["nuclei", "nucleoli", "nucleoplasm"]) for (const metric of METRICS) scenes[`statistics-${region}-${metric}`] = statisticsScene(region, metric);
// After an example the statistics view holds the analysis the draft set up; each analysis it
// offers is calculated, as a visitor continuing from the AI would.
async function statisticsAfter(page) {
  await tab(page, "統計");
  const operation = statistics(page).getByRole("combobox", {name: "解析", exact: true});
  for (const kind of await choices(operation)) {
    await operation.selectOption(kind); await idle(page);
    await calculate(page);
    await figures(page, kind === "comparison");
  }
}
const EXAMPLES = config.examples ?? 3;
for (let index = 0; index < EXAMPLES; index++) scenes[`ai-${index + 1}`] = async page => {
  await page.getByLabel("AIへの指示").click();
  await example(page, index);
  await statisticsAfter(page);
};
scenes["ai-in-order"] = async page => {
  await page.getByLabel("AIへの指示").click();
  for (let index = 0; index < EXAMPLES; index++) await example(page, index);
  await statisticsAfter(page);
};
await mkdir(config.out, {recursive: true});
// Scenes are independent (each starts from the seed), so several run at once.
const names = Object.keys(scenes).filter(name => !config.only || config.only.includes(name));
const queue = [...names];
await Promise.all(Array.from({length: config.concurrency ?? 3}, async () => {
  while (queue.length) {const name = queue.shift(); await scene(name, scenes[name]);}
}));
const entries = names.flatMap(name => recorded.get(name) ?? []);
await browser.close();

await mkdir(path.join(config.out, "files"), {recursive: true});
for (const [file, body] of bodies) await writeFile(path.join(config.out, "files", file), body);
await writeFile(path.join(config.out, "journal.json"), JSON.stringify({version: 1, entries}, null, 1) + "\n");
report.entries = entries.length;
await writeFile(path.join(config.out, "journal-report.json"), JSON.stringify(report, null, 1) + "\n");
console.log(JSON.stringify({entries: entries.length, scenes: report.scenes, alerts: report.alerts.length, consoleErrors: report.consoleErrors.length}));
