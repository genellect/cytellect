import { test, expect, type Page, type APIResponse } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
const root=path.resolve(__dirname,"../../..");
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
 const canvas=page.getByTestId("image-canvas").locator("canvas").first();
 await canvas.scrollIntoViewIfNeeded();await canvas.hover();await page.mouse.wheel(0,-100);
 await expect(page.getByRole("button",{name:"全体を表示 · 110%",exact:true})).toBeVisible();
 const bounds=await canvas.boundingBox();expect(bounds).not.toBeNull();
 const base=Math.min((bounds!.width-48)/256,(bounds!.height-48)/256);
 for(const [x,y] of [[5,25],[20,25],[20,40],[5,40]])await canvas.click({position:{x:(bounds!.width-256*base)/2+x*base*1.1,y:(bounds!.height-256*base)/2+y*base*1.1}});
 await expect(page.getByRole("button",{name:"輪郭を保存・再測定 · 4 点",exact:true})).toBeEnabled();
 console.log("phase: saving ROI");
 const edit=await mutation(page,"/edits",()=>page.getByRole("button",{name:/輪郭を保存・再測定/}).click());
 await waitJob(page,edit.job_id);
 const editReport=await json(await page.request.get(api+`/v1/revisions/${edit.revision_id}/measurements`));
 const firstManual=editReport.manual_rois[0];
 const rawManual=page.locator("details").filter({has:page.locator("summary",{hasText:"手動ROIの測定値"})});
 await rawManual.locator("summary").click();
 await expect(rawManual.locator("tbody tr").first().locator("td").nth(2)).toHaveText(Number(firstManual.gfp_mean.toPrecision(5)).toLocaleString("en-US",{maximumFractionDigits:5}));
 const rawNucleoli=page.locator("details").filter({has:page.locator("summary",{hasText:"核小体候補ごとの測定値"})});
 await rawNucleoli.locator("summary").click();
 await expect(rawNucleoli.locator("tbody tr").first().locator("td").nth(3)).not.toHaveText("—");
 await expect(page.getByRole("button",{name:"↶ Undo"})).toBeEnabled();
 await mutation(page,"/current",()=>page.getByRole("button",{name:"↶ Undo"}).click());
 await expect(page.getByRole("button",{name:"↷ Redo"})).toBeEnabled();
 await mutation(page,"/current",()=>page.getByRole("button",{name:"↷ Redo"}).click());
 // Create a second branch from the original revision; Redo must return to this branch.
 await mutation(page,"/current",()=>page.getByRole("button",{name:"↶ Undo"}).click());
 await page.getByText("座標から多角形を指定",{exact:true}).click();
 await page.getByLabel("頂点（x,y を空白または改行で区切る）").fill("8,25 23,25 23,40 8,40");
 await page.getByRole("button",{name:"座標を反映",exact:true}).click();
 const branch=await mutation(page,"/edits",()=>page.getByRole("button",{name:/輪郭を保存・再測定/}).click());await waitJob(page,branch.job_id);
 await mutation(page,"/current",()=>page.getByRole("button",{name:"↶ Undo"}).click());
 const redoRequest=page.waitForRequest(r=>r.url().endsWith("/current")&&r.method()==="POST");
 await mutation(page,"/current",()=>page.getByRole("button",{name:"↷ Redo"}).click());
 expect((await redoRequest).postDataJSON().revision_id).toBe(branch.revision_id);
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
 const figureData=await json(await page.request.get(api+`/v1/jobs/${statistics.job_id}/files/figure-data.json`));expect(figureData.style.preset).toBe("nature-single");expect(figureData.style.width_mm).toBeCloseTo(89);
 const caption=await page.request.get(api+`/v1/jobs/${statistics.job_id}/files/figure-caption.md`);expect(caption.status()).toBe(200);
 // A model switch must not inherit the default paired test or paired plot.
 await page.getByLabel("図の種類",{exact:true}).selectOption("paired");
 await page.getByLabel("統計モデル",{exact:true}).selectOption("exploratory");
 await expect(page.getByLabel("図の種類",{exact:true})).toHaveValue("distribution");
 await page.getByText("感度解析",{exact:true}).click();
 await page.getByLabel("事前指定のGFP閾値（カンマ区切り）").fill("0,100000");
 const sent=page.waitForRequest(r=>r.url().includes("/statistics")&&r.method()==="POST");
 const exploratory=await mutation(page,"/statistics",()=>page.getByRole("button",{name:"統計と図を生成",exact:true}).click());
 expect((await sent).postDataJSON().paired).toBe(false);
 await waitJob(page,exploratory.job_id);
 await expect(page.getByRole("heading",{name:"GFPとの関連・調整回帰",exact:true})).toBeVisible();
 const scenarios=page.getByTestId("sensitivity-result");await expect(scenarios).toHaveCount(2);
 await scenarios.first().locator(":scope > summary").click();
 await expect(scenarios.first().getByRole("columnheader",{name:"Holm調整p",exact:true})).toBeVisible();
 await expect(scenarios.last().locator(":scope > summary")).toContainText("推定不可");
 for(const file of ["model-coefficients.csv","repeat-trend.csv","sensitivity-comparisons.csv","sensitivity-counts.csv","sensitivity-status.csv"]){const csv=await page.request.get(api+`/v1/jobs/${exploratory.job_id}/files/${file}`);expect(csv.status(),file).toBe(200);}
 const shot=process.env.CYTELLECT_SCREENSHOT_DIR;
 if(shot){fs.mkdirSync(shot,{recursive:true});await page.screenshot({path:path.join(shot,"synthetic-statistics.png"),fullPage:true});}
 await page.getByRole("button",{name:/03 保存と履歴/}).click();
 const exported=await mutation(page,"/export",()=>page.getByRole("button",{name:"解析パッケージを生成",exact:true}).click());
 await waitJob(page,exported.job_id);
 await expect(page.getByRole("button",{name:"ZIPを保存 ↓",exact:true})).toBeVisible();
 const zip=await page.request.get(api+`/v1/jobs/${exported.job_id}/files/analysis.zip`);expect(zip.status()).toBe(200);expect((await zip.body()).length).toBeGreaterThan(1000);
 await page.getByRole("button",{name:/01 画像と領域/}).click();
 if(shot)await page.screenshot({path:path.join(shot,"synthetic-workbench.png"),fullPage:true});
 // Corrected nuclei must survive a changed nucleolar recipe; old figures stay identifiable.
 await page.getByLabel("修正対象",{exact:true}).selectOption("nuclei");
 await page.getByRole("button",{name:"削除",exact:true}).click();
 await page.getByLabel("対象ID（複数はカンマ区切り）").fill("1");
 const nuclearEdit=await mutation(page,"/edits",()=>page.getByRole("button",{name:"選択した領域を削除・再測定",exact:true}).click());
 await waitJob(page,nuclearEdit.job_id);
 await expect(page.getByText(/核の修正により 1 視野/)).toBeVisible();
 await page.getByLabel("平滑化 σ / px",{exact:true}).fill("0.5");
 await page.getByLabel("除外理由",{exact:true}).fill("Synthetic exclusion regression");
 await page.getByRole("button",{name:"除外指定",exact:true}).first().click();
 const resegmentRequest=page.waitForRequest(r=>r.url().endsWith("/resegment")&&r.method()==="POST");
 const resegmented=await mutation(page,"/resegment",()=>page.getByRole("button",{name:"核小体候補を再検出 · 6 視野",exact:true}).click());
 const payload=(await resegmentRequest).postDataJSON();expect(payload.recipe.smoothing_sigma_px).toBe(0.5);expect(payload.field_ids).toHaveLength(6);expect(payload.exclusions).toHaveLength(1);expect(Object.keys(payload.backgrounds)).toHaveLength(6);
 await waitJob(page,resegmented.job_id);
 const renewed=await json(await page.request.get(api+`/v1/revisions/${resegmented.revision_id}/measurements`));
 expect(renewed.field_failures).toEqual([]);expect(renewed.invalidated_nucleoli).toEqual([]);
 expect(renewed.cells.some((c:{field_id:string;nucleus_id:number})=>c.field_id===fixture.field_ids[0]&&c.nucleus_id===1)).toBe(false);
 expect(renewed.cells.some((c:{excluded:boolean;exclusion_reason:string})=>c.excluded&&c.exclusion_reason==="Synthetic exclusion regression")).toBe(true);
 await page.getByRole("button",{name:/02 統計と図表/}).click();
 await expect(page.getByText("この図は採用中の画像解析版とは別の解析版、または数値表から作成されています。保存する前に参照元を確認してください。")).toBeVisible();
 await page.getByRole("button",{name:/01 画像と領域/}).click();
 await page.setViewportSize({width:390,height:844});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
 if(shot)await page.screenshot({path:path.join(shot,"synthetic-mobile.png"),fullPage:true});
 // Inject the actual worker failure shape to verify the UI contract, without changing scientific data.
 await page.route(api+`/v1/revisions/${resegmented.revision_id}/measurements`,async route=>route.fulfill({json:{...renewed,field_failures:[{field_id:fixture.field_ids[0],reason:"fiji_detection_capacity_exceeded",category:"EngineUnavailable"}]}}));
 await page.reload();
 await page.getByRole("button",{name:/Synthetic browser validation 有効期限/}).click();
 await expect(page.getByText(/この画像は現在の自動検出の上限を超えています/)).toBeVisible();
 await page.getByLabel("領域、背景、対象選別、失敗・除外理由を確認しました。").check();
 await expect(page.getByRole("button",{name:"品質確認を完了",exact:true})).toBeDisabled();
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
 await page.getByLabel("GFPチャンネルも登録する",{exact:true}).check();
 for(const role of ["dapi","ncl","gfp"])await page.locator(`input[name="${role}"]`).setInputFiles(path.join(fixtureDir,role+".tif"));
 await page.getByLabel("群",{exact:true}).fill("Synthetic");
 await page.getByLabel("独立実験単位",{exact:true}).fill("unit-1");
 await page.getByLabel("試料",{exact:true}).fill("sample-1");
 await page.getByLabel("撮影日／バッチ",{exact:true}).fill("day-1");
 await page.getByLabel("登録する画像の染色とチャンネル対応を確認しました。").check();
 const uploaded=await mutation(page,"/fields",()=>page.getByRole("button",{name:"この視野を登録",exact:true}).click());
 await expect(page.getByText("0 / 1 視野確認済み")).toBeVisible();
 const outsider=await browser.newContext();
 const denied=await outsider.request.get(api+`/v1/fields/${uploaded.id}/preview`);expect(denied.status()).toBe(401);
 await outsider.close();
});

test("two-channel inputs preserve actual roles; GFP field trial and figure presets",async({page})=>{
 test.skip(!process.env.CYTELLECT_TEST_DATA_DIR,"Requires isolated test backend");
 const errors:string[]=[];page.on("pageerror",e=>errors.push(e.message));
 await login(page);
 await page.getByLabel("作業名",{exact:true}).fill("Public GFP optional-channel validation");
 await page.getByRole("button",{name:"作業を作成"}).click();
 await page.getByText("＋ 画像を登録",{exact:true}).click();
 await page.getByLabel("測定対象",{exact:true}).selectOption("gfp");
 await expect(page.locator('input[name="ncl"]')).toHaveCount(0);
 for(const role of ["dapi","gfp"])await page.locator(`input[name="${role}"]`).setInputFiles(path.join(root,"fixtures/public/bbbc013",`A01-${role}.tif`));
 await page.getByLabel("群",{exact:true}).fill("BBBC013 A01");
 await page.getByLabel("独立実験単位",{exact:true}).fill("public-plate");
 await page.getByLabel("試料",{exact:true}).fill("A01");
 await page.getByLabel("撮影日／バッチ",{exact:true}).fill("public-acquisition");
 await page.getByLabel("登録する画像の染色とチャンネル対応を確認しました。").check();
 const uploaded=await mutation(page,"/fields",()=>page.getByRole("button",{name:"この視野を登録",exact:true}).click());
 expect(uploaded.image_info.channel_roles).toEqual(["dapi","gfp"]);
 await expect(page.getByRole("button",{name:"この視野を登録",exact:true})).toBeHidden();
 await expect(page.getByLabel("レシピ",{exact:true})).toHaveValue("gfp-nuclear-2d");
 await expect(page.getByRole("button",{name:"NCL",exact:true})).toHaveCount(0);
 await expect(page.getByLabel("核小体候補の定義")).toHaveCount(0);
 await page.getByRole("button",{name:"GFP",exact:true}).click();
 await page.getByRole("button",{name:"背景ROI",exact:true}).click();
 await page.getByText("座標から多角形を指定",{exact:true}).click();
 await page.getByLabel("頂点（x,y を空白または改行で区切る）").fill("1,1 4,1 4,4 1,4");
 await page.getByRole("button",{name:"座標を反映",exact:true}).click();
 await page.getByRole("button",{name:/背景を確定/}).click();
 const trial=await mutation(page,"/analyses",()=>page.getByRole("button",{name:"この視野で試す",exact:true}).click());
 await waitJob(page,trial.job_id);
 const report=await json(await page.request.get(api+`/v1/revisions/${trial.revision_id}/measurements`));
 expect(report.cells.length).toBeGreaterThan(100);
 expect(report.nucleoli).toHaveLength(0);
 expect(report.cells.every((c:Record<string,unknown>)=>c.ncl_nucleus_mean_corrected===undefined||c.ncl_nucleus_mean_corrected===null)).toBeTruthy();
 await expect(page.getByRole("columnheader",{name:"GFP 補正平均",exact:true})).toBeVisible();
 await expect(page.locator("tbody tr")).toHaveCount(report.cells.length);
 await expect(page.getByRole("columnheader",{name:"NCL 核全体",exact:true})).toHaveCount(0);
 const shot=process.env.CYTELLECT_SCREENSHOT_DIR;
 if(shot){fs.mkdirSync(shot,{recursive:true});await page.screenshot({path:path.join(shot,"public-gfp-private-workbench.png"),fullPage:true});}
 await page.getByRole("button",{name:/02 統計と図表/}).click();
 await expect(page.getByLabel("指標",{exact:true})).toHaveValue("gfp_mean_corrected");
 await expect(page.getByLabel("指標",{exact:true}).locator("option")).toHaveCount(7);
 await expect(page.getByLabel("図のサイズ",{exact:true})).toHaveValue("nature-single");
 await expect(page.getByLabel("幅 / inch",{exact:true})).toHaveCount(0);
 await page.getByLabel("図のサイズ",{exact:true}).selectOption("custom");
 await expect(page.getByLabel("幅 / inch",{exact:true})).toBeVisible();
 await page.getByLabel("図のサイズ",{exact:true}).selectOption("nature-double");
 await expect(page.getByLabel("幅 / inch",{exact:true})).toHaveCount(0);
 expect(errors).toEqual([]);
});

test("two-channel NCL OME upload has explicit roles and no GFP controls",async({page})=>{
 test.skip(!process.env.CYTELLECT_TEST_DATA_DIR,"Requires isolated test backend");
 await login(page);
 await page.getByLabel("作業名",{exact:true}).fill("Synthetic NCL OME role validation");
 await page.getByRole("button",{name:"作業を作成"}).click();
 await page.getByText("＋ 画像を登録",{exact:true}).click();
 await page.getByLabel("入力形式",{exact:true}).selectOption("ome");
 const fixtureDir=path.join(process.env.CYTELLECT_TEST_DATA_DIR!,"browser-fixtures");
 const file=path.join(fixtureDir,"ncl-two.ome.tif");
 execFileSync(python,["-c","import pathlib,sys,tifffile,numpy as np;from cytellect_analysis.synthetic import synthetic_field;p=pathlib.Path(sys.argv[1]);p.parent.mkdir(parents=True,exist_ok=True);c,_,_=synthetic_field();tifffile.imwrite(p,np.stack([c['dapi'],c['ncl']]),ome=True,metadata={'axes':'CYX'},photometric='minisblack')",file],{env:process.env});
 await page.locator('input[name="ome"]').setInputFiles(file);
 await expect(page.locator('input[name="gfp_index"]')).toHaveCount(0);
 await page.getByLabel("群",{exact:true}).fill("Synthetic");
 await page.getByLabel("独立実験単位",{exact:true}).fill("unit-1");
 await page.getByLabel("試料",{exact:true}).fill("sample-1");
 await page.getByLabel("撮影日／バッチ",{exact:true}).fill("day-1");
 await page.getByLabel("登録する画像の染色とチャンネル対応を確認しました。").check();
 const uploaded=await mutation(page,"/fields",()=>page.getByRole("button",{name:"この視野を登録",exact:true}).click());
 expect(uploaded.image_info.channel_roles).toEqual(["dapi","ncl"]);
 await expect(page.getByRole("button",{name:"NCL",exact:true})).toBeVisible();
 await expect(page.getByRole("button",{name:"GFP",exact:true})).toHaveCount(0);
 await expect(page.getByLabel("GFPによる選別")).toHaveCount(0);
});


test("numeric CSV -> paired comparison -> Methods and replay package",async({page})=>{
 test.skip(!process.env.CYTELLECT_TEST_DATA_DIR,"Requires isolated test backend");
 await login(page);
 await page.getByLabel("作業名",{exact:true}).fill("Synthetic numeric table workflow");
 await page.getByRole("button",{name:"作業を作成"}).click();
 await page.getByRole("button",{name:/02 統計と図表/}).click();
 await page.getByText("測定済み数値CSVを取り込む",{exact:true}).click();
 const csv="condition,experimental_unit,sample,field_id,acquisition_date,pair,value\n"+Array.from({length:3},(_,i)=>`Control,unit-${i},c-${i},cf-${i},day-${i},pair-${i},${10*(i+1)}\nTreatment,unit-${i},t-${i},tf-${i},day-${i},pair-${i},${10*(i+1)+[1,2,4][i]}\n`).join("");
 await page.getByLabel("数値CSV",{exact:true}).setInputFiles({name:"synthetic-measurements.csv",mimeType:"text/csv",buffer:Buffer.from(csv)});
 const table=await mutation(page,"/tables",()=>page.getByRole("button",{name:"数値表を登録",exact:true}).click());
 await expect(page.getByLabel("基準群",{exact:true})).toHaveValue("Control");
 await page.getByLabel("独立実験単位と対応関係を確認しました。").check();
 const stats=await mutation(page,"/statistics",()=>page.getByRole("button",{name:"統計と図を生成",exact:true}).click());
 await waitJob(page,stats.job_id);
 await expect(page.getByRole("button",{name:"数値表の再実行パッケージ ↓",exact:true})).toBeVisible();
 await page.getByLabel("解析するデータ",{exact:true}).selectOption("images");
 await expect(page.getByRole("heading",{name:"統計結果",exact:true})).toHaveCount(0);
 await page.getByLabel("解析するデータ",{exact:true}).selectOption(table.table_id);
 await expect(page.getByRole("heading",{name:"統計結果",exact:true})).toBeVisible();
 for(const file of ["analysis.zip","methods.md"]){const response=await page.request.get(api+`/v1/jobs/${stats.job_id}/files/${file}`);expect(response.status()).toBe(200);expect((await response.body()).length).toBeGreaterThan(100);}
});
