import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
test("public real-image viewer: selection, channels, measurements, mobile",async({page})=>{
 const errors:string[]=[];page.on("pageerror",e=>errors.push(e.message));
 await page.goto("/demo");
 await expect(page.getByAltText(/4DN.*公開実画像/)).toBeVisible();
 await expect(page.getByRole("heading",{name:"Nucleus 01",exact:true})).toBeVisible();
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
 expect(errors).toEqual([]);
});

test("unconfigured public build makes no analysis connection",async({page})=>{
 test.skip(process.env.CYTELLECT_EXPECT_UNCONFIGURED!=="1","Production without API only");
 const connections:string[]=[];page.on("request",r=>{if(r.url().includes(":8000")||r.url().includes("/v1/"))connections.push(r.url());});
 await page.goto("/");
 await expect(page.getByRole("button",{name:"ワークスペースに接続"})).toBeDisabled();
 await expect(page.getByRole("link",{name:/サンプルを試す/})).toBeVisible();
 await page.getByRole("link",{name:/サンプルを試す/}).click();
 await expect(page.getByAltText(/4DN.*公開実画像/)).toBeVisible();
 expect(connections).toEqual([]);
});
