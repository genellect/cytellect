import { test, expect, type Page, type APIResponse } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
const root=path.resolve("../..");
const api=process.env.CYTELLECT_TEST_API_ORIGIN||"http://localhost:8000";
const python=process.env.CYTELLECT_TEST_PYTHON||path.join(root,".venv",process.platform==="win32"?"Scripts/python.exe":"bin/python");
function invite(){
 if(process.env.CYTELLECT_TEST_DATA_DIR){
  return execFileSync(python,["-c","import os;from pathlib import Path;from cytellect_api.db import Store;print(Store(Path(os.environ['CYTELLECT_TEST_DATA_DIR'])).invite(1))"],{encoding:"utf8",env:process.env}).trim();
 }
 const file=process.env.CYTELLECT_TEST_INVITE_FILE;
 if(!file)throw new Error("Use a fresh synthetic-only invite file or isolated test data directory");
 return fs.readFileSync(file,"utf8").trim();
}
async function login(page:Page){
 await page.goto("/");
 await page.getByLabel("招待コード",{exact:true}).fill(invite());
 await page.getByRole("button",{name:"ワークスペースに接続"}).click();
 await expect(page.getByRole("heading",{name:"新しい作業"})).toBeVisible();
}
async function json(response:APIResponse){expect(response.ok()).toBeTruthy();return response.json();}
async function waitJob(page:Page,id:string){
 await expect.poll(async()=>{
  const job=await json(await page.request.get(api+"/v1/jobs/"+id));
  if(["failed","cancelled"].includes(job.state))throw new Error("Synthetic job failed: "+job.error);
  return job.state;
 },{timeout:600000,intervals:[1000,2000,3000]}).toBe("succeeded");
}
async function mutation(page:Page,suffix:string,action:()=>Promise<void>){
 const pending=page.waitForResponse(r=>r.url().includes(suffix)&&r.request().method()==="POST");
 await action();const response=await pending;
 expect(response.ok(),await response.text()).toBeTruthy();
 return response.json();
}
test("synthetic invite → detect → edit → remeasure → statistics → export",async({page})=>{
 const errors:string[]=[];page.on("pageerror",e=>errors.push(e.message));
 console.log("phase: login");
 await login(page);
 await page.getByLabel("作業名",{exact:true}).fill("Synthetic browser validation");
 await page.getByRole("button",{name:"作業を作成"}).click();
 const fixture=await mutation(page,"/synthetic",()=>page.getByRole("button",{name:"合成データで試す"}).click());
 await expect(page.getByText("6 / 6 視野確認済み")).toBeVisible();
 const analysis=await mutation(page,"/analyses",()=>page.getByRole("button",{name:"条件を固定して全視野を解析"}).click());
 await waitJob(page,analysis.job_id);
 console.log("phase: segmentation completed");
 await expect(page.getByRole("button",{name:"現在のマスクで条件を更新"})).toBeVisible();
 await expect(page.locator("tbody tr")).not.toHaveCount(0);
 console.log("phase: manual ROI");
 await page.getByLabel("修正対象",{exact:true}).selectOption("manual");
 await page.getByRole("button",{name:"追加",exact:true}).click();
 await page.getByText("座標から多角形を指定",{exact:true}).click();
 await page.getByLabel("頂点（x,y を空白または改行で区切る）").fill("5,25 20,25 20,40 5,40");
 await page.getByRole("button",{name:"座標を反映",exact:true}).click();
 console.log("phase: saving ROI");
 const edit=await mutation(page,"/edits",()=>page.getByRole("button",{name:/輪郭を保存・再測定/}).click());
 await waitJob(page,edit.job_id);
 await expect(page.getByRole("button",{name:"↶ Undo"})).toBeEnabled();
 await mutation(page,"/current",()=>page.getByRole("button",{name:"↶ Undo"}).click());
 await expect(page.getByRole("button",{name:"↷ Redo"})).toBeEnabled();
 await mutation(page,"/current",()=>page.getByRole("button",{name:"↷ Redo"}).click());
 await page.getByLabel("領域、背景、対象選別、失敗・除外理由を確認しました。").check();
 await mutation(page,"/review",()=>page.getByRole("button",{name:"品質確認を完了",exact:true}).click());
 await page.getByRole("button",{name:/02 統計と図表/}).click();
 await page.getByLabel("独立実験単位と対応関係を確認しました。").check();
 const statistics=await mutation(page,"/statistics",()=>page.getByRole("button",{name:"統計と図を生成",exact:true}).click());
 await waitJob(page,statistics.job_id);
 await expect(page.getByRole("heading",{name:"統計結果",exact:true})).toBeVisible();
 await expect(page.getByAltText("保存された測定表から生成した統計図")).toBeVisible();
 const svg=await page.request.get(api+`/v1/jobs/${statistics.job_id}/files/figure.svg`);
 expect(svg.status()).toBe(200);expect(svg.headers()["cache-control"]).toContain("no-store");
 const shot=process.env.CYTELLECT_SCREENSHOT_DIR;
 if(shot){fs.mkdirSync(shot,{recursive:true});await page.screenshot({path:path.join(shot,"synthetic-statistics.png"),fullPage:true});}
 await page.getByRole("button",{name:/03 保存と履歴/}).click();
 const exported=await mutation(page,"/export",()=>page.getByRole("button",{name:"解析パッケージを生成",exact:true}).click());
 await waitJob(page,exported.job_id);
 await expect(page.getByRole("button",{name:"ZIPを保存 ↓",exact:true})).toBeVisible();
 const zip=await page.request.get(api+`/v1/jobs/${exported.job_id}/files/analysis.zip`);expect(zip.status()).toBe(200);expect((await zip.body()).length).toBeGreaterThan(1000);
 await page.getByRole("button",{name:/01 画像と領域/}).click();
 if(shot)await page.screenshot({path:path.join(shot,"synthetic-workbench.png"),fullPage:true});
 await page.setViewportSize({width:390,height:844});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
 if(shot)await page.screenshot({path:path.join(shot,"synthetic-mobile.png"),fullPage:true});
 expect(errors).toEqual([]);
 const report=await json(await page.request.get(api+`/v1/revisions/${edit.revision_id}/measurements`));
 expect(report.manual_rois.length).toBeGreaterThan(0);
 expect(fixture.field_ids.length).toBe(6);
 expect(await page.evaluate(()=>({local:localStorage.length,session:sessionStorage.length}))).toEqual({local:0,session:0});
});
test("channel TIFF upload and explicit mapping; private session isolation",async({page,browser})=>{
 test.skip(!process.env.CYTELLECT_TEST_DATA_DIR,"Requires isolated synthetic test backend");
 await login(page);
 await page.getByLabel("作業名",{exact:true}).fill("Synthetic TIFF upload");
 await page.getByRole("button",{name:"作業を作成"}).click();
 await page.getByText("＋ 画像を登録",{exact:true}).click();
 const fixtureDir=path.join(process.env.CYTELLECT_TEST_DATA_DIR!,"browser-fixtures");
 execFileSync(python,["-c","import pathlib,sys,tifffile;from cytellect_analysis.synthetic import synthetic_field;p=pathlib.Path(sys.argv[1]);p.mkdir(parents=True,exist_ok=True);channels,_,_=synthetic_field();[tifffile.imwrite(p/(k+'.tif'),v) for k,v in channels.items()]",fixtureDir],{env:process.env});
 for(const role of ["DAPI","NCL","GFP"])await page.getByLabel(role+" TIFF",{exact:true}).setInputFiles(path.join(fixtureDir,role.toLowerCase()+".tif"));
 await page.getByLabel("群",{exact:true}).fill("Synthetic");
 await page.getByLabel("独立実験単位",{exact:true}).fill("unit-1");
 await page.getByLabel("試料",{exact:true}).fill("sample-1");
 await page.getByLabel("撮影日／バッチ",{exact:true}).fill("day-1");
 await page.getByLabel("DAPI・NCL・GFPのチャンネル対応を確認しました。").check();
 const uploaded=await mutation(page,"/fields",()=>page.getByRole("button",{name:"この視野を登録",exact:true}).click());
 await expect(page.getByText("0 / 1 視野確認済み")).toBeVisible();
 const outsider=await browser.newContext();
 const denied=await outsider.request.get(api+`/v1/fields/${uploaded.id}/preview`);expect(denied.status()).toBe(401);
 await outsider.close();
});
