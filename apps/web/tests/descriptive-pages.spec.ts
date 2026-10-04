import {test,expect,type Page,type APIResponse} from "@playwright/test";
import {execFileSync} from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import {createRegionWorkspace,workspaceTestRuntime} from "./workspace-session";
import type {DescriptiveResult} from "../src/lib/descriptive-view";
import type {components} from "../src/lib/generated";

const root=path.resolve(__dirname,"../../..");const {api,python,dataDir}=workspaceTestRuntime();const evidence=process.env.CYTELLECT_SCREENSHOT_DIR;
type PagedResult=DescriptiveResult&{figure:components["schemas"]["PagedDescriptiveOutput"]};
async function json(response:Pick<APIResponse,"ok"|"json">){expect(response.ok()).toBeTruthy();return response.json();}
async function post(page:Page,url:string,data:unknown){return json(await page.request.post(api+url,{data,headers:{Origin:new URL(page.url()).origin,"X-Cytellect-Request":"1"}}));}
async function waitJob(page:Page,id:string){await expect.poll(async()=>{const job=await json(await page.request.get(`${api}/v1/jobs/${id}`));if(["failed","cancelled"].includes(job.state))throw Error(job.error);return job.state;},{timeout:180000,intervals:[500,1000]}).toBe("succeeded");}
async function mutation(page:Page,action:()=>Promise<void>){const response=page.waitForResponse(r=>new URL(r.url()).pathname.endsWith("/descriptive")&&r.request().method()==="POST");await action();return json(await response);}
async function openWork(page:Page,title:string){await page.reload();await page.getByRole("button",{name:new RegExp(title)}).click();await page.getByRole("button",{name:/02 図の出力/}).click();}
async function imageReady(page:Page){const image=page.getByAltText("領域の測定値と視野内中央値の分布図",{exact:true});await expect(image).toBeVisible();await expect.poll(()=>image.evaluate(element=>(element as HTMLImageElement).complete&&(element as HTMLImageElement).naturalWidth>0)).toBe(true);return image;}
async function screenshot(page:Page,name:string){if(evidence){fs.mkdirSync(evidence,{recursive:true});await page.screenshot({path:path.join(evidence,name),fullPage:true});}}

test("descriptive pages retain every source field and recover tables without substituting a stale figure",async({page})=>{
 const errors:string[]=[];page.on("pageerror",error=>errors.push(error.message));
 const title="Public-image pagination fixture";const workspace=await createRegionWorkspace(page,title);
 const scratch=fs.mkdtempSync(path.join(dataDir||os.tmpdir(),"descriptive-pages-"));
 // Duplicate registered public pixels only for UI coverage. Rectangles/empty mask are artificial;
 // these nine fields are neither biological segmentations nor nine independent experiments.
 execFileSync(python,["-c","import sys,numpy as np,tifffile;from pathlib import Path;a=tifffile.imread(sys.argv[1]);m=np.zeros(a.shape,dtype=np.uint32);m[25:40,25:40]=1;m[50:60,50:70]=2;tifffile.imwrite(Path(sys.argv[2])/'labels.tif',m);tifffile.imwrite(Path(sys.argv[2])/'empty.tif',np.zeros_like(m))",path.join(root,"fixtures/public/bbbc013/A01-dapi.tif"),scratch]);
 const headers={Origin:new URL(page.url()).origin,"X-Cytellect-Request":"1"};const fields:Array<{id:string}>=[];
 for(let i=0;i<9;i++)fields.push(await json(await page.request.post(`${api}/v1/workspaces/${workspace.id}/region-fields`,{headers,multipart:{
  specification:JSON.stringify({version:"1.0.0",channels:[{channel_id:"dna",label:"DRAQ",stain:"DRAQ",identity_confirmed:true}],metadata:{condition:null,sample:null,experimental_unit:null,acquisition_date:null,pair:null,repeat_length:null}}),
  ch0:{name:"public-DRAQ.tif",mimeType:"image/tiff",buffer:fs.readFileSync(path.join(root,`fixtures/public/bbbc013/${["A01","A06","A12"][i%3]}-dapi.tif`))},
  labels:{name:"artificial-labels.tif",mimeType:"image/tiff",buffer:fs.readFileSync(path.join(scratch,i===8?"empty.tif":"labels.tif"))},
 } })));
 const initial=await post(page,`/v1/workspaces/${workspace.id}/region-analyses`,{recipe:{id:"region-2d",version:"1.0.0",region_set_id:"regions",label:"Artificial rectangle areas",source:"imported"},measurement:{version:"1.0.0",mode:"area_only"},backgrounds:{},exclusions:[]});
 await waitJob(page,initial.job_id);await post(page,`/v1/revisions/${initial.revision_id}/review`,{});
 const selection={source:"region",region_set_id:"regions",channel_id:null,metric:"area_px"};
 const old=await post(page,`/v1/revisions/${initial.revision_id}/descriptive`,{mode:"descriptive",selection,group_by:"field",plot:{kind:"distribution",preset:"custom",width_inches:12,height_inches:4,font_size:7,language:"en",x_label:"",y_label:"",group_order:[]}});
 await waitJob(page,old.job_id);await openWork(page,title);await imageReady(page);await expect(page.getByLabel("記述図のページ番号",{exact:true})).toHaveCount(0);
 const oldResult=await json(await page.request.get(`${api}/v1/jobs/${old.job_id}/result`));expect(oldResult.spec).not.toHaveProperty("figure_policy");expect(oldResult.figure.descriptive_figure_version).toBe("1.0.1");
 await page.getByLabel("表示する測定値",{exact:true}).selectOption("area_px");
 const created=await mutation(page,()=>page.getByRole("button",{name:"分布図を作成",exact:true}).click());await waitJob(page,created.job_id);await imageReady(page);
 const result:PagedResult=await json(await page.request.get(`${api}/v1/jobs/${created.job_id}/result`));
 expect(result.figure.status).toBe("ready");expect(result.spec.figure_policy).toEqual({version:"2.0.0",layout:"field-pages"});expect(result.figure.page_plan.map(plan=>plan.field_numbers)).toEqual([[1,2,3,4,5,6,7,8],[9]]);
 expect(result.figure.page_plan.flatMap(plan=>plan.field_ids)).toEqual(result.field_summary.map(row=>row.field_id));expect(result.counts).toMatchObject({observations:16,input_fields:9,selected_fields:8,experimental_units:null});expect(result).not.toHaveProperty("comparisons");
 expect(result.field_summary.find(row=>row.field_id===fields[8].id)).toMatchObject({selected_rows:0,median:null,status:"no_regions"});
 await expect(page.getByText("16 観測 · 採用値のある視野 8 / 入力 9 視野",{exact:true})).toBeVisible();
 const firstBlob=await page.getByAltText("領域の測定値と視野内中央値の分布図",{exact:true}).getAttribute("src");
 const missing=`**/v1/jobs/${created.job_id}/files/figure-002.png`;
 await page.route(missing,route=>route.fulfill({status:404,contentType:"application/json",body:JSON.stringify({detail:"artifact_unavailable"})}));
 await page.getByRole("button",{name:"次のページ",exact:true}).click();await expect(page.getByText("このページの図を読み込めません。測定表と出典は下で確認できます。",{exact:true})).toBeVisible();await expect(page.getByAltText("領域の測定値と視野内中央値の分布図",{exact:true})).toHaveCount(0);
 await expect(page.getByText("16 観測 · 採用値のある視野 8 / 入力 9 視野",{exact:true})).toBeVisible();await page.unroute(missing);await page.getByRole("button",{name:"このページを再読み込み",exact:true}).click();await imageReady(page);
 expect(await page.getByAltText("領域の測定値と視野内中央値の分布図",{exact:true}).getAttribute("src")).not.toBe(firstBlob);await expect(page.getByText("2 / 2 ページ · 図の視野 9 · 全 9 視野",{exact:true})).toBeVisible();
 const trace=page.locator("details").filter({has:page.locator(":scope > summary",{hasText:"図に使った測定値"})});await trace.locator(":scope > summary").click();await expect(trace.getByRole("button",{name:/図の視野 \d+ 領域 \d+ を画像で確認/})).toHaveCount(16);
 const download=page.waitForEvent("download");await page.getByRole("button",{name:"全視野の元データ ↓",exact:true}).click();const csv=await download;const csvPath=path.join(scratch,"all-observations.csv");await csv.saveAs(csvPath);
 const csvRows=JSON.parse(execFileSync(python,["-c","import csv,json,sys;rows=list(csv.DictReader(open(sys.argv[1],encoding='utf-8')));print(json.dumps({'rows':len(rows),'fields':len({r['field_id'] for r in rows})}))",csvPath],{encoding:"utf8"}));expect(csvRows).toEqual({rows:16,fields:8});
 await screenshot(page,"descriptive-pages-desktop.png");await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await screenshot(page,"descriptive-pages-mobile.png");await page.setViewportSize({width:1440,height:1000});
 const sourceChild=await post(page,`/v1/revisions/${initial.revision_id}/region-metadata`,{version:"1.0.0",fields:{[fields[0].id]:{condition:"Source-navigation fixture",sample:null,experimental_unit:null,acquisition_date:null,pair:null,repeat_length:null}}});await waitJob(page,sourceChild.job_id);
 await openWork(page,title);await expect(page.getByLabel("保存済みの記述図",{exact:true})).toContainText("旧版の結果");await page.getByLabel("記述図のページ番号",{exact:true}).selectOption("1");await imageReady(page);
 const lastRow=page.getByRole("row").filter({hasText:"図の視野 9"});await lastRow.getByRole("button",{name:"この解析版の画像を確認",exact:true}).click();await expect(page.getByRole("heading",{name:"測定結果",exact:true})).toBeVisible();expect((await json(await page.request.get(`${api}/v1/workspaces/${workspace.id}`))).active_revision).toBe(initial.revision_id);
 // A real layout rejection leaves all tables intact. Wider re-rendering preserves the saved label.
 const failed=await post(page,`/v1/revisions/${initial.revision_id}/descriptive`,{mode:"descriptive",selection,group_by:"field",figure_policy:{version:"2.0.0",layout:"field-pages"},plot:{kind:"distribution",preset:"nature-single",width_inches:7,height_inches:3,font_size:7,language:"en",x_label:"W".repeat(60),y_label:"",group_order:fields.map(field=>field.id)}});
 await waitJob(page,failed.job_id);const failedResult:PagedResult=await json(await page.request.get(`${api}/v1/jobs/${failed.job_id}/result`));expect(failedResult.figure.status).toBe("tables_only");expect(failedResult.figure.error?.code).toBe("figure_text_outside_canvas");expect(failedResult.figure.pages).toEqual([]);
 const changed=await post(page,`/v1/revisions/${initial.revision_id}/region-metadata`,{version:"1.0.0",fields:{[fields[0].id]:{condition:"Artificial metadata revision",sample:null,experimental_unit:null,acquisition_date:null,pair:null,repeat_length:null}}});await waitJob(page,changed.job_id);
 await openWork(page,title);await expect(page.getByText("測定表を保存しました。図は作成できませんでした。",{exact:true})).toBeVisible();await expect(page.getByAltText("領域の測定値と視野内中央値の分布図",{exact:true})).toHaveCount(0);await expect(page.getByLabel("保存済みの記述図",{exact:true})).toContainText("旧版の結果");
 await page.getByLabel("記述図の幅",{exact:true}).selectOption("nature-double");await expect(page.getByText(/183 mm（保存時から変更）/)).toBeVisible();
 const retryUrl=`**/v1/revisions/${initial.revision_id}/descriptive`;await page.route(retryUrl,route=>route.fulfill({status:404,contentType:"application/json",body:JSON.stringify({detail:"workspace_not_found"})}));
 await page.getByRole("button",{name:"この解析版で図を再作成",exact:true}).click();await expect(page.getByText(/保存済みの測定表は引き続き確認できます/)).toBeVisible();await expect(page.getByRole("button",{name:"全視野の元データ ↓",exact:true})).toBeVisible();await page.unroute(retryUrl);
 await screenshot(page,"descriptive-tables-only-recovery.png");
 const retryRequest=page.waitForRequest(request=>request.method()==="POST"&&new URL(request.url()).pathname.endsWith("/descriptive"));const recovered=await mutation(page,()=>page.getByRole("button",{name:"この解析版で図を再作成",exact:true}).click());
 const submitted=await retryRequest;expect(new URL(submitted.url()).pathname).toBe(`/v1/revisions/${initial.revision_id}/descriptive`);expect(submitted.postDataJSON()).toMatchObject({selection,plot:{preset:"nature-double",x_label:"W".repeat(60)}});await waitJob(page,recovered.job_id);await imageReady(page);
 const recoveredResult:PagedResult=await json(await page.request.get(`${api}/v1/jobs/${recovered.job_id}/result`));expect(recoveredResult.figure.status).toBe("ready");expect(recoveredResult.plot_data).toEqual(failedResult.plot_data);expect(recoveredResult.selection).toEqual(failedResult.selection);expect(recoveredResult.figure.page_plan[1]).toMatchObject({field_ids:[fields[8].id],field_numbers:[9]});await page.getByLabel("記述図のページ番号",{exact:true}).selectOption("1");await imageReady(page);await expect(page.getByText("2 / 2 ページ · 図の視野 9 · 全 9 視野",{exact:true})).toBeVisible();expect((await json(await page.request.get(`${api}/v1/jobs/${failed.job_id}/result`))).figure.status).toBe("tables_only");expect(errors).toEqual([]);
 if(evidence)fs.writeFileSync(path.join(evidence,"descriptive-pages-receipt.json"),JSON.stringify({scope:"Registered BBBC013 pixels duplicated for nine UI fields with artificial rectangle/empty labels; no biological segmentation or independent-replicate claim",oldFigureVersion:oldResult.figure.descriptive_figure_version,newFigureVersion:result.figure.descriptive_figure_version,pages:result.figure.page_plan.map(plan=>plan.field_numbers),yLimits:result.figure.y_limits,counts:result.counts,csvRows,emptyLastPageRetained:true,missingImageNeverUsesPreviousBlob:true,tablesOnlyError:failedResult.figure.error,savedRevisionRetry:true,failedSourceRetryRetainsTables:true,successfulWiderRetryPreservesObservations:true,pageErrors:errors},null,2));
});
