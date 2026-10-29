import {expect, test, type Page, type Route} from "@playwright/test";

/**
 * Sign-in for the cloud features of the local build, with every /v1 route mocked.
 * Needs the local static build (`pnpm build:local`, served on a loopback origin) in
 * CYTELLECT_LOCAL_UI_URL; no analysis API, cloud service or research data is used.
 * The addresses are reserved example domains.
 */
const origin = process.env.CYTELLECT_LOCAL_UI_URL || "";
const EMAIL = "researcher@example.org";
test.skip(!origin, "Requires the local static build served at CYTELLECT_LOCAL_UI_URL");
// Dates are shown in the PC's time zone; fix it so the expected text is stable.
test.use({timezoneId: "Asia/Tokyo"});

type Account = Record<string, unknown>;
type Mock = {
  session: boolean; firstRun: boolean; account: Account; update: {status: number; body: unknown};
  /** GET answers after an update starts (the last one repeats); `null` stands for a dropped connection. */
  updateAfter?: Array<Record<string, unknown> | null>; updateStarted?: {status: number; body: unknown};
  onCode?: (email: string) => {status: number; body: Account};
  onVerify?: (code: string) => {status: number; body: Account};
  logoutFails?: boolean; accountHeld?: Promise<void>;
  calls: string[];
};

async function mockLocalApi(page: Page, overrides: Partial<Mock> = {}): Promise<Mock> {
  const mock: Mock = {session: false, firstRun: true, account: {state: "signed_out"}, update: {status: 404, body: {detail: "Not Found"}}, calls: [], ...overrides};
  const json = (route: Route, status: number, body: unknown) => route.fulfill({status, contentType: "application/json", body: JSON.stringify(body)});
  await page.route(url => url.pathname.startsWith("/v1/"), async route => {
    const request = route.request(), path = new URL(request.url()).pathname, method = request.method();
    mock.calls.push(`${method} ${path}`);
    const body = request.postData() ? JSON.parse(request.postData()!) : {};
    if (path === "/v1/session") return mock.session ? json(route, 200, {authenticated: true, mode: "local", retention_mode: "manual", retention_hours: null}) : json(route, 401, {detail: "session_required"});
    if (path === "/v1/local/setup") return json(route, 200, {mode: "local", ready: true, fiji_configured: true, retention_mode: "manual", retention_hours: null});
    if (path === "/v1/local/first-run") return json(route, 200, {first_run: mock.firstRun});
    if (path === "/v1/local/session") {mock.session = true; return json(route, 200, {authenticated: true, mode: "local", retention_mode: "manual", retention_hours: null});}
    if (path === "/v1/account" && method === "GET") {await mock.accountHeld; return json(route, 200, mock.account);}
    if (path === "/v1/account/code") {
      const reply = mock.onCode?.(body.email) ?? {status: 200, body: {state: "code_sent", email: body.email, retry_after_seconds: 60}};
      if (reply.status === 200) mock.account = reply.body;
      return json(route, reply.status, reply.body);
    }
    if (path === "/v1/account/verify") {
      const reply = mock.onVerify?.(body.code) ?? (body.code === "123456"
        ? {status: 200, body: {state: "allowed", email: EMAIL}} : {status: 400, body: {detail: "account_code_invalid", attempts_left: 4}});
      if (reply.status === 200) mock.account = {...reply.body, limits: {gpu_seconds_month: 3600, proposal_usd_month: 5}, usage: {gpu_seconds: 0, proposal_usd: 0}, resets_at: "2026-11-01T00:00:00Z"};
      return json(route, reply.status, reply.body);
    }
    if (path === "/v1/account/logout" && mock.logoutFails) return json(route, 503, {detail: "local_api_unreachable"});
    if (path === "/v1/account/logout") {mock.account = {state: "signed_out"}; return json(route, 200, mock.account);}
    if (path === "/v1/account/gpu") return json(route, 200, {state: "idle"});
    if (path === "/v1/app/update" && method === "POST") {
      const reply = mock.updateStarted ?? {status: 202, body: {available: true, state: "downloading"}};
      return json(route, reply.status, reply.body);
    }
    if (path === "/v1/app/update" && mock.updateAfter && mock.calls.includes("POST /v1/app/update")) {
      const next = mock.updateAfter.length > 1 ? mock.updateAfter.shift()! : mock.updateAfter[0];
      return next === null ? route.abort("connectionreset") : json(route, 200, next);
    }
    if (path === "/v1/app/update") return json(route, mock.update.status, mock.update.body);
    if (path === "/v1/workspaces" && method === "GET") return json(route, 200, []);
    return json(route, 404, {detail: "workspace_not_found"});
  });
  return mock;
}

test("first launch offers this PC or the cloud features, and local analysis needs no sign-in", async ({page}) => {
  const mock = await mockLocalApi(page);
  await page.goto(origin + "/workspace");
  await expect(page.getByRole("heading", {name: "インストールが完了しました"})).toBeVisible();
  await expect(page.getByRole("button", {name: /クラウド機能を有効にする/})).toBeVisible();
  await page.getByRole("button", {name: /このPCで解析を始める/}).click();
  await expect(page.getByText(/公開の練習画像（BBBC013）/)).toBeVisible();
  await expect(page.getByRole("link", {name: "練習画像をダウンロード"})).toHaveAttribute("href", /Cytellect-BBBC013-practice-v1\.zip$/);
  await expect(page.getByRole("button", {name: "ログイン", exact: true})).toBeVisible();
  expect(mock.calls).not.toContain("POST /v1/account/code");
  // The choice is remembered: the next start shows the usual start screen.
  mock.session = false;
  await page.reload();
  await expect(page.getByRole("button", {name: "解析を開始"})).toBeVisible();
  await expect(page.getByRole("heading", {name: "インストールが完了しました"})).toHaveCount(0);
});

test("sign-in with an e-mail code: resend waits, wrong codes count down, success shows availability", async ({page}) => {
  await page.clock.install();
  await mockLocalApi(page);
  await page.goto(origin + "/workspace");
  await page.getByRole("button", {name: /クラウド機能を有効にする/}).click();
  const dialog = page.getByRole("dialog", {name: "クラウド機能を有効にする"});
  await dialog.getByLabel("メールアドレス").fill(" Researcher@Example.org ");
  await dialog.getByRole("button", {name: "コードを送る"}).click();
  await expect(dialog.getByText(`${EMAIL} にコードを送りました。`)).toBeVisible();
  await expect(dialog.getByText(/迷惑メール/)).toBeVisible();
  const resend = dialog.getByRole("button", {name: /コードを再送/});
  await expect(resend).toBeDisabled();
  await expect(resend).toContainText("秒後");
  await page.clock.fastForward(61_000);
  await expect(resend).toBeEnabled();
  // Tab stays inside the dialog.
  for (let index = 0; index < 8; index++) await page.keyboard.press("Tab");
  expect(await dialog.evaluate(element => element.contains(document.activeElement))).toBe(true);
  await dialog.getByLabel("6 桁のコード").fill("000000");
  await dialog.getByRole("button", {name: "ログイン", exact: true}).click();
  await expect(dialog.getByRole("alert")).toContainText("あと 4 回入力できます");
  await dialog.getByRole("alert").getByText("詳細").click();
  await expect(dialog.getByRole("alert").locator("code")).toHaveText("account_code_invalid");
  await dialog.getByRole("button", {name: "メールアドレスを修正"}).click();
  await expect(dialog.getByLabel("メールアドレス")).toBeVisible();
  await dialog.getByRole("button", {name: "コードを送る"}).click();
  await dialog.getByLabel("6 桁のコード").fill("123456");
  await dialog.getByRole("button", {name: "ログイン", exact: true}).click();
  await expect(page.getByRole("heading", {name: "クラウド機能が使えます"})).toBeVisible();
  await page.getByRole("button", {name: "作業に戻る"}).click();
  await expect(page.getByText("GPU・解析提案：利用可")).toBeVisible();
  await expect(page.getByText(EMAIL).first()).toBeVisible();
});

test("an unapproved address waits at the top and switches to continuing the login once approved", async ({page}) => {
  await page.clock.install();
  const mock = await mockLocalApi(page, {session: true, firstRun: false, onCode: email => mock.account.approved
    ? {status: 200, body: {state: "code_sent", email, retry_after_seconds: 60}}
    : {status: 200, body: {state: "pending_approval", email, requested_at: 1793000000}}});
  await page.goto(origin + "/workspace");
  await page.getByRole("button", {name: "ログイン", exact: true}).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("メールアドレス").fill("newcomer@example.org");
  await dialog.getByRole("button", {name: "コードを送る"}).click();
  await expect(dialog.getByText(/オーナーに利用を申請しました/)).toBeVisible();
  await expect(dialog.getByRole("heading", {name: "承認を待っています"})).toBeFocused();
  await dialog.getByRole("button", {name: "ローカルの解析を続ける"}).click();
  // Focus returns to the header control that opened the dialog.
  await expect(page.getByRole("button", {name: "承認待ち"})).toBeFocused();
  await expect(page.getByText(/^承認待ち（.*に申請）/)).toBeVisible();
  // The request can be folded to one line but stays at the top.
  await page.getByRole("button", {name: "ローカルの解析を続ける"}).click();
  await expect(page.getByText("承認待ち。このPCでの解析は使えます。")).toBeVisible();
  await page.getByRole("button", {name: "承認待ち"}).click();
  await expect(page.getByRole("dialog").getByRole("heading", {name: "承認を待っています"})).toBeVisible();
  mock.account = {...mock.account, approved: true};
  await page.clock.fastForward(46_000);
  // The open dialog switches to continuing the login as well.
  await expect(page.getByRole("dialog").getByRole("heading", {name: "承認されました"})).toBeVisible();
  await page.keyboard.press("Escape");
  const resume = page.getByRole("button", {name: "承認されました。ログインを続ける"});
  await expect(resume).toBeVisible();
  await resume.click();
  await expect(page.getByRole("dialog").getByText("newcomer@example.org にコードを送りました。")).toBeVisible();
});

test("a used-up GPU allowance names the date it resumes, and an update is offered only when the route answers", async ({page}) => {
  const mock = await mockLocalApi(page, {session: true, firstRun: false, update: {status: 200, body: {available: true, latest: "0.1.0-local.22"}},
    account: {state: "allowed", email: EMAIL, limits: {gpu_seconds_month: 3600, proposal_usd_month: 5},
      usage: {gpu_seconds: 3600, proposal_usd: 1.2}, resets_at: "2026-12-01T00:00:00+09:00"}});
  await page.goto(origin + "/workspace");
  await expect(page.getByText("GPU：今月の上限（12月1日に再開）")).toBeVisible();
  await page.getByRole("group").filter({hasText: EMAIL}).locator("summary").click();
  await expect(page.getByText(/今月の GPU の利用上限に達しました。12月1日から再び使えます/)).toBeVisible();
  await expect(page.getByText("GPU の起動を待つ時間も、GPU の利用時間に数えます。")).toBeVisible();
  mock.logoutFails = true;
  await page.getByRole("button", {name: "ログアウト"}).click();
  await expect(page.getByRole("alert").filter({hasText: "ログアウトできませんでした"})).toBeVisible();
  await expect(page.getByText("更新があります（0.1.0-local.22）。研究データと設定は引き継がれます。")).toBeVisible();
});

const LATEST = {available: true, current: "0.1.0-local.21", latest: "0.1.0-local.22",
  notes_url: "https://github.com/genellect/cytellect/releases/tag/v0.1.0-local.22", state: "idle", error: null};

test("an update is followed through the restart until it completes", async ({page}) => {
  await page.clock.install();
  const mock = await mockLocalApi(page, {session: true, firstRun: false, update: {status: 200, body: LATEST},
    updateAfter: [{...LATEST, state: "installing"}, null, {...LATEST, available: false, current: "0.1.0-local.22", state: "updated"}]});
  await page.goto(origin + "/workspace");
  await expect(page.getByRole("link", {name: "変更内容"})).toHaveAttribute("href", LATEST.notes_url);
  await page.getByRole("button", {name: "更新する"}).click();
  await expect(page.getByText(/^更新しています。/)).toBeVisible();
  expect(mock.calls).toContain("POST /v1/app/update");
  for (let step = 0; step < 4; step++) await page.clock.fastForward(3_100);
  await expect(page.getByText("更新が完了しました（0.1.0-local.22）。")).toBeVisible();
});

test("a failed update says so with its code under 詳細, and an unsafe notes link is not shown", async ({page}) => {
  const mock = await mockLocalApi(page, {session: true, firstRun: false,
    update: {status: 200, body: {...LATEST, notes_url: "https://example.com/notes"}},
    updateStarted: {status: 202, body: {...LATEST, state: "failed", error: "update_failed"}}});
  await page.goto(origin + "/workspace");
  await expect(page.getByText(/更新があります/)).toBeVisible();
  await expect(page.getByRole("link", {name: "変更内容"})).toHaveCount(0);
  await page.getByRole("button", {name: "更新する"}).click();
  const failure = page.getByRole("alert").filter({hasText: "更新できませんでした。今の版のまま使えます。あとでもう一度お試しください。"});
  await expect(failure).toBeVisible();
  await expect(failure).not.toContainText("update_failed", {useInnerText: true});
  await failure.getByText("詳細").click();
  await expect(failure.locator("code")).toHaveText("update_failed");
  expect(mock.calls.filter(call => call === "POST /v1/app/update")).toHaveLength(1);
});

test("an update waits while analyses run, and an installed version starts at the next launch", async ({page}) => {
  await page.clock.install();
  const mock = await mockLocalApi(page, {session: true, firstRun: false, update: {status: 200, body: LATEST},
    updateStarted: {status: 409, body: {...LATEST, error: "update_jobs_running"}}});
  await page.goto(origin + "/workspace");
  await page.getByRole("button", {name: "更新する"}).click();
  await expect(page.getByText(/^解析が終わってから更新してください。/)).toBeVisible();
  await expect(page.getByRole("alert").filter({hasText: /更新/})).toHaveCount(0);
  await expect(page.getByRole("button", {name: "更新する"})).toBeEnabled();
  mock.updateStarted = {status: 202, body: {...LATEST, state: "installing"}};
  mock.updateAfter = [{...LATEST, available: false, state: "installed"}];
  await page.getByRole("button", {name: "更新する"}).click();
  await page.clock.fastForward(3_100);
  await expect(page.getByText("更新の準備ができました（0.1.0-local.22）。次に Cytellect を起動したときに新しい版になります。")).toBeVisible();
});

test("a rollback from the last run is shown once at start", async ({page}) => {
  await mockLocalApi(page, {session: true, firstRun: false,
    update: {status: 200, body: {...LATEST, state: "rolled_back", error: "health_check_failed"}}});
  await page.goto(origin + "/workspace");
  await expect(page.getByText("元の版で起動しました。あとでもう一度更新してください。")).toBeVisible();
  await page.reload();
  await expect(page.getByText(/更新があります/)).toBeVisible();
  await expect(page.getByText("元の版で起動しました。あとでもう一度更新してください。")).toHaveCount(0);
});

test("an installation without the update route shows no update notice", async ({page}) => {
  const mock = await mockLocalApi(page, {session: true, firstRun: false});
  await page.goto(origin + "/workspace");
  await expect(page.getByRole("button", {name: "ログイン", exact: true})).toBeVisible();
  await expect.poll(() => mock.calls.includes("GET /v1/app/update")).toBe(true);
  await expect(page.getByText(/更新があります/)).toHaveCount(0);
});

test("while the first account check waits for the network, the header offers no sign-in", async ({page}) => {
  let release!: () => void;
  const mock = await mockLocalApi(page, {session: true, firstRun: false, account: {state: "allowed", email: EMAIL},
    accountHeld: new Promise<void>(resolve => {release = resolve;})});
  await page.goto(origin + "/workspace");
  await expect(page.getByRole("button", {name: "確認しています"})).toBeDisabled();
  await expect(page.getByRole("button", {name: "ログイン", exact: true})).toHaveCount(0);
  release();
  await expect(page.getByText("GPU・解析提案：利用可")).toBeVisible();
  expect(mock.calls).not.toContain("POST /v1/account/code");
});
