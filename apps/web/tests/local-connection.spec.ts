import {expect, test, type Page, type Route} from "@playwright/test";

/**
 * The local workspace's connection notice (#284 W9), with every /v1 route mocked: no answer, the wrong
 * origin and an abnormal previous stop each have their own line. Needs the local static build
 * (`pnpm build:local`, served on a loopback origin) in CYTELLECT_LOCAL_UI_URL. No image is used.
 */
const origin = process.env.CYTELLECT_LOCAL_UI_URL || "";
test.skip(!origin, "Requires the local static build served at CYTELLECT_LOCAL_UI_URL");
test.use({timezoneId: "Asia/Tokyo"});

type Mock = {down: boolean; origin: boolean; previous: {abnormal: boolean; reason: string | null; time: number | null}; calls: string[]};

async function mockLocalApi(page: Page, overrides: Partial<Mock> = {}): Promise<Mock> {
  const mock: Mock = {down: false, origin: false, previous: {abnormal: false, reason: null, time: null}, calls: [], ...overrides};
  const json = (route: Route, status: number, body: unknown) => route.fulfill({status, contentType: "application/json", body: JSON.stringify(body)});
  await page.route(url => url.pathname.startsWith("/v1/"), async route => {
    const request = route.request(), path = new URL(request.url()).pathname, method = request.method();
    mock.calls.push(`${method} ${path}`);
    if (path === "/v1/local/session") return json(route, 200, {authenticated: true, mode: "local", retention_mode: "manual", retention_hours: null});
    if (path === "/v1/local/first-run") return json(route, 200, {first_run: false});
    if (path === "/v1/account") return json(route, 200, {state: "signed_out"});
    if (path === "/v1/account/gpu") return json(route, 200, {state: "idle"});
    if (path === "/v1/app/update") return json(route, 404, {detail: "Not Found"});
    if (mock.down) return route.abort("connectionrefused");
    if (path === "/v1/local/setup") return json(route, 200, {mode: "local", ready: true, fiji_configured: true, retention_mode: "manual", retention_hours: null});
    if (path === "/v1/local/previous-stop") return json(route, 200, mock.previous);
    if (mock.origin) return json(route, 403, {detail: "local_origin_required"});
    if (path === "/v1/workspaces" && method === "GET") return json(route, 200, []);
    return json(route, 404, {detail: "workspace_not_found"});
  });
  return mock;
}

test("no answer names the service and the launcher, checks again, and re-reads once it answers", async ({page}) => {
  const mock = await mockLocalApi(page, {down: true});
  await page.goto(origin + "/workspace");
  const notice = page.getByRole("status").filter({hasText: "ローカルのサービス"});
  await expect(notice).toContainText("ローカルのサービス：接続なし");
  await expect(notice).toContainText("再開には、デスクトップの「Cytellect」の起動が必要です。");
  // The browser's own text never reaches the researcher, and the old 「再読み込み」 alert is not shown.
  await expect(page.getByText("Failed to fetch")).toHaveCount(0);
  await expect(page.getByRole("button", {name: "保存状態を再読み込み"})).toHaveCount(0);
  mock.down = false;
  await page.getByRole("button", {name: "再接続", exact: true}).click();
  await expect(notice).toHaveCount(0);
  await expect.poll(() => mock.calls.filter(call => call === "GET /v1/workspaces").length).toBeGreaterThanOrEqual(2);
});

test("the wrong origin says where to open the workspace, without a button that cannot help", async ({page}) => {
  await mockLocalApi(page, {origin: true});
  await page.goto(origin + "/workspace");
  const alert = page.getByRole("alert").filter({hasText: "ローカルのサービス：接続の拒否"});
  await expect(alert).toContainText("作業画面には、デスクトップの「Cytellect」から開いた画面が必要です。");
  await expect(alert.getByRole("button")).toHaveCount(0);
});

test("an abnormal previous stop is named in one line that can be closed", async ({page}) => {
  await mockLocalApi(page, {previous: {abnormal: true, reason: "local_worker_stopped", time: Date.UTC(2026, 10, 23, 9, 28) / 1000}});
  await page.goto(origin + "/workspace");
  const line = page.getByRole("status").filter({hasText: "前回の停止"});
  await expect(line).toContainText("前回の停止：計算処理の停止 · 11月23日 18:28");
  // Until it is closed, a reload shows it again; once closed, the same stop is not shown again.
  await page.reload();
  await expect(line).toContainText("前回の停止：計算処理の停止");
  await line.getByRole("button", {name: "閉じる"}).click();
  await expect(line).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole("navigation", {name: "作業の切替"})).toBeVisible();
  await expect(line).toHaveCount(0);
});
