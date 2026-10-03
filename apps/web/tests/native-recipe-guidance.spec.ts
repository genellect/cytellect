import {test,expect,type Page,type APIResponse} from "@playwright/test";
import {execFileSync} from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import {createRegionWorkspace,workspaceTestRuntime} from "./workspace-session";
import {expectGfpPreview} from "./image-preview";

const {api,python,dataDir}=workspaceTestRuntime();
const root=path.resolve(__dirname,"../../..");
const evidence=process.env.CYTELLECT_SCREENSHOT_DIR;
async function json(response:Pick<APIResponse,"ok"|"json">){expect(response.ok()).toBe(true);return response.json();}
async function post(page:Page,url:string,options:Parameters<Page["request"]["post"]>[1]){
 return page.request.post(api+url,{...options,headers:{Origin:new URL(page.url()).origin,"X-Cytellect-Request":"1"}});
}
async function mutation(page:Page,suffix:string,action:()=>Promise<void>){const response=page.waitForResponse(r=>new URL(r.url()).pathname.endsWith(suffix)&&r.request().method()==="POST");await action();return json(await response);}
async function job(page:Page,id:string){await expect.poll(async()=>{const result=await json(await page.request.get(`${api}/v1/jobs/${id}`));if(["failed","cancelled"].includes(result.state))throw Error(result.error||result.state);return result.state;},{timeout:600000,intervals:[1000,2000]}).toBe("succeeded");}
async function reopen(page:Page,title:string){await page.reload();await page.getByRole("button",{name:new RegExp(`^${title} 有効期限`)}).click();}
async function background(page:Page){
 await page.getByRole("button",{name:"背景ROI",exact:true}).click();
 const details=page.locator("details").filter({has:page.locator("summary",{hasText:"座標から多角形を指定"})});
 if(!await details.evaluate(el=>(el as HTMLDetailsElement).open))await details.locator("summary").click();
 await page.getByLabel("頂点（x,y を空白または改行で区切る）").fill("1,1 4,1 4,4 1,4");
 await page.getByRole("button",{name:"座標を反映",exact:true}).click();
 await page.getByRole("button",{name:"背景を確定 · 4 点",exact:true}).click();
}
async function field(page:Page,condition:string){await page.getByRole("button").filter({has:page.getByText(condition,{exact:true})}).click();}
async function shot(page:Page,name:string){if(evidence){fs.mkdirSync(evidence,{recursive:true});await page.screenshot({path:path.join(evidence,name),fullPage:true});}}
async function upload(page:Page,wid:string,condition:string,files:Record<string,string>){
 return json(await post(page,`/v1/workspaces/${wid}/fields`,{multipart:{metadata:JSON.stringify({condition,experimental_unit:"UI fixture only",sample:condition,acquisition_date:"numerical interface check"}),...Object.fromEntries(Object.entries(files).map(([role,file])=>[role,{name:"unrelated-name.tif",mimeType:"image/tiff",buffer:fs.readFileSync(file)}]))}}));
}

test("reopened public GFP inputs require an explicit compatible recipe and preserve saved results",async({page})=>{
 const errors:string[]=[];page.on("pageerror",()=>errors.push("pageerror"));
 const title="公開GFP入力とレシピの確認";const workspace=await createRegionWorkspace(page,title);
 const fixture=path.join(root,"fixtures/public/bbbc013");
 const registered=await upload(page,workspace.id,"公開DRAQ・FKHR-EGFP",{dapi:path.join(fixture,"A01-dapi.tif"),gfp:path.join(fixture,"A01-gfp.tif")});
 expect(registered.image_info.channel_roles).toEqual(["dapi","gfp"]);
 await reopen(page,title);await expectGfpPreview(page);
 const recipe=page.getByLabel("レシピ",{exact:true});const trial=page.getByRole("button",{name:"この視野で試す",exact:true});const batch=page.getByRole("button",{name:"条件を固定して全視野を解析",exact:true});
 await expect(recipe).toHaveValue("ncl-native-2d");
 await expect(page.getByRole("status",{name:"選択視野のレシピ適合",exact:true})).toContainText("NCLが未取得");
 await expect(page.getByRole("status",{name:"選択視野のレシピ適合",exact:true})).toContainText("GFP · 核内輝度");
 let submissions=0;page.on("request",request=>{if(request.method()==="POST"&&new URL(request.url()).pathname.endsWith("/analyses"))submissions++;});
 await background(page);await expect(trial).toBeDisabled();await expect(batch).toBeDisabled();expect(submissions).toBe(0);
 await shot(page,"native-recipe-missing-ncl-desktop.png");await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await shot(page,"native-recipe-missing-ncl-mobile.png");await page.setViewportSize({width:1440,height:1000});
 await recipe.selectOption("gfp-nuclear-2d");await expect(trial).toBeEnabled();
 const queued=await mutation(page,"/analyses",()=>trial.click());await job(page,queued.job_id);
 const saved=await json(await page.request.get(`${api}/v1/revisions/${queued.revision_id}`));const measured=await json(await page.request.get(`${api}/v1/revisions/${queued.revision_id}/measurements`));
 expect(saved.config.recipe.id).toBe("gfp-nuclear-2d");expect(saved.config.field_ids).toEqual([registered.id]);expect(measured.cells.length).toBeGreaterThan(0);expect(measured.nucleoli).toEqual([]);
 await expect(page.getByRole("button",{name:"現在のマスクで条件を更新",exact:true})).toBeVisible();
 await recipe.selectOption("ncl-native-2d");await expect(trial).toBeDisabled();await expect(batch).toBeDisabled();await expect(page.getByRole("button",{name:"現在のマスクで条件を更新",exact:true})).toBeDisabled();await expect(page.getByRole("button",{name:/^核小体候補を再検出/})).toBeDisabled();
 expect(submissions).toBe(1);
 expect(await json(await page.request.get(`${api}/v1/revisions/${queued.revision_id}`))).toEqual(saved);
 expect(await json(await page.request.get(`${api}/v1/revisions/${queued.revision_id}/measurements`))).toEqual(measured);
 expect((await json(await page.request.get(`${api}/v1/workspaces/${workspace.id}`))).active_revision).toBe(queued.revision_id);
 await reopen(page,title);await expect(recipe).toHaveValue("gfp-nuclear-2d");await expect(page.getByRole("status",{name:"選択視野のレシピ適合",exact:true})).toHaveCount(0);expect(errors).toEqual([]);
 if(evidence)fs.writeFileSync(path.join(evidence,"native-recipe-public-scope.json"),JSON.stringify({dataset:"BBBC013 A01",stains:["DRAQ","FKHR-EGFP"],scope:"Actual public two-channel input, explicit recipe selection, immutable result identity. The fixed background polygon is a numerical/UI test region, not a verified cell-free biological background. No biological comparison or segmentation accuracy claim."},null,2));
});

test("trial batch and saved-revision channel scopes respect optional GFP conditions without silently excluding fields",async({page})=>{
 if(!dataDir)throw Error("Isolated test data is required");
 const errors:string[]=[];page.on("pageerror",()=>errors.push("pageerror"));
 const title="既知画素のチャンネル条件検証";const workspace=await createRegionWorkspace(page,title);const folder=fs.mkdtempSync(path.join(dataDir,"recipe-input-"));
 execFileSync(python,["-c","import sys,tifffile;from pathlib import Path;from cytellect_analysis.synthetic import synthetic_field;p=Path(sys.argv[1]);c,_,_=synthetic_field();[tifffile.imwrite(p/f'{key}.tif',value,photometric='minisblack') for key,value in c.items()]",folder],{env:process.env});
 const ncl=await upload(page,workspace.id,"NCL二チャンネル",{dapi:path.join(folder,"dapi.tif"),ncl:path.join(folder,"ncl.tif")});
 const three=await upload(page,workspace.id,"三チャンネル",{dapi:path.join(folder,"dapi.tif"),ncl:path.join(folder,"ncl.tif"),gfp:path.join(folder,"gfp.tif")});
 const gfp=await upload(page,workspace.id,"GFP二チャンネル",{dapi:path.join(folder,"dapi.tif"),gfp:path.join(folder,"gfp.tif")});
 const registeredIds=(await json(await page.request.get(`${api}/v1/workspaces/${workspace.id}/fields`))).map((f:{id:string})=>f.id) as string[];
 const nclNumber=registeredIds.indexOf(ncl.id)+1,threeNumber=registeredIds.indexOf(three.id)+1;
 await reopen(page,title);const recipe=page.getByLabel("レシピ",{exact:true});const trial=page.getByRole("button",{name:"この視野で試す",exact:true});const batch=page.getByRole("button",{name:"条件を固定して全視野を解析",exact:true});
 for(const condition of ["NCL二チャンネル","三チャンネル","GFP二チャンネル"]){await field(page,condition);await background(page);}
 await expect(trial).toBeDisabled();await expect(batch).toBeDisabled();
 await recipe.selectOption("gfp-nuclear-2d");await expect(trial).toBeEnabled();await expect(batch).toBeDisabled();
 const batchIssue=page.getByLabel("全視野のレシピ適合",{exact:true});await batchIssue.locator("summary").click();await expect(batchIssue).toContainText(`視野 ${nclNumber}：GFPが未取得`);
 await field(page,"NCL二チャンネル");await expect(trial).toBeDisabled();await recipe.selectOption("ncl-native-2d");await expect(trial).toBeEnabled();await expect(batch).toBeDisabled();
 await field(page,"三チャンネル");await page.getByRole("combobox",{name:"GFPによる選別",exact:true}).selectOption("manual");await field(page,"NCL二チャンネル");await expect(trial).toBeDisabled();
 await page.getByRole("combobox",{name:"GFPによる選別",exact:true}).selectOption("none");await expect(trial).toBeEnabled();
 await field(page,"三チャンネル");await page.getByLabel("GFP上限（任意）",{exact:true}).fill("0");await field(page,"NCL二チャンネル");await expect(trial).toBeDisabled();await expect(page.getByLabel("GFP上限（任意）",{exact:true})).toHaveValue("0");await page.getByLabel("GFP上限（任意）",{exact:true}).fill("");await expect(trial).toBeEnabled();
 await field(page,"三チャンネル");await page.getByRole("combobox",{name:"GFPによる選別",exact:true}).selectOption("negative-control");await page.getByLabel(`視野 ${threeNumber} · 三チャンネル`,{exact:true}).check();await page.getByLabel("陰性対照の分布から閾値を確認しました。",{exact:true}).check();
 await field(page,"NCL二チャンネル");await page.getByRole("combobox",{name:"GFPによる選別",exact:true}).selectOption("none");await expect(trial).toBeDisabled();await expect(page.getByRole("status",{name:"選択視野のレシピ適合",exact:true})).toContainText("陰性対照が解析対象に含まれていません");await page.getByRole("button",{name:"陰性対照の指定を解除",exact:true}).click();await expect(trial).toBeEnabled();
 const queued=await mutation(page,"/analyses",()=>trial.click());await job(page,queued.job_id);await expect(page.getByRole("button",{name:"現在のマスクで条件を更新",exact:true})).toBeVisible();
 const saved=await json(await page.request.get(`${api}/v1/revisions/${queued.revision_id}`));const measured=await json(await page.request.get(`${api}/v1/revisions/${queued.revision_id}/measurements`));expect(saved.config.field_ids).toEqual([ncl.id]);
 await field(page,"三チャンネル");await page.getByLabel("GFP上限（任意）",{exact:true}).fill("0");await expect(trial).toBeEnabled();await expect(batch).toBeDisabled();await expect(page.getByRole("button",{name:"現在のマスクで条件を更新",exact:true})).toBeDisabled();await expect(page.getByRole("button",{name:/^核小体候補を再検出/})).toBeDisabled();await expect(page.getByRole("status",{name:"保存版のレシピ適合",exact:true})).toContainText(`視野 ${nclNumber}：GFPが未取得`);
 expect(await json(await page.request.get(`${api}/v1/revisions/${queued.revision_id}`))).toEqual(saved);expect(await json(await page.request.get(`${api}/v1/revisions/${queued.revision_id}/measurements`))).toEqual(measured);expect((await json(await page.request.get(`${api}/v1/workspaces/${workspace.id}/fields`))).map((f:{id:string})=>f.id).sort()).toEqual([ncl.id,three.id,gfp.id].sort());
 await expectGfpPreview(page);await shot(page,"native-recipe-saved-scope-desktop.png");await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await shot(page,"native-recipe-saved-scope-mobile.png");expect(errors).toEqual([]);
});
