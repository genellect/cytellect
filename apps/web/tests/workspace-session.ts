/** Shared browser-test bootstrap. Local acceptance never creates invitation tokens. */
import {expect,type Page} from "@playwright/test";
import {execFileSync} from "node:child_process";
import path from "node:path";

const root=path.resolve(__dirname,"../../..");

export function workspaceTestRuntime(env:Record<string,string|undefined>=process.env){
 const local=env.CYTELLECT_TEST_LOCAL==="1";
 const api=env.CYTELLECT_TEST_API_ORIGIN||"http://localhost:8000";
 const python=env.CYTELLECT_TEST_PYTHON||path.join(root,".venv",process.platform==="win32"?"Scripts/python.exe":"bin/python");
 const dataDir=env.CYTELLECT_TEST_DATA_DIR;
 if(local){
  if(!env.CYTELLECT_WEB_URL||!env.CYTELLECT_TEST_API_ORIGIN||!env.CYTELLECT_TEST_PYTHON||!dataDir)
   throw Error("Local acceptance requires explicit Web/API origin, Python and private data directory");
  const web=new URL(env.CYTELLECT_WEB_URL), backend=new URL(api);
  if(web.origin!==backend.origin||web.hostname!=="127.0.0.1"||web.protocol!=="http:"||
     [web,backend].some(url=>url.username||url.password||url.search||url.hash||url.pathname!=="/"))
   throw Error("Local acceptance requires the same literal loopback Web/API origin");
  const relative=path.relative(root,path.resolve(dataDir));
  if(!path.isAbsolute(python)||!path.isAbsolute(dataDir)||!relative||
     (!relative.startsWith(`..${path.sep}`)&&relative!==".."&&!path.isAbsolute(relative)))
   throw Error("Local acceptance requires an explicit interpreter and data outside the checkout");
 }
 return {api,python,dataDir,local};
}

export async function createRegionWorkspace(page:Page,title:string){
 const runtime=workspaceTestRuntime();
 await page.goto("/legacy");
 if(runtime.local){
  expect(new URL(page.url()).origin).toBe(new URL(runtime.api).origin);
  const setup=await page.request.get(`${runtime.api}/v1/local/setup`);
  expect(setup.ok()).toBeTruthy();
  expect(await setup.json()).toMatchObject({mode:"local",ready:true,fiji_configured:true});
  await expect(page.getByLabel("招待コード",{exact:true})).toHaveCount(0);
  await page.getByRole("button",{name:"解析を開始",exact:false}).click();
 }else{
  if(!runtime.dataDir)throw Error("An isolated browser test data directory is required");
  // Capture the one-use value in memory only. Do not emit it to logs or receipts.
  const token=execFileSync(runtime.python,["-c","import os;from pathlib import Path;from cytellect_api.db import Store;print(Store(Path(os.environ['CYTELLECT_TEST_DATA_DIR'])).invite(300))"],
   {encoding:"utf8",env:process.env,stdio:["ignore","pipe","ignore"]}).trim();
  await page.getByLabel("招待コード",{exact:true}).fill(token);
  await page.getByRole("button",{name:"ワークスペースに接続"}).click();
 }
 await page.getByLabel("作業名",{exact:true}).fill(title);
 await expect(page.getByRole("combobox",{name:"解析の種類",exact:true})).toHaveValue("regions");
 const pending=page.waitForResponse(response=>new URL(response.url()).pathname==="/v1/workspaces"&&response.request().method()==="POST");
 await page.getByRole("button",{name:"作業を作成",exact:true}).click();
 const response=await pending;
 expect(response.ok()).toBeTruthy();
 return response.json();
}
