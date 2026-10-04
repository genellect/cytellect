import {test,expect,type Page,type APIResponse} from "@playwright/test";
import {execFileSync} from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import {createRegionWorkspace,workspaceTestRuntime} from "./workspace-session";
import {expectGfpPreview} from "./image-preview";

const {api,python,dataDir}=workspaceTestRuntime();const evidence=process.env.CYTELLECT_SCREENSHOT_DIR;
async function json(response:Pick<APIResponse,"ok"|"json">){expect(response.ok()).toBeTruthy();return response.json();}
async function post(page:Page,url:string,data:unknown){return json(await page.request.post(api+url,{data,headers:{Origin:new URL(page.url()).origin,"X-Cytellect-Request":"1"}}));}
async function waitJob(page:Page,id:string){await expect.poll(async()=>{const job=await json(await page.request.get(`${api}/v1/jobs/${id}`));if(["failed","cancelled"].includes(job.state))throw Error(job.error);return job.state;},{timeout:120000,intervals:[500]}).toBe("succeeded");}
async function shot(page:Page,name:string){if(evidence){fs.mkdirSync(evidence,{recursive:true});await page.screenshot({path:path.join(evidence,name),fullPage:true});}}
async function fixture(page:Page,subset=false){
 if(!dataDir)throw Error("Private data directory required");const scratch=fs.mkdtempSync(path.join(dataDir,"navigation-fixture-"));
 // Deterministic pixels exercise state/navigation only, not microscopy or biological independence.
 execFileSync(python,["-c",`import sys,numpy as np,tifffile
from pathlib import Path
p=Path(sys.argv[1]);m=np.zeros((32,32),dtype=np.uint32);m[6:9,6:9]=1
for name,a in [('labels',m),('first',np.arange(1024,dtype=np.uint16).reshape(32,32)),('second',np.full((32,32),30,dtype=np.uint16))]:tifffile.imwrite(p/f'{name}.tif',a)
`,scratch]);
 const title=subset?"部分解析の視野対応": "通常移動の下書き保持";const space=await createRegionWorkspace(page,title);
 for(let i=0;i<3;i++)await json(await page.request.post(`${api}/v1/workspaces/${space.id}/region-fields`,{headers:{Origin:new URL(page.url()).origin,"X-Cytellect-Request":"1"},multipart:{specification:JSON.stringify({version:"1.0.0",channels:[{channel_id:"first",label:"第一信号",stain:null,identity_confirmed:true},{channel_id:"second",label:"第二信号",stain:null,identity_confirmed:true}],metadata:{sample:`入力${i+1}`}}),ch0:{name:"first.tif",mimeType:"image/tiff",buffer:fs.readFileSync(path.join(scratch,"first.tif"))},ch1:{name:"second.tif",mimeType:"image/tiff",buffer:fs.readFileSync(path.join(scratch,"second.tif"))},labels:{name:"regions.tif",mimeType:"image/tiff",buffer:fs.readFileSync(path.join(scratch,"labels.tif"))}}}));
 const fields=await json(await page.request.get(`${api}/v1/workspaces/${space.id}/region-fields`));const selected=subset?fields.slice(1):fields;
 const bg={polygon:[[24,24],[28,24],[28,28],[24,28]],confirmed:true};
 const config={recipe:{id:"region-2d",version:"1.0.0",region_set_id:"regions",label:"検証領域",source:"imported",defining_channel_id:null},field_ids:selected.map((f:{id:string})=>f.id),backgrounds:Object.fromEntries(selected.map((f:{id:string})=>[f.id,{first:bg,second:bg}])),exclusions:[]};
 const initial=await post(page,`/v1/workspaces/${space.id}/region-analyses`,config);await waitJob(page,initial.job_id);
 const derived=await post(page,`/v1/revisions/${initial.revision_id}/region-metadata`,{version:"1.0.0",fields:Object.fromEntries(selected.map((f:{id:string;metadata:unknown})=>[f.id,f.metadata]))});await waitJob(page,derived.job_id);
 await page.reload();await page.getByRole("button",{name:new RegExp(title)}).click();await expect(page.getByRole("region",{name:"全視野の品質一覧",exact:true})).toBeVisible();await expectGfpPreview(page);
 return {space,fields,initial,derived,config,scratch};
}
async function uploadAgain(page:Page,scratch:string){
 await page.getByText("＋ 画像を登録",{exact:true}).click();
 for(const [index,name] of ["first","second"].entries()){await page.getByLabel(`チャンネル ${index+1} の画像`,{exact:true}).setInputFiles(path.join(scratch,`${name}.tif`));await page.getByLabel(`チャンネル ${index+1} の画像と表示名の対応を確認しました。`,{exact:true}).check();}
 await page.getByLabel("整数ラベル TIFF",{exact:true}).setInputFiles(path.join(scratch,"labels.tif"));
 const response=page.waitForResponse(r=>r.url().endsWith("/region-fields")&&r.request().method()==="POST");await page.getByRole("button",{name:"この視野を登録",exact:true}).click();expect((await response).ok()).toBe(true);
}
const tab=(page:Page,name:string)=>page.getByRole("navigation",{name:"解析工程"}).getByRole("button",{name:new RegExp(name)});
const coordinates=(page:Page)=>page.getByRole("textbox",{name:/頂点/});
async function openCoordinates(page:Page){const summary=page.getByText("座標から多角形を指定",{exact:true});if(!await summary.evaluate(el=>el.closest("details")!.open))await summary.click();}
async function addDraft(page:Page){await page.getByRole("button",{name:"追加",exact:true}).click();await openCoordinates(page);await coordinates(page).fill("16,16 20,16 20,20");await page.getByRole("button",{name:"座標を反映",exact:true}).click();}

test("ordinary navigation preserves region and comparison drafts until explicit discard",async({page})=>{
 test.setTimeout(240000);const errors:string[]=[];page.on("pageerror",e=>errors.push(e.message));const f=await fixture(page);const saved=await json(await page.request.get(`${api}/v1/revisions/${f.derived.revision_id}/region-measurements`));
 await addDraft(page);await page.getByRole("button",{name:"第二信号",exact:true}).click();await shot(page,"draft-channel-attempt.png");
 const dialog=page.getByRole("dialog",{name:"未保存の変更を確認"});await expect(dialog).toBeVisible();await dialog.getByRole("button",{name:"編集を続ける",exact:true}).click();await expect(coordinates(page)).toHaveValue("16,16 20,16 20,20");await expect(page.getByRole("button",{name:"領域を保存・再測定 · 3 点",exact:true})).toBeVisible();
 for(const target of [page.locator('aside').getByRole("button",{name:/02/}).first(),page.getByRole("button",{name:"選択",exact:true}),page.getByRole("button",{name:"第二信号 ✓",exact:true})]){await target.click();await expect(dialog).toBeVisible();await dialog.getByRole("button",{name:"編集を続ける",exact:true}).click();await expect(coordinates(page)).toHaveValue("16,16 20,16 20,20");}
 await page.getByRole("button",{name:"第二信号",exact:true}).click();await dialog.getByRole("button",{name:"変更を破棄して続ける",exact:true}).click();await expect(coordinates(page)).toHaveValue("");await expect(page.getByRole("button",{name:"第二信号",exact:true})).toHaveClass(/segmentActive/);
 // Compatible background configuration survives ordinary channel changes without a discard prompt.
 await page.getByRole("button",{name:"背景",exact:true}).click();await openCoordinates(page);await coordinates(page).fill("20,24 23,24 23,27");await page.getByRole("button",{name:"座標を反映",exact:true}).click();await page.getByRole("button",{name:"背景を確定 · 3 点",exact:true}).click();await page.getByRole("button",{name:"第一信号",exact:true}).click();await expect(dialog).toHaveCount(0);
 await tab(page,"保存と履歴").click();await page.getByRole("button",{name:"この解析版に切り替える",exact:true}).first().click();await expect(dialog).toContainText("測定条件");await dialog.getByRole("button",{name:"編集を続ける",exact:true}).click();await tab(page,"画像と領域").click();await expect(page.getByRole("button",{name:"背景・除外を反映して再測定",exact:true})).toBeEnabled();
 await page.getByRole("button",{name:"背景・除外を反映して再測定",exact:true}).click();await expect.poll(async()=> (await json(await page.request.get(`${api}/v1/workspaces/${f.space.id}`))).active_revision).not.toBe(f.derived.revision_id);await expect(page.getByRole("button",{name:"背景・除外を反映して再測定",exact:true})).toBeDisabled();
 await tab(page,"統計解析").click();await page.getByLabel("視野 1 の条件",{exact:true}).fill("未保存の条件");await page.getByLabel("実験デザイン",{exact:true}).selectOption("paired");await page.getByLabel("対応の根拠",{exact:true}).fill("実験記録から入力途中");await tab(page,"画像と領域").click();await tab(page,"統計解析").click();await expect(page.getByLabel("視野 1 の条件",{exact:true})).toHaveValue("未保存の条件");await expect(page.getByLabel("対応の根拠",{exact:true})).toHaveValue("実験記録から入力途中");
 await tab(page,"画像と領域").click();await addDraft(page);await page.getByRole("button",{name:"領域を保存・再測定 · 3 点",exact:true}).click();await expect(dialog).toContainText("比較");await dialog.getByRole("button",{name:"編集を続ける",exact:true}).click();await expect(coordinates(page)).toHaveValue("16,16 20,16 20,20");
 await tab(page,"保存と履歴").click();await page.getByRole("button",{name:"この解析版に切り替える",exact:true}).first().click();await expect(dialog).toContainText("輪郭");await shot(page,"draft-history-desktop.png");await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await shot(page,"draft-history-mobile.png");await dialog.getByRole("button",{name:"編集を続ける",exact:true}).click();
 await page.getByRole("button",{name:"この解析版に切り替える",exact:true}).first().click();await dialog.getByRole("button",{name:"変更を破棄して続ける",exact:true}).click();await expect.poll(async()=> (await json(await page.request.get(`${api}/v1/workspaces/${f.space.id}`))).active_revision).toBe(f.initial.revision_id);await tab(page,"統計解析").click();await expect(page.getByLabel("視野 1 の条件",{exact:true})).toHaveValue("");await expect(page.getByLabel("実験デザイン",{exact:true})).toHaveValue("");expect(await json(await page.request.get(`${api}/v1/revisions/${f.derived.revision_id}/region-measurements`))).toEqual(saved);// Registration keeps its existing auto-selection when safe, but never erases an unrelated outline draft.
 await tab(page,"画像と領域").click();await uploadAgain(page,f.scratch);await expect(page.locator('aside').getByRole("button",{name:/04/}).first()).toHaveClass(/activeField/);
 await page.locator('aside').getByRole("button",{name:/01/}).first().click();await addDraft(page);await uploadAgain(page,f.scratch);await expect(page.locator('aside').getByRole("button",{name:/01/}).first()).toHaveClass(/activeField/);await expect(coordinates(page)).toHaveValue("16,16 20,16 20,20");await expect(page.getByRole("button",{name:"領域を保存・再測定 · 3 点",exact:true})).toBeVisible();await page.getByRole("button",{name:"頂点を消去",exact:true}).click();expect(errors).toEqual([]);
});

test("partial analysis retains original field labels in metadata, readiness and mobile quality cards",async({page})=>{
 test.setTimeout(180000);const f=await fixture(page,true);await tab(page,"統計解析").click();await shot(page,"subset-before-entry.png");
 await expect(page.getByLabel("視野 2 の条件",{exact:true})).toHaveCount(1);await expect(page.getByLabel("視野 3 の条件",{exact:true})).toHaveCount(1);await expect(page.getByLabel("視野 1 の条件",{exact:true})).toHaveCount(0);
 const readiness=page.getByRole("region",{name:"比較の前に確認すること"});await expect(readiness).toContainText("視野 3：条件が未記録");await readiness.getByText(/ほか .* 件を確認/).click();await readiness.getByRole("button",{name:"視野 3 の条件へ",exact:true}).click();await expect(page.getByLabel("視野 3 の条件",{exact:true})).toBeFocused();
 await page.getByLabel("視野 2 の条件",{exact:true}).fill("A");await page.getByLabel("視野 3 の条件",{exact:true}).fill("B");await tab(page,"画像と領域").click();await tab(page,"統計解析").click();await expect(page.getByLabel("視野 3 の条件",{exact:true})).toHaveValue("B");
 // A failed save keeps the metadata payload and active revision, including when other form resets were acknowledged.
 await page.getByLabel("実験デザイン",{exact:true}).selectOption("independent");
 const metadataUrl=`**/v1/revisions/${f.derived.revision_id}/region-metadata`;await page.route(metadataUrl,route=>route.fulfill({status:503,contentType:"application/json",body:JSON.stringify({detail:"request_failed"})}));
 await page.getByRole("button",{name:"実験情報を新しい解析版に保存",exact:true}).click();const discard=page.getByRole("dialog",{name:"未保存の変更を確認"});await expect(discard).toContainText("比較条件");await expect(discard).not.toContainText("未保存の実験情報");await discard.getByRole("button",{name:"変更を破棄して続ける",exact:true}).click();await expect(page.getByRole("alert").first()).toBeVisible();await expect(page.getByLabel("視野 2 の条件",{exact:true})).toHaveValue("A");await expect(page.getByLabel("視野 3 の条件",{exact:true})).toHaveValue("B");await expect(page.getByRole("button",{name:"実験情報を新しい解析版に保存",exact:true})).toBeEnabled();expect((await json(await page.request.get(`${api}/v1/workspaces/${f.space.id}`))).active_revision).toBe(f.derived.revision_id);await page.unroute(metadataUrl);
 const accepted=page.waitForResponse(r=>r.url().endsWith("/region-metadata")&&r.request().method()==="POST");await page.getByRole("button",{name:"実験情報を新しい解析版に保存",exact:true}).click();await discard.getByRole("button",{name:"変更を破棄して続ける",exact:true}).click();const response=await accepted;expect(response.ok()).toBe(true);const posted=response.request().postDataJSON();expect(Object.keys(posted.fields).sort()).toEqual([f.fields[1].id,f.fields[2].id].sort());expect(posted.fields[f.fields[1].id].condition).toBe("A");expect(posted.fields[f.fields[2].id].condition).toBe("B");const created=await response.json();await waitJob(page,created.job_id);await expect(page.locator("main")).toContainText("解析版 3 / 対象 2 視野");const metadataSummary=page.getByText("視野と実験単位の対応",{exact:true});if(!await metadataSummary.evaluate(el=>el.closest("details")!.open))await metadataSummary.click();await expect(page.getByRole("button",{name:"実験情報を新しい解析版に保存",exact:true})).toBeDisabled();
 await tab(page,"画像と領域").click();const overview=page.getByRole("region",{name:"全視野の品質一覧",exact:true});await expect(overview.getByRole("row",{name:/品質一覧の視野/})).toHaveCount(2);await expect(overview).toContainText("視野 2");await expect(overview).toContainText("視野 3");await expect(overview).toContainText("品質確認前");await shot(page,"subset-quality-desktop.png");
 await page.setViewportSize({width:390,height:844});const table=overview.getByRole("region",{name:"全視野の診断表",exact:true});expect(await table.evaluate(el=>el.scrollWidth<=el.clientWidth)).toBe(true);expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await table.scrollIntoViewIfNeeded();await shot(page,"subset-quality-mobile.png");if(evidence)await overview.screenshot({path:path.join(evidence,"subset-quality-card-mobile.png")});
 expect((await json(await page.request.get(`${api}/v1/revisions/${f.derived.revision_id}`))).config.field_snapshot[f.fields[1].id].metadata.condition).toBeNull();
});
