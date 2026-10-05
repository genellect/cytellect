import { expect, test, type Page } from "@playwright/test";

/** Single-workspace prototype with recorded public BBBC013 outputs (no analysis API). */

async function adoptPublicSample(page: Page) {
  await page.goto("/workspace");
  await page.getByRole("button", { name: "公開画像で試す" }).click();
  await expect(page.getByRole("heading", { name: "解析案" })).toBeVisible();
  // Index-only names never establish stains: the run stays blocked until one set-wide mapping.
  await expect(page.getByRole("button", { name: "解析を実行" })).toBeDisabled();
  await expect(page.getByText("チャンネル「channel1」の染色と役割")).toBeVisible();
  await page.getByLabel("channel1 の染色名").fill("FKHR-EGFP");
  await page.getByLabel("channel1 の役割").selectOption("measure");
  await page.getByLabel("channel2 の染色名").fill("DRAQ");
  await page.getByLabel("channel2 の役割").selectOption("nuclear");
  await page.getByRole("button", { name: "対応を全視野に適用" }).click();
  await expect(page.getByRole("button", { name: "解析を実行" })).toBeEnabled();
  await page.getByRole("button", { name: "解析を実行" }).click();
}

test("adds images, adopts one proposal and inspects fields while the run continues", async ({ page }) => {
  await page.goto("/workspace");
  // No workspace form or method choice precedes adding images.
  await expect(page.getByRole("heading", { name: "画像を追加" })).toBeVisible();
  await expect(page.getByRole("button", { name: "フォルダを追加" })).toBeVisible();
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
  await page.keyboard.press("Control+z");
  await expect(figure).toContainText("n = 350");
});

test("a figure point opens its source image and region, and exports are actual outputs", async ({ page }) => {
  await adoptPublicSample(page);
  await expect(page.getByText("完了 3/3")).toBeVisible({ timeout: 20000 });
  await page.getByRole("button", { name: /^核面積/ }).click();
  await page.locator('circle[data-field="BBBC013/01-A-01"][data-region="5"]').click();
  await expect(page.getByRole("img", { name: "ウェル A01の画像" })).toBeVisible();
  await expect(page.locator('polygon[data-region="5"]')).toHaveClass(/outlineSelected/);
  await page.getByRole("button", { name: /測定値/ }).click();
  await expect(page.locator('tr[aria-selected="true"] th')).toHaveText("5");
  await page.getByText("書き出し", { exact: true }).click();
  const svg = await page.getByRole("link", { name: "SVG" }).getAttribute("href");
  expect((await page.request.get(svg!)).headers()["content-type"]).toContain("svg");
  await expect(page.getByText("PDFは解析APIの接続後に作成します")).toBeVisible();
});

test("added files are grouped once and a prototype failure stays on that field", async ({ page }) => {
  await page.goto("/workspace");
  await page.getByTestId("file-input").setInputFiles([
    { name: "A01_dapi.tif", mimeType: "image/tiff", buffer: Buffer.from("x") },
    { name: "A01_gfp.tif", mimeType: "image/tiff", buffer: Buffer.from("x") },
    { name: "A02_dapi.tif", mimeType: "image/tiff", buffer: Buffer.from("x") },
    { name: "A02_gfp.tif", mimeType: "image/tiff", buffer: Buffer.from("x") },
    { name: "notes.txt", mimeType: "text/plain", buffer: Buffer.from("x") },
  ]);
  await expect(page.getByText("1 件はTIFF以外のため追加しませんでした。")).toBeVisible();
  await expect(page.getByText("2 視野 · 解析案を確認")).toBeVisible();
  await expect(page.getByRole("button", { name: "解析を実行" })).toBeEnabled();
  await page.getByRole("button", { name: "解析を実行" }).click();
  await expect(page.getByText("完了 0/2 · 要確認 2")).toBeVisible({ timeout: 20000 });
  await expect(page.getByRole("alert").filter({ hasText: "再実行" })).toContainText("追加した画像の解析は実行しません");
});

for (const viewport of [{ width: 1366, height: 768 }, { width: 1440, height: 900 }, { width: 1024, height: 768 }, { width: 390, height: 844 }]) {
  test(`main operations stay reachable at ${viewport.width}x${viewport.height}`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await adoptPublicSample(page);
    await expect(page.getByText("完了 3/3")).toBeVisible({ timeout: 20000 });
    await expect(page.getByText("書き出し", { exact: true })).toBeInViewport();
    await expect(page.getByRole("img", { name: /の画像$/ })).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(0);
  });
}
