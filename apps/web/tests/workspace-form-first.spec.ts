import {aiReadFixture} from "./ai-read-fixture";
import {expect,test} from "@playwright/test";
import {mkdir,writeFile} from "node:fs/promises";
import path from "node:path";
import type {ImportedField,WorkspaceSelection} from "../src/lib/workspace/api-adapter";
import type {ExperimentDesign} from "../src/lib/workspace/experiment-design";

/** Transport/UI contract only: the bytes are not microscopy images (#284 W5, W6). A new workspace opens on adding
 * images; choices accumulate in the list, 追加 registers them, and the experiment view assigns them to a group only
 * on the researcher's choice: a selected row and its target, or folder suggestions applied with 「案を適用」. */
test("images come first, accumulate across choices, and go to the group the researcher assigns",async({page,context})=>{
  const workspace={id:"w",title:"画像解析",active_revision:null,created:1,expires:9999999999,deleted:false};
  let fields:ImportedField[]=[];
  let selection:WorkspaceSelection={version:0,entries:[]};
  let specification:{version:number;spec:{experiment?:ExperimentDesign}|null}={version:0,spec:null};
  let created=false,uploads=0;
  const unexpected:string[]=[],pageErrors:string[]=[];
  page.on("pageerror",error=>pageErrors.push(error.message));
  await context.route("**/v1/**",async route=>{
    if(await aiReadFixture(route))return;

    const request=route.request(),path=new URL(request.url()).pathname,method=request.method();
    const headers={"Access-Control-Allow-Origin":new URL(page.url()).origin,"Access-Control-Allow-Credentials":"true","Access-Control-Allow-Headers":"content-type,x-cytellect-request","Access-Control-Allow-Methods":"GET,POST,PUT,DELETE,OPTIONS"};
    const json=(body:unknown,status=200)=>route.fulfill({status,headers,contentType:"application/json",body:JSON.stringify(body)});
    if(method==="OPTIONS")return route.fulfill({status:204,headers});
    if(path==="/v1/session")return json({authenticated:true,retention_hours:24,demo:false});
    if(path==="/v1/workspaces"){if(method==="POST"){created=true;return json(workspace,201);}return json(created?[workspace]:[]);}
    if(path==="/v1/workspaces/w")return json(workspace);
    if(path.endsWith("/selection")){
      if(method==="POST"){
        const body=request.postDataJSON() as WorkspaceSelection;
        if(body.version!==selection.version)return json({detail:"workspace_selection_changed"},409);
        selection={...body,version:selection.version+1};
      }
      return json(selection);
    }
    if(path.endsWith("/region-fields")){
      if(method==="POST"){
        uploads++;
        const key=/"client_upload_id":"([^"]+)"/.exec(request.postDataBuffer()!.toString())?.[1];
        const field:ImportedField={id:`f${uploads}`,workspace_id:"w",metadata:{},image_info:{shape:[32,32],input_mode:"native",channels:[{channel_id:"c1",label:"c1",stain:null},{channel_id:"c2",label:"c2",stain:null}]}};
        fields=[...fields,field];
        selection={...selection,entries:selection.entries.map(entry=>entry.id===key&&!entry.field_id?{...entry,field_id:field.id}:entry)};
        return json(field,201);
      }
      return json(fields);
    }
    if(path.endsWith("/analysis-spec")){
      if(method==="PUT"){const body=request.postDataJSON();expect(body.version).toBe(specification.version);specification={version:specification.version+1,spec:body.spec};}
      return json(specification);
    }
    if(path.endsWith("/channel-assignments"))return json({version:0,assignments:[],global_field_ids:[],groups:[]});
    if(path.endsWith("/field-links"))return json({version:0,entries:[]});
    if(path.endsWith("/revisions")||path.endsWith("/jobs")||path.endsWith("/runs"))return json([]);
    if(path.endsWith("/preview"))return route.fulfill({headers,contentType:"image/svg+xml",body:'<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"><rect width="32" height="32" fill="#182237"/></svg>'});
    if(path==="/v1/intake/inspect")return json({kind:"native",role:"image",code:null,sha256:"0".repeat(64),bytes:3,shape:[32,32],dtype:"uint16",channel_names:null,thumbnail_png:null});
    unexpected.push(`${method} ${path}`);
    return json({detail:"unexpected_route"},404);
  });
  const loaded=page.waitForResponse(response=>new URL(response.url()).pathname==="/v1/workspaces"&&response.request().method()==="GET");
  await page.goto("/workspace");
  await loaded;
  await expect(page.getByRole("heading",{name:"画像を追加",exact:true,level:1})).toBeVisible();
  // A second choice adds to the first instead of replacing it (#284 input 3); both stains join one field.
  await page.getByTestId("file-input").setInputFiles([{name:"A01_c1.tif",mimeType:"image/tiff",buffer:Buffer.from([1,2,3])}]);
  const list=page.getByRole("region",{name:"取り込みの一覧"});
  await expect(list.getByRole("status")).toHaveText("受け取り：1 · 画像：1（1 視野）");
  await page.getByTestId("file-input").setInputFiles([{name:"A01_c2.tif",mimeType:"image/tiff",buffer:Buffer.from([4,5,6])}]);
  await expect(list.getByRole("status")).toHaveText("受け取り：2 · 画像：2（1 視野）");
  await expect(list.getByRole("row").filter({hasText:"C1 · C2"})).toContainText("追加待ち");
  expect(uploads).toBe(0);
  await list.getByRole("button",{name:"追加",exact:true}).click();
  await expect.poll(()=>uploads).toBe(1);
  // No group is assumed: the experiment view lists the field without a suggestion, and the researcher assigns it.
  await page.getByRole("navigation",{name:"作業の切替"}).getByRole("button",{name:"実験",exact:true}).click();
  await page.getByRole("button",{name:/^2 画面/}).click();
  const table=page.getByRole("region",{name:"群・実験回が未割り当ての視野"});
  await expect(table.getByRole("row").filter({hasText:"A01"})).toContainText("案なし");
  await expect(table.getByRole("button",{name:"案を適用"})).toHaveCount(0);
  const run=new Date().toISOString().slice(0,10);
  await table.getByLabel("A01 を選択").check();
  await table.getByLabel("選択した視野の割付先").selectOption({label:`${run} · 処理`});
  await table.getByRole("button",{name:/^選択した視野を割付/}).click();
  await expect(table).toHaveCount(0);
  const design=specification.spec!.experiment!;
  const treated=design.groups.find(group=>group.label==="処理")!;
  expect(design.layout).toBe("pair");
  expect(design.fields?.f1).toMatchObject({group_id:treated.id,run_id:design.runs![0].id});
  await expect(page.getByRole("cell").filter({hasText:"処理 · 1 視野"})).toBeVisible();
  // The image view opens with the settings panel closed, as the demo does.
  await page.getByRole("navigation",{name:"作業の切替"}).getByRole("button",{name:"画像",exact:true}).click();
  await expect(page.getByRole("button",{name:"2 画面",exact:true})).toHaveAttribute("aria-pressed","true");
  await expect(page.getByRole("complementary",{name:"画像解析",exact:true})).toHaveCount(0);
  await page.getByRole("button",{name:"設定パネル",exact:true}).click();
  await expect(page.getByRole("complementary",{name:"画像解析",exact:true})).toBeVisible();
  expect(unexpected).toEqual([]);
  expect(pageErrors).toEqual([]);
});

test("a folder of runs and groups is suggested as such, and applied only with 「案を適用」 (#284 W6, synthetic bytes)",async({page,context})=>{
  const root=path.join(test.info().outputDir,"Rep1");
  for(const [group,byte] of [["未処理",1],["ActD 1 µM",7]] as const)for(const [index,stain] of ["Hoechst","C02","C03"].entries()){
    await mkdir(path.join(root,group),{recursive:true});await writeFile(path.join(root,group,`視野01-${stain}.tif`),Buffer.from([byte+index,9,9]));}
  const workspace={id:"w",title:"画像解析",active_revision:null,created:1,expires:9999999999,deleted:false};
  let fields:ImportedField[]=[],selection:WorkspaceSelection={version:0,entries:[]},specification:{version:number;spec:{experiment?:ExperimentDesign}|null}={version:0,spec:null},created=false;
  const pageErrors:string[]=[];page.on("pageerror",error=>pageErrors.push(error.message));
  await context.route("**/v1/**",async route=>{
    if(await aiReadFixture(route))return;
    const request=route.request(),pathname=new URL(request.url()).pathname,method=request.method();
    const headers={"Access-Control-Allow-Origin":new URL(page.url()).origin,"Access-Control-Allow-Credentials":"true","Access-Control-Allow-Headers":"content-type,x-cytellect-request","Access-Control-Allow-Methods":"GET,POST,PUT,DELETE,OPTIONS"};
    const json=(body:unknown,status=200)=>route.fulfill({status,headers,contentType:"application/json",body:JSON.stringify(body)});
    if(method==="OPTIONS")return route.fulfill({status:204,headers});
    if(pathname==="/v1/session")return json({authenticated:true,retention_hours:24,demo:false});
    if(pathname==="/v1/workspaces"){if(method==="POST"){created=true;return json(workspace,201);}return json(created?[workspace]:[]);}
    if(pathname==="/v1/workspaces/w")return json(workspace);
    if(pathname.endsWith("/selection")){if(method==="POST"){const body=request.postDataJSON() as WorkspaceSelection;if(body.version!==selection.version)return json({detail:"workspace_selection_changed"},409);selection={...body,version:selection.version+1};}return json(selection);}
    if(pathname.endsWith("/region-fields")){if(method==="POST"){const key=/"client_upload_id":"([^"]+)"/.exec(request.postDataBuffer()!.toString())?.[1];
      const field:ImportedField={id:`f${fields.length+1}`,workspace_id:"w",metadata:{},image_info:{shape:[32,32],input_mode:"native",channels:["hoechst","c02","c03"].map(id=>({channel_id:id,label:id,stain:null}))}};
      fields=[...fields,field];selection={...selection,entries:selection.entries.map(entry=>entry.id===key&&!entry.field_id?{...entry,field_id:field.id}:entry)};return json(field,201);}return json(fields);}
    if(pathname.endsWith("/analysis-spec")){if(method==="PUT"){const body=request.postDataJSON();specification={version:specification.version+1,spec:body.spec};}return json(specification);}
    if(pathname==="/v1/intake/inspect")return json({kind:"native",role:"image",code:null,sha256:"0".repeat(64),bytes:3,shape:[32,32],dtype:"uint16",channel_names:null,thumbnail_png:null});
    if(pathname.endsWith("/channel-assignments"))return json({version:0,assignments:[],global_field_ids:[],groups:[]});
    if(pathname.endsWith("/field-links"))return json({version:0,entries:[]});
    if(pathname.endsWith("/revisions")||pathname.endsWith("/jobs")||pathname.endsWith("/runs"))return json([]);
    if(pathname.endsWith("/assistant-messages"))return json({messages:[]});
    if(pathname.endsWith("/preview"))return route.fulfill({headers,contentType:"image/svg+xml",body:'<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"/>'});
    return json({detail:"unexpected_route"},404);
  });
  await page.goto("/workspace");
  await expect(page.getByRole("heading",{name:"画像を追加",exact:true,level:1})).toBeVisible();
  await page.getByTestId("folder-input").setInputFiles(root);
  const list=page.getByRole("region",{name:"取り込みの一覧"});
  await expect(list.getByRole("status")).toHaveText("受け取り：6 · 画像：6（2 視野）");
  await list.getByRole("button",{name:"追加",exact:true}).click();
  await expect.poll(()=>fields.length).toBe(2);
  await page.getByRole("navigation",{name:"作業の切替"}).getByRole("button",{name:"実験",exact:true}).click();
  // Before a design, the folders' suggestion is stated; the form is still the researcher's choice.
  await expect(page.getByRole("status").filter({hasText:"フォルダーからの案：2 群（未処理、ActD 1 µM） · 実験回 1"})).toBeVisible();
  await page.getByRole("button",{name:/^2 画面/}).click();
  const table=page.getByRole("region",{name:"群・実験回が未割り当ての視野"});
  await expect(table.getByRole("cell").filter({hasText:"Rep1 · 未処理"})).toBeVisible();
  await expect(table.getByRole("cell").filter({hasText:"Rep1 · ActD 1 µM"})).toBeVisible();
  expect(Object.keys(specification.spec?.experiment?.fields??{})).toEqual([]);
  await table.getByRole("button",{name:"案を適用",exact:true}).click();
  await expect(table).toHaveCount(0);
  const design=specification.spec!.experiment!;
  const rep1=design.runs!.find(run=>run.label==="Rep1")!;
  const byGroup=Object.fromEntries(design.groups.map(group=>[group.label,Object.entries(design.fields??{}).filter(([,value])=>value.group_id===group.id&&value.run_id===rep1.id).length]));
  expect(byGroup).toEqual({"未処理":1,"ActD 1 µM":1});
  expect(fields.every(field=>field.image_info.channels.length===3)).toBe(true);
  expect(pageErrors).toEqual([]);
});
