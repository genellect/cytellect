import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { createHash } from "node:crypto";
import published from "../src/lib/published-release.json";
// The published record names its asset; the installer replaces the ZIP steps (src/lib/release.ts).
const assetFile=published.asset==="installer"?`Cytellect-Setup-${published.version}.exe`:`Cytellect-${published.version}-windows-x64.zip`;
test("unconfigured public build makes no analysis connection",async({page})=>{
 await page.emulateMedia({reducedMotion:"reduce"});
 test.skip(process.env.CYTELLECT_EXPECT_UNCONFIGURED!=="1","Production without API only");
 const connections:string[]=[];page.on("request",r=>{if(r.url().includes(":8000")||r.url().includes("/v1/"))connections.push(r.url());});
 await page.goto("/");
 const release=process.env.CYTELLECT_EXPECT_RELEASE_URL??published.url;
 if(release){
  await expect(page.getByRole("link",{name:/Windows版をダウンロード/})).toHaveAttribute("href",release);
  await expect(page.getByLabel("招待コード",{exact:true})).toHaveCount(0);
  await expect(page.locator("#download").getByText(/Windows 10／11（64ビット）/)).toBeVisible();
  // The LP shows no install steps; they appear only after the download starts, then live on /download.
  const download=page.locator("#download").getByRole("link",{name:/Windows版をダウンロード/});
  await expect(page.getByRole("dialog",{name:"ダウンロードを始めました"})).toHaveCount(0);
  await download.evaluate(a=>a.addEventListener("click",e=>e.preventDefault()));
  await download.click();
  const next=page.getByRole("dialog",{name:"ダウンロードを始めました"});
  if(/\/Cytellect-Setup-[^/]+\.exe$/.test(release)){
   await expect(next.getByText(/「インストール」を押す/)).toBeVisible();
   await expect(next.getByText(/展開/)).toHaveCount(0);
  }else{
   await expect(next.getByText("ダウンロードしたZIPを展開する",{exact:true})).toBeVisible();
   await expect(next.getByText(/「インストール」/)).toHaveCount(0);
  }
  await page.keyboard.press("Escape");
  await expect(next).toHaveCount(0);
  // Free and cloud are told apart; the cloud is adopted through the contact form.
  await expect(page.locator("#download").getByRole("link",{name:/研究室で導入を相談/}).first()).toHaveAttribute("href","https://compass-official.pages.dev/contact/");
  await page.getByText("画像はPCの外に出ますか？",{exact:true}).click();
  await expect(page.getByText(/検出に使う画像だけを送り、クラウドには残しません。/)).toBeVisible();
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
 expect(download.suggestedFilename()).toBe(assetFile);
 const destination=testInfo.outputPath(assetFile);
 await download.saveAs(destination);
 const bytes=fs.readFileSync(destination);
 expect(bytes.length).toBe(published.size_bytes);
 expect(createHash("sha256").update(bytes).digest("hex")).toBe(published.sha256);
});
test("the install guide page shows what happens before and after the download",async({page})=>{
 test.skip(process.env.CYTELLECT_EXPECT_UNCONFIGURED!=="1","Production without API only");
 const release=process.env.CYTELLECT_EXPECT_RELEASE_URL??published.url;
 test.skip(!release,"No published release");
 await page.goto("/download");
 await expect(page.getByRole("heading",{level:1,name:"Windows版のインストール"})).toBeVisible();
 await expect(page.getByRole("link",{name:/Windows版をダウンロード/})).toHaveAttribute("href",release);
 await expect(page.getByRole("heading",{name:"インストールで起きること"})).toBeVisible();
 await expect(page.getByRole("heading",{name:"うまくいかないとき"})).toBeVisible();
 await expect(page.getByRole("heading",{name:"やめるとき"})).toBeVisible();
 // The guide is a page of its own: the download here does not open the LP's popover.
 const download=page.getByRole("link",{name:/Windows版をダウンロード/});
 await download.evaluate(a=>a.addEventListener("click",e=>e.preventDefault()));
 await download.click();
 await expect(page.getByRole("dialog")).toHaveCount(0);
 for(const width of [1440,390]){
  await page.setViewportSize({width,height:900});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
 }
});
