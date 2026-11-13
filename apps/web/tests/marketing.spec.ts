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
 await expect(hero.locator("figure")).toHaveCount(0);await expect(hero.getByRole("list")).toHaveCount(0);
 await expect(hero.locator("video")).toHaveCount(0);await expect(hero.locator("canvas")).toHaveCount(0);
 await expect(hero.getByRole("link",{name:"ダウンロード",exact:true})).toHaveAttribute("href","#download");
 await expect(hero.getByRole("link",{name:"デモを体験する",exact:true})).toHaveAttribute("href","/demo");
 await expect(hero.getByRole("button",{name:/領域/})).toHaveCount(0);
 // What Cytellect does is one list that is both the switch and the content: detection and measurement open first,
 // and each feature names itself and says in a line what is behind it. Without the 3D space (reduced motion here)
 // the open feature shows its demo captures as glass plates and opens the same demo screen.
 const experience=page.locator("#workflow");
 await expect(experience).toHaveAttribute("data-mode","plates");
 await expect(page.getByRole("tab")).toHaveCount(0);
 const features=page.getByRole("list",{name:"Cytellectでできること",exact:true});
 const heads=features.locator(":scope > li > button");
 await expect(heads.locator("b")).toHaveText(["検出と測定","要約と考察","AIによる設定","統計と論文の図"]);
 await expect(heads.nth(1)).toContainText("結論の一文と、考察まで");
 await expect(heads.nth(0)).toHaveAttribute("aria-expanded","true");
 await expect(page.getByRole("region",{name:/検出と測定/}).getByAltText(/^核ごとの表。/)).toBeVisible();
 const scenes:{id:string;workspaceId:string}[]=(await (await page.request.get("/showcase/snapshot/scenes.json")).json()).scenes;
 const scene=(id:string,step:string)=>`/demo?id=${scenes.find(item=>item.id===id)!.workspaceId}&step=${step}`;
 const plk1="cpg0016-jump-source13-plk1",oxaliplatin="zenodo-6643470-oxaliplatin";
 for(const [index,name,title,link,href,images] of [[1,"要約と考察",/^結果を読み解く時間を、/,"この結果をデモで開く",scene(plk1,"statistics"),3],[2,"AIによる設定",/^やりたいことを一文で。/,"デモで指示する",scene(plk1,"statistics"),2],[3,"統計と論文の図",/^統計の検定も、論文に載せる図も、/,"この図をデモで開く",scene(plk1,"figure"),3],[0,"検出と測定",/^測りたい値が、/,"この表をデモで開く",scene(oxaliplatin,"image"),1]] as const){
  await heads.nth(index).click();
  await expect(heads.nth(index)).toHaveAttribute("aria-expanded","true");
  await expect(features.locator('[aria-expanded="true"]')).toHaveCount(1);
  const region=page.getByRole("region",{name:new RegExp(name)});
  await expect(region.getByRole("heading",{name:title})).toBeVisible();
  await expect(region.getByRole("link",{name:link,exact:true})).toHaveAttribute("href",href);
  await expect(region.locator('figure img[src^="/marketing/lp-"]')).toHaveCount(images);
 }
 // Measurements are not tied to one structure; the nucleolus figures stand without a heading.
 await expect(page.getByRole("region",{name:/検出と測定/}).getByRole("list",{name:"測れる値",exact:true}).getByRole("listitem")).toHaveCount(6);
 await expect(page.getByText("一例：核小体の研究")).toHaveCount(0);
 // The latter half runs from research to the patients waiting, then invites to the demo before the reference material.
 const impact=page.getByRole("region",{name:"研究の先に、待っている患者さんがいる。",exact:true});
 const impactSteps=impact.getByRole("list",{name:"研究から患者さんまで",exact:true}).getByRole("listitem");
 await expect(impactSteps.locator("b")).toHaveText(["病気のしくみを解き明かす","新しい薬の可能性を見つける","患者へ届ける"]);
 expect(await page.locator("main > :is(section,figure)").evaluateAll(nodes=>nodes.slice(-3).map(node=>node.id))).toEqual(["impact","start","download"]);
 const invite=page.getByRole("region",{name:"その未来を、あなたの研究から。",exact:true});
 await expect(invite.getByRole("link",{name:"デモを体験する",exact:true})).toHaveAttribute("href","/demo");
 await expect(invite.getByRole("link",{name:"Windows版（無料）",exact:true})).toHaveAttribute("href","#download");
 const dir=process.env.CYTELLECT_SCREENSHOT_DIR;if(dir)fs.mkdirSync(dir,{recursive:true});
 for(const [width,height] of [[1440,900],[1280,800],[768,1024],[390,844],[360,800]]){
  await page.setViewportSize({width,height});
  await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  const stepBoxes=await impactSteps.evaluateAll(nodes=>nodes.map(node=>{const {x,y,right}=node.getBoundingClientRect();return {x,y,right};}));
  expect(stepBoxes.every(box=>box.x>=0&&box.right<=width)).toBe(true);
  for(let i=1;i<stepBoxes.length;i++){
   if(width>760){expect(stepBoxes[i].x).toBeGreaterThan(stepBoxes[i-1].x);expect(stepBoxes[i].y).toBe(stepBoxes[0].y);}
   else{expect(stepBoxes[i].y).toBeGreaterThan(stepBoxes[i-1].y);expect(stepBoxes[i].x).toBe(stepBoxes[0].x);}
  }
  await expect(hero.getByRole("heading")).toBeVisible();
  expect(await hero.locator("h1 span").evaluateAll(nodes=>nodes.every(node=>node.getBoundingClientRect().right<=innerWidth-16&&node.scrollWidth<=node.clientWidth))).toBe(true);
  expect(await page.locator("h2 span").evaluateAll(nodes=>nodes.every(node=>node.getBoundingClientRect().right<=innerWidth-16&&node.scrollWidth<=node.clientWidth))).toBe(true);
  for(const name of [/^画像解析を、一部の専門家の技術から、/,/^手作業で数週間かかっていた解析を、/,/^研究の先に、待っている患者さんがいる。$/,/^その未来を、あなたの研究から。$/,/^まず、あなたのPCで。そして、研究室へ。$/]){await expect(page.getByRole("heading",{name})).toBeVisible();}
  if(dir){for(const img of await page.locator('main img[src^="/marketing/"]').filter({visible:true}).all()){await img.scrollIntoViewIfNeeded();await expect.poll(()=>img.evaluate((node:HTMLImageElement)=>node.complete&&node.naturalWidth>0)).toBe(true);}await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:path.join(dir,`lp-${width}.png`),fullPage:true});if(width===1440||width===390)await page.screenshot({path:path.join(dir,`lp-hero-${width}.png`),fullPage:false});}
 }
 await page.setViewportSize({width:390,height:844});await page.evaluate(()=>scrollTo(0,0));
 const toggle=page.getByRole("button",{name:"メニューを開く",exact:true});await toggle.click();
 const nav=page.getByRole("navigation",{name:"モバイルナビゲーション"});
 await expect(nav.getByRole("link")).toHaveText(["プロダクト","ガイド","About the Developer","ダウンロード","デモを体験 →"]);
 await expect(nav.getByRole("link",{name:"About the Developer",exact:true})).toHaveAttribute("href","https://yuto-matsui.com/");
 await page.keyboard.press("Escape");await expect(toggle).toBeFocused();await expect(toggle).toHaveAttribute("aria-expanded","false");
 await toggle.click();await nav.getByRole("link",{name:"ガイド",exact:true}).click();await expect(toggle).toHaveAttribute("aria-expanded","false");
 await expect(page.getByRole("heading",{name:"よくある質問",exact:true})).toBeInViewport();
 const images=page.locator('main img[src^="/marketing/"]').filter({visible:true});
 for(const img of await images.all()){await img.scrollIntoViewIfNeeded();await expect.poll(()=>img.evaluate((node:HTMLImageElement)=>node.complete&&node.naturalWidth>0)).toBe(true);}
 // The wide table scrolls inside its own frame on a phone; the page itself never scrolls sideways.
 const table=page.getByAltText(/^核ごとの表。/);await table.scrollIntoViewIfNeeded();
 expect(await table.evaluate((img:HTMLImageElement)=>img.clientWidth>img.parentElement!.clientWidth)).toBe(true);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 expect(errors).toEqual([]);
});

test("on a wide screen the tabs sit beside one 3D space of the demo's screens",async({page})=>{
 const errors:string[]=[];page.on("pageerror",error=>errors.push(error.message));
 await page.setViewportSize({width:1440,height:900});await page.emulateMedia({reducedMotion:"no-preference"});
 await page.goto("/");
 test.skip(!(await page.evaluate(()=>!!document.createElement("canvas").getContext("webgl2"))),"No WebGL 2 in this browser");
 const experience=page.locator("#workflow");
 await expect(experience).toHaveAttribute("data-mode","space");
 await expect(experience.locator("canvas")).toHaveCount(1);
 // The whole tour fits in one screen: the section does not grow with the number of features.
 expect(await experience.evaluate(node=>node.getBoundingClientRect().height)).toBeLessThan(900*1.9);
 const features=page.getByRole("list",{name:"Cytellectでできること",exact:true});
 const heads=features.locator(":scope > li > button");
 // The tour plays by itself while it is on screen: the open feature fills its line and the next one opens.
 await features.scrollIntoViewIfNeeded();await page.mouse.move(2,2);
 await expect(heads.nth(0)).toHaveAttribute("aria-expanded","true");
 await expect(heads.nth(1)).toHaveAttribute("aria-expanded","true",{timeout:15000});
 // Choosing a feature stops it.
 await heads.nth(3).click();
 await expect(features.locator("span[data-running]")).toHaveCount(0);
 const panel=page.getByRole("region",{name:/統計と論文の図/});
 await expect(panel.getByRole("link",{name:"この図をデモで開く",exact:true})).toBeVisible();
 // The plates stay in the page for assistive technology, drawn by the 3D space instead.
 await expect(panel.getByAltText(/^グラフの設定。幅/)).toHaveCount(1);
 await page.emulateMedia({reducedMotion:"reduce"});
 await expect(experience).toHaveAttribute("data-mode","plates");await expect(experience.locator("canvas")).toHaveCount(0);
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
test("the landing page carries no long story, on the page or behind a link", async ({page}) => {
 await page.goto("/");
 await expect(page.getByRole("region", { name: "Cytellectが生まれた理由" })).toHaveCount(0);
 await expect(page.getByText("Cytellectが生まれた理由")).toHaveCount(0);
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
 await expect(credits.getByRole("link")).toHaveCount(9);
 await expect(credits.getByRole("link",{name:"JUMP Cell Painting Consortium / Cell Painting Gallery",exact:true})).toHaveAttribute("href","https://github.com/broadinstitute/cellpainting-gallery");
 await expect(credits.getByRole("link",{name:"CC0 1.0",exact:true})).toHaveAttribute("href","https://creativecommons.org/publicdomain/zero/1.0/deed.ja");
 await expect(credits.getByRole("link",{name:"Schmidt HB, Rohatgi R, Brandman O (2022) / Zenodo",exact:true})).toHaveAttribute("href","https://doi.org/10.5281/zenodo.6643470");
 await expect(credits.getByRole("link",{name:"CC BY 4.0",exact:true})).toHaveAttribute("href","https://creativecommons.org/licenses/by/4.0/deed.ja");
 expect(await credits.getByRole("link").evaluateAll(links=>links.every(link=>/^https:\/\/(www\.pexels\.com|unsplash\.com|doi\.org|creativecommons\.org|github\.com\/broadinstitute)\//.test((link as HTMLAnchorElement).href)&&(link as HTMLAnchorElement).rel.includes("noopener")))).toBe(true);
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
