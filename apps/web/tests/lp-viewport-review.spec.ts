import {test,expect} from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
const dir=process.env.CYTELLECT_SCREENSHOT_DIR;
test.beforeEach(()=>{test.skip(process.env.CYTELLECT_EXPECT_UNCONFIGURED!=='1','Unconfigured public build only');});
test('hero actions remain reachable and the film poster fills the hero in every viewport',async({page})=>{
 if(dir)fs.mkdirSync(dir,{recursive:true});await page.emulateMedia({reducedMotion:'reduce'});await page.goto('/');await page.evaluate(()=>document.fonts.ready);
 for(const [width,height] of [[1440,900],[1366,768],[1280,600],[1024,768],[768,1024],[390,844],[390,667],[360,640],[320,568],[740,390],[844,390]]){
 await page.setViewportSize({width,height});await page.evaluate(()=>scrollTo(0,0));const hero=page.getByRole('region',{name:'Get your microscopy publication-ready.',exact:true});
 const heroBox=(await hero.boundingBox())!;
 for(const locator of [hero.getByRole('heading'),hero.getByRole('link',{name:'ダウンロード',exact:true}),hero.getByRole('link',{name:'デモを触る',exact:true})]){const b=await locator.boundingBox();expect(b).not.toBeNull();expect(b!.y).toBeGreaterThanOrEqual(68);expect(b!.y+b!.height).toBeLessThanOrEqual(heroBox.height+1);if(height>=600)expect(b!.y+b!.height).toBeLessThanOrEqual(height+1);await locator.scrollIntoViewIfNeeded();await expect(locator).toBeInViewport();await page.evaluate(()=>scrollTo({top:0,behavior:'instant'}));}
 const composition=await page.getByTestId('hero-film').locator('img').evaluate((img,box)=>{const image=img.getBoundingClientRect();return {fit:getComputedStyle(img).objectFit,top:image.top,height:image.height-box.height,width:image.width-innerWidth};},heroBox);expect(composition.fit).toBe('cover');expect(Math.abs(composition.top)).toBeLessThan(1);expect(Math.abs(composition.height)).toBeLessThan(1);expect(Math.abs(composition.width)).toBeLessThan(1);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);if(dir)await page.screenshot({path:path.join(dir,`hero-${width}x${height}.png`)});
 }
 await expect(page.getByText('© 2026 Genellect Inc. All rights reserved.',{exact:true})).toBeVisible();
 for(const width of [1440,390]){await page.setViewportSize({width,height:900});const screen=page.getByAltText(/^Cytellectの公開デモ。/);await screen.scrollIntoViewIfNeeded();await expect.poll(()=>screen.evaluate((img:HTMLImageElement)=>img.complete&&img.naturalWidth>0)).toBe(true);expect(await screen.evaluate((img:HTMLImageElement)=>Math.abs(img.clientWidth/img.clientHeight-img.naturalWidth/img.naturalHeight))).toBeLessThan(.01);expect(await screen.evaluate((img:HTMLImageElement)=>img.getBoundingClientRect().right<=innerWidth)).toBe(true);if(dir)await page.screenshot({path:path.join(dir,`workspace-${width}.png`)});}
 if(dir){await page.locator('footer').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(dir,'footer-mobile.png')});}
});

test('the playing hero film covers short desktop and tablet heroes without overflow',async({page})=>{
 await page.emulateMedia({reducedMotion:'no-preference'});
 for(const [width,height] of [[1280,600],[844,390],[768,1024]]){
  await page.setViewportSize({width,height});await page.goto('/');const film=page.getByTestId('hero-film');await expect(film).toHaveAttribute('data-state','playing');await page.getByRole('button',{name:'背景映像を停止',exact:true}).click();
  const hero=(await page.getByRole('region',{name:'Get your microscopy publication-ready.',exact:true}).boundingBox())!;const b=(await film.locator('video').boundingBox())!;expect(Math.abs(b.y-hero.y)).toBeLessThan(1);expect(Math.abs(b.height-hero.height)).toBeLessThan(1);expect(Math.abs(b.width-width)).toBeLessThan(1);expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);if(dir)await page.screenshot({path:path.join(dir,`hero-film-${width}x${height}.png`)});
 }
});
