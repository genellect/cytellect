import { expect, test, type Page } from "@playwright/test";

const origin = "https://cytellect.vercel.app";
test.beforeEach(() => test.skip(process.env.CYTELLECT_EXPECT_UNCONFIGURED !== "1", "Public build only"));
test.afterEach(async ({ page }) => { await page.waitForLoadState("networkidle"); await page.unrouteAll({ behavior: "wait" }); });

async function isolatedSite(page: Page, baseURL: string, blocked = false) {
  const tags: string[] = [];
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.route(`${origin}/**`, async route => {
    const response = await route.fetch({ url: route.request().url().replace(origin, baseURL.replace(/\/$/, "")) });
    await route.fulfill({ response });
  });
  await page.route("https://www.googletagmanager.com/**", async route => {
    tags.push(route.request().url());
    if (blocked) return route.abort();
    // No events reach Google in automated CI. Retain the actual tag queue contract.
    await route.fulfill({ contentType: "text/javascript", body: `
      window.testEvents=[];
      function accept(args) { window.testEvents.push(Array.from(args)); if(args[2]?.event_callback) args[2].event_callback(); }
      window.dataLayer.forEach(accept); window.dataLayer.push=accept;
    ` });
  });
  return tags;
}
async function commands(page: Page) {
  const frame = page.frames().find(frame => frame.url() === `${origin}/lp-metrics.html`);
  return frame?.evaluate(() => (window as Window & { testEvents?: unknown[][] }).testEvents || []) || [];
}

test("LP sends only fixed page identity and allowlisted actions; exit destroys the tag", async ({page, baseURL}) => {
  const tags = await isolatedSite(page, baseURL!);
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto(`${origin}/?private_name=DO_NOT_SEND#private-result`);
  await expect.poll(async () => JSON.stringify(await commands(page))).toContain('"page_view"');
  expect(tags).toHaveLength(1);
  expect(tags[0]).toContain("id=G-EHKJ8B8N0Y");
  const initial = await commands(page);
  expect(JSON.stringify(initial)).not.toMatch(/DO_NOT_SEND|private-result|private_name/);
  const config = initial.find(row => row[0] === "config")?.[2] as Record<string, unknown>;
  expect(config).toMatchObject({ page_location: `${origin}/`, page_title: "Cytellect", send_page_view: false, allow_google_signals: false });
  await page.locator('[data-lp-event="download_section"]').first().click();
  await expect.poll(async () => JSON.stringify(await commands(page))).toContain('"download_section_click"');
  expect((await commands(page)).filter(row => row[1] === "page_view")).toHaveLength(1);
  // Unknown messages and content never become events.
  await page.evaluate(() => document.querySelector("iframe")?.contentWindow?.postMessage({ type:"cytellect-lp-event", id:"private-file.tif", sequence:8 }, location.origin));
  expect(JSON.stringify(await commands(page))).not.toContain("private-file");
  await page.locator('[data-lp-event="example"]').first().click();
  await expect(page).toHaveURL(`${origin}/demo`);
  await expect(page.locator('iframe[src="/lp-metrics.html"]')).toHaveCount(0);
  expect(await page.evaluate(() => "dataLayer" in window)).toBe(false);
  expect(tags).toHaveLength(1);
  expect(errors).toEqual([]);
});

test("download click uses a fixed event without sending the asset URL", async ({page, baseURL}) => {
  await isolatedSite(page, baseURL!);
  await page.goto(origin);
  await expect.poll(async () => JSON.stringify(await commands(page))).toContain('"page_view"');
  // A normal Ctrl-click preserves browser behavior and leaves the LP available for inspection.
  await page.locator('[data-lp-event="download"]').evaluate((anchor: HTMLAnchorElement) => {
    anchor.addEventListener("click", event => event.preventDefault());
    anchor.dispatchEvent(new MouseEvent("click", { bubbles:true, ctrlKey:true }));
  });
  await expect.poll(async () => JSON.stringify(await commands(page))).toContain('"download_click"');
  const events = await commands(page);
  expect(JSON.stringify(events)).not.toContain("releases/download");
});

test("non-LP routes, standalone frame, localhost and privacy opt-out never load Google", async ({page, baseURL}) => {
  const tags = await isolatedSite(page, baseURL!);
  for (const path of ["/plan", "/demo", "/lp-metrics.html"]) {
    await page.goto(origin + path);
    await page.waitForLoadState("networkidle");
    await expect(page.locator('iframe[src="/lp-metrics.html"]')).toHaveCount(0);
  }
  await page.goto(baseURL!);
  await page.waitForLoadState("networkidle");
  await expect(page.locator('iframe[src="/lp-metrics.html"]')).toHaveCount(0);
  await page.addInitScript(() => Object.defineProperty(navigator, "globalPrivacyControl", { value:true }));
  await page.goto(origin);
  await expect(page.locator('[data-cytellect-public-landing]')).toBeVisible();
  await expect(page.locator('iframe[src="/lp-metrics.html"]')).toHaveCount(0);
  expect(tags).toEqual([]);
});

test("blocking Google leaves navigation usable", async ({page, baseURL}) => {
  await isolatedSite(page, baseURL!, true);
  await page.goto(origin);
  await page.locator('[data-lp-event="planning"]').click();
  await expect(page).toHaveURL(`${origin}/plan`);
  await expect(page.locator('iframe[src="/lp-metrics.html"]')).toHaveCount(0);
});


test("installed-user guidance is visible without contacting a local service", async ({page, baseURL}) => {
  await isolatedSite(page, baseURL!);
  const localRequests: string[] = [];
  page.on("request", request => { if (/^http:\/\/(127\.0\.0\.1|localhost):8765/.test(request.url())) localRequests.push(request.url()); });
  await page.goto(origin);
  await page.getByRole("navigation", { name:"メインナビゲーション" }).getByRole("link", {name:"インストール済みの方"}).click();
  await expect(page.locator("#launch")).toBeInViewport();
  await expect(page.locator("#launch")).toContainText("ブラウザで開く");
  await expect(page.locator("#launch")).toContainText("再ダウンロード・再インストールは不要です。");
  expect(localRequests).toEqual([]);
});

