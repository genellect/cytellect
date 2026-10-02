import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { createHash } from "node:crypto";
import published from "../src/lib/published-release.json";
test("public real-image viewer: selection, channels, measurements, mobile",async({page})=>{
 const errors:string[]=[];page.on("pageerror",e=>errors.push(e.message));page.on("console",m=>{if(m.type()==="error")errors.push(m.text());});
 await page.goto("/demo");
 await expect(page.getByAltText(/4DN.*公開実画像/)).toBeVisible();
 await expect(page.getByRole("heading",{name:"Nucleus 01",exact:true})).toBeVisible();
 await page.getByRole("button",{name:"DAPI",exact:true}).click();
 await expect(page.getByAltText(/4DN.*公開実画像/)).toHaveAttribute("src",/demo-dapi/);
 await page.getByRole("button",{name:"DAPI + NCL",exact:true}).click();
 await page.getByRole("button",{name:"次の核",exact:true}).click();
 await expect(page.getByRole("heading",{name:"Nucleus 02",exact:true})).toBeVisible();
 await page.getByLabel("輪郭",{exact:true}).uncheck();
 await page.getByLabel("輪郭",{exact:true}).check();
 const dir=process.env.CYTELLECT_SCREENSHOT_DIR;
 if(dir){fs.mkdirSync(dir,{recursive:true});await page.screenshot({path:path.join(dir,"public-demo-desktop.png"),fullPage:true});}
 await page.getByRole("button",{name:/02 測定値/}).click();
 await expect(page.locator("tbody tr")).toHaveCount(100);
 const downloaded=page.waitForEvent("download");await page.getByRole("button",{name:"CSV ↓",exact:true}).click();expect((await downloaded).suggestedFilename()).toContain("4DN");
 await page.getByRole("button",{name:/01 画像と領域/}).click();
 await page.setViewportSize({width:390,height:844});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
 if(dir)await page.screenshot({path:path.join(dir,"public-demo-mobile.png"),fullPage:true});
 await page.getByLabel("画像",{exact:true}).selectOption("bbbc039");
 await expect(page.getByAltText(/BBBC039.*公開実画像/)).toBeVisible();
 await page.getByLabel("画像",{exact:true}).selectOption("bbbc013");
 await expect(page.getByAltText(/BBBC013v1.*公開実画像/)).toBeVisible();
 await expect(page.getByText("GFP 平均輝度（原値）",{exact:true})).toBeVisible();
 await page.getByRole("button",{name:"DRAQ · 核染色",exact:true}).click();
 await expect(page.getByAltText(/BBBC013v1.*公開実画像/)).toHaveAttribute("src",/demo-dapi/);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
 if(dir)await page.screenshot({path:path.join(dir,"public-gfp-mobile.png"),fullPage:true});
 await page.setViewportSize({width:1440,height:900});
 if(dir)await page.screenshot({path:path.join(dir,"public-gfp-desktop.png"),fullPage:true});
 await page.getByRole("button",{name:/02 測定値/}).click();
 await expect(page.locator("tbody tr")).toHaveCount(350);
 const gfpCsv=page.waitForEvent("download");await page.getByRole("button",{name:"CSV ↓",exact:true}).click();expect((await gfpCsv).suggestedFilename()).toContain("BBBC013v1");
 expect(errors).toEqual([]);
});

test("unconfigured public build makes no analysis connection",async({page})=>{
 test.skip(process.env.CYTELLECT_EXPECT_UNCONFIGURED!=="1","Production without API only");
 const connections:string[]=[];page.on("request",r=>{if(r.url().includes(":8000")||r.url().includes("/v1/"))connections.push(r.url());});
 await page.goto("/");
 const release=process.env.CYTELLECT_EXPECT_RELEASE_URL??published.url;
 if(release){
  await expect(page.getByRole("link",{name:/Cytellectをダウンロード/})).toHaveAttribute("href",release);
  await expect(page.getByLabel("招待コード",{exact:true})).toHaveCount(0);
  await expect(page.getByText("Windows · x64",{exact:false})).toBeVisible();
  await page.getByText("保存先と削除について",{exact:true}).click();
  await expect(page.getByText(/終了中に期限を迎えたデータは次回起動時に削除します。/)).toBeVisible();
 }else{
  await expect(page.getByRole("button",{name:"ワークスペースに接続"})).toBeDisabled();
  await expect(page.getByRole("link",{name:/Cytellectをダウンロード/})).toHaveCount(0);
 }
 for(const width of [1440,390]){
  await page.setViewportSize({width,height:900});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  if(process.env.CYTELLECT_SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.CYTELLECT_SCREENSHOT_DIR,`public-download-${width}.png`),fullPage:true});
 }
 await expect(page.getByRole("link",{name:/サンプルを試す/})).toBeVisible();
 await page.getByRole("link",{name:/サンプルを試す/}).click();
 await expect(page.getByAltText(/4DN.*公開実画像/)).toBeVisible();
 if(release){await page.getByRole("link",{name:"ダウンロード",exact:true}).click();await expect(page.getByRole("link",{name:/Cytellectをダウンロード/})).toHaveAttribute("href",release);}
 expect(connections).toEqual([]);
});

test("published Windows asset downloads with the recorded checksum",async({page},testInfo)=>{
 test.skip(process.env.CYTELLECT_TEST_RELEASE_DOWNLOAD!=="1","Explicit public release download verification only");
 await page.goto("/");
 const pending=page.waitForEvent("download");
 await page.getByRole("link",{name:/Cytellectをダウンロード/}).click();
 const download=await pending;
 expect(download.suggestedFilename()).toBe(`Cytellect-${published.version}-windows-x64.zip`);
 const destination=testInfo.outputPath("published-windows.zip");
 await download.saveAs(destination);
 const bytes=fs.readFileSync(destination);
 expect(bytes.length).toBe(published.size_bytes);
 expect(createHash("sha256").update(bytes).digest("hex")).toBe(published.sha256);
});
