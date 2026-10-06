import { test, expect, type Page, type APIResponse } from "@playwright/test";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const root=path.resolve(__dirname,"../../..");
const api=process.env.CYTELLECT_TEST_API_ORIGIN||"http://localhost:8000";
const python=process.env.CYTELLECT_TEST_PYTHON||path.join(root,".venv",process.platform==="win32"?"Scripts/python.exe":"bin/python");

function invite(){
 if(process.env.CYTELLECT_TEST_DATA_DIR)return execFileSync(python,["-c","import os;from pathlib import Path;from cytellect_api.db import Store;print(Store(Path(os.environ['CYTELLECT_TEST_DATA_DIR'])).invite(300))"],{encoding:"utf8",env:process.env}).trim();
 if(process.env.CYTELLECT_TEST_INVITE_FILE)return fs.readFileSync(process.env.CYTELLECT_TEST_INVITE_FILE,"utf8").trim();
 throw new Error("Use an isolated test data directory or a fresh test invitation");
}
async function json(response:Pick<APIResponse,"ok"|"json">){expect(response.ok()).toBeTruthy();return response.json();}
async function mutation(page:Page,suffix:string,action:()=>Promise<void>){
 const response=page.waitForResponse(r=>r.url().includes(suffix)&&r.request().method()==="POST");
 await action();return json(await response);
}
async function createWorkspace(page:Page,title:string){
 await page.goto("/legacy");await page.getByLabel("招待コード",{exact:true}).fill(invite());
 await page.getByRole("button",{name:"ワークスペースに接続"}).click();
 await page.getByLabel("作業名",{exact:true}).fill(title);
 await page.getByRole("combobox",{name:"解析の種類",exact:true}).selectOption("nuclear");
 return mutation(page,"/v1/workspaces",()=>page.getByRole("button",{name:"作業を作成"}).click());
}
async function waitJob(page:Page,id:string){
 await expect.poll(async()=>{const job=await json(await page.request.get(`${api}/v1/jobs/${id}`));if(["failed","cancelled"].includes(job.state))throw new Error(`Test job failed: ${job.error}`);return job.state;},{timeout:600000,intervals:[1000,2000,3000]}).toBe("succeeded");
}
async function polygon(page:Page,points:string){
 const details=page.locator("details").filter({has:page.locator("summary",{hasText:"座標から多角形を指定"})});
 if(!await details.evaluate(element=>(element as HTMLDetailsElement).open))await details.locator("summary").click();
 await page.getByLabel("頂点（x,y を空白または改行で区切る）").fill(points);
 await page.getByRole("button",{name:"座標を反映",exact:true}).click();
}

test("successive public-image fields retain explicit experiment metadata but reset file and channel confirmation",async({page})=>{
 const errors:string[]=[];page.on("pageerror",error=>errors.push(error.message));
 const workspace=await createWorkspace(page,"Public image metadata continuity");
 const upload=page.locator("details").filter({has:page.locator("summary",{hasText:"＋ 画像を登録"})});
 await upload.locator(":scope > summary").click();
 await page.getByLabel("測定対象",{exact:true}).selectOption("gfp");
 const metadata={condition:"Public sample",experimental_unit:"culture-1",sample:"slide-1",acquisition_date:"reference-batch",pair:"pair-1",repeat_length:"",pixel_size_um:""};
 for(const [name,value] of Object.entries(metadata))await upload.locator(`input[name="${name}"]`).fill(value);
 async function files(){await upload.locator('input[name="dapi"]').setInputFiles(path.join(root,"fixtures/public/bbbc013/A01-dapi.tif"));await upload.locator('input[name="gfp"]').setInputFiles(path.join(root,"fixtures/public/bbbc013/A01-gfp.tif"));await page.getByLabel("登録する画像の染色とチャンネル対応を確認しました。").check();}
 await files();await mutation(page,"/fields",()=>page.getByRole("button",{name:"この視野を登録",exact:true}).click());
 await expect(upload).not.toHaveAttribute("open","");
 await upload.locator(":scope > summary").click();
 for(const [name,value] of Object.entries(metadata))await expect(upload.locator(`input[name="${name}"]`)).toHaveValue(value);
 await expect(upload.locator('input[name="dapi"]')).toHaveValue("");await expect(upload.locator('input[name="gfp"]')).toHaveValue("");
 await expect(page.getByLabel("登録する画像の染色とチャンネル対応を確認しました。")).not.toBeChecked();
 await expect(page.getByText("前の視野の実験情報を引き継いでいます。異なる項目だけ変更してください。")).toBeVisible();
 await upload.locator('input[name="sample"]').fill("slide-2");await files();
 await mutation(page,"/fields",()=>page.getByRole("button",{name:"この視野を登録",exact:true}).click());
 const saved=await json(await page.request.get(`${api}/v1/workspaces/${workspace.id}/fields`));
 expect(saved).toHaveLength(2);expect(saved.map((field:{metadata:{sample:string}})=>field.metadata.sample).sort()).toEqual(["slide-1","slide-2"]);
 expect(saved.every((field:{metadata:{experimental_unit:string;condition:string;pair:string}})=>field.metadata.experimental_unit==="culture-1"&&field.metadata.condition==="Public sample"&&field.metadata.pair==="pair-1")).toBe(true);
 await expect(page.getByRole("button",{name:"この視野で試す",exact:true})).toBeDisabled();
 await expect(page.getByRole("button",{name:"条件を固定して全視野を解析",exact:true})).toBeDisabled();
 await page.getByRole("button",{name:"背景を設定 →",exact:true}).click();
 await expect(page.getByRole("button",{name:/背景を確定/})).toBeVisible();
 await polygon(page,"1,1 4,1 4,4 1,4");await page.getByRole("button",{name:"背景を確定 · 4 点",exact:true}).click();
 await expect(page.getByRole("button",{name:"この視野で試す",exact:true})).toBeEnabled();
 await expect(page.getByRole("button",{name:"条件を固定して全視野を解析",exact:true})).toBeDisabled();
 await upload.locator(":scope > summary").click();await page.getByRole("button",{name:"実験情報をクリア",exact:true}).click();
 for(const name of Object.keys(metadata))await expect(upload.locator(`input[name="${name}"]`)).toHaveValue("");
 expect(errors).toEqual([]);
});

test("edited representative masks survive batch expansion and re-detection requires an explicit confirmation",async({page})=>{
 const errors:string[]=[];page.on("pageerror",error=>errors.push(error.message));
 const workspace=await createWorkspace(page,"Representative field reuse regression");
 const fixture=await mutation(page,"/synthetic",()=>page.getByRole("button",{name:"合成データで試す",exact:true}).click());
 const trial=await mutation(page,"/analyses",()=>page.getByRole("button",{name:"この視野で試す",exact:true}).click());await waitJob(page,trial.job_id);
 await expect(page.getByRole("button",{name:"現在のマスクで条件を更新",exact:true})).toBeVisible();
 await page.getByLabel("修正対象",{exact:true}).selectOption("nuclei");await page.getByRole("button",{name:"削除",exact:true}).click();
 await page.getByLabel("対象ID（複数はカンマ区切り）").fill("1");
 const edited=await mutation(page,"/edits",()=>page.getByRole("button",{name:"選択した領域を削除・再測定",exact:true}).click());await waitJob(page,edited.job_id);
 const editedMasks=await json(await page.request.get(`${api}/v1/revisions/${edited.revision_id}/fields/${fixture.field_ids[0]}/masks`));
 expect(editedMasks.nuclei.some((nucleus:{id:number})=>nucleus.id===1)).toBe(false);
 await expect(page.getByTestId("batch-scope")).toContainText("1 視野の修正済み領域を保持し、残り 5 視野を検出");
 const submitted=page.waitForRequest(r=>r.url().endsWith("/analyses")&&r.method()==="POST");
 const batch=await mutation(page,"/analyses",()=>page.getByRole("button",{name:"条件を固定して全視野を解析",exact:true}).click());
 expect((await submitted).postDataJSON()).toMatchObject({reuse_revision:edited.revision_id,field_ids:null});await waitJob(page,batch.job_id);
 const batchMasks=await json(await page.request.get(`${api}/v1/revisions/${batch.revision_id}/fields/${fixture.field_ids[0]}/masks`));expect(batchMasks).toEqual(editedMasks);
 const batchRevision=await json(await page.request.get(`${api}/v1/revisions/${batch.revision_id}`));expect(batchRevision.config.field_ids).toHaveLength(6);
 const report=await json(await page.request.get(`${api}/v1/revisions/${batch.revision_id}/measurements`));expect(report.invalidated_nucleoli).toContain(fixture.field_ids[0]);expect(report.cells.some((cell:{field_id:string;nucleus_id:number})=>cell.field_id===fixture.field_ids[0]&&cell.nucleus_id===1)).toBe(false);
 await expect(page.getByTestId("batch-scope")).toContainText("6 視野の修正済み領域を保持");
 await page.getByLabel("平滑化 σ / px",{exact:true}).fill("0.5");
 let requested=0;page.on("request",request=>{if(request.method()==="POST"&&request.url().endsWith("/analyses"))requested++;});
 await page.getByRole("button",{name:"条件を固定して全視野を解析",exact:true}).click();
 const confirmation=page.getByRole("alert",{name:"再検出の確認"});await expect(confirmation).toContainText("全 6 視野を再検出");expect(requested).toBe(0);
 await confirmation.getByRole("button",{name:"取消",exact:true}).click();await expect(confirmation).not.toBeVisible();expect(requested).toBe(0);
 const unchanged=await json(await page.request.get(`${api}/v1/workspaces/${workspace.id}`));expect(unchanged.active_revision).toBe(batch.revision_id);
 await page.getByRole("button",{name:"この視野で試す",exact:true}).click();await expect(confirmation).toContainText("選択中の1視野を再検出");expect(requested).toBe(0);
 const confirmed=page.waitForRequest(r=>r.url().endsWith("/analyses")&&r.method()==="POST");
 const redetected=await mutation(page,"/analyses",()=>confirmation.getByRole("button",{name:"再検出して解析",exact:true}).click());
 expect((await confirmed).postDataJSON()).toMatchObject({reuse_revision:null,field_ids:[fixture.field_ids[0]],recipe:{smoothing_sigma_px:0.5}});await waitJob(page,redetected.job_id);
 const oldMasks=await json(await page.request.get(`${api}/v1/revisions/${batch.revision_id}/fields/${fixture.field_ids[0]}/masks`));expect(oldMasks).toEqual(editedMasks);
 await expect(page.locator("tbody tr")).not.toHaveCount(0);
 const dir=process.env.CYTELLECT_SCREENSHOT_DIR;if(dir){fs.mkdirSync(dir,{recursive:true});await page.screenshot({path:path.join(dir,"guided-workbench-desktop.png"),fullPage:true});}
 await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 if(dir)await page.screenshot({path:path.join(dir,"guided-workbench-mobile.png"),fullPage:true});
 expect(errors).toEqual([]);
});
