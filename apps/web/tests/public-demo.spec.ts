import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { createHash } from "node:crypto";
import published from "../src/lib/published-release.json";
// The published record names its asset; the installer replaces the ZIP steps (src/lib/release.ts).
const assetFile=published.asset==="installer"?`Cytellect-Setup-${published.version}.exe`:`Cytellect-${published.version}-windows-x64.zip`;
const storeApp="ms-windows-store://pdp/?ProductId=9PGKTQGV7X5C";
const storeWeb="https://apps.microsoft.com/detail/9PGKTQGV7X5C";
const storeButton="Microsoft Store で入手";
test("unconfigured public build makes no analysis connection",async({page})=>{
 await page.emulateMedia({reducedMotion:"reduce"});
 test.skip(process.env.CYTELLECT_EXPECT_UNCONFIGURED!=="1","Production without API only");
 const connections:string[]=[];page.on("request",r=>{if(r.url().includes(":8000")||r.url().includes("/v1/"))connections.push(r.url());});
 await page.goto("/");
 const release=process.env.CYTELLECT_EXPECT_RELEASE_URL;
 const hero=page.getByRole("region",{name:"Get your microscopy publication-ready.",exact:true});
 if(release===undefined){
  await expect(hero.getByRole("link",{name:storeButton})).toHaveAttribute("href",storeApp);
  await expect(page.locator("#download").getByRole("link",{name:storeButton})).toHaveAttribute("href",storeApp);
  await expect(page.locator("#download").getByRole("link",{name:"Store の掲載ページ"})).toHaveAttribute("href",storeWeb);
  await expect(page.getByRole("link",{name:/Windows版をダウンロード/})).toHaveCount(0);
  await expect(page.locator("#download").getByText("Windows 11（x64）",{exact:true})).toBeVisible();
 }else if(release){
  await expect(page.getByRole("link",{name:/Windows版をダウンロード/})).toHaveAttribute("href",release);
  await expect(page.locator("#download").getByText(/Windows 10／11（64ビット）/)).toBeVisible();
  // The LP shows no install steps; they appear only after the download starts, then live on /download.
  const download=page.locator("#download").getByRole("link",{name:/Windows版をダウンロード/});
  await expect(page.getByRole("dialog",{name:"ダウンロードを始めました"})).toHaveCount(0);
  await download.evaluate(a=>a.addEventListener("click",e=>e.preventDefault()));
  await download.click();
  const next=page.getByRole("dialog",{name:"ダウンロードを始めました"});
  if(/\/Cytellect-Setup-[^/]+\.exe$/.test(release)){
   await expect(next.getByText(/「インストール」を押します/)).toBeVisible();
   await expect(next.getByText(/展開/)).toHaveCount(0);
  }else{
   await expect(next.getByText("ダウンロードしたZIPを展開します。",{exact:true})).toBeVisible();
   await expect(next.getByText(/「インストール」/)).toHaveCount(0);
  }
  await page.keyboard.press("Escape");
  await expect(next).toHaveCount(0);
 }else{
  await expect(page.locator("#download").getByRole("link",{name:"デモを体験する",exact:true})).toBeVisible();
  await expect(page.getByRole("link",{name:/Windows版をダウンロード/})).toHaveCount(0);
  await expect(page.getByRole("link",{name:storeButton})).toHaveCount(0);
 }
 await expect(page.getByLabel("招待コード",{exact:true})).toHaveCount(0);
 await expect(page.locator("#download").getByRole("link",{name:/研究室で導入を相談/}).first()).toHaveAttribute("href","https://compass-official.pages.dev/contact/");
 await page.getByText("画像はPCの外に出ますか？",{exact:true}).click();
 await expect(page.getByText(/検出に使う画像だけを送り、クラウドには残しません。/)).toBeVisible();
 for(const width of [1440,390]){
  await page.setViewportSize({width,height:900});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  if(process.env.CYTELLECT_SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.CYTELLECT_SCREENSHOT_DIR,`public-download-${width}.png`),fullPage:true});
 }
 await expect(hero.getByRole("link",{name:"デモを体験する",exact:true})).toBeVisible();
 await hero.getByRole("link",{name:"デモを体験する",exact:true}).click();
 // The example is the production workspace on the serverless demo transport (tests/showcase.spec.ts).
 await expect(page).toHaveURL(/\/demo(\?|$)/);
 await expect(page.getByText("デモ",{exact:true})).toBeVisible();
 if(release!==""){
  await page.setViewportSize({width:1440,height:900});
  await page.getByRole("link",{name:"ダウンロード",exact:true}).click();
  const link=page.locator("#download").getByRole("link",{name:release===undefined?storeButton:/Windows版をダウンロード/});
  await expect(link).toHaveAttribute("href",release??storeApp);
 }
 expect(connections).toEqual([]);
});

test("published Windows asset downloads with the recorded checksum",async({page},testInfo)=>{
 test.skip(process.env.CYTELLECT_TEST_RELEASE_DOWNLOAD!=="1","Explicit public release download verification only");
 await page.goto("/");
 const pending=page.waitForEvent("download");
 await page.getByRole("link",{name:/Windows版をダウンロード/}).click();
 const download=await pending;
 expect(download.suggestedFilename()).toBe(assetFile);
 const destination=testInfo.outputPath(assetFile);
 await download.saveAs(destination);
 const bytes=fs.readFileSync(destination);
 expect(bytes.length).toBe(published.size_bytes);
 expect(createHash("sha256").update(bytes).digest("hex")).toBe(published.sha256);
});
test("the install guide matches the public Windows distribution",async({page})=>{
 test.skip(process.env.CYTELLECT_EXPECT_UNCONFIGURED!=="1","Production without API only");
 const release=process.env.CYTELLECT_EXPECT_RELEASE_URL;
 test.skip(release==="","Windows distribution disabled");
 await page.goto("/download");
 await expect(page.getByRole("heading",{level:1,name:"Windows版のインストール"})).toBeVisible();
 const download=page.getByRole("link",{name:release===undefined?storeButton:/Windows版をダウンロード/});
 await expect(download).toHaveAttribute("href",release??storeApp);
 if(release===undefined){
  await expect(page.getByRole("heading",{name:"インストールと起動"})).toBeVisible();
  await expect(page.getByRole("heading",{name:"更新",exact:true})).toBeVisible();
  await expect(page.getByRole("link",{name:"Store の掲載ページ"})).toHaveAttribute("href",storeWeb);
 }else{
  await expect(page.getByRole("heading",{name:"インストールの手順"})).toBeVisible();
  await expect(page.getByRole("heading",{name:"トラブルシューティング"})).toBeVisible();
 }
 await expect(page.getByRole("heading",{name:"アンインストール"})).toBeVisible();
 // The guide is a page of its own: the download here does not open the LP's popover.
 await download.evaluate(a=>a.addEventListener("click",e=>e.preventDefault()));
 await download.click();
 await expect(page.getByRole("dialog")).toHaveCount(0);
 for(const width of [1440,390]){
  await page.setViewportSize({width,height:900});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
 }
});
