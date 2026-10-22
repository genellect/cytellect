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
  await expect(page.getByText(/Windows PCで動作します。/)).toBeVisible();
  await page.getByText("保存先と削除について",{exact:true}).click();
  await expect(page.getByText(/終了中に期限を迎えたデータは次回起動時に削除します。/)).toBeVisible();
 }else{
  await expect(page.getByRole("link",{name:/公開画像を見る/})).toBeVisible();
  await expect(page.getByLabel("招待コード",{exact:true})).toHaveCount(0);
  await expect(page.getByRole("link",{name:/Windows版をダウンロード/})).toHaveCount(0);
 }
 for(const width of [1440,390]){
  await page.setViewportSize({width,height:900});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  if(process.env.CYTELLECT_SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.CYTELLECT_SCREENSHOT_DIR,`public-download-${width}.png`),fullPage:true});
 }
 await expect(page.getByRole("link",{name:"解析例を見る",exact:true})).toBeVisible();
 await page.getByRole("link",{name:"解析例を見る",exact:true}).click();
 // The example is the production workspace on the serverless demo transport (tests/showcase.spec.ts).
 await expect(page).toHaveURL(/\/demo(\?|$)/);
 await expect(page.getByText("デモ",{exact:true})).toBeVisible();
 if(release){await page.setViewportSize({width:1440,height:900});await page.getByRole("link",{name:"ダウンロード",exact:true}).click();await expect(page.getByRole("link",{name:/Windows版をダウンロード/})).toHaveAttribute("href",release);}
 expect(connections).toEqual([]);
});

test("public landing links saved measurements to their exact image regions",async({page})=>{
 await page.emulateMedia({reducedMotion:"reduce"});
 test.skip(process.env.CYTELLECT_EXPECT_UNCONFIGURED!=="1","Public landing only");
 const errors:string[]=[];const analysisRequests:string[]=[];
 page.on("pageerror",e=>errors.push(e.message));page.on("console",m=>{if(m.type()==="error")errors.push(m.text());});
 page.on("request",r=>{if(new URL(r.url()).pathname.startsWith("/v1/"))analysisRequests.push(r.url());});
 const source=JSON.parse(fs.readFileSync(path.resolve("public/demo/4dn-ncl/data.json"),"utf8")) as {measurements:{nucleus_id:number;area_px:number;ncl_nucleus_mean_raw:number}[]};
 await page.goto("/");
 await expect(page.getByRole("heading",{level:1})).toHaveText("Get your microscopy publication-ready.");
 await page.getByText("画像と測定値を見比べる",{exact:false}).click();
 const image=page.getByAltText("4DN公開蛍光画像の領域と測定値の対応例");
 await expect(image).toBeVisible();
 await expect.poll(()=>image.evaluate((node:HTMLImageElement)=>node.complete&&node.naturalWidth===1739)).toBe(true);
 await expect(page.getByRole("button",{name:/^図の領域 /})).toHaveCount(source.measurements.length);
 const selected=source.measurements[21];
 await page.getByRole("button",{name:`図の領域 ${selected.nucleus_id}`,exact:true}).click();
 await expect(page.locator('[aria-live="polite"]')).toContainText(selected.area_px.toLocaleString("ja-JP")+" px²");
 await expect(page.locator('[aria-live="polite"]')).toContainText(selected.ncl_nucleus_mean_raw.toFixed(1));
 await expect(page.getByRole("button",{name:`画像の領域 ${selected.nucleus_id}`,exact:true})).toHaveAttribute("stroke","#d8f28c");
 await page.getByRole("button",{name:"画像の領域 1",exact:true}).click();
 await expect(page.locator('[aria-live="polite"]')).toContainText(source.measurements[0].area_px.toLocaleString("ja-JP")+" px²");
 await page.getByLabel("輪郭",{exact:true}).uncheck();
 await expect(page.getByRole("button",{name:"画像の領域 1",exact:true})).toHaveAttribute("stroke","none");
 await page.getByLabel("輪郭",{exact:true}).check();
 await page.getByText("この表示の条件",{exact:true}).click();
 await expect(page.getByText(/OME名と画像形態に基づく暫定対応/)).toBeVisible();
 const downloading=page.waitForEvent("download");await page.getByRole("link",{name:"図の元データを保存 ↓",exact:true}).click();
 const download=await downloading;const downloadPath=await download.path();
 expect(JSON.parse(fs.readFileSync(downloadPath!,"utf8")).measurements).toEqual(source.measurements);
 await page.getByText("この表示の条件",{exact:true}).click();
 for(const width of [1440,390]){
  await page.setViewportSize({width,height:900});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  await expect(page.getByRole("link",{name:"解析設定を見る",exact:true}).first()).toHaveAttribute("href","/plan");
 }
 expect(errors).toEqual([]);expect(analysisRequests).toEqual([]);
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
