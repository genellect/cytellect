import {expect, test} from "@playwright/test";

/**
 * The installed app's /workspace opens without a 401 or another browser console error: the first
 * visit's session check, 「解析を開始」, and the cloud-account and update checks that follow. A 401
 * from any of them is logged by the browser as an error ("Failed to load resource … 401"), which the
 * long Goals C1 case (workspace-jump-plk1.spec.ts) also refuses. No image is used and Fiji is not run.
 */
test("the local workspace opens without a 401 or a console error", async ({page}) => {
  test.skip(process.env.CYTELLECT_TEST_LOCAL !== "1", "Requires an isolated packaged local runtime");
  const unauthorized: string[] = [], consoleErrors: string[] = [], pageErrors: string[] = [];
  const probes: Array<{status: number; authenticated: boolean}> = [];
  page.on("response", response => {
    const {pathname} = new URL(response.url());
    if (response.status() === 401) unauthorized.push(`${response.request().method()} ${pathname}`);
    if (pathname === "/v1/local/session" && response.request().method() === "GET")
      void response.json().then((body: {authenticated: boolean}) => probes.push({status: response.status(), authenticated: body.authenticated}), () => {});
  });
  page.on("console", message => {if (message.type() === "error") consoleErrors.push(message.text());});
  page.on("pageerror", error => pageErrors.push(error.message));

  await page.goto("/workspace");
  // A fresh installation offers two ways to begin; one that already holds work shows 「解析を開始」.
  const start = page.getByRole("button", {name: /このPCで解析を始める|^解析を開始/}).first();
  await expect(start).toBeEnabled();
  await expect.poll(() => probes).toEqual([{status: 200, authenticated: false}]);
  const account = page.waitForResponse(response => new URL(response.url()).pathname === "/v1/account" && response.request().method() === "GET");
  await start.click();
  expect((await account).status()).toBe(200);
  await expect(page.getByRole("navigation", {name: "作業の切替"})).toBeVisible();

  // Opening it again with the session (a reload) checks the same way, now authenticated.
  const again = page.waitForResponse(response => new URL(response.url()).pathname === "/v1/account" && response.request().method() === "GET");
  await page.reload();
  expect((await again).status()).toBe(200);
  await expect(page.getByRole("navigation", {name: "作業の切替"})).toBeVisible();
  await expect.poll(() => probes.at(-1)).toEqual({status: 200, authenticated: true});

  expect(unauthorized).toEqual([]);
  expect(pageErrors).toEqual([]);
  expect(consoleErrors).toEqual([]);
});
