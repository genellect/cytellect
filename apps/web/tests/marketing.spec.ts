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
  for(const name of [/^Cytellectは、顕微鏡画像の解析から統計、/,/^画像解析や統計が専門でなくても、/,/^積み重ねた実験の成果を、/]){await expect(page.getByRole("heading",{name})).toBeVisible();}
  if(dir){for(const img of await page.locator('main img[src^="/marketing/"]').all()){await img.scrollIntoViewIfNeeded();await expect.poll(()=>img.evaluate((node:HTMLImageElement)=>node.complete&&node.naturalWidth>0)).toBe(true);}await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:path.join(dir,`lp-${width}.png`),fullPage:true});if(width===1440||width===390)await page.screenshot({path:path.join(dir,`lp-hero-${width}.png`),fullPage:false});}
 }
 await page.setViewportSize({width:390,height:844});await page.evaluate(()=>scrollTo(0,0));
 const toggle=page.getByRole("button",{name:"メニューを開く",exact:true});await toggle.click();
 const nav=page.getByRole("navigation",{name:"モバイルナビゲーション"});
 await expect(nav.getByRole("link")).toHaveText(["プロダクト","ガイド","About the Developer","ダウンロード ↓"]);
 await expect(nav.getByRole("link",{name:"About the Developer",exact:true})).toHaveAttribute("href","https://yuto-matsui.com/");
 await page.keyboard.press("Escape");await expect(toggle).toBeFocused();await expect(toggle).toHaveAttribute("aria-expanded","false");
 await toggle.click();await nav.getByRole("link",{name:"ガイド",exact:true}).click();await expect(toggle).toHaveAttribute("aria-expanded","false");
 await expect(page.getByRole("heading",{name:"使い方と解析方法",exact:true})).toBeVisible();
 const images=page.locator('main img[src^="/marketing/"]');
 for(const img of await images.all()){await img.scrollIntoViewIfNeeded();await expect.poll(()=>img.evaluate((node:HTMLImageElement)=>node.complete&&node.naturalWidth>0)).toBe(true);}
 await page.getByRole("link",{name:"グラフを拡大",exact:true}).click();await expect(page).toHaveURL(/figure-public\.svg$/);await page.goBack();await expect(hero.getByRole("heading",{level:1})).toBeVisible();
 expect(errors).toEqual([]);
});

test("a failed hero film leaves the poster and primary action available",async({page})=>{
 await page.emulateMedia({reducedMotion:"no-preference"});
 await page.route(/\/marketing\/hero-film\.(webm|mp4)$/,route=>route.abort());
 await page.goto("/");
 const film=page.getByTestId("hero-film");
 await expect(film).toHaveAttribute("data-state","error");
 const poster=film.locator("img");
 await expect(poster).toBeVisible();
 await expect.poll(()=>poster.evaluate((node:HTMLImageElement)=>node.complete&&node.naturalWidth>0)).toBe(true);
 await expect(film.locator("video")).toHaveCount(0);
 await expect(page.getByRole("button",{name:"背景映像を停止",exact:true})).toHaveCount(0);
 await expect(page.getByRole("region",{name:"Get your microscopy publication-ready.",exact:true}).getByRole("link",{name:"ダウンロード",exact:true})).toBeVisible();
});

test("a researcher can stop the hero film and keep it stopped after navigation",async({page})=>{
 const errors:string[]=[];page.on("pageerror",error=>errors.push(error.message));page.on("console",message=>{if(message.type()==="error")errors.push(message.text());});
 await page.setViewportSize({width:1440,height:900});
 await page.emulateMedia({reducedMotion:"no-preference"});
 await page.goto("/");
 const film=page.getByTestId("hero-film");const video=film.locator("video");
 await expect(film).toHaveAttribute("data-state","playing");
 await expect.poll(()=>video.evaluate((node:HTMLVideoElement)=>node.currentTime)).toBeGreaterThan(0.2);
 await page.getByRole("button",{name:"背景映像を停止",exact:true}).click();
 await expect(film).toHaveAttribute("data-paused","true");
 await expect(video).toHaveJSProperty("paused",true);
 const dir=process.env.CYTELLECT_SCREENSHOT_DIR;if(dir){fs.mkdirSync(dir,{recursive:true});await page.screenshot({path:path.join(dir,"lp-hero-film.png")});}
 await page.getByRole("link",{name:"プロダクト",exact:true}).click();
 await page.evaluate(()=>scrollTo(0,0));
 await expect(page.getByRole("button",{name:"背景映像を再生",exact:true})).toBeVisible();
 await expect(video).toHaveJSProperty("paused",true);
 await page.getByRole("button",{name:"背景映像を再生",exact:true}).click();
 await expect(video).toHaveJSProperty("paused",false);
 // The film stops while the hero is off screen and resumes when it returns.
 await page.locator("#download").scrollIntoViewIfNeeded();
 await expect(video).toHaveJSProperty("paused",true);
 await page.evaluate(()=>scrollTo(0,0));
 await expect(video).toHaveJSProperty("paused",false);
 await page.emulateMedia({reducedMotion:"reduce"});await expect(film.locator("video")).toHaveCount(0);await expect(film.locator("img")).toBeVisible();
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

test("the story for general readers opens in place and keeps its text", async ({page}) => {
 await page.emulateMedia({reducedMotion:"reduce"});
 await page.goto("/");
 const story = page.getByRole("region", { name: "Cytellectが生まれた理由" });
 await expect(story).toContainText("私たちの体は、約30兆個もの細胞から成り立っている。");
 const toggle = story.getByRole("button", { name: "続きを読む" });
 await expect(toggle).toHaveAttribute("aria-expanded", "false");
 await expect(story.getByText("次世代の研究者のためのアプリケーションである。")).not.toBeInViewport();
 await toggle.click();
 await expect(story.getByRole("button", { name: "閉じる" })).toHaveAttribute("aria-expanded", "true");
 // The complete text must become visible after the expansion, without a timer-owned inline height.
 await expect.poll(() => page.locator("#story-more").evaluate(element => element.clientHeight >= element.scrollHeight)).toBe(true);
 const closing = story.getByText("次世代の研究者のためのアプリケーションである。");
 await closing.scrollIntoViewIfNeeded();
 await expect(closing).toBeInViewport();
 expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test("the wordmark returns to the hero from anywhere on the page", async ({page}) => {
 await page.emulateMedia({reducedMotion:"reduce"});await page.goto("/");
 await page.locator("#download").scrollIntoViewIfNeeded();
 await expect.poll(()=>page.evaluate(()=>scrollY)).toBeGreaterThan(0);
 const previousUrl = page.url();
 let navigations = 0; page.on("framenavigated", () => navigations++);
 await page.getByRole("link",{name:"Cytellect ホーム",exact:true}).click();
 await expect.poll(()=>page.evaluate(()=>scrollY)).toBe(0);
 await expect(page.getByRole("heading",{level:1})).toBeInViewport();
 expect(page.url()).toBe(previousUrl); expect(navigations).toBe(0);
 // The animated scroll also runs while the hero film is allowed to play.
 await page.emulateMedia({reducedMotion:"no-preference"});
 await page.locator("#download").scrollIntoViewIfNeeded();
 await page.getByRole("link",{name:"Cytellect ホーム",exact:true}).click();
 await expect.poll(()=>page.evaluate(()=>scrollY)).toBe(0);
 expect(page.url()).toBe(previousUrl); expect(navigations).toBe(0);
});
