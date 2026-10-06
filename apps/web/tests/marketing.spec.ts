import {test,expect} from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

test.beforeEach(()=>{test.skip(process.env.CYTELLECT_EXPECT_UNCONFIGURED!=="1","Unconfigured public build only");});

test("immersive LP keeps outcomes readable across viewports and routes to the real product",async({page})=>{
 const errors:string[]=[];page.on("pageerror",error=>errors.push(error.message));
 await page.emulateMedia({reducedMotion:"reduce"});
 await page.goto("/");
 const hero=page.getByRole("region",{name:"Get your microscopy publication-ready.",exact:true});
 await expect(hero.getByRole("heading",{level:1})).toHaveText("Get your microscopy publication-ready.");
 await expect(hero.locator("p")).toHaveCount(0);
 await expect(hero.locator("video")).toHaveCount(0);await expect(hero.locator("canvas")).toHaveCount(0);
 await expect(hero.getByRole("link",{name:"ダウンロード",exact:true})).toHaveAttribute("href","#download");
 await expect(hero.getByRole("link",{name:"解析例を見る",exact:true})).toHaveAttribute("href","/demo");
 await expect(hero.getByRole("button",{name:/領域/})).toHaveCount(0);
 await expect(page.getByRole("link",{name:"グラフを拡大",exact:true})).toHaveAttribute("href","/marketing/figure-public.svg");
 const dir=process.env.CYTELLECT_SCREENSHOT_DIR;if(dir)fs.mkdirSync(dir,{recursive:true});
 for(const [width,height] of [[1440,900],[1280,800],[768,1024],[390,844],[360,800]]){
  await page.setViewportSize({width,height});
  await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await expect(hero.getByRole("heading")).toBeVisible();
  expect(await hero.locator("h1 span").evaluateAll(nodes=>nodes.every(node=>node.getBoundingClientRect().right<=innerWidth-16&&node.scrollWidth<=node.clientWidth))).toBe(true);
  expect(await page.locator("h2 span").evaluateAll(nodes=>nodes.every(node=>node.getBoundingClientRect().right<=innerWidth-16&&node.scrollWidth<=node.clientWidth))).toBe(true);
  for(const name of [/研究に使える\s*時間を、もっと。/,/コードを書かずに、\s*統計まで。/,/その研究を、\s*伝わる一枚に。/]){await expect(page.getByRole("heading",{name,exact:true})).toBeVisible();}
  if(dir){for(const img of await page.locator('main img[src^="/marketing/"]').all()){await img.scrollIntoViewIfNeeded();await expect.poll(()=>img.evaluate((node:HTMLImageElement)=>node.complete&&node.naturalWidth>0)).toBe(true);}await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:path.join(dir,`lp-${width}.png`),fullPage:true});if(width===1440||width===390)await page.screenshot({path:path.join(dir,`lp-hero-${width}.png`),fullPage:false});}
 }
 await page.setViewportSize({width:390,height:844});await page.evaluate(()=>scrollTo(0,0));
 const toggle=page.getByRole("button",{name:"メニューを開く",exact:true});await toggle.click();
 const nav=page.getByRole("navigation",{name:"モバイルナビゲーション"});
 await expect(nav.getByRole("link")).toHaveText(["プロダクト","解析例","解析画面","ガイド","ダウンロード ↗","インストール済みの方"]);
 await page.keyboard.press("Escape");await expect(toggle).toBeFocused();await expect(toggle).toHaveAttribute("aria-expanded","false");
 await toggle.click();await nav.getByRole("link",{name:"ガイド",exact:true}).click();await expect(toggle).toHaveAttribute("aria-expanded","false");
 await expect(page.getByRole("heading",{name:"使い方と解析方法",exact:true})).toBeVisible();
 const images=page.locator('main img[src^="/marketing/"]');
 for(const img of await images.all()){await img.scrollIntoViewIfNeeded();await expect.poll(()=>img.evaluate((node:HTMLImageElement)=>node.complete&&node.naturalWidth>0)).toBe(true);}
 await page.getByRole("link",{name:"グラフを拡大",exact:true}).click();await expect(page).toHaveURL(/figure-public\.svg$/);await page.goBack();await expect(hero.getByRole("heading",{level:1})).toBeVisible();
 expect(errors).toEqual([]);
});

test("failed 3D asset leaves the poster and primary action available",async({page})=>{
 await page.emulateMedia({reducedMotion:"no-preference"});
 await page.route("**/marketing/cell-sculpture.glb",route=>route.abort());
 await page.goto("/");
 await expect(page.getByTestId("hero-scene")).toHaveAttribute("data-state","error");
 const poster=page.getByAltText("青く照らされた細胞構造",{exact:true});
 await expect(poster).toBeVisible();
 await expect.poll(()=>poster.evaluate((node:HTMLImageElement)=>node.complete&&node.naturalWidth>0)).toBe(true);
 await expect(page.getByRole("region",{name:"Get your microscopy publication-ready.",exact:true}).getByRole("link",{name:"ダウンロード",exact:true})).toBeVisible();
 await expect(page.locator("canvas")).toHaveCount(0);
 await page.unroute("**/marketing/cell-sculpture.glb");
 await page.route("**/marketing/cell-sculpture.glb",async route=>{
  const response=await route.fetch();const body=await response.body();
  const jsonLength=body.readUInt32LE(12);const json=body.subarray(20,20+jsonLength).toString("utf8");
  // Equal-length unknown keys simulate a valid model with missing surface maps.
  const missingNormal=json.replaceAll('"normalTexture"','"unusedTexture"');expect(missingNormal).not.toBe(json);
  body.write(missingNormal,20,"utf8");await route.fulfill({response,body});
 });
 await page.reload();await expect(page.getByTestId("hero-scene")).toHaveAttribute("data-state","error");
 await expect(poster).toBeVisible();await expect(page.locator("canvas")).toHaveCount(0);
});

test("a researcher can stop the real 3D rendering and keep it stopped after navigation",async({page})=>{
 const errors:string[]=[];page.on("pageerror",error=>errors.push(error.message));page.on("console",message=>{if(message.type()==="error")errors.push(message.text());});
 await page.setViewportSize({width:1440,height:900});
 await page.emulateMedia({reducedMotion:"no-preference"});
 await page.goto("/");
 const scene=page.getByTestId("hero-scene");
 await expect(scene).toHaveAttribute("data-state","ready");
 await expect(scene.locator("canvas")).toBeVisible();
 const rendered=scene.locator("[data-render-count]");
 await page.getByRole("button",{name:"背景映像を停止",exact:true}).click();
 await expect(scene).toHaveAttribute("data-paused","true");
 const count=await rendered.getAttribute("data-render-count");
 await page.waitForTimeout(180);
 await expect(rendered).toHaveAttribute("data-render-count",count!);
 const dir=process.env.CYTELLECT_SCREENSHOT_DIR;if(dir){fs.mkdirSync(dir,{recursive:true});await page.screenshot({path:path.join(dir,"lp-hero-3d.png")});}
 await page.getByRole("link",{name:"プロダクト",exact:true}).click();
 await page.evaluate(()=>scrollTo(0,0));
 await expect(page.getByRole("button",{name:"背景映像を再生",exact:true})).toBeVisible();
 await expect(scene).toHaveAttribute("data-paused","true");
 await page.getByRole("button",{name:"背景映像を再生",exact:true}).click();
 await expect.poll(async()=>Number(await rendered.getAttribute("data-render-count"))).toBeGreaterThan(Number(count));
 const figure=page.getByAltText(/^公開画像の817領域/);await figure.scrollIntoViewIfNeeded();
 await page.waitForTimeout(180);const offscreen=await rendered.getAttribute("data-render-count");await page.waitForTimeout(180);await expect(rendered).toHaveAttribute("data-render-count",offscreen!);
 const stage=figure.locator("xpath=ancestor::figure/parent::div");await expect.poll(()=>stage.evaluate(node=>node.style.getPropertyValue("--paper-angle"))).not.toBe("");
 await page.emulateMedia({reducedMotion:"reduce"});await expect.poll(()=>stage.evaluate(node=>node.style.getPropertyValue("--paper-angle"))).toBe("");await expect(scene.locator("canvas")).toHaveCount(0);
 expect(errors).toEqual([]);
});
test("product walkthrough is explicitly started and returns to the real still image",async({page})=>{
 await page.emulateMedia({reducedMotion:"reduce"});await page.goto("/");
 await expect(page.getByRole("region",{name:"Get your microscopy publication-ready.",exact:true}).locator("video")).toHaveCount(0);
 await expect(page.getByLabel("解析の操作例",{exact:true})).toHaveCount(0);
 await page.getByRole("button",{name:"操作例を見る",exact:true}).click();
 const clip=page.getByLabel("解析の操作例",{exact:true});
 await expect(clip).toBeVisible();await expect(clip).toHaveJSProperty("paused",false);
 await page.getByRole("button",{name:"画面例に戻る",exact:true}).click();
 await expect(clip).toHaveCount(0);
 await expect(page.getByAltText(/^公開蛍光画像を読み込んだCytellect/)).toBeVisible();
});
