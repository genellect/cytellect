// Send preset AI instructions through the real workspace UI (as a visitor would) so the
// API records each proposal context; the UI then applies the draft and runs its preview.
// Config arrives as JSON on stdin (see build.py record_proposals). Prints one JSON line.
import {createRequire} from "node:module";
import path from "node:path";

const config = JSON.parse(await new Promise(resolve => {let text = ""; process.stdin.on("data", chunk => text += chunk); process.stdin.on("end", () => resolve(text));}));
const require = createRequire(path.join(config.web, "package.json"));
const {chromium} = require("@playwright/test");
const report = {sent: [], alerts: [], consoleErrors: [], requests: [], bodies: []};
const browser = await chromium.launch({executablePath: config.chromium, headless: true});
const context = await browser.newContext({viewport: {width: 1440, height: 900}});
await context.addCookies([{name: config.cookie, value: config.token, domain: "127.0.0.1", path: "/", httpOnly: true, sameSite: "Strict"}]);
const page = await context.newPage();
page.on("console", message => {if (message.type() === "error") report.consoleErrors.push(message.text().slice(0, 300));});
page.on("pageerror", error => report.consoleErrors.push(String(error).slice(0, 300)));
page.on("request", request => {
  if (request.method() === "POST" && request.url().endsWith("/proposal-drafts")) report.bodies.push(JSON.parse(request.postData() || "{}"));
});
page.on("response", response => {
  const request = response.request();
  if (request.url().startsWith(config.api) && request.method() !== "GET")
    report.requests.push(`${request.method()} ${new URL(request.url()).pathname.replace(/[0-9a-f-]{36}/g, "<id>")} ${response.status()}`);
});

async function settle() {
  await page.waitForLoadState("networkidle").catch(() => {});
  for (let index = 0; index < 600; index++) {
    const status = await page.locator("header [role=status]").first().textContent().catch(() => "");
    if (!status) break;
    await page.waitForTimeout(500);
  }
  await page.waitForLoadState("networkidle").catch(() => {});
}

await page.goto(`${config.origin}/workspace${config.workspace ? `?id=${config.workspace}` : ""}`, {waitUntil: "domcontentloaded", timeout: 180000});
await page.locator("[class*=fieldCard]").first().waitFor({timeout: 180000});
await settle();
for (const instruction of config.instructions) {
  await page.getByLabel("AIへの指示").fill(instruction);
  await page.getByRole("button", {name: "AIへ送信"}).click();
  await page.waitForTimeout(500);
  await settle();
  const alerts = (await page.getByRole("alert").allTextContents()).map(text => text.trim()).filter(Boolean);
  report.alerts.push(...alerts.map(text => `${instruction}: ${text.slice(0, 200)}`));
  const panel = page.getByRole("complementary", {name: "AI", exact: true});
  report.sent.push({instruction, answered: await panel.getByRole("button", {name: "AIによる設定変更を戻す"}).count() > 0});
}
await browser.close();
console.log(JSON.stringify(report));
