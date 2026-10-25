// Record every GET response the real workspace UI makes while opening the seeded
// workspace and switching 画像 (each field, region and channel), 統計 and
// グラフ (each saved figure). Config arrives as JSON on stdin (see build.py).
import {createHash} from "node:crypto";
import {mkdir, writeFile} from "node:fs/promises";
import {createRequire} from "node:module";
import path from "node:path";

const config = JSON.parse(await new Promise(resolve => {let text = ""; process.stdin.on("data", chunk => text += chunk); process.stdin.on("end", () => resolve(text));}));
const require = createRequire(path.join(config.web, "package.json"));
const {chromium} = require("@playwright/test");
const KEEP_HEADERS = ["content-type", "x-cytellect-preview-display"];
const EXTENSIONS = {"application/json": ".json", "image/png": ".png", "image/svg+xml": ".svg", "text/csv": ".csv", "application/pdf": ".pdf"};

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
const context = await browser.newContext({viewport: {width: 1440, height: 900}});
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
const count = await cards.count();
if (count !== config.fields) report.alerts.push(`field count ${count} != ${config.fields}`);
// Every field, region and channel a visitor can look at, so browsing never meets an unrecorded
// view (regions through the settings panel; never 細胞ROI: it starts a run).
const region = page.locator("select").filter({has: page.locator("option[value=nucleoplasm]")}).first();
const channels = page.locator("[class*=channelBar] > button[aria-pressed]:not([aria-label])");
for (let index = 0; index < count; index++) {
  await step(`field ${index + 1}`, () => cards.nth(index).click());
  if (!(await region.isVisible())) await step("settings panel", () => page.getByRole("button", {name: "設定パネル"}).click());
  for (const value of config.regions ?? ["nuclei", "nucleoli", "nucleoplasm"]) {
    await step(`field ${index + 1} region ${value}`, () => region.selectOption(value));
    const total = await channels.count();
    for (let channel = 0; channel < total; channel++) await step(`field ${index + 1} ${value} channel ${channel + 1}`, () => channels.nth(channel).click());
  }
}
await step("first field", () => cards.first().click());
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
