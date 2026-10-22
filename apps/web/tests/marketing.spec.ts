import {test,expect} from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

test.beforeEach(()=>{test.skip(process.env.CYTELLECT_EXPECT_UNCONFIGURED!=="1","Unconfigured public build only");});
const heroName="Get your microscopy publication-ready.";

test("the LP leads with the product, keeps every viewport readable and routes into the demo",async({page})=>{
 const errors:string[]=[];page.on("pageerror",error=>errors.push(error.message));
 await page.emulateMedia({reducedMotion:"reduce"});
 await page.goto("/");
 const hero=page.getByRole("region",{name:heroName,exact:true});
 await expect(hero.getByRole("heading",{level:1})).toHaveText(heroName);
 await expect(hero.getByText("画像をアップロードするだけで、論文の図まで。",{exact:true})).toBeVisible();
 await expect(hero.getByRole("link",{name:"デモを触る",exact:true})).toHaveAttribute("href","/demo");
 await expect(hero.getByRole("link",{name:"ダウンロード",exact:true})).toHaveAttribute("href","#download");
 await expect(page.getByRole("banner").getByRole("link",{name:"デモを触る",exact:true})).toHaveAttribute("href","/demo");
 await expect(hero.locator("canvas")).toHaveCount(0);
 for(const [name,href] of [["検出をデモで見る","/demo?step=image"],["測定値と画像をデモで見る","/demo?step=image"],["統計をデモで見る","/demo?step=statistics"],["図をデモで見る","/demo?step=figure"]]){
  await expect(page.getByRole("link",{name,exact:true})).toHaveAttribute("href",href);
 }
 for(const name of ["核小体まで、自動で見える。","すべての数値が、元の画像につながる。","統計と論文の図まで、ひと続きで。","主張ではなく、検証した数字を。","やりたいことを書けば、解析の設定ができる。","研究データは、あなたの手元に。"]){
  await expect(page.getByRole("heading",{name,exact:true})).toBeVisible();
 }
 const numbers=page.getByRole("region",{name:"主張ではなく、検証した数字を。"});
 for(const value of ["90","0.92","817","482"])await expect(numbers.getByText(value,{exact:true})).toBeVisible();
 await expect(page.getByText("GFP陽性細胞の核小体の輝度を群間比較したい",{exact:true})).toBeVisible();
 await expect(page.getByRole("link",{name:"グラフを拡大",exact:true})).toHaveAttribute("href","/marketing/figure-public.svg");
 const dir=process.env.CYTELLECT_SCREENSHOT_DIR;if(dir)fs.mkdirSync(dir,{recursive:true});
 for(const [width,height] of [[1440,900],[1280,720],[820,1180],[390,844],[360,800]]){
  await page.setViewportSize({width,height});await page.evaluate(()=>scrollTo(0,0));
  await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await expect(hero.getByRole("heading")).toBeVisible();
  // Both primary actions sit in the first viewport.
  for(const name of ["デモを触る","ダウンロード"]){const box=(await hero.getByRole("link",{name,exact:true}).boundingBox())!;expect(box.y+box.height).toBeLessThanOrEqual(height);}
  expect(await page.locator("h1, h2").evaluateAll(nodes=>nodes.every(node=>{const box=node.getBoundingClientRect();return box.right<=innerWidth-8&&node.scrollWidth<=node.clientWidth+1;}))).toBe(true);
  if(dir){for(const img of await page.locator('main img[src^="/marketing/"]').all()){await img.scrollIntoViewIfNeeded();await expect.poll(()=>img.evaluate((node:HTMLImageElement)=>node.complete&&node.naturalWidth>0)).toBe(true);}await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:path.join(dir,`lp-${width}.png`),fullPage:true});if(width===1440||width===390)await page.screenshot({path:path.join(dir,`lp-hero-${width}.png`),fullPage:false});}
 }
 await page.setViewportSize({width:390,height:844});await page.evaluate(()=>scrollTo(0,0));
 const toggle=page.getByRole("button",{name:"メニューを開く",exact:true});await toggle.click();
 const nav=page.getByRole("navigation",{name:"モバイルナビゲーション"});
 await expect(nav.getByRole("link")).toHaveText(["プロダクト","使い方","ガイド","ダウンロード","About the Developer"]);
 await expect(nav.getByRole("link",{name:"About the Developer",exact:true})).toHaveAttribute("href","https://yuto-matsui.com/");
 await page.keyboard.press("Escape");await expect(toggle).toBeFocused();await expect(toggle).toHaveAttribute("aria-expanded","false");
 await toggle.click();await nav.getByRole("link",{name:"ガイド",exact:true}).click();await expect(toggle).toHaveAttribute("aria-expanded","false");
 await expect(page.getByRole("heading",{name:"使い方と解析方法",exact:true})).toBeInViewport();
 await expect(page.getByRole("contentinfo").getByRole("link",{name:/About the Developer/})).toHaveAttribute("href","https://yuto-matsui.com/");
 const images=page.locator('main img[src^="/marketing/"]');
 for(const img of await images.all()){await img.scrollIntoViewIfNeeded();await expect.poll(()=>img.evaluate((node:HTMLImageElement)=>node.complete&&node.naturalWidth>0)).toBe(true);}
 await page.getByRole("link",{name:"グラフを拡大",exact:true}).click();await expect(page).toHaveURL(/figure-public\.svg$/);await page.goBack();await expect(hero.getByRole("heading",{level:1})).toBeVisible();
 expect(errors).toEqual([]);
});

test("failed 3D asset leaves the poster and primary action available",async({page})=>{
 await page.emulateMedia({reducedMotion:"no-preference"});
 await page.route("**/marketing/optical-assembly.glb",route=>route.abort());
 await page.goto("/");
 await expect(page.getByTestId("hero-scene")).toHaveAttribute("data-state","error");
 const poster=page.getByAltText("光と透明な構造が広がる3D空間",{exact:true});
 await expect(poster).toBeVisible();
 await expect.poll(()=>poster.evaluate((node:HTMLImageElement)=>node.complete&&node.naturalWidth>0)).toBe(true);
 await expect(page.getByRole("region",{name:heroName,exact:true}).getByRole("link",{name:"デモを触る",exact:true})).toBeVisible();
 await expect(page.locator("canvas")).toHaveCount(0);
 await page.unroute("**/marketing/optical-assembly.glb");
 await page.route("**/marketing/optical-assembly.glb",async route=>{
  // Truncated GLB must keep the same usable fallback as an offline request.
  await route.fulfill({status:200,contentType:"model/gltf-binary",body:Buffer.from("glTF")});
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
 // Pause while scrolling on software WebGL runners; then verify live rendering
 // below the hero independently of the scroll action.
 await page.getByRole("button",{name:"背景映像を停止",exact:true}).click();
 const figure=page.getByAltText(/^公開画像の817領域/);await figure.scrollIntoViewIfNeeded();
 await page.getByRole("button",{name:"背景映像を再生",exact:true}).click();
 const belowHero=await rendered.getAttribute("data-render-count");await expect.poll(async()=>Number(await rendered.getAttribute("data-render-count"))).toBeGreaterThan(Number(belowHero));
 await page.emulateMedia({reducedMotion:"reduce"});await expect(scene.locator("canvas")).toHaveCount(0);
 expect(errors).toEqual([]);
});

// Playwright's Chromium has no H.264 decoder, so playback is simulated here; the
// component's own decisions (when to play, pause or fall back) are what is tested.
const simulatedPlayback=()=>{
 const states=new WeakMap<HTMLMediaElement,boolean>();
 Object.defineProperty(HTMLMediaElement.prototype,"paused",{configurable:true,get(){return states.get(this)??true;}});
 HTMLMediaElement.prototype.play=function(){states.set(this,false);this.dispatchEvent(new Event("playing"));return Promise.resolve();};
 HTMLMediaElement.prototype.pause=function(){if(states.get(this)===false){states.set(this,true);this.dispatchEvent(new Event("pause"));}};
};

test("the hero product video waits for the researcher under reduced motion and can always be paused",async({page})=>{
 await page.addInitScript(simulatedPlayback);
 // The 3D background is covered elsewhere; keep this case about the product clip.
 await page.route("**/marketing/optical-assembly.glb",route=>route.abort());
 await page.setViewportSize({width:1440,height:900});
 await page.emulateMedia({reducedMotion:"reduce"});await page.goto("/");
 const hero=page.getByRole("region",{name:heroName,exact:true});
 const clip=hero.locator("video");
 await expect(hero.getByRole("button",{name:"動画を再生",exact:true})).toBeVisible();
 await expect(clip).toHaveJSProperty("paused",true);
 await expect(clip).toHaveCSS("opacity","0");
 await hero.getByRole("button",{name:"動画を再生",exact:true}).click();
 await expect(clip).toHaveJSProperty("paused",false);
 await hero.getByRole("button",{name:"動画を停止",exact:true}).click();
 await expect(clip).toHaveJSProperty("paused",true);
 await expect(hero.getByRole("button",{name:"動画を再生",exact:true})).toBeVisible();
 // Without a motion preference, the clip plays on its own while on screen.
 await page.emulateMedia({reducedMotion:"no-preference"});await page.reload();
 await expect(hero.getByRole("button",{name:"動画を停止",exact:true})).toBeVisible();
 await expect(hero.locator("video")).toHaveJSProperty("paused",false);
 await hero.getByRole("button",{name:"動画を停止",exact:true}).click();
 await expect(hero.locator("video")).toHaveJSProperty("paused",true);
 // Phones keep the recorded still when the hero has one, and never start the video.
 if(await hero.locator("picture source").count()){
  await page.setViewportSize({width:390,height:844});await page.reload();
  await expect(hero.getByRole("button",{name:/動画を/})).toHaveCount(0);
  await expect(hero.locator("video")).toHaveJSProperty("paused",true);
  await expect.poll(()=>hero.locator("img").first().evaluate((node:HTMLImageElement)=>node.currentSrc)).toContain("-mobile");
 }
});

test("a failed product video leaves the still image in place",async({page})=>{
 await page.route("**/marketing/optical-assembly.glb",route=>route.abort());
 await page.route(/\/marketing\/.*\.mp4$/,route=>route.abort());
 await page.emulateMedia({reducedMotion:"no-preference"});
 await page.goto("/");
 const hero=page.getByRole("region",{name:heroName,exact:true});
 await expect(hero.locator("video")).toHaveCount(0);
 await expect(hero.getByRole("button",{name:/動画を/})).toHaveCount(0);
 const still=hero.getByRole("img");
 await expect(still).toBeVisible();
 expect(await still.evaluate((node:HTMLImageElement)=>node.complete&&node.naturalWidth>0)).toBe(true);
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
 // This case verifies the wordmark's animated scroll, not GPU throughput.
 // Real WebGL start/stop is exercised separately above.
 await page.route("**/marketing/optical-assembly.glb",route=>route.abort());
 await page.emulateMedia({reducedMotion:"no-preference"});
 await expect(page.getByTestId("hero-scene")).toHaveAttribute("data-state","error");
 await page.locator("#download").scrollIntoViewIfNeeded();
 await page.getByRole("link",{name:"Cytellect ホーム",exact:true}).click();
 await expect.poll(()=>page.evaluate(()=>scrollY)).toBe(0);
 expect(page.url()).toBe(previousUrl); expect(navigations).toBe(0);
});
