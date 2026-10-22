import {test,expect} from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
const dir=process.env.CYTELLECT_SCREENSHOT_DIR;
test.beforeEach(()=>{test.skip(process.env.CYTELLECT_EXPECT_UNCONFIGURED!=='1','Unconfigured public build only');});
test('hero actions remain reachable and the optical background fills every viewport',async({page})=>{
 if(dir)fs.mkdirSync(dir,{recursive:true});await page.emulateMedia({reducedMotion:'reduce'});await page.goto('/');await page.evaluate(()=>document.fonts.ready);
 for(const [width,height] of [[1440,900],[1366,768],[1280,600],[1024,768],[768,1024],[390,844],[390,667],[360,640],[320,568],[740,390],[844,390]]){
 await page.setViewportSize({width,height});await page.evaluate(()=>scrollTo(0,0));const hero=page.getByRole('region',{name:'Get your microscopy publication-ready.',exact:true});
 const heroBox=(await hero.boundingBox())!;
 for(const locator of [hero.getByRole('heading'),hero.getByRole('link',{name:'デモを触る',exact:true}),hero.getByRole('link',{name:'ダウンロード',exact:true})]){const b=await locator.boundingBox();expect(b).not.toBeNull();expect(b!.y).toBeGreaterThanOrEqual(68);expect(b!.y+b!.height).toBeLessThanOrEqual(heroBox.height+1);if(height>=600)expect(b!.y+b!.height).toBeLessThanOrEqual(height+1);await locator.scrollIntoViewIfNeeded();await expect(locator).toBeInViewport();await page.evaluate(()=>scrollTo({top:0,behavior:'instant'}));}
 const composition=await page.getByAltText('光と透明な構造が広がる3D空間').evaluate(img=>{const image=img.getBoundingClientRect();return {fit:getComputedStyle(img).objectFit,top:image.top,height:image.height-innerHeight,width:image.width-innerWidth};});expect(composition.fit).toBe('cover');expect(Math.abs(composition.top)).toBeLessThan(1);expect(Math.abs(composition.height)).toBeLessThan(1);expect(Math.abs(composition.width)).toBeLessThan(1);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);if(dir)await page.screenshot({path:path.join(dir,`hero-${width}x${height}.png`)});
 }
 await expect(page.getByText('© 2026 Yuto Matsui. All rights reserved.',{exact:true})).toBeVisible();
 for(const width of [1440,390]){await page.setViewportSize({width,height:900});const planning=page.getByAltText('公開画像3視野の核の平均輝度を、視野ごとの分布と集計表で示した統計画面');await planning.scrollIntoViewIfNeeded();await expect.poll(()=>planning.evaluate((img:HTMLImageElement)=>img.complete&&img.naturalWidth>0)).toBe(true);expect(await planning.evaluate((img:HTMLImageElement)=>Math.abs(img.clientWidth/img.clientHeight-img.naturalWidth/img.naturalHeight))).toBeLessThan(.01);await expect(page.getByRole('link',{name:'統計画面を拡大'})).toHaveAttribute('href','/marketing/planning-public.png');if(dir)await page.screenshot({path:path.join(dir,`planning-${width}.png`)});}
 if(dir){await page.locator('footer').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(dir,'footer-mobile.png')});}
});

test('optical WebGL covers short desktop and tablet views without overflow',async({page})=>{
 await page.emulateMedia({reducedMotion:'no-preference'});
 for(const [width,height] of [[1280,600],[844,390],[768,1024]]){
  await page.setViewportSize({width,height});await page.goto('/');const scene=page.getByTestId('hero-scene');await expect(scene).toHaveAttribute('data-state','ready');await page.getByRole('button',{name:'背景映像を停止',exact:true}).click();
  const canvas=scene.locator('canvas');const b=await canvas.boundingBox();expect(Math.abs(b!.y)).toBeLessThan(1);expect(Math.abs(b!.height-height)).toBeLessThan(1);expect(Math.abs(b!.width-width)).toBeLessThan(1);expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);if(dir)await page.screenshot({path:path.join(dir,`hero-webgl-${width}x${height}.png`)});
 }
});
