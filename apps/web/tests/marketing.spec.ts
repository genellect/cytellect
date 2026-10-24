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
 await expect(hero.getByRole("link",{name:"デモを体験する",exact:true})).toHaveAttribute("href","/demo");
 await expect(hero.getByRole("button",{name:/領域/})).toHaveCount(0);
 // What Cytellect does is split into tabs; each opens the matching step of the public demo.
 const features=page.getByRole("tablist",{name:"Cytellectでできること",exact:true});
 await expect(features.getByRole("tab")).toHaveText(["解析の流れ","自動検出","AIによる設定","統計と論文の図"]);
 for(const [tab,title,link,href] of [["自動検出",/^汎用のAIでは見つからない構造も、/,"この画像をデモで解析する","/demo?step=image"],["AIによる設定",/^やりたいことを一文で。/,"デモを体験する","/demo"],["統計と論文の図",/^統計の検定も、論文に載せる図も、/,"デモを体験する","/demo"],["解析の流れ",/^画像を入れるだけ。/,"デモで操作する","/demo"]] as const){
  await features.getByRole("tab",{name:tab,exact:true}).click();
  const panel=page.getByRole("tabpanel",{name:tab,exact:true});
  await expect(panel.getByRole("heading",{name:title})).toBeVisible();
  await expect(panel.getByRole("link",{name:link,exact:true})).toHaveAttribute("href",href);
  await expect(page.getByRole("tabpanel")).toHaveCount(1);
 }
 await features.getByRole("tab",{name:"解析の流れ",exact:true}).press("ArrowLeft");
 await expect(features.getByRole("tab",{name:"統計と論文の図",exact:true})).toBeFocused();
 await expect(features.getByRole("tab",{name:"統計と論文の図",exact:true})).toHaveAttribute("aria-selected","true");
 await expect(page.getByRole("link",{name:"図を拡大",exact:true})).toHaveAttribute("href","/marketing/lp-figure.svg");
 // The latter half runs from research to the patients waiting, then invites to the demo before the reference material.
 await expect(page.getByRole("list",{name:"研究から患者さんまで",exact:true}).getByRole("listitem").locator("b")).toHaveText(["測る","解き明かす","見つける","届ける"]);
 expect(await page.locator("main > :is(section,figure)").evaluateAll(nodes=>nodes.slice(-3).map(node=>node.id))).toEqual(["impact","start","download"]);
 const invite=page.getByRole("region",{name:"その未来を、あなたの研究から。",exact:true});
 await expect(invite.getByRole("link",{name:"デモを体験する",exact:true})).toHaveAttribute("href","/demo");
 await expect(invite.getByRole("link",{name:"Windows版（無料）",exact:true})).toHaveAttribute("href","#download");
 const dir=process.env.CYTELLECT_SCREENSHOT_DIR;if(dir)fs.mkdirSync(dir,{recursive:true});
 for(const [width,height] of [[1440,900],[1280,800],[768,1024],[390,844],[360,800]]){
  await page.setViewportSize({width,height});
  await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await expect(hero.getByRole("heading")).toBeVisible();
  expect(await hero.locator("h1 span").evaluateAll(nodes=>nodes.every(node=>node.getBoundingClientRect().right<=innerWidth-16&&node.scrollWidth<=node.clientWidth))).toBe(true);
  expect(await page.locator("h2 span").evaluateAll(nodes=>nodes.every(node=>node.getBoundingClientRect().right<=innerWidth-16&&node.scrollWidth<=node.clientWidth))).toBe(true);
  for(const name of [/^画像解析を、一部の専門家の技術から、/,/^手作業で数週間かかっていた解析を、/,/^研究の先に、待っている患者さんがいる。$/,/^その未来を、あなたの研究から。$/,/^Windows版は無料。測定も保存も、/]){await expect(page.getByRole("heading",{name})).toBeVisible();}
  if(dir){for(const img of await page.locator('main img[src^="/marketing/"]').filter({visible:true}).all()){await img.scrollIntoViewIfNeeded();await expect.poll(()=>img.evaluate((node:HTMLImageElement)=>node.complete&&node.naturalWidth>0)).toBe(true);}await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:path.join(dir,`lp-${width}.png`),fullPage:true});if(width===1440||width===390)await page.screenshot({path:path.join(dir,`lp-hero-${width}.png`),fullPage:false});}
 }
 await page.setViewportSize({width:390,height:844});await page.evaluate(()=>scrollTo(0,0));
 const toggle=page.getByRole("button",{name:"メニューを開く",exact:true});await toggle.click();
 const nav=page.getByRole("navigation",{name:"モバイルナビゲーション"});
 await expect(nav.getByRole("link")).toHaveText(["プロダクト","ガイド","About the Developer","ダウンロード","デモを体験 →"]);
 await expect(nav.getByRole("link",{name:"About the Developer",exact:true})).toHaveAttribute("href","https://yuto-matsui.com/");
 await page.keyboard.press("Escape");await expect(toggle).toBeFocused();await expect(toggle).toHaveAttribute("aria-expanded","false");
 await toggle.click();await nav.getByRole("link",{name:"ガイド",exact:true}).click();await expect(toggle).toHaveAttribute("aria-expanded","false");
 await expect(page.getByRole("navigation",{name:"使い方と解析方法",exact:true})).toBeInViewport();
 const images=page.locator('main img[src^="/marketing/"]').filter({visible:true});
 for(const img of await images.all()){await img.scrollIntoViewIfNeeded();await expect.poll(()=>img.evaluate((node:HTMLImageElement)=>node.complete&&node.naturalWidth>0)).toBe(true);}
 await page.getByRole("link",{name:"図を拡大",exact:true}).click();await expect(page).toHaveURL(/lp-figure\.svg$/);await page.goBack();await expect(hero.getByRole("heading",{level:1})).toBeVisible();
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
test("the story for general readers opens in place and keeps its text", async ({page}) => {
 await page.emulateMedia({reducedMotion:"reduce"});
 await page.goto("/");
 const story = page.getByRole("region", { name: "Cytellectが生まれた理由" });
 await expect(story).toContainText("私たちの体は、約30兆個もの細胞から成り立っている。");
 const toggle = story.getByRole("button", { name: "Cytellectが生まれた理由を読む" });
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

test("the mission statement sets in two balanced lines on desktop",async({page})=>{
 await page.setViewportSize({width:1440,height:900});await page.goto("/");
 const mission=page.getByRole("heading",{name:"画像解析を、一部の専門家の技術から、すべての生命科学研究者が使える研究基盤に。",exact:true});
 expect(await mission.evaluate(node=>Math.round(node.getBoundingClientRect().height/parseFloat(getComputedStyle(node).lineHeight)))).toBe(2);
});

test("the footer credits every image and video at its source and has no security link",async({page})=>{
 await page.goto("/");
 const footer=page.getByRole("contentinfo");
 await expect(footer.getByRole("link",{name:/セキュリティ/})).toHaveCount(0);
 await expect(footer.getByRole("link",{name:/provenance|出典/})).toHaveCount(0);
 const credits=footer.locator("details");
 await expect(credits).not.toHaveAttribute("open");
 await credits.getByText("画像・映像の出典",{exact:true}).click();
 await expect(credits.getByRole("link")).toHaveCount(7);
 await expect(credits.getByRole("link",{name:"Schmidt HB, Rohatgi R, Brandman O (2022) / Zenodo",exact:true})).toHaveAttribute("href","https://doi.org/10.5281/zenodo.6643470");
 await expect(credits.getByRole("link",{name:"CC BY 4.0",exact:true})).toHaveAttribute("href","https://creativecommons.org/licenses/by/4.0/deed.ja");
 expect(await credits.getByRole("link").evaluateAll(links=>links.every(link=>/^https:\/\/(www\.pexels\.com|unsplash\.com|doi\.org|creativecommons\.org)\//.test((link as HTMLAnchorElement).href)&&(link as HTMLAnchorElement).rel.includes("noopener")))).toBe(true);
});

test("on phones the demo stays one tap away through the latter half and steps aside for the invitation",async({page})=>{
 await page.emulateMedia({reducedMotion:"reduce"});
 await page.setViewportSize({width:390,height:844});await page.goto("/");
 const bar=page.getByTestId("demo-bar");
 await page.locator("#workflow").scrollIntoViewIfNeeded();
 await expect(bar).toHaveAttribute("data-shown","false");
 await page.locator("#guide").scrollIntoViewIfNeeded();
 await expect(bar).toHaveAttribute("data-shown","true");
 await expect(bar.locator("a")).toHaveAttribute("href","/demo");
 await page.locator("#start").scrollIntoViewIfNeeded();
 await expect(bar).toHaveAttribute("data-shown","false");
 await page.setViewportSize({width:1440,height:900});
 await expect(bar).toBeHidden();
});
