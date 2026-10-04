import {test,expect,type Page,type APIResponse} from "@playwright/test";
import {execFileSync} from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import {createRegionWorkspace,workspaceTestRuntime} from "./workspace-session";
import {expectGfpPreview} from "./image-preview";

const {api,python,dataDir}=workspaceTestRuntime();
const root=path.resolve(__dirname,"../../..");
const evidence=process.env.CYTELLECT_SCREENSHOT_DIR;
const header="x-cytellect-preview-display";
const csrf={Origin:api,"X-Cytellect-Request":"1"};
// The normal API origin differs from the UI origin; use the configured browser origin.
async function mutate(page:Page,url:string,options:Parameters<Page["request"]["post"]>[1]){
 return page.request.post(api+url,{...options,headers:{...csrf,Origin:new URL(page.url()).origin}});
}
async function json(response:APIResponse){expect(response.ok()).toBeTruthy();return response.json();}
async function job(page:Page,id:string){await expect.poll(async()=>{const value=await json(await page.request.get(`${api}/v1/jobs/${id}`));if(value.state==="failed")throw Error(value.error);return value.state;},{timeout:120000}).toBe("succeeded");}
async function shot(page:Page,name:string){if(evidence){fs.mkdirSync(evidence,{recursive:true});await page.screenshot({path:path.join(evidence,name),fullPage:true});}}
async function reopen(page:Page,title:string){await page.reload();await page.getByRole("button",{name:new RegExp(`^${title} 有効期限`)}).click();}
async function gain(page:Page,value:string){await page.getByRole("slider",{name:"表示ゲイン",exact:true}).evaluate((element,next)=>{const slider=element as HTMLInputElement;Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,"value")!.set!.call(slider,next);slider.dispatchEvent(new Event("input",{bubbles:true}));slider.dispatchEvent(new Event("change",{bubbles:true}));},value);}
function numericalInputs(){
 const folder=fs.mkdtempSync(path.join(dataDir||os.tmpdir(),"preview-numerical-"));
 execFileSync(python,["-c","import sys,numpy as np,tifffile;from pathlib import Path;p=Path(sys.argv[1]);a=np.full((128,128),100,np.uint16);a[32:96,32:96]=4100;a[50:70,50:70]=2100;lab=np.zeros_like(a,dtype=np.uint32);lab[40:80,40:80]=1;[(tifffile.imwrite(p/f'{i}-a.tif',a+i*1000),tifffile.imwrite(p/f'{i}-b.tif',np.full_like(a,4095 if i==0 else 0))) for i in range(2)];tifffile.imwrite(p/'labels.tif',lab)",folder]);
 return folder;
}
// Never retain URLs, query strings, identifiers, message text or response bodies.
function diagnosticRoute(raw:string){
 try{
  const url=new URL(raw);
  if(!["http:","https:"].includes(url.protocol))return "non_http";
  if(!["localhost","127.0.0.1"].includes(url.hostname))return "external";
  const pathname=url.pathname;
  if(pathname==="/v1/session")return "session";
  if(pathname.startsWith("/v1/local/"))return "local_setup_or_session";
  if(/^\/v1\/(region-)?fields\/[^/]+\/preview$/.test(pathname))return "image_preview";
  if(pathname.startsWith("/v1/workspaces"))return "workspace_api";
  if(pathname.startsWith("/v1/revisions"))return "revision_api";
  if(pathname.startsWith("/v1/jobs"))return "job_api";
  if(pathname.startsWith("/v1/"))return "other_api";
  if(pathname.startsWith("/_next/"))return "next_asset";
  if(/^\/plan(?:\/|\.txt|$)/.test(pathname))return "planning_static";
  if(/^\/favicon\.(?:ico|png|svg)$/.test(pathname))return "favicon";
  return "other_local_static";
 }catch{return "unknown";}
}
function diagnosticMessage(text:string){
 const react=/Minified React error #(\d{1,4})\b/.exec(text);
 const status=/\bstatus(?: code)?(?: of)?\s+([1-5]\d{2})\b/i.exec(text);
 return {code:react?"react_minified":/Content Security Policy|violates the following.*directive/i.test(text)?"content_security_policy":/Failed to (?:load resource|fetch)/i.test(text)?"resource_or_fetch_failed":"other",react_code:react?Number(react[1]):null,status:status?Number(status[1]):null};
}
function observe(page:Page){
 let bootstrapSeen=false;let injectedPreview:string|null=null;let injectedSeen=false;
 const diagnostics:unknown[]=[];let diagnosticCount=0;
 function record(value:unknown){diagnosticCount++;if(diagnostics.length<24)diagnostics.push(value);}
 const errors:string[]=[];page.on("pageerror",error=>{errors.push("pageerror");record({event:"pageerror",route:"unknown",...diagnosticMessage(error.message)});});
 page.on("console",message=>{
  if(message.type()!=="error")return;
  const source=message.location().url;
  if(!bootstrapSeen&&source===`${api}/v1/session`&&message.text().includes("status of 401")){bootstrapSeen=true;return;}
  if(!injectedSeen&&injectedPreview!==null&&source===injectedPreview&&message.text().includes("status of 503")){injectedSeen=true;return;}
  errors.push("console_error");
  record({event:"console_error",route:diagnosticRoute(source),...diagnosticMessage(message.text())});
 });
 page.on("response",response=>{if(response.status()>=400)record({event:"http_error",route:diagnosticRoute(response.url()),status:response.status()});});
 page.on("request",request=>{const url=new URL(request.url());if(["http:","https:"].includes(url.protocol)&&!["localhost","127.0.0.1"].includes(url.hostname))errors.push("external_request");});
 return {errors,injectPreviewFailure:(url:string)=>{expect(injectedPreview).toBeNull();injectedPreview=url;},verify:()=>{const context=JSON.stringify({safe_preview_diagnostics:diagnostics,total:diagnosticCount});expect(bootstrapSeen,context).toBe(true);expect(injectedSeen,context).toBe(injectedPreview!==null);expect(errors,context).toEqual([]);}};
}

test("display ranges follow decoded planes and gain without changing reviewed measurements",async({page})=>{
 const errors=observe(page);
 const space=await createRegionWorkspace(page,"表示範囲の数値検証");const folder=numericalInputs();const fields:{id:string}[]=[];
 for(let i=0;i<2;i++)fields.push(await json(await mutate(page,`/v1/workspaces/${space.id}/region-fields`,{multipart:{specification:JSON.stringify({channels:[{channel_id:"merge",label:"検証信号",identity_confirmed:true},{channel_id:"constant",label:"一定値",identity_confirmed:true}],metadata:{condition:`数値検証 ${i+1}`}}),ch0:{name:"a.tif",mimeType:"image/tiff",buffer:fs.readFileSync(path.join(folder,`${i}-a.tif`))},ch1:{name:"b.tif",mimeType:"image/tiff",buffer:fs.readFileSync(path.join(folder,`${i}-b.tif`))},labels:{name:"labels.tif",mimeType:"image/tiff",buffer:fs.readFileSync(path.join(folder,"labels.tif"))}}})));
 const queued=await json(await mutate(page,`/v1/workspaces/${space.id}/region-analyses`,{data:{recipe:{region_set_id:"regions",label:"数値検証の領域",source:"imported"},field_ids:fields.map(f=>f.id),backgrounds:Object.fromEntries(fields.map(f=>[f.id,Object.fromEntries(["merge","constant"].map(c=>[c,{polygon:[[0,0],[15,0],[15,15],[0,15]],confirmed:true}]))]))}}));await job(page,queued.job_id);
 await json(await mutate(page,`/v1/revisions/${queued.revision_id}/review`,{data:{}}));
 const report=await json(await page.request.get(`${api}/v1/revisions/${queued.revision_id}/measurements`));const revision=await json(await page.request.get(`${api}/v1/revisions/${queued.revision_id}`));
 await reopen(page,"表示範囲の数値検証");const range=page.getByRole("region",{name:"画像の表示範囲",exact:true});
 await expect(range).toContainText("表示下限 100 ／ 上限 4,100");await expectGfpPreview(page);
 await gain(page,"2");await expect(range).toContainText("表示下限 100 ／ 上限 2,100");await range.getByText("表示条件",{exact:true}).click();await expect(range).toContainText("保存画素の範囲100–4100");
 await shot(page,"preview-numerical-desktop.png");await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await shot(page,"preview-numerical-mobile.png");await page.setViewportSize({width:1440,height:1000});
 // A slower prior channel must not replace the newest channel's decoded image or range.
 let release!:()=>void;const held=new Promise<void>(resolve=>{release=resolve;});let intercepted=false;
 await page.route("**/region-fields/*/preview?**",async route=>{const u=new URL(route.request().url());if(u.searchParams.get("channel_id")==="constant"&&!intercepted){intercepted=true;const response=await route.fetch();await held;await route.fulfill({response});}else await route.continue();});
 await page.getByRole("button",{name:"背景",exact:true}).click();await page.getByRole("button",{name:"一定値",exact:true}).click();await expect.poll(()=>intercepted).toBe(true);await expect(range).toHaveCount(0);
 await page.locator('[data-testid="image-canvas"] canvas').first().click({position:{x:150,y:150}});await expect(page.getByRole("button",{name:"背景を確定 · 0 点",exact:true})).toBeDisabled();
 await page.getByRole("button",{name:"検証信号",exact:true}).click();await expect(range).toContainText("表示下限 100 ／ 上限 2,100");release();await page.unrouteAll({behavior:"wait"});await expect(range).toContainText("検証信号");await expect(range).not.toContainText("一定値");await page.getByRole("button",{name:"選択",exact:true}).click();
 await page.getByRole("button",{name:"一定値",exact:true}).click();await expect(range).toContainText("表示下限 4,095 ／ 上限 4,095.5");await range.getByText("表示条件",{exact:true}).click();await expect(range).toContainText("全画素が同じ値です");
 await page.getByRole("button").filter({has:page.getByText("数値検証 2",{exact:true})}).click();await expect(range).toContainText("表示下限 0 ／ 上限 0.5");
 // An old server can display pixels, but no range may be inferred from the PNG.
 await page.route("**/region-fields/*/preview?**",async route=>{const response=await route.fetch();const headers={...response.headers()};delete headers[header];await route.fulfill({response,headers});});
 await gain(page,"1.5");await expect(page.getByRole("status").filter({hasText:"表示範囲を確認できません"})).toBeVisible();await expect(range).toHaveCount(0);await expectGfpPreview(page);await page.unrouteAll({behavior:"wait"});
 await page.route("**/region-fields/*/preview?**",async route=>{const response=await route.fetch();await route.fulfill({response,headers:{...response.headers(),[header]:"{}"}});});
 await gain(page,"1.6");await expect(page.getByRole("status").filter({hasText:"画像と表示条件の対応を確認できませんでした"})).toBeVisible();await expect(range).toHaveCount(0);await expectGfpPreview(page);await page.unrouteAll({behavior:"wait"});
 let fail=true;await page.route("**/region-fields/*/preview?**",async route=>{if(fail){fail=false;errors.injectPreviewFailure(route.request().url());await route.fulfill({status:503,body:""});}else await route.continue();});
 await gain(page,"1");await expect(page.getByRole("alert").filter({hasText:"画像を読み込めませんでした"})).toBeVisible();await page.getByRole("button",{name:"再読み込み",exact:true}).click();await expect(range).toContainText("表示下限 0 ／ 上限 1");await page.unrouteAll({behavior:"wait"});
 let corrupt=true;await page.route("**/region-fields/*/preview?**",async route=>{if(corrupt){corrupt=false;const response=await route.fetch();await route.fulfill({response,body:"not a PNG"});}else await route.continue();});
 await gain(page,"2");await expect(page.getByRole("alert").filter({hasText:"画像を読み込めませんでした"})).toBeVisible();await expect(range).toHaveCount(0);await page.getByRole("button",{name:"再読み込み",exact:true}).click();await expect(range).toContainText("表示下限 0 ／ 上限 0.5");await page.unrouteAll({behavior:"wait"});
 expect(await json(await page.request.get(`${api}/v1/revisions/${queued.revision_id}/measurements`))).toEqual(report);expect(await json(await page.request.get(`${api}/v1/revisions/${queued.revision_id}`))).toEqual(revision);errors.verify();
});

test("published DRAQ and FKHR-EGFP composite shows actual per-plane ranges without a fabricated NCL component",async({page})=>{
 const errors=observe(page);const space=await createRegionWorkspace(page,"公開画像の表示確認");
 const fixtures=path.join(root,"fixtures/public/bbbc013");
 const bounds=JSON.parse(execFileSync(python,["-c","import sys,json,tifffile;from pathlib import Path;p=Path(sys.argv[1]);print(json.dumps({c:[int((a:=tifffile.imread(p/f'A01-{c}.tif')).min()),int(a.max())] for c in ['dapi','gfp']}))",fixtures],{encoding:"utf8"}));
 const field=await json(await mutate(page,`/v1/workspaces/${space.id}/fields`,{multipart:{metadata:JSON.stringify({condition:"公開入力の表示検証",experimental_unit:"UI fixture only",sample:"A01",acquisition_date:"not provided"}),dapi:{name:"nuclear.tif",mimeType:"image/tiff",buffer:fs.readFileSync(path.join(fixtures,"A01-dapi.tif"))},gfp:{name:"signal.tif",mimeType:"image/tiff",buffer:fs.readFileSync(path.join(fixtures,"A01-gfp.tif"))}}}));
 await reopen(page,"公開画像の表示確認");const range=page.getByRole("region",{name:"画像の表示範囲",exact:true});await expect(range).toContainText("核染色");await expect(range).toContainText("GFP");await expect(range).not.toContainText("NCL");await expectGfpPreview(page);
 const response=await page.request.get(`${api}/v1/fields/${field.id}/preview`);const display=JSON.parse(response.headers()[header]);expect(display.planes).toHaveLength(2);for(const plane of display.planes)expect([plane.source_min,plane.source_max]).toEqual(bounds[plane.channel_id]);
 await range.getByText("表示条件",{exact:true}).click();await shot(page,"preview-public-composite-desktop.png");await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await shot(page,"preview-public-composite-mobile.png");errors.verify();
 if(evidence)fs.writeFileSync(path.join(evidence,"preview-public-scope.json"),JSON.stringify({dataset:"BBBC013 A01",stains:["DRAQ","FKHR-EGFP"],scope:"Published 8-bit export preview and actual stored-value limits only; no biological comparison or segmentation claim.",bounds},null,2));
});
