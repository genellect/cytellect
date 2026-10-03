import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { expectGfpPreview } from "./image-preview";
const root=path.resolve(__dirname,"../../..");
const origin=process.env.CYTELLECT_WEB_URL||"http://127.0.0.1:8765";
test("local package starts without invitation, processes real GFP, and retains work",async({page})=>{
 test.skip(process.env.CYTELLECT_TEST_LOCAL!=="1","Requires an isolated packaged local runtime");
 const errors:string[]=[];const external:string[]=[];
 page.on("pageerror",e=>errors.push(e.message));
 page.on("request",r=>{if(/^https?:/.test(r.url())&&new URL(r.url()).origin!==new URL(origin).origin)external.push(r.url());});
 const startupAt=Date.now();const startupHttp:{session:number|null;setup:number|null}={session:null,setup:null};
 page.on("response",response=>{const pathname=new URL(response.url()).pathname;if(pathname==="/v1/session")startupHttp.session=response.status();if(pathname==="/v1/local/setup")startupHttp.setup=response.status();});
 await page.goto("/");
 try{await expect(page.getByRole("heading",{name:"ワークスペース",exact:true})).toBeVisible();}
 catch(error){
  // Fixed categories only: never emit cookies, response bodies, URLs or research-bearing DOM.
  try{
   const [loading,login,workspace,startEnabled,cookies]=await Promise.all([
    page.getByText("ワークスペースを開いています…",{exact:true}).isVisible(),
    page.getByRole("heading",{name:"ワークスペース",exact:true}).isVisible(),
    page.getByRole("heading",{name:"実験ワークスペース",exact:true}).isVisible(),
    page.getByRole("button",{name:"解析を開始",exact:false}).evaluateAll(buttons=>buttons.some(button=>!(button as HTMLButtonElement).disabled)),
    page.context().cookies(origin),
   ]);
   console.log("CYTELLECT_LOCAL_BOOTSTRAP_DIAGNOSTIC",JSON.stringify({version:1,elapsed_ms:Date.now()-startupAt,session_http_status:startupHttp.session,setup_http_status:startupHttp.setup,loading_visible:loading,login_heading_visible:login,workspace_heading_visible:workspace,start_button_enabled:startEnabled,cookie_count:cookies.length,page_error_count:errors.length}));
  }catch{/* Diagnostics must never replace the original assertion failure. */}
  throw error;
 }
 await expect(page.getByRole("button",{name:"解析を開始",exact:false})).toBeEnabled();
 await expect(page.getByLabel("招待コード",{exact:true})).toHaveCount(0);
 const unauthenticated=await page.request.get(origin+"/v1/session");expect(unauthenticated.status()).toBe(401);
 const screenshot=process.env.CYTELLECT_SCREENSHOT_DIR;
 if(screenshot){fs.mkdirSync(screenshot,{recursive:true});await page.screenshot({path:path.join(screenshot,"local-start-desktop.png"),fullPage:true});}
 await page.setViewportSize({width:390,height:844});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
 if(screenshot)await page.screenshot({path:path.join(screenshot,"local-start-mobile.png"),fullPage:true});
 await page.setViewportSize({width:1440,height:1000});
 await page.getByRole("button",{name:"解析を開始",exact:false}).click();
 await expect(page.getByRole("heading",{name:"新しい作業",exact:true})).toBeVisible();
 const cookies=await page.context().cookies(origin);
 expect(cookies.some(c=>c.httpOnly&&c.sameSite==="Strict")).toBe(true);
 const denied=await page.request.post(origin+"/v1/local/session",{headers:{Origin:"https://example.com","X-Cytellect-Request":"1"}});
 expect(denied.status()).toBe(403);
 const title="Public GFP local browser check "+Date.now();
 await page.getByLabel("作業名",{exact:true}).fill(title);
 await page.getByRole("combobox",{name:"解析の種類",exact:true}).selectOption("nuclear");
 await page.getByRole("button",{name:"作業を作成"}).click();
 await page.getByText("＋ 画像を登録",{exact:true}).click();
 await page.getByLabel("測定対象",{exact:true}).selectOption("gfp");
 for(const role of ["dapi","gfp"])await page.locator(`input[name="${role}"]`).setInputFiles(path.join(root,"fixtures/public/bbbc013",`A01-${role}.tif`));
 await page.getByLabel("群",{exact:true}).fill("BBBC013 A01");
 await page.getByLabel("独立実験単位",{exact:true}).fill("public-plate");
 await page.getByLabel("試料",{exact:true}).fill("A01");
 await page.getByLabel("撮影日／バッチ",{exact:true}).fill("public-acquisition");
 await page.getByLabel("登録する画像の染色とチャンネル対応を確認しました。").check();
 await page.getByRole("button",{name:"この視野を登録",exact:true}).click();
 await expect(page.getByLabel("レシピ",{exact:true})).toHaveValue("gfp-nuclear-2d");
 await page.getByRole("button",{name:"背景ROI",exact:true}).click();
 await page.getByText("座標から多角形を指定",{exact:true}).click();
 await page.getByLabel("頂点（x,y を空白または改行で区切る）").fill("1,1 4,1 4,4 1,4");
 await page.getByRole("button",{name:"座標を反映",exact:true}).click();
 await page.getByRole("button",{name:/背景を確定/}).click();
 const mutation=async(suffix:string,action:()=>Promise<void>)=>{
  const pending=page.waitForResponse(r=>r.url().endsWith(suffix)&&r.request().method()==="POST");await action();
  const response=await pending;expect(response.ok(),await response.text()).toBeTruthy();return response.json();
 };
 const waitJob=async(id:string)=>{
  await expect.poll(async()=>{const r=await page.request.get(origin+"/v1/jobs/"+id);const j=await r.json();if(["failed","cancelled"].includes(j.state))throw Error("Local test job failed: "+j.error);return j.state;},{timeout:600000,intervals:[1000,2000,3000]}).toBe("succeeded");
 };
 const trial=await mutation("/analyses",()=>page.getByRole("button",{name:"この視野で試す",exact:true}).click());
 await waitJob(trial.job_id);
 await expect(page.getByRole("columnheader",{name:"GFP 補正平均",exact:true})).toBeVisible();
 const response=await page.request.get(origin+`/v1/revisions/${trial.revision_id}/measurements`);
 const report=await response.json();expect(report.cells.length).toBeGreaterThan(100);expect(report.nucleoli).toHaveLength(0);
 await expectGfpPreview(page);
 if(screenshot)await page.screenshot({path:path.join(screenshot,"local-gfp-workbench.png"),fullPage:true});
 await page.getByLabel("領域、背景、対象選別、失敗・除外理由を確認しました。").check();
 await mutation("/review",()=>page.getByRole("button",{name:"品質確認を完了",exact:true}).click());
 await page.getByRole("button",{name:/03 保存と履歴/}).click();
 const pending=page.waitForResponse(r=>r.url().includes("/export?")&&r.request().method()==="POST");
 await page.getByRole("button",{name:"解析パッケージを生成",exact:true}).click();const exported=await (await pending).json();
 await waitJob(exported.job_id);
 await expect(page.getByRole("button",{name:"ZIPを保存 ↓",exact:true})).toBeVisible();
 const saved=page.waitForEvent("download");await page.getByRole("button",{name:"ZIPを保存 ↓",exact:true}).click();expect((await saved).suggestedFilename()).toBe("cytellect-analysis.zip");
 await page.reload();
 await expect(page.getByRole("heading",{name:"実験ワークスペース",exact:true})).toBeVisible();
 await expect(page.getByRole("button",{name:new RegExp(title)})).toBeVisible();
 expect(await page.evaluate(()=>({local:localStorage.length,session:sessionStorage.length}))).toEqual({local:0,session:0});
 expect(external).toEqual([]);expect(errors).toEqual([]);
});
