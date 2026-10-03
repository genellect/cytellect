import { expect, test } from "@playwright/test";

for (const width of [1440, 390]) {
  test(`planning choices remain local and are not adopted automatically at ${width}px`, async ({ page, baseURL }) => {
    await page.setViewportSize({ width, height: 950 });
    const unexpected: string[] = [];
    page.on("request", request => {
      const url = new URL(request.url());
      if (url.pathname.startsWith("/v1/") || (url.protocol.startsWith("http") && url.origin !== new URL(baseURL!).origin)) unexpected.push(url.origin + url.pathname);
    });
    await page.goto("/plan");
    await expect(page.getByRole("heading", { name: /何を測るか、\s*から始める。/ })).toBeVisible();
    await expect(page.getByLabel("測定する領域", { exact: true })).toHaveValue("unknown");
    await page.getByLabel("測定する領域", { exact: true }).selectOption("nucleus");
    await page.getByLabel("測定する蛍光チャンネル", { exact: true }).selectOption("gfp");
    await page.getByLabel("測定に使う画像", { exact: true }).selectOption("grayscale-2d");
    await page.getByLabel("核染色チャンネル", { exact: true }).selectOption("yes");
    await expect(page.getByRole("heading", { name: "核内GFP定量", exact: true })).toBeVisible();
    await page.getByLabel("まず確認したいこと", { exact: true }).selectOption("paired");
    await page.getByLabel("独立して条件を割り付けた単位", { exact: true }).selectOption("fields");
    const downloadEvent = page.waitForEvent("download");
    await page.getByRole("button", { name: "計画メモを保存" }).click();
    const download = await downloadEvent;
    const stream = await download.createReadStream();
    const chunks: Buffer[] = [];
    for await (const chunk of stream!) chunks.push(Buffer.from(chunk));
    const receipt = JSON.parse(Buffer.concat(chunks).toString("utf8"));
    expect(receipt.status).toBe("planning-only-not-adopted");
    expect(receipt.guidance.statistics).toBe("undetermined");
    expect(receipt.guidance.questions.some((q: { id: string }) => q.id === "independence")).toBe(true);
    await page.getByLabel("測定する蛍光チャンネル", { exact: true }).selectOption("other");
    await expect(page.getByRole("heading", { name: "任意の領域・マーカーは対応を拡張中" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "核内GFP定量", exact: true })).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    expect(await page.evaluate(() => ({ local: localStorage.length, session: sessionStorage.length }))).toEqual({ local: 0, session: 0 });
    await page.reload();
    await expect(page.getByLabel("測定する領域", { exact: true })).toHaveValue("unknown");
    expect(unexpected).toEqual([]);
  });
}
