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
async function screenshot(page:Page,name:string){if(evidence){fs.mkdirSync(evidence,{recursive:true});await page.screenshot({path:path.join(evidence,name),fullPage:true});}}
async function reopen(page:Page,title:string){await page.reload();await page.getByRole("button",{name:new RegExp(title)}).click();await expect(page.getByRole("region",{name:"全視野の品質一覧",exact:true})).toBeVisible();}

test("saved all-field quality diagnostics locate hidden-channel warnings without modifying review or measurements",async({page})=>{
 test.setTimeout(240000);const errors:string[]=[];page.on("pageerror",error=>errors.push(error.message));
 if(!dataDir)throw Error("Private test data directory required");const scratch=fs.mkdtempSync(path.join(dataDir,"quality-fixture-"));
 // Exact artificial uint16 pixels test diagnostic/navigation semantics, not microscopy accuracy or biological quality.
 execFileSync(python,["-c",`import sys,numpy as np,tifffile
from pathlib import Path
p=Path(sys.argv[1])
for i in range(3):
 m=np.zeros((32,32),dtype=np.uint32);m[6:8,6:8]=1;m[12:14,12:14]=2
 if i==2:m[6:8,6:8]=0;m[0:2,0:2]=1
 a=np.full((32,32),10,dtype=np.uint16);b=np.full((32,32),20,dtype=np.uint16)
 if i==1:b[6,6]=100
 if i==2:a[0,0]=65535
 for name,value in [('labels',m),('first',a),('second',b)]:tifffile.imwrite(p/f'{i}-{name}.tif',value)
`,scratch]);
 const title="全視野の品質・既知画素検証";const space=await createRegionWorkspace(page,title);const registered=[];
 for(let i=0;i<3;i++)registered.push(await json(await page.request.post(`${api}/v1/workspaces/${space.id}/region-fields`,{headers:{Origin:new URL(page.url()).origin,"X-Cytellect-Request":"1"},multipart:{specification:JSON.stringify({version:"1.0.0",channels:[{channel_id:"first",label:"参照信号",stain:null,identity_confirmed:true,acquisition_saturation_value:i===2?null:1000,acquisition_saturation_confirmed:i!==2},{channel_id:"second",label:"確認信号",stain:null,identity_confirmed:true,acquisition_saturation_value:100,acquisition_saturation_confirmed:true}],metadata:{sample:`数値視野 ${i+1}`}}),ch0:{name:"first.tif",mimeType:"image/tiff",buffer:fs.readFileSync(path.join(scratch,`${i}-first.tif`))},ch1:{name:"second.tif",mimeType:"image/tiff",buffer:fs.readFileSync(path.join(scratch,`${i}-second.tif`))},labels:{name:"regions.tif",mimeType:"image/tiff",buffer:fs.readFileSync(path.join(scratch,`${i}-labels.tif`))}}})));
 const ordered=await json(await page.request.get(`${api}/v1/workspaces/${space.id}/region-fields`));const number=(id:string)=>ordered.findIndex((item:{id:string})=>item.id===id)+1;
 const bg={polygon:[[24,24],[28,24],[28,28],[24,28]],confirmed:true};const backgrounds=Object.fromEntries(registered.map(field=>[field.id,{first:bg,second:bg}]));
 const config={recipe:{id:"region-2d",version:"1.0.0",region_set_id:"regions",label:"検証領域",source:"imported",defining_channel_id:null},backgrounds,exclusions:[{field_id:registered[2].id,region_id:1,reason:"既知画素・除外の表示検証"}]};
 const initial=await post(page,`/v1/workspaces/${space.id}/region-analyses`,config);await waitJob(page,initial.job_id);
 const derived=await post(page,`/v1/revisions/${initial.revision_id}/region-metadata`,{version:"1.0.0",fields:Object.fromEntries(registered.map(field=>[field.id,field.metadata]))});await waitJob(page,derived.job_id);
 const savedRevision=await json(await page.request.get(`${api}/v1/revisions/${derived.revision_id}`));const savedReport=await json(await page.request.get(`${api}/v1/revisions/${derived.revision_id}/region-measurements`));
 expect(savedRevision.reviewed).toBe(false);expect(savedReport.field_masks[registered[1].id].mask_revision_id).toBe(initial.revision_id);
 await reopen(page,title);await expectGfpPreview(page);const overview=page.getByRole("region",{name:"全視野の品質一覧",exact:true});
 await expect(overview).toContainText("この解析版全体：品質確認前");await expect(overview.getByRole("row",{name:/品質一覧の視野/})).toHaveCount(3);
 const first=overview.getByRole("row",{name:`品質一覧の視野 ${number(registered[0].id)}`,exact:true});await expect(first).toContainText("2 領域");await expect(first).toContainText("この診断で該当なし");
 const second=overview.getByRole("row",{name:`品質一覧の視野 ${number(registered[1].id)}`,exact:true});await expect(second.getByLabel(`視野 ${number(registered[1].id)} 確認信号 の診断`,{exact:true})).toContainText("取得時飽和：採用対象 1 / 除外対象 0 領域");
 const third=overview.getByRole("row",{name:`品質一覧の視野 ${number(registered[2].id)}`,exact:true});await expect(third).toContainText("2 領域");await expect(third).toContainText("画像端：採用対象 0 / 除外対象 1 領域");await expect(third).toContainText("取得上限不明");await expect(third).toContainText("保存形式上限：採用対象 0 / 除外対象 1 領域");
 await overview.scrollIntoViewIfNeeded();await screenshot(page,"quality-overview-desktop.png");if(evidence)await overview.screenshot({path:path.join(evidence,"quality-table-desktop.png")});
 await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await screenshot(page,"quality-overview-mobile.png");if(evidence)await overview.screenshot({path:path.join(evidence,"quality-table-mobile.png")});await overview.getByRole("region",{name:"全視野の診断表",exact:true}).evaluate(element=>{element.scrollLeft=element.scrollWidth;element.scrollTop=140;});if(evidence)await overview.screenshot({path:path.join(evidence,"quality-diagnostics-mobile.png")});await page.setViewportSize({width:1440,height:1000});
 await second.getByRole("button",{name:`視野 ${number(registered[1].id)} 確認信号 を品質一覧から確認`,exact:true}).click();await expect(page.getByRole("status",{name:"保存済み品質一覧の視野",exact:true})).toContainText("測定チャンネル: 確認信号");await expect(page.getByRole("button",{name:"確認信号",exact:true})).toHaveClass(/segmentActive/);await expect(page.getByLabel("選択した領域ID",{exact:true})).toHaveValue("");await expectGfpPreview(page);await screenshot(page,"quality-channel-selected.png");
 await third.getByText("画像端の領域と値",{exact:true}).click();await third.getByRole("button",{name:"画像端の領域 1 を画像で確認",exact:true}).click();await expect(page.getByLabel("選択した領域ID",{exact:true})).toHaveValue("1");await expect(page.getByText(/品質一覧に記録された領域 1 を表示しています/)).toContainText("領域の形状を確認しています");
 expect(await json(await page.request.get(`${api}/v1/revisions/${derived.revision_id}`))).toEqual(savedRevision);expect(await json(await page.request.get(`${api}/v1/revisions/${derived.revision_id}/region-measurements`))).toEqual(savedReport);
 // A coordinate draft is preserved; viewing the list never approves the revision.
 await page.getByRole("button",{name:"追加",exact:true}).click();await page.getByText("座標から多角形を指定",{exact:true}).click();const draft=page.getByRole("textbox",{name:/頂点/});await draft.fill("17,17 20,17 20,20");await expect(second.getByRole("button",{name:/品質一覧から確認/})).toHaveCount(2);for(const button of await second.getByRole("button",{name:/品質一覧から確認/}).all())await expect(button).toBeDisabled();await expect(draft).toHaveValue("17,17 20,17 20,20");await page.getByRole("button",{name:"頂点を消去",exact:true}).click();await page.getByRole("button",{name:"選択",exact:true}).click();
 // A failed mask read must not switch to another field or make a false source claim.
 const beforeField=await page.getByRole("button",{name:"確認信号",exact:true}).getAttribute("class");await page.route(`**/v1/revisions/${derived.revision_id}/region-masks?field_id=${registered[1].id}`,route=>route.fulfill({status:503,contentType:"application/json",body:JSON.stringify({detail:"request_failed"})}));
 await second.getByRole("button",{name:/確認信号 を品質一覧から確認/}).click();await expect(page.locator("main").getByRole("alert")).toBeVisible();await expect(page.getByRole("status",{name:"保存済み品質一覧の視野",exact:true})).toHaveCount(0);await expect.poll(()=>page.locator('nav[aria-label="解析工程"]').evaluate(el=>!!el.closest("[inert]"))).toBe(false);expect(await page.getByRole("button",{name:"確認信号",exact:true}).getAttribute("class")).toBe(beforeField);await page.unroute(`**/v1/revisions/${derived.revision_id}/region-masks?field_id=${registered[1].id}`);
 // Area-only, empty and failed states come from real saved API/worker results, not injected QC payloads.
 const area=await post(page,`/v1/revisions/${derived.revision_id}/region-reconfigure`,{...config,measurement:{version:"1.0.0",mode:"area_only"},backgrounds:{}});await waitJob(page,area.job_id);await reopen(page,title);await expect(overview).toContainText("未測定（面積のみ）");await expect(overview).not.toContainText("取得上限不明");
 const failing={...backgrounds,[registered[1].id]:{first:bg,second:{polygon:[[6,6],[8,6],[8,8],[6,8]],confirmed:true}}};
 const failed=await post(page,`/v1/revisions/${area.revision_id}/region-reconfigure`,{...config,measurement:null,backgrounds:failing});await waitJob(page,failed.job_id);await reopen(page,title);await expect(second).toContainText("処理失敗");await expect(second).toContainText("領域数不明");await second.getByRole("button",{name:/入力画像を確認/}).click();await expect(page.getByRole("status",{name:"品質確認の入力画像",exact:true})).toBeVisible();await expect(page.getByLabel("輪郭",{exact:true})).not.toBeChecked();await expectGfpPreview(page);
 const excluded=await post(page,`/v1/revisions/${failed.revision_id}/region-reconfigure`,{...config,backgrounds:failing,exclusions:[...config.exclusions,{field_id:registered[1].id,region_id:null,reason:"失敗状態の表示検証"}]});await waitJob(page,excluded.job_id);await reopen(page,title);await expect(second).toContainText("理由付き失敗除外");await expect(second).toContainText("領域数不明");
 await post(page,`/v1/workspaces/${space.id}/current`,{revision_id:area.revision_id});const emptyMask=await json(await page.request.get(`${api}/v1/revisions/${area.revision_id}/region-masks?field_id=${registered[0].id}`));const empty=await post(page,`/v1/revisions/${area.revision_id}/region-edits`,{field_id:registered[0].id,region_set_id:"regions",operation:"delete",ids:[1,2],polygon:[],expected_mask_revision_id:emptyMask.metadata.mask_revision_id});await waitJob(page,empty.job_id);await reopen(page,title);await expect(first).toContainText("領域なし");await expect(first).toContainText("0 領域");await expect(first).not.toContainText("品質良好");
 await post(page,`/v1/workspaces/${space.id}/current`,{revision_id:derived.revision_id});await reopen(page,title);expect(await json(await page.request.get(`${api}/v1/revisions/${derived.revision_id}`))).toEqual(savedRevision);expect(await json(await page.request.get(`${api}/v1/revisions/${derived.revision_id}/region-measurements`))).toEqual(savedReport);expect(errors).toEqual([]);
 if(evidence)fs.writeFileSync(path.join(evidence,"quality-scope.json"),JSON.stringify({fixture:"Three fields, two channels, deterministic uint16 values and artificial masks",scientific_scope:"No biological quality or segmentation performance assertion",review_unchanged:true,measurements_unchanged:true,mask_reuse_checked:true,states:["measured","area_only","no_regions","failed","excluded_failed"]},null,2));
});
