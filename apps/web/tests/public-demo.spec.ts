import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { createHash } from "node:crypto";
import published from "../src/lib/published-release.json";
test("unconfigured public build makes no analysis connection",async({page})=>{
 await page.emulateMedia({reducedMotion:"reduce"});
 test.skip(process.env.CYTELLECT_EXPECT_UNCONFIGURED!=="1","Production without API only");
 const connections:string[]=[];page.on("request",r=>{if(r.url().includes(":8000")||r.url().includes("/v1/"))connections.push(r.url());});
 await page.goto("/");
 const release=process.env.CYTELLECT_EXPECT_RELEASE_URL??published.url;
 if(release){
  await expect(page.getByRole("link",{name:/Windows版をダウンロード/})).toHaveAttribute("href",release);
  await expect(page.getByLabel("招待コード",{exact:true})).toHaveCount(0);
  await expect(page.getByText(/Windows 10／11（64ビット）・空き容量 5 GB 以上を推奨/)).toBeVisible();
  await page.getByText("保存先と削除について",{exact:true}).click();
  await expect(page.getByText(/終了中に期限を迎えたデータは次回起動時に削除します。/)).toBeVisible();
 }else{
  await expect(page.locator("#download").getByRole("link",{name:"デモを体験する",exact:true})).toBeVisible();
  await expect(page.getByLabel("招待コード",{exact:true})).toHaveCount(0);
  await expect(page.getByRole("link",{name:/Windows版をダウンロード/})).toHaveCount(0);
 }
 for(const width of [1440,390]){
  await page.setViewportSize({width,height:900});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  if(process.env.CYTELLECT_SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.CYTELLECT_SCREENSHOT_DIR,`public-download-${width}.png`),fullPage:true});
 }
 const hero=page.getByRole("region",{name:"Get your microscopy publication-ready.",exact:true});
 await expect(hero.getByRole("link",{name:"デモを体験する",exact:true})).toBeVisible();
 await hero.getByRole("link",{name:"デモを体験する",exact:true}).click();
 // The example is the production workspace on the serverless demo transport (tests/showcase.spec.ts).
 await expect(page).toHaveURL(/\/demo(\?|$)/);
 await expect(page.getByText("デモ",{exact:true})).toBeVisible();
 if(release){await page.setViewportSize({width:1440,height:900});await page.getByRole("link",{name:"ダウンロード",exact:true}).click();await expect(page.getByRole("link",{name:/Windows版をダウンロード/})).toHaveAttribute("href",release);}
 expect(connections).toEqual([]);
});

test("published Windows asset downloads with the recorded checksum",async({page},testInfo)=>{
 test.skip(process.env.CYTELLECT_TEST_RELEASE_DOWNLOAD!=="1","Explicit public release download verification only");
 await page.goto("/");
 const pending=page.waitForEvent("download");
 await page.getByRole("link",{name:/Windows版をダウンロード/}).click();
 const download=await pending;
 expect(download.suggestedFilename()).toBe(`Cytellect-${published.version}-windows-x64.zip`);
 const destination=testInfo.outputPath("published-windows.zip");
 await download.saveAs(destination);
 const bytes=fs.readFileSync(destination);
 expect(bytes.length).toBe(published.size_bytes);
 expect(createHash("sha256").update(bytes).digest("hex")).toBe(published.sha256);
});
