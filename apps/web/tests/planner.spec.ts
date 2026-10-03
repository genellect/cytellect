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
    await expect(page.getByRole("heading", { name: /測りたいことから、\s*解析を選ぶ。/ })).toBeVisible();
    await expect(page.getByLabel("測定する領域", { exact: true })).toHaveValue("unknown");
    await page.getByLabel("測りたい量",{exact:true}).selectOption("mean");
    await page.getByLabel("測定する領域", { exact: true }).selectOption("nucleus");
    await page.getByLabel("領域の決め方",{exact:true}).selectOption("nuclear-stain");
    await page.getByLabel("測定する蛍光チャンネル", { exact: true }).selectOption("gfp");
    await page.getByLabel("測定に使う画像", { exact: true }).selectOption("grayscale-2d");
    await page.getByLabel("核染色チャンネル", { exact: true }).selectOption("yes");
    await expect(page.getByRole("radio", { name: "核内GFP解析", exact: true })).toBeVisible();
    await page.getByLabel("まず確認したいこと", { exact: true }).selectOption("paired");
    await page.getByLabel("独立して条件を割り付けた単位", { exact: true }).selectOption("fields");
    const downloadEvent = page.waitForEvent("download");
    await page.getByRole("button", { name: "計画メモを保存" }).click();
    const download = await downloadEvent;
    const stream = await download.createReadStream();
    const chunks: Buffer[] = [];
    for await (const chunk of stream!) chunks.push(Buffer.from(chunk));
    const receipt = JSON.parse(Buffer.concat(chunks).toString("utf8"));
    expect(receipt.version).toBe(process.env.CYTELLECT_EXPECT_PLAN_VERSION||(process.env.CYTELLECT_TEST_LOCAL==="1"||process.env.CYTELLECT_TEST_API_ORIGIN?"2.1.0":"2.0.0"));
    expect(receipt.answers.comparison).toBe("paired");expect(receipt.answers.allocation).toBe("fields");
    expect(Object.keys(receipt).sort()).toEqual(["answers","format","version"]);
    await page.getByLabel("測定する蛍光チャンネル", { exact: true }).selectOption("other");
    await expect(page.getByRole("radio", { name: "核染色からの核検出・測定", exact:true })).toBeVisible();
    await expect(page.getByRole("radio", { name: "核内GFP解析", exact: true })).toHaveCount(0);
    await page.getByLabel("測りたい量",{exact:true}).selectOption("area");
    await page.getByLabel("GFPによる陽性選別",{exact:true}).selectOption("negative-control");
    await page.getByLabel("陽性選別に使うチャンネル",{exact:true}).selectOption("gfp");
    await expect(page.getByRole("radio", { name: "核内GFP解析", exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    expect(await page.evaluate(() => ({ local: localStorage.length, session: sessionStorage.length }))).toEqual({ local: 0, session: 0 });
    await page.reload();
    await expect(page.getByLabel("測定する領域", { exact: true })).toHaveValue("unknown");
    expect(unexpected).toEqual([]);
  });
}
