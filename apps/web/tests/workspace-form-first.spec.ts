import {expect,test} from "@playwright/test";
import type {ImportedField,WorkspaceSelection} from "../src/lib/workspace/api-adapter";
import type {ExperimentDesign} from "../src/lib/workspace/experiment-design";

/** Transport/UI contract only: the bytes are not microscopy images. Images added before the form of the
 * experiment is chosen wait for that choice, and two screens put them in the group the researcher names. */
test("images added before the form wait for it and go to the chosen group of two screens",async({page,context})=>{
  const workspace={id:"w",title:"画像解析",active_revision:null,created:1,expires:9999999999,deleted:false};
  let fields:ImportedField[]=[];
  let selection:WorkspaceSelection={version:0,entries:[]};
  let specification:{version:number;spec:{experiment?:ExperimentDesign}|null}={version:0,spec:null};
  let created=false,uploads=0;
  const unexpected:string[]=[],pageErrors:string[]=[];
  page.on("pageerror",error=>pageErrors.push(error.message));
  await context.route("**/v1/**",async route=>{
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
        fields=[{id:"f1",workspace_id:"w",metadata:{},image_info:{shape:[32,32],input_mode:"native",channels:[{channel_id:"c1",label:"c1",stain:null},{channel_id:"c2",label:"c2",stain:null}]}}];
        return json(fields[0],201);
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
    unexpected.push(`${method} ${path}`);
    return json({detail:"unexpected_route"},404);
  });
  const loaded=page.waitForResponse(response=>new URL(response.url()).pathname==="/v1/workspaces"&&response.request().method()==="GET");
  await page.goto("/workspace");
  await loaded;
  await expect(page.getByRole("heading",{name:"解析の形を選ぶ",exact:true,level:1})).toBeVisible();
  await page.getByTestId("file-input").setInputFiles([{name:"A01_c1.tif",mimeType:"image/tiff",buffer:Buffer.from([1,2,3])},{name:"A01_c2.tif",mimeType:"image/tiff",buffer:Buffer.from([4,5,6])}]);
  // Nothing is registered until the form is chosen.
  await expect(page.getByRole("status").filter({hasText:"画像 2 件を受け取りました。"})).toBeVisible();
  expect(uploads).toBe(0);
  await page.getByRole("button",{name:/^2 画面/}).click();
  const place=page.getByRole("region",{name:"受け取った画像の追加先"});
  await expect(place).toBeVisible();
  expect(uploads).toBe(0);
  // No group is assumed: the researcher names it.
  await expect(place.getByRole("button",{name:"追加",exact:true})).toBeDisabled();
  const run=new Date().toISOString().slice(0,10);
  await place.getByLabel("追加先",{exact:true}).selectOption({label:`${run} · 処理`});
  await place.getByRole("button",{name:"追加",exact:true}).click();
  await expect(place).toHaveCount(0);
  expect(uploads).toBe(1);
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
