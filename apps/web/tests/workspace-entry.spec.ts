import {expect, test} from "@playwright/test";

test("public root opens the workspace without analytics or a private API connection", async ({page}) => {
  test.skip(process.env.CYTELLECT_EXPECT_UNCONFIGURED !== "1", "Public build only");
  const external: string[] = [];
  page.on("request", request => {if (/google-analytics|googletagmanager|\/v1\//.test(request.url())) external.push(request.url());});
  await page.goto("/");
  await expect(page.getByRole("heading", {name:"画像解析", exact:true})).toBeVisible();
  await expect(page.getByRole("button", {name:"画像を追加", exact:true})).toBeDisabled();
  expect(external).toEqual([]);
  expect((await page.request.get("/legacy")).status()).toBe(404);
});

test("configured root requires a session and enters the workspace after invitation exchange", async ({page}) => {
  test.skip(process.env.CYTELLECT_EXPECT_UNCONFIGURED === "1", "Configured build only");
  let authenticated = false;
  const token = "public-test-invitation-not-a-secret";
  await page.route("**/v1/**", async route => {
    const headers = {"Access-Control-Allow-Origin": new URL(page.url()).origin, "Access-Control-Allow-Credentials":"true", "Access-Control-Allow-Headers":"content-type,x-cytellect-request"};
    const method = route.request().method(), path = new URL(route.request().url()).pathname;
    if (method === "OPTIONS") return route.fulfill({status:204, headers});
    if (path === "/v1/session") return route.fulfill({status: authenticated ? 200 : 401, headers, contentType:"application/json", body:JSON.stringify(authenticated ? {authenticated:true,retention_hours:24,demo:false} : {detail:"session_required"})});
    if (path === "/v1/invitations/redeem") {expect(route.request().postDataJSON()).toEqual({token}); authenticated = true;return route.fulfill({headers,contentType:"application/json",body:"{}"});}
    return route.fulfill({status:404, headers,contentType:"application/json",body:'{"detail":"not_found"}'});
  });
  await page.goto("/");
  await expect(page.getByTestId("file-input")).toHaveCount(0);
  await page.getByLabel("招待コード",{exact:true}).fill(token);
  await page.getByRole("button",{name:"ワークスペースに接続",exact:true}).click();
  await expect(page.getByRole("button",{name:"画像を追加",exact:true})).toBeEnabled();
  await expect(page.getByLabel("招待コード",{exact:true})).toHaveCount(0);
});
