import { test,expect,type Page,type APIResponse } from "@playwright/test";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { expectGfpPreview } from "./image-preview";
import {workspaceTestRuntime,createRegionWorkspace} from "./workspace-session";

const root=path.resolve(__dirname,"../../..");
const {api,python}=workspaceTestRuntime();
const publicFixture=process.env.CYTELLECT_TEST_REGION_FIXTURES;
const evidence=process.env.CYTELLECT_SCREENSHOT_DIR;
function fixtures(){
 if(publicFixture)return {first:path.join(publicFixture,"a9-actin.tif"),second:path.join(publicFixture,"a9-dna.tif"),labels:path.join(publicFixture,"a9-detected-nuclei-labels.tif"),names:["Actin","核染色"],count:115};
 const scratch=fs.mkdtempSync(path.join(process.env.CYTELLECT_TEST_DATA_DIR||os.tmpdir(),"region-ui-labels-"));const labels=path.join(scratch,"labels.tif");
 // These two rectangles test editing, not biological segmentation accuracy. Image pixels stay untouched.
 execFileSync(python,["-c","import sys,numpy as np,tifffile;a=tifffile.imread(sys.argv[1]);m=np.zeros(a.shape,dtype=np.uint32);m[25:40,25:40]=1;m[50:65,50:65]=2;tifffile.imwrite(sys.argv[2],m)",path.join(root,"fixtures/public/bbbc013/A01-gfp.tif"),labels]);
 return {first:path.join(root,"fixtures/public/bbbc013/A01-gfp.tif"),second:path.join(root,"fixtures/public/bbbc013/A01-dapi.tif"),labels,names:["FKHR-EGFP","DRAQ"],count:2};
}
async function json(response:Pick<APIResponse,"ok"|"json">){expect(response.ok()).toBeTruthy();return response.json();}
async function mutation(page:Page,suffix:string,action:()=>Promise<void>){const response=page.waitForResponse(r=>r.url().includes(suffix)&&r.request().method()==="POST");await action();return json(await response);}
async function waitJob(page:Page,id:string){await expect.poll(async()=>{const job=await json(await page.request.get(`${api}/v1/jobs/${id}`));if(["failed","cancelled"].includes(job.state))throw Error(`Job failed: ${job.error}`);return job.state;},{timeout:180000,intervals:[500,1000]}).toBe("succeeded");}
const create=createRegionWorkspace;
async function polygon(page:Page,coordinates:string){const details=page.locator("details").filter({has:page.locator(":scope > summary",{hasText:"座標から多角形を指定"})});if(!await details.evaluate(el=>(el as HTMLDetailsElement).open))await details.locator(":scope > summary").click();await page.getByLabel("頂点（x,y を空白または改行で区切る）").fill(coordinates);await page.getByRole("button",{name:"座標を反映",exact:true}).click();}
async function background(page:Page,coordinates="0,0 15,0 15,15 0,15"){await page.getByRole("button",{name:"背景",exact:true}).click();await polygon(page,coordinates);await page.getByRole("button",{name:/^背景を確定/}).click();}
async function screenshot(page:Page,name:string){if(evidence){fs.mkdirSync(evidence,{recursive:true});await page.screenshot({path:path.join(evidence,name),fullPage:true});}}

test("public two-channel regions preserve unknown replication through edits, description and a reproducibility bundle",async({page})=>{
 const fixture=fixtures();const errors:string[]=[];const unexpectedOrigins:string[]=[];page.on("pageerror",error=>errors.push(error.message));page.on("request",request=>{const url=new URL(request.url());if(["http:","https:"].includes(url.protocol)&&!['localhost','127.0.0.1'].includes(url.hostname))unexpectedOrigins.push(url.origin);});
 const workspace=await create(page,"Public region measurements");
 await page.getByLabel("チャンネル 1 の表示名",{exact:true}).fill(fixture.names[0]);await page.getByLabel("チャンネル 1 の画像",{exact:true}).setInputFiles(fixture.first);await page.getByLabel("チャンネル 1 の画像と表示名の対応を確認しました。",{exact:true}).check();
 await page.getByRole("button",{name:"チャンネルを追加",exact:true}).click();await page.getByLabel("チャンネル 2 の表示名",{exact:true}).fill(fixture.names[1]);await page.getByLabel("チャンネル 2 の画像",{exact:true}).setInputFiles(fixture.second);await page.getByLabel("チャンネル 2 の画像と表示名の対応を確認しました。",{exact:true}).check();
 await page.getByText("画素サイズと領域マスク",{exact:true}).click();await page.getByLabel("領域マスクを取り込む",{exact:true}).check();await page.getByLabel("整数ラベル TIFF",{exact:true}).setInputFiles(fixture.labels);
 const field=await mutation(page,"/region-fields",()=>page.getByRole("button",{name:"この視野を登録",exact:true}).click());expect(field.metadata).toMatchObject({condition:null,experimental_unit:null,sample:null,pair:null});expect(field.image_info.channels.every((ch:{stain:string|null})=>ch.stain===null)).toBe(true);
 await expect(page.getByRole("button",{name:"この視野で始める",exact:true})).toBeDisabled();await background(page);await expect(page.getByRole("button",{name:"この視野で始める",exact:true})).toBeDisabled();await page.getByRole("button",{name:fixture.names[1],exact:true}).click();await background(page);await expect(page.getByRole("group",{name:"領域編集",exact:true})).toHaveCSS("display","flex");
 const initialized=await mutation(page,"/region-analyses",()=>page.getByRole("button",{name:"この視野で始める",exact:true}).click());await waitJob(page,initialized.job_id);await expect(page.getByRole("table").filter({has:page.getByRole("columnheader",{name:"領域ID",exact:true})}).locator("tbody tr")).toHaveCount(fixture.count);await expectGfpPreview(page);
 const initial=await json(await page.request.get(`${api}/v1/revisions/${initialized.revision_id}/region-measurements`));expect(initial.field_tables[field.id].rows).toHaveLength(fixture.count*2);expect(initial.field_tables[field.id].rows.every((row:{area_um2:number|null})=>row.area_um2===null)).toBe(true);
 await page.getByLabel("選択した領域ID",{exact:true}).fill("1");await page.getByRole("button",{name:"削除",exact:true}).click();
 const edited=await mutation(page,"/region-edits",()=>page.getByRole("button",{name:"選択した領域を削除・再測定",exact:true}).click());await waitJob(page,edited.job_id);await expect(page.getByRole("table").filter({has:page.getByRole("columnheader",{name:"領域ID",exact:true})}).locator("tbody tr")).toHaveCount(fixture.count-1);
 const editedMasks=await json(await page.request.get(`${api}/v1/revisions/${edited.revision_id}/region-masks?field_id=${field.id}`));expect(editedMasks.regions.some((region:{id:number})=>region.id===1)).toBe(false);
 await mutation(page,"/current",()=>page.getByRole("button",{name:"↶ Undo",exact:true}).click());await expect(page.getByRole("table").filter({has:page.getByRole("columnheader",{name:"領域ID",exact:true})}).locator("tbody tr")).toHaveCount(fixture.count);await mutation(page,"/current",()=>page.getByRole("button",{name:"↷ Redo",exact:true}).click());await expect(page.getByRole("table").filter({has:page.getByRole("columnheader",{name:"領域ID",exact:true})}).locator("tbody tr")).toHaveCount(fixture.count-1);
 await page.getByLabel("領域、チャンネルごとの背景、失敗・除外理由を確認しました。",{exact:true}).check();await mutation(page,"/review",()=>page.getByRole("button",{name:"品質確認を完了",exact:true}).click());
 await screenshot(page,"generic-imported-desktop.png");await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await screenshot(page,"generic-imported-mobile.png");await page.setViewportSize({width:1440,height:1000});
 await page.getByRole("button",{name:/02 図の出力/}).click();await page.getByLabel("表示する測定値",{exact:true}).selectOption("channel-1-mean_corrected");const described=await mutation(page,"/descriptive",()=>page.getByRole("button",{name:"分布図を作成",exact:true}).click());await waitJob(page,described.job_id);
 const result=await json(await page.request.get(`${api}/v1/jobs/${described.job_id}/result`));expect(result.counts).toMatchObject({observations:fixture.count-1,input_fields:1,experimental_units:null});expect(result).not.toHaveProperty("comparisons");
 const plot=page.getByAltText("領域の測定値と視野内中央値の分布図",{exact:true});await expect(plot).toBeVisible();await expect.poll(()=>plot.evaluate(image=>(image as HTMLImageElement).complete&&(image as HTMLImageElement).naturalWidth>0)).toBe(true);
 await expect(page.getByLabel("保存済みの測定値",{exact:true})).toContainText(fixture.names[0]);await page.getByLabel("表示する測定値",{exact:true}).selectOption("area_px");await expect(page.getByText(/表示中は保存済みの条件による結果です/)).toBeVisible();
 // Reproduce a stale post-submit list response: terminal cached jobs must not
 // stop tracking the newly accepted job. The direct job endpoint remains live.
 const previousJobs=await json(await page.request.get(`${api}/v1/workspaces/${workspace.id}/jobs`));
 let staleJobListResponses=0;
 const jobListUrl=`**/v1/workspaces/${workspace.id}/jobs`;
 await page.route(jobListUrl,async route=>{
  if(staleJobListResponses===0&&route.request().method()==="GET"){
   staleJobListResponses++;
   await route.fulfill({contentType:"application/json",body:JSON.stringify(previousJobs)});
  }else await route.continue();
 });
 let failedStatusReads=0;
 const selectedStatusUrl="**/v1/jobs/*";
 await page.route(selectedStatusUrl,async route=>{
  if(failedStatusReads===0&&route.request().method()==="GET"){
   failedStatusReads++;
   await route.fulfill({status:503,contentType:"application/json",body:JSON.stringify({detail:"request_failed"})});
  }else await route.continue();
 });
 let releaseRequest!:()=>void;const requestGate=new Promise<void>(resolve=>{releaseRequest=resolve;});await page.route("**/descriptive",async route=>{if(route.request().method()==="POST")await requestGate;await route.continue();});
 const newDescription=mutation(page,"/descriptive",()=>page.getByRole("button",{name:"分布図を作成",exact:true}).click());await expect(page.getByText("図の生成を受け付けています。",{exact:true})).toBeVisible();await expect(plot).toHaveCount(0);await expect(page.getByRole("button",{name:"SVG ↓",exact:true})).toHaveCount(0);releaseRequest();const areaDescription=await newDescription;await page.unroute("**/descriptive");await waitJob(page,areaDescription.job_id);
 await expect(page.getByText("図の処理状態を取得できませんでした。",{exact:true})).toBeVisible();await expect(plot).toHaveCount(0);await expect(page.getByRole("button",{name:"SVG ↓",exact:true})).toHaveCount(0);
 await page.getByRole("button",{name:"処理状態を再読み込み",exact:true}).click();
 await expect(page.getByLabel("保存済みの測定値",{exact:true})).toContainText("面積");await expect(plot).toBeVisible();await expect.poll(()=>plot.evaluate(image=>(image as HTMLImageElement).complete&&(image as HTMLImageElement).naturalWidth>0)).toBe(true);
 expect(staleJobListResponses).toBe(1);expect(failedStatusReads).toBe(1);await page.unroute(jobListUrl);await page.unroute(selectedStatusUrl);
 const jobsAfterRetry=await json(await page.request.get(`${api}/v1/workspaces/${workspace.id}/jobs`));
 expect(jobsAfterRetry.filter((job:{id:string})=>!previousJobs.some((previous:{id:string})=>previous.id===job.id)).map((job:{id:string})=>job.id)).toEqual([areaDescription.job_id]);
 const areaResult=await json(await page.request.get(`${api}/v1/jobs/${areaDescription.job_id}/result`));expect(areaResult.counts.observations).toBe(fixture.count-1);expect(areaResult.spec.selection).toMatchObject({metric:"area_px",channel_id:null});
 for(const name of ["SVG ↓","全視野の元データ ↓"]){const pending=page.waitForEvent("download");await page.getByRole("button",{name,exact:true}).click();const file=await pending;expect(await file.failure()).toBeNull();if(evidence)await file.saveAs(path.join(evidence,file.suggestedFilename()));}
 await screenshot(page,"generic-description-desktop.png");await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await screenshot(page,"generic-description-mobile.png");await page.setViewportSize({width:1440,height:1000});
 await page.getByRole("button",{name:"この解析版の画像を確認",exact:true}).click();await expect(page.getByRole("heading",{name:"測定結果",exact:true})).toBeVisible();await expect(page.getByRole("table").filter({has:page.getByRole("columnheader",{name:"領域ID",exact:true})}).locator("tbody tr")).toHaveCount(fixture.count-1);await expectGfpPreview(page);expect((await json(await page.request.get(`${api}/v1/workspaces/${workspace.id}`))).active_revision).toBe(edited.revision_id);
 await page.getByRole("button",{name:/04 保存と履歴/}).click();await expect(page.getByLabel("原画像もZIPへ含める",{exact:true})).not.toBeChecked();const exported=await mutation(page,"/export?",()=>page.getByRole("button",{name:"解析パッケージを生成",exact:true}).click());await waitJob(page,exported.job_id);
 const download=page.waitForEvent("download");await page.getByRole("button",{name:"ZIPを保存 ↓",exact:true}).click();const zip=await download;expect(await zip.failure()).toBeNull();const zipPath=evidence?path.join(evidence,"cytellect-regions.zip"):path.join(process.env.CYTELLECT_TEST_DATA_DIR!,`ui-${workspace.id}.zip`);await zip.saveAs(zipPath);
 const receipt=JSON.parse(execFileSync(python,["-c","import sys,zipfile,json,hashlib;z=zipfile.ZipFile(sys.argv[1]);m=json.loads(z.read('manifest.json'));assert m['format']=='cytellect-region-reproducibility/1';assert m['raw_included'] is False;assert not any(p.startswith('raw/') for p in z.namelist());assert all(hashlib.sha256(z.read(p)).hexdigest()==h for p,h in m['files'].items());print(json.dumps({'format':m['format'],'raw_included':m['raw_included'],'verified_files':len(m['files'])}))",zipPath],{encoding:"utf8"}));expect(receipt.verified_files).toBeGreaterThan(10);expect(errors).toEqual([]);expect(unexpectedOrigins).toEqual([]);
 if(evidence)fs.writeFileSync(path.join(evidence,"generic-browser-receipt.json"),JSON.stringify({dataset:publicFixture?"BBBC007 a9":"BBBC013 A01 with test-only rectangle labels",inputRegions:fixture.count,retainedRegions:fixture.count-1,channels:fixture.names,metadataUnknownPreserved:true,counts:result.counts,areaCounts:areaResult.counts,newFigureHidesOldDuringSubmission:true,zip:receipt,consolePageErrors:errors,unexpectedRequestOrigins:unexpectedOrigins},null,2));
});

test("manual regions start empty and become measured only after an explicit polygon",async({page})=>{
 const fixture=fixtures();await create(page,"Manual public-image regions");await page.getByLabel("チャンネル 1 の表示名",{exact:true}).fill(fixture.names[0]);await page.getByLabel("チャンネル 1 の画像",{exact:true}).setInputFiles(fixture.first);await page.getByLabel("チャンネル 1 の画像と表示名の対応を確認しました。",{exact:true}).check();const first=await mutation(page,"/region-fields",()=>page.getByRole("button",{name:"この視野を登録",exact:true}).click());await background(page);
 const initialized=await mutation(page,"/region-analyses",()=>page.getByRole("button",{name:"この視野で始める",exact:true}).click());await waitJob(page,initialized.job_id);await expect(page.getByText("領域はまだありません。画像を囲んで追加してください。領域なしを輝度0として扱いません。",{exact:true})).toBeVisible();await expect(page.getByRole("table").filter({has:page.getByRole("columnheader",{name:"領域ID",exact:true})}).locator("tbody tr")).toHaveCount(0);
 await page.getByRole("button",{name:"追加",exact:true}).click();await polygon(page,"25,25 40,25 40,40 25,40");const edited=await mutation(page,"/region-edits",()=>page.getByRole("button",{name:/^領域を保存/}).click());await waitJob(page,edited.job_id);await expect(page.getByRole("table").filter({has:page.getByRole("columnheader",{name:"領域ID",exact:true})}).locator("tbody tr")).toHaveCount(1);await expectGfpPreview(page);await screenshot(page,"generic-manual-desktop.png");
 const canonical=await json(await page.request.get(`${api}/v1/revisions/${edited.revision_id}/region-masks?field_id=${first.id}`));
 // Background/region overlap is a recoverable field failure, never a zero measurement.
 await background(page,"30,30 35,30 35,35 30,35");const failed=await mutation(page,"/region-reconfigure",()=>page.getByRole("button",{name:"背景・除外を反映して再測定",exact:true}).click());await waitJob(page,failed.job_id);const failedReport=await json(await page.request.get(`${api}/v1/revisions/${failed.revision_id}/region-measurements`));expect(failedReport.field_failures).toHaveLength(1);await expect(page.getByRole("button",{name:"品質確認を完了",exact:true})).toBeDisabled();expect(await json(await page.request.get(`${api}/v1/revisions/${failed.revision_id}/region-masks?field_id=${first.id}`))).toEqual(canonical);
 await background(page);const recovered=await mutation(page,"/region-reconfigure",()=>page.getByRole("button",{name:"背景・除外を反映して再測定",exact:true}).click());await waitJob(page,recovered.job_id);await expect(page.getByRole("table").filter({has:page.getByRole("columnheader",{name:"領域ID",exact:true})}).locator("tbody tr")).toHaveCount(1);const recoveredReport=await json(await page.request.get(`${api}/v1/revisions/${recovered.revision_id}/region-measurements`));expect(recoveredReport.field_failures).toEqual([]);
 await page.getByText("＋ 画像を登録",{exact:true}).click();await expect(page.getByLabel("チャンネル 1 の表示名",{exact:true})).toHaveValue(fixture.names[0]);await expect(page.getByLabel("チャンネル 1 の画像と表示名の対応を確認しました。",{exact:true})).not.toBeChecked();await page.getByLabel("チャンネル 1 の画像",{exact:true}).setInputFiles(fixture.first);await page.getByLabel("チャンネル 1 の画像と表示名の対応を確認しました。",{exact:true}).check();const second=await mutation(page,"/region-fields",()=>page.getByRole("button",{name:"この視野を登録",exact:true}).click());await background(page);
 const submitted=page.waitForRequest(request=>request.url().endsWith("/region-analyses")&&request.method()==="POST");const batch=await mutation(page,"/region-analyses",()=>page.getByRole("button",{name:"領域を保持して全視野を測定",exact:true}).click());expect((await submitted).postDataJSON().reuse_revision).toBe(recovered.revision_id);await waitJob(page,batch.job_id);const retained=await json(await page.request.get(`${api}/v1/revisions/${batch.revision_id}/region-masks?field_id=${first.id}`));expect(retained).toEqual(canonical);const report=await json(await page.request.get(`${api}/v1/revisions/${batch.revision_id}/region-measurements`));expect(report.field_tables[first.id].rows).toHaveLength(1);expect(report.field_outcomes[second.id]).toBe("no_regions");
});
