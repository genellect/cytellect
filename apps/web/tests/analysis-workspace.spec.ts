import { expect, test, type Page } from "@playwright/test";

/** Single-workspace prototype with recorded public BBBC013 outputs (no analysis API). */

async function adoptPublicSample(page: Page) {
  // The registered example opens only from a link (site or review), never from the workspace UI.
  await page.goto("/workspace?demo=bbbc013");
  await expect(page.getByRole("heading", { name: "解析案" })).toBeVisible();
  // Index-only names never establish stains; the only decision is one click on the nuclear channel.
  await expect(page.getByRole("button", { name: "解析を実行" })).toBeDisabled();
  await expect(page.getByText("核検出に使うチャンネルを選択")).toBeVisible();
  await expect(page.locator("main input:visible, main select:visible")).toHaveCount(0);
  await page.getByRole("radio", { name: "channel2 を核検出に使う" }).click();
  await expect(page.getByRole("button", { name: "解析を実行" })).toBeEnabled();
  await expect(page.getByText("channel1 平均輝度（補正前）")).toBeVisible();
  await page.getByRole("button", { name: "解析を実行" }).click();
}

test("adds images, adopts one proposal and inspects fields while the run continues", async ({ page }) => {
  await page.goto("/workspace");
  // No workspace form or method choice precedes adding images.
  await expect(page.getByRole("heading", { name: "画像を追加" })).toBeVisible();
  await expect(page.getByRole("button", { name: "フォルダを追加" })).toBeVisible();
  await expect(page.getByText("画像と原値の測定は解析サーバーで処理します。")).toBeVisible();
  await expect(page.getByText(/公開画像|サンプル/)).toHaveCount(0);
  await adoptPublicSample(page);
  await expect(page.getByRole("status").filter({ hasText: "解析中" })).toBeVisible();
  await expect(page.locator("polygon[data-region]").first()).toBeVisible();
  await expect(page.getByRole("button", { name: /ウェル A12/ })).toContainText(/待機|解析中/);
  await expect(page.getByText("完了 3/3")).toBeVisible({ timeout: 20000 });
});

test("a correction updates only that field's figure and can be undone", async ({ page }) => {
  await adoptPublicSample(page);
  await expect(page.getByText("完了 3/3")).toBeVisible({ timeout: 20000 });
  await page.locator('polygon[data-region="12"]').click();
  const panel = page.getByRole("complementary", { name: "選択対象の操作" });
  await expect(panel.getByText("領域 12", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "対象から除外" }).click();
  await expect(panel.getByText("領域 12（除外）")).toBeVisible();
  await page.getByRole("button", { name: /^核面積/ }).click();
  const figure = page.getByRole("img", { name: /核面積の視野ごとの分布/ });
  await expect(figure).toContainText("n = 349（除外 1）");
  await expect(figure).toContainText("n = 242");
  // Styling never reruns analysis: counts and the correction are unchanged.
  await page.getByLabel("幅").selectOption("183");
  await expect(figure).toContainText("n = 349（除外 1）");
  // The saved example figure is offered only when it matches what is displayed.
  await page.locator("summary", { hasText: "書き出し" }).click();
  await expect(page.getByText("修正後の書き出しはプロトタイプでは未対応").first()).toBeVisible();
  await page.locator("summary", { hasText: "書き出し" }).click();
  await page.keyboard.press("Control+z");
  await expect(figure).toContainText("n = 350");
  await page.locator("summary", { hasText: "書き出し" }).click();
  await expect(page.getByText("表示中のグラフが異なります").first()).toBeVisible();
  await expect(page.getByRole("link", { name: /CSV/ })).toBeVisible();
});

test("regions can be chosen from the keyboard through the measurement table", async ({ page }) => {
  await adoptPublicSample(page);
  await expect(page.getByText("完了 3/3")).toBeVisible({ timeout: 20000 });
  await page.getByRole("button", { name: /測定値/ }).click();
  await page.getByRole("button", { name: "領域 7 を選択" }).focus();
  await page.keyboard.press("Enter");
  const panel = page.getByRole("complementary", { name: "選択対象の操作" });
  await expect(panel.getByText("領域 7", { exact: true })).toBeVisible();
  await expect(page.locator('polygon[data-region="7"]')).toHaveClass(/outlineSelected/);
  await expect(page.getByRole("button", { name: "領域 7 を選択" })).toHaveAttribute("aria-current", "true");
});

test("a stopped run keeps finished fields and resumes the rest", async ({ page }) => {
  await adoptPublicSample(page);
  await page.getByRole("button", { name: "中断" }).click();
  await expect(page.getByText(/· 中断/)).toBeVisible();
  await page.getByRole("button", { name: "再開" }).click();
  await expect(page.getByText("完了 3/3")).toBeVisible({ timeout: 20000 });
});

test("a figure point opens its source image and region, and exports are actual outputs", async ({ page }) => {
  await adoptPublicSample(page);
  await expect(page.getByText("完了 3/3")).toBeVisible({ timeout: 20000 });
  await page.getByRole("button", { name: /^核面積/ }).click();
  await page.locator('circle[data-field="BBBC013/01-A-01"][data-region="5"]').click();
  await expect(page.getByRole("img", { name: "ウェル A01の画像" })).toBeVisible();
  await expect(page.locator('polygon[data-region="5"]')).toHaveClass(/outlineSelected/);
  await page.getByRole("button", { name: /測定値/ }).click();
  await expect(page.getByRole("button", { name: "領域 5 を選択" })).toHaveAttribute("aria-current", "true");
  await page.locator("summary", { hasText: "書き出し" }).click();
  const svg = await page.getByRole("link", { name: "SVG" }).getAttribute("href");
  expect((await page.request.get(svg!)).headers()["content-type"]).toContain("svg");
  await expect(page.getByText("プロトタイプでは未対応")).toBeVisible();
});

test("added files are grouped once and rejected real uploads remain visible", async ({ page }) => {
  test.skip(process.env.CYTELLECT_EXPECT_UNCONFIGURED === "1", "Upload transport is exercised in the configured API browser job");
  await page.route("**/v1/workspaces", route => route.fulfill({contentType: "application/json", body: JSON.stringify({id: "grouping-test"})}));
  await page.route("**/v1/workspaces/grouping-test/region-fields", route => route.fulfill({status: 422, contentType: "application/json", body: JSON.stringify({detail: "unsupported_or_invalid_region_image"})}));
  await page.goto("/workspace");
  await page.getByTestId("file-input").setInputFiles([
    { name: "A01_dapi.tif", mimeType: "image/tiff", buffer: Buffer.from("x") },
    { name: "A01_gfp.tif", mimeType: "image/tiff", buffer: Buffer.from("y") },
    { name: "A02_dapi.tif", mimeType: "image/tiff", buffer: Buffer.from("z") },
    { name: "A02_gfp.tif", mimeType: "image/tiff", buffer: Buffer.from("w") },
    { name: "notes.txt", mimeType: "text/plain", buffer: Buffer.from("x") },
    { name: "overview.tif", mimeType: "image/tiff", buffer: Buffer.from("v") },
  ]);
  await expect(page.getByText(/TIFF以外の 1 件は追加していません/)).toBeVisible();
  // Nothing is dropped silently: the unreadable name is listed with what to do.
  const summary = page.getByRole("region", { name: "読み込み結果" });
  await expect(summary).toContainText("5 ファイル → 2 視野 · 2 チャンネル");
  await expect(summary).toContainText("チャンネルを判別できないファイル（1）");
  await expect(summary).toContainText("overview.tif");
  // A named nuclear stain needs no channel decision at all.
  await expect(page.getByText("核検出：DAPI（ファイル名）")).toBeVisible();
  await expect(page.getByRole("button", { name: "解析を実行" })).toBeDisabled();
  await expect(page.locator("main").getByRole("alert")).toContainText("2D・8/16-bitグレースケールTIFF");
  await expect(page.getByRole("link", { name: /SVG|CSV/ })).toHaveCount(0);
});

test("files that form no field are shown and the run stays unavailable", async ({ page }) => {
  test.skip(process.env.CYTELLECT_EXPECT_UNCONFIGURED === "1", "Image grouping requires the configured workspace");
  await page.goto("/workspace");
  await page.getByTestId("file-input").setInputFiles([
    { name: "field01.ome.tif", mimeType: "image/tiff", buffer: Buffer.from("x") },
    { name: "image.tif", mimeType: "image/tiff", buffer: Buffer.from("x") },
  ]);
  const summary = page.getByRole("region", { name: "読み込み結果" });
  await expect(summary).toContainText("2 ファイル → 0 視野");
  await expect(summary).toContainText("チャンネルを取り込み時に読み取るファイル（1）");
  await expect(summary).toContainText("チャンネルを判別できないファイル（1）");
  await expect(page.getByRole("button", { name: "解析を実行" })).toHaveCount(0);
});

for (const viewport of [{ width: 1366, height: 768 }, { width: 1440, height: 900 }, { width: 1024, height: 768 }, { width: 390, height: 844 }]) {
  test(`main operations stay reachable at ${viewport.width}x${viewport.height}`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await adoptPublicSample(page);
    await expect(page.getByText("完了 3/3")).toBeVisible({ timeout: 20000 });
    await expect(page.locator("summary", { hasText: "書き出し" })).toBeInViewport();
    await expect(page.getByRole("img", { name: /の画像$/ })).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(0);
  });
}
