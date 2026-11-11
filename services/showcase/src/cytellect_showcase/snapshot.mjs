// Record every GET response the real workspace UI makes while opening the seeded
// workspace and switching 画像 (each field, region and channel; each field's nucleus table and
// its ZIP; each field's partition table and CSV for every target, reference and channel),
// 統計 and グラフ (each saved figure). Config arrives as JSON on stdin (see build.py).
import {createHash} from "node:crypto";
import {mkdir, writeFile} from "node:fs/promises";
import {createRequire} from "node:module";
import path from "node:path";

const config = JSON.parse(await new Promise(resolve => {let text = ""; process.stdin.on("data", chunk => text += chunk); process.stdin.on("end", () => resolve(text));}));
const require = createRequire(path.join(config.web, "package.json"));
const {chromium} = require("@playwright/test");
const KEEP_HEADERS = ["content-type", "x-cytellect-preview-display"];
const EXTENSIONS = {"application/json": ".json", "image/png": ".png", "image/svg+xml": ".svg", "text/csv": ".csv", "application/pdf": ".pdf", "application/zip": ".zip"};

const entries = {}, bodies = new Map(), report = {nonGet: [], consoleErrors: [], alerts: [], changed: [], steps: [], failedRequests: []};
const pending = new Set();
let started = Date.now();
async function step(label, action) {
  started = Date.now();
  try {await action(); await settle(label);}
  catch (error) {
    report.alerts.push(`${label}: walk step failed: ${String(error).split("\n")[0].slice(0, 200)}`);
    await page.screenshot({path: path.join(config.out, `failure-${report.alerts.length}.png`)}).catch(() => {});
  }
}
const browser = await chromium.launch({executablePath: config.chromium, headless: true});
const context = await browser.newContext({viewport: {width: 1440, height: 900}, acceptDownloads: true});
const page = await context.newPage();
page.on("console", message => {if (message.type() === "error") report.consoleErrors.push(message.text().slice(0, 300));});
page.on("pageerror", error => report.consoleErrors.push(String(error).slice(0, 300)));
page.on("requestfailed", request => {if (request.url().startsWith(config.api)) report.failedRequests.push(`${request.method()} ${request.url()}`);});
page.on("request", request => {
  if (!request.url().startsWith(config.api)) return;
  if (!["GET", "OPTIONS"].includes(request.method())) report.nonGet.push(`${request.method()} ${new URL(request.url()).pathname}`);
});
page.on("response", response => {
  const request = response.request();
  if (!request.url().startsWith(config.api) || request.method() !== "GET") return;
  const task = (async () => {
    const url = new URL(request.url());
    const key = `GET ${url.pathname}${url.search}`;
    let body;
    try {body = await response.body();} catch {return;}
    const headers = response.headers();
    const kept = KEEP_HEADERS.filter(name => headers[name] !== undefined).map(name => [name, headers[name]]);
    const type = (headers["content-type"] || "").split(";")[0].trim();
    const digest = createHash("sha256").update(body).digest("hex");
    const file = `${digest.slice(0, 24)}${EXTENSIONS[type] || ".bin"}`;
    if (entries[key] && entries[key].file !== file) report.changed.push(key);
    entries[key] = {status: response.status(), headers: kept, file};
    bodies.set(file, body);
  })();
  pending.add(task); task.finally(() => pending.delete(task));
});

async function settle(label) {
  await page.waitForLoadState("networkidle").catch(() => {});
  for (let index = 0; index < 8; index++) {
    const status = await page.locator("header [role=status]").first().textContent().catch(() => "");
    if (!status) break;
    await page.waitForTimeout(500);
  }
  await page.waitForLoadState("networkidle").catch(() => {});
  await Promise.all([...pending]);
  for (const text of await page.getByRole("alert").allTextContents()) if (text.trim()) report.alerts.push(`${label}: ${text.trim().slice(0, 300)}`);
  report.steps.push(`${label} ${Math.round((Date.now() - started) / 100) / 10}s`);
}

// Session of the workspace owner, created by the builder (never logged or saved).
await context.addCookies([{name: config.cookie, value: config.token, domain: "127.0.0.1", path: "/", httpOnly: true, sameSite: "Strict"}]);
await page.goto(`${config.origin}/workspace${config.workspace ? `?id=${config.workspace}` : ""}`, {waitUntil: "domcontentloaded", timeout: 180000});
const cards = page.locator("[class*=fieldCard]");
try {await cards.first().waitFor({timeout: 180000});}
catch (error) {
  await mkdir(config.out, {recursive: true});
  await page.screenshot({path: path.join(config.out, "failure.png")});
  console.error((await page.locator("body").innerText()).slice(0, 2000), report);
  throw error;
}
await settle("initial");
await mkdir(config.out, {recursive: true});
// One field at a time, so every field's own views are requested. Side by side lists only the two shown
// fields, so the fields are counted (and walked) after leaving it.
const pair = page.getByRole("button", {name: "2 画面", exact: true});
if (await pair.count() && await pair.getAttribute("aria-pressed") === "true") await step("one field at a time", () => pair.click());
// The fields the pair opens on load first; the others follow, so the list is counted once they are all in.
for (let waited = 0; waited < 360 && await cards.count() < config.fields; waited++) await page.waitForTimeout(500);
const count = await cards.count();
if (count !== config.fields) report.alerts.push(`field count ${count} != ${config.fields}`);
/** Whether a control appears (a table's save button shows once the table has arrived). */
const appears = (locator, timeout = 60000) => locator.waitFor({state: "visible", timeout}).then(() => true, () => false);
/** A save button's download, awaited so its GET is recorded (the page keeps no copy of the file). */
async function saved(button) {
  const download = page.waitForEvent("download", {timeout: 180000});
  await button.click();
  await download;
}
/**
 * The shown field's nucleus table and its ZIP, and its partition tables: every target and reference
 * (different regions of the same nuclei) with every measured channel, each with its CSV. The nucleus
 * table is read with the nuclei shown, from the table beside the image or, without room, below it.
 */
async function fieldTables(number) {
  await step(`field ${number} nuclei`, () => region.selectOption("nuclei"));
  const toggle = page.getByRole("button", {name: "核ごとの表", exact: true});
  if (!await toggle.count()) {
    const drawer = page.getByRole("button", {name: /^測定値/}).first();
    if (await drawer.count() && await drawer.getAttribute("aria-expanded") !== "true") await step(`field ${number} measurements`, () => drawer.click());
  }
  if (await toggle.count()) {
    await step(`field ${number} nucleus table`, () => toggle.first().click());
    const zip = page.getByRole("button", {name: "CSV を保存", exact: true}).first();
    if (await appears(zip)) await step(`field ${number} nucleus table zip`, () => saved(zip));
    else report.alerts.push(`field ${number}: no nucleus table ZIP button`);
    await step(`field ${number} channel table`, () => page.getByRole("button", {name: "このチャンネル", exact: true}).first().click());
  } else report.alerts.push(`field ${number}: no nucleus table toggle`);
  // The partition is the table of the nucleolus-and-nucleoplasm colour mode (MV-05): every target and
  // reference (by name) with every stain of the toolbar, each loaded without a button, with its CSV.
  const color = page.getByRole("toolbar", {name: "画像の表示"}).getByRole("combobox", {name: "色分け", exact: true});
  if (!await color.locator("option[value=compartments]:not([disabled])").count()) return;
  await step(`field ${number} compartments`, () => color.selectOption("compartments"));
  const drawer = page.getByRole("button", {name: /^測定値/}).first();
  const panel = page.getByRole("region", {name: "区画への分配"}).first();
  if (!await appears(panel) && await drawer.count() && await drawer.getAttribute("aria-expanded") !== "true") await step(`field ${number} measurements`, () => drawer.click());
  const target = panel.getByRole("combobox", {name: "対象", exact: true}), reference = panel.getByRole("combobox", {name: "参照", exact: true});
  if (await appears(target)) {
    const names = await target.locator("option").evaluateAll(options => options.map(option => option.value).filter(Boolean));
    const stains = page.getByRole("toolbar", {name: "画像の表示"}).locator("button[data-channel]");
    report.partitions = report.partitions ?? 0;
    for (const t of names) for (const r of names) {
      if (t === r) continue;
      for (let c = 0; c < await stains.count(); c++) {
        await step(`field ${number} partition ${report.partitions + 1}`, async () => {await stains.nth(c).click(); await target.selectOption(t); await reference.selectOption(r);});
        const csv = panel.getByRole("button", {name: "原値・補正値をCSV保存", exact: true});
        if (await appears(csv)) await step(`field ${number} partition csv`, () => saved(csv));
        else report.alerts.push(`field ${number}: no partition CSV button`);
        report.partitions++;
      }
    }
    // The default pair (nucleoplasm ÷ nucleoli) is left chosen for the next field.
    await target.selectOption("nucleoplasm"); await reference.selectOption("nucleoli");
  } else report.alerts.push(`field ${number}: no partition choices`);
  await step(`field ${number} outlines`, () => color.selectOption("outline"));
}
// Every field, region and channel a visitor can look at, so browsing never meets an unrecorded
// view (regions through the settings panel; never 細胞ROI: it starts a run).
const region = page.locator("select").filter({has: page.locator("option[value=nucleoplasm]")}).first();
const channels = page.locator("[class*=channelBar] button[data-channel], [class*=channelBar] button[data-composite]");
for (let index = 0; index < count; index++) {
  await step(`field ${index + 1}`, () => cards.nth(index).click());
  if (!(await region.isVisible())) await step("settings panel", () => page.getByRole("button", {name: "設定パネル"}).click());
  for (const value of config.regions ?? ["nuclei", "nucleoli", "nucleoplasm"]) {
    await step(`field ${index + 1} region ${value}`, () => region.selectOption(value));
    const total = await channels.count();
    for (let channel = 0; channel < total; channel++) await step(`field ${index + 1} ${value} channel ${channel + 1}`, () => channels.nth(channel).click());
  }
  await fieldTables(index + 1);
}
await step("first field", () => cards.first().click());
if (await pair.count() && await pair.getAttribute("aria-pressed") === "false") await step("side by side", () => pair.click());
await step("region nuclei", () => region.selectOption("nuclei"));
const tabs = page.getByRole("navigation", {name: "作業の切替"});
await step("statistics", () => tabs.getByRole("button", {name: "統計"}).click());
await step("figure", () => tabs.getByRole("button", {name: "グラフ"}).click());
const history = page.locator("select").filter({has: page.locator("option[disabled]", {hasText: "図を選択"})}).first();
if (await history.count()) {
  const values = await history.locator("option:not([disabled])").evaluateAll(options => options.map(option => option.value));
  for (const value of values) await step(`figure ${value}`, () => history.selectOption(value));
  report.figures = values.length;
} else report.alerts.push("no saved figure history");
await step("back to image", () => tabs.getByRole("button", {name: "画像"}).click());
/** Records one more GET with the same session (GETs never change the state); its status (200 is recorded). */
async function recordRead(path) {
  if (entries[`GET ${path}`]) return 200;
  const response = await context.request.get(config.api + path, {headers: {Origin: config.origin}});
  if (response.status() !== 200) return response.status();
  const body = await response.body(), headers = response.headers();
  const type = (headers["content-type"] || "").split(";")[0].trim();
  const file = `${createHash("sha256").update(body).digest("hex").slice(0, 24)}${EXTENSIONS[type] || ".bin"}`;
  entries[`GET ${path}`] = {status: 200, headers: KEEP_HEADERS.filter(name => headers[name] !== undefined).map(name => [name, headers[name]]), file};
  bodies.set(file, body);
  return 200;
}
// A saved result's figure points open their source fields (the result's revision, each field's pinned
// revision, its measurements and masks), so returning from a result to its images is recorded too.
report.sources = 0;
for (const [key, entry] of Object.entries({...entries})) {
  if (!/^GET \/v1\/jobs\/[^/]+\/(result|common-statistics)$/.test(key) || !bodies.get(entry.file)) continue;
  let revision;
  try {revision = JSON.parse(bodies.get(entry.file).toString("utf8")).revision_id;} catch {continue;}
  if (typeof revision !== "string" || await recordRead(`/v1/revisions/${revision}`) !== 200) continue;
  const record = JSON.parse(bodies.get(entries[`GET /v1/revisions/${revision}`].file).toString("utf8"));
  const pinned = record.config?.cohort_sources ?? {};
  for (const field of record.config?.field_ids ?? []) {
    const source = pinned[field]?.revision_id ?? revision;
    if (await recordRead(`/v1/revisions/${source}`) !== 200) {report.alerts.push(`source revision ${source}`); continue;}
    if (await recordRead(`/v1/revisions/${source}/region-measurements`) !== 200
        || await recordRead(`/v1/revisions/${source}/region-masks?field_id=${encodeURIComponent(field)}`) !== 200) report.alerts.push(`source ${source} ${field}`);
    report.sources++;
  }
}
// The statistics view reads each source's list of nuclei without an established nucleolus (Q-05)
// for any region a visitor chooses there: one read per shown revision and field, kept when the
// revision has compartments (a nuclear one answers 409 and is never read).
report.ledgers = 0;
for (const key of Object.keys(entries)) {
  const shown = /^GET \/v1\/revisions\/([^/?]+)\/region-masks\?field_id=([^&]+)$/.exec(key);
  if (!shown) continue;
  const status = await recordRead(`/v1/revisions/${shown[1]}/compartment-ledger?field_id=${shown[2]}`);
  if (status === 200) report.ledgers++;
  else if (status !== 409) report.alerts.push(`ledger ${shown[1]} ${shown[2]}: ${status}`);
}
// Chromium does not keep bodies of responses the page consumed as blobs (previews, figure
// files); fetch those same GETs again with the same session (GETs never change the state).
report.refetched = 0;
for (const [key, entry] of Object.entries(entries)) {
  if (bodies.get(entry.file)?.length) continue;
  const response = await context.request.get(config.api + key.slice(4), {headers: {Origin: config.origin}});
  const body = await response.body(), headers = response.headers();
  const type = (headers["content-type"] || "").split(";")[0].trim();
  const file = `${createHash("sha256").update(body).digest("hex").slice(0, 24)}${EXTENSIONS[type] || ".bin"}`;
  if (!body.length || response.status() !== entry.status) report.alerts.push(`refetch failed ${key}`);
  entries[key] = {status: response.status(), headers: KEEP_HEADERS.filter(name => headers[name] !== undefined).map(name => [name, headers[name]]), file};
  bodies.set(file, body);
  report.refetched++;
}
await browser.close();

await mkdir(path.join(config.out, "files"), {recursive: true});
for (const [file, body] of bodies) if (Object.values(entries).some(entry => entry.file === file)) await writeFile(path.join(config.out, "files", file), body);
const sorted = Object.fromEntries(Object.keys(entries).sort().map(key => [key, entries[key]]));
await writeFile(path.join(config.out, "index.json"), JSON.stringify({version: 1, entries: sorted}, null, 1) + "\n");
report.entries = Object.keys(entries).length;
await writeFile(path.join(config.out, "report.json"), JSON.stringify(report, null, 1) + "\n");
console.log(JSON.stringify({entries: report.entries, nonGet: report.nonGet.length, consoleErrors: report.consoleErrors.length, alerts: report.alerts.length}));
