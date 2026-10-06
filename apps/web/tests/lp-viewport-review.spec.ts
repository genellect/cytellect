import {test,expect} from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
const dir=process.env.CYTELLECT_SCREENSHOT_DIR;
test.beforeEach(()=>{test.skip(process.env.CYTELLECT_EXPECT_UNCONFIGURED!=='1','Unconfigured public build only');});
test('first viewport includes hero actions and artwork across window sizes',async({page})=>{
 if(dir)fs.mkdirSync(dir,{recursive:true});await page.emulateMedia({reducedMotion:'reduce'});await page.goto('/product');await page.evaluate(()=>document.fonts.ready);
 for(const [width,height] of [[1440,900],[1366,768],[1280,600],[1024,768],[768,1024],[390,844],[390,667],[360,640],[320,568],[740,390],[844,390]]){
 await page.setViewportSize({width,height});await page.evaluate(()=>scrollTo(0,0));const hero=page.getByRole('region',{name:'Get your microscopy publication-ready.',exact:true});
 for(const locator of [hero,hero.getByRole('heading'),hero.getByRole('link',{name:'ダウンロード',exact:true}),hero.getByRole('link',{name:'解析例を見る',exact:true}),hero.getByAltText('青く照らされた細胞構造')]){const b=await locator.boundingBox();expect(b).not.toBeNull();expect(b!.y).toBeGreaterThanOrEqual(0);expect(b!.y+b!.height).toBeLessThanOrEqual(height+1);}
 if(width<=760){const composition=await hero.getByAltText('青く照らされた細胞構造').evaluate(img=>{const frame=img.closest('section')!.getBoundingClientRect();const image=img.getBoundingClientRect();return {fit:getComputedStyle(img).objectFit,top:image.top-frame.top,height:image.height-frame.height,width:image.width-frame.width};});expect(composition.fit).toBe('cover');expect(Math.abs(composition.top)).toBeLessThan(1);expect(Math.abs(composition.height)).toBeLessThan(1);expect(Math.abs(composition.width)).toBeLessThan(1);}
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);if(dir)await page.screenshot({path:path.join(dir,`hero-${width}x${height}.png`)});
 }
 await expect(page.getByText('© 2026 Yuto Matsui. All rights reserved.',{exact:true})).toBeVisible();
 for(const width of [1440,390]){await page.setViewportSize({width,height:900});const planning=page.getByAltText('測定の目的に対応する解析方法と必要な入力を確認する画面');await planning.scrollIntoViewIfNeeded();await expect.poll(()=>planning.evaluate((img:HTMLImageElement)=>img.complete&&img.naturalWidth>0)).toBe(true);expect(await planning.evaluate((img:HTMLImageElement)=>Math.abs(img.clientWidth/img.clientHeight-img.naturalWidth/img.naturalHeight))).toBeLessThan(.01);await expect(page.getByRole('link',{name:'解析設定の画面を拡大'})).toHaveAttribute('href','/marketing/planning-public.png');if(dir)await page.screenshot({path:path.join(dir,`planning-${width}.png`)});}
 if(dir){await page.locator('footer').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(dir,'footer-mobile.png')});}
});

test('complete cell remains framed in short desktop and tablet WebGL views',async({page})=>{
 await page.emulateMedia({reducedMotion:'no-preference'});
 for(const [width,height] of [[1280,600],[844,390],[768,1024]]){
  await page.setViewportSize({width,height});await page.goto('/product');const scene=page.getByTestId('hero-scene');await expect(scene).toHaveAttribute('data-state','ready');await page.getByRole('button',{name:'背景映像を停止',exact:true}).click();
  const canvas=scene.locator('canvas');const b=await canvas.boundingBox();expect(b!.y).toBeGreaterThanOrEqual(76);expect(b!.y+b!.height).toBeLessThanOrEqual(height+1);if(dir)await page.screenshot({path:path.join(dir,`hero-webgl-${width}x${height}.png`)});
 }
});
