import {aiReadFixture} from "./ai-read-fixture";
import {expect,test,type BrowserContext,type Page} from "@playwright/test";
import type {ImportedField,WorkspaceSelection} from "../src/lib/workspace/api-adapter";
import type {ExperimentDesign} from "../src/lib/workspace/experiment-design";

/** Transport/UI contract only: the bytes are not microscopy images (#284 W1). The API stand-in mirrors its rules: the
 * version check, a field's row never disappears, a row without a field may be removed, and an upload sent again under
 * the same row key resolves that row. Bytes "BAD" are refused as unreadable; a name with "labels" as a 32-bit mask. */
async function serve(page:Page,context:BrowserContext,options:{existing?:boolean}={}){
  const workspace={id:"w",title:"画像解析",active_revision:null,created:1,expires:9999999999,deleted:false};
  const state={fields:[] as ImportedField[],selection:{version:0,entries:[]} as WorkspaceSelection,
    specification:{version:0,spec:null} as {version:number;spec:{experiment?:ExperimentDesign}|null},created:!!options.existing,unexpected:[] as string[],pageErrors:[] as string[]};
  page.on("pageerror",error=>state.pageErrors.push(error.message));
  await context.route("**/v1/**",async route=>{
    if(await aiReadFixture(route))return;
    const request=route.request(),path=new URL(request.url()).pathname,method=request.method();
    const headers={"Access-Control-Allow-Origin":new URL(page.url()).origin,"Access-Control-Allow-Credentials":"true","Access-Control-Allow-Headers":"content-type,x-cytellect-request","Access-Control-Allow-Methods":"GET,POST,PUT,DELETE,OPTIONS"};
    const json=(body:unknown,status=200)=>route.fulfill({status,headers,contentType:"application/json",body:JSON.stringify(body)});
    if(method==="OPTIONS")return route.fulfill({status:204,headers});
    if(path==="/v1/session")return json({authenticated:true,retention_hours:24,demo:false});
    if(path==="/v1/workspaces"){if(method==="POST"){state.created=true;return json(workspace,201);}return json(state.created?[workspace]:[]);}
    if(path==="/v1/workspaces/w")return json(workspace);
    if(path.endsWith("/selection")){
      if(method==="POST"){
        const body=request.postDataJSON() as WorkspaceSelection;
        if(body.version!==state.selection.version)return json({detail:"workspace_selection_changed"},409);
        if(state.selection.entries.some(entry=>entry.field_id&&!body.entries.some(value=>value.id===entry.id)))return json({detail:"workspace_entries_cannot_disappear"},409);
        state.selection={...body,version:state.selection.version+1};
      }
      return json(state.selection);
    }
    if(path.endsWith("/region-fields")){
      if(method==="POST"){
        const upload=request.postDataBuffer()!.toString();
        if(upload.includes("labels"))return json({detail:"region_image_bit_depth_unsupported"},422);
        if(upload.includes("BAD"))return json({detail:"unsupported_or_invalid_region_image"},422);
        const key=/"client_upload_id":"([^"]+)"/.exec(upload)?.[1];
        const field:ImportedField={id:`field-${state.fields.length+1}`,workspace_id:"w",metadata:{},image_info:{shape:[32,32],input_mode:"native",channels:[{channel_id:"c1",label:"c1",stain:null}]}};
        state.fields=[...state.fields,field];
        // The API joins a field to the row whose key it was sent under (selection_at).
        state.selection={...state.selection,entries:state.selection.entries.map(entry=>entry.id===key&&!entry.field_id?{...entry,field_id:field.id}:entry)};
        return json(field,201);
      }
      return json(state.fields);
    }
    if(path.endsWith("/analysis-spec")){
      if(method==="PUT"){const body=request.postDataJSON();if(body.version!==state.specification.version)return json({detail:"analysis_spec_changed"},409);state.specification={version:state.specification.version+1,spec:body.spec};}
      return json(state.specification);
    }
    if(path.endsWith("/channel-assignments"))return json({version:0,assignments:[],global_field_ids:[],groups:[]});
    if(path.endsWith("/field-links"))return json({version:0,entries:[]});
    if(path.endsWith("/revisions")||path.endsWith("/jobs")||path.endsWith("/runs"))return json([]);
    if(path.endsWith("/preview"))return route.fulfill({headers,contentType:"image/svg+xml",body:'<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"><rect width="32" height="32" fill="#182237"/></svg>'});
    state.unexpected.push(`${method} ${path}`);
    return json({detail:"unexpected_route"},404);
  });
  return state;
}
const tiff=(name:string,content:string)=>({name,mimeType:"image/tiff",buffer:Buffer.from(content)});

test("a refused image never stops the others, keeps its name and reason after a reload, and is replaced or removed without a reason",async({page,context})=>{
  const state=await serve(page,context,{existing:true});
  const loaded=page.waitForResponse(response=>new URL(response.url()).pathname.endsWith("/analysis-spec"));
  await page.goto("/workspace?id=w");
  await loaded;
  await page.getByTestId("file-input").setInputFiles([tiff("A01_c1.tif","ok-1"),tiff("A01-labels.tif","mask"),tiff("broken_c1.tif","BAD"),{name:"読み方.txt",mimeType:"text/plain",buffer:Buffer.from("notes")}]);
  await page.getByRole("button",{name:/^実験デザインなしで登録/}).click();
  // The result of the choice, item by item; no alert, no reason to type.
  await expect(page.getByRole("status").filter({hasText:"登録：1 視野 · 読み取れない：1 件 · マスクの候補：1 件 · 対象外：1 件"})).toBeVisible();
  await expect(page.getByRole("alert").filter({hasText:/\S/})).toHaveCount(0);
  const list=page.locator("details").filter({hasText:/^取込 \d+件/});
  await expect(list.locator("li").filter({hasText:"broken_c1.tif：読み取り不可"})).toBeVisible();
  await expect(list.locator("li").filter({hasText:"A01-labels.tif：マスクの候補 · 32-bit 整数ラベル"})).toBeVisible();
  await expect(list.locator("li").filter({hasText:"読み方.txt：対象外 · TIFF 以外"})).toBeVisible();
  await expect(page.getByLabel(/除外の理由/)).toHaveCount(0);
  await expect(page.getByText(/import-[0-9a-f]/)).toHaveCount(0);
  const rows=()=>state.selection.entries.filter(entry=>!entry.field_id);
  expect(rows().map(entry=>[entry.intake?.names,entry.intake?.code]).sort()).toEqual([[["A01-labels.tif"],"region_image_bit_depth_unsupported"],[["broken_c1.tif"],"unsupported_or_invalid_region_image"]]);
  // Statistics are not blocked by the refused images.
  await page.getByRole("button",{name:"統計",exact:true}).click();
  await expect(page.getByText(/比較の前に/)).toHaveCount(0);
  // After a reload the rows keep their names and reasons (#284 involvement 3).
  const reloaded=page.waitForResponse(response=>new URL(response.url()).pathname.endsWith("/analysis-spec"));
  await page.reload();
  await reloaded;
  await page.getByText("取込 2件",{exact:true}).click();
  await expect(page.getByText("名称不明",{exact:true})).toHaveCount(0);
  const broken=page.locator("li").filter({hasText:"broken_c1.tif"});
  await expect(broken).toContainText("読み取り不可");
  // Replace: the same row is resolved; no new row.
  const entry=rows().find(value=>value.intake?.names[0]==="broken_c1.tif")!.id;
  await broken.getByRole("button",{name:"差し替え",exact:true}).click();
  await page.getByTestId("replace-input").setInputFiles([tiff("broken_c1.tif","ok-2")]);
  await expect(page.locator("li").filter({hasText:"broken_c1.tif"})).toHaveCount(0);
  expect(state.selection.entries.filter(value=>value.id===entry)).toEqual([expect.objectContaining({field_id:"field-2",intake:{names:["broken_c1.tif"],state:"registered"}})]);
  // Remove: the mask candidate's row goes; the registered fields stay.
  await page.getByText("取込 1件",{exact:true}).click();
  await page.locator("li").filter({hasText:"A01-labels.tif"}).getByRole("button",{name:"記録から削除",exact:true}).click();
  await expect(page.getByText(/^取込 \d+件$/)).toHaveCount(0);
  expect(state.selection.entries.map(value=>value.field_id)).toEqual(["field-1","field-2"]);
  expect(state.unexpected).toEqual([]);
  expect(state.pageErrors).toEqual([]);
});

test("images added in a group's cell go to that group, though another image of the same choice is refused (#284 control C)",async({page,context})=>{
  const state=await serve(page,context);
  const loaded=page.waitForResponse(response=>new URL(response.url()).pathname==="/v1/workspaces"&&response.request().method()==="GET");
  await page.goto("/workspace");
  await loaded;
  await page.getByRole("button",{name:/^2 画面/}).click();
  const design=()=>state.specification.spec!.experiment!;
  await expect.poll(()=>state.specification.spec?.experiment?.groups.length).toBe(2);
  const control=design().groups.find(group=>group.id===design().control_group_id)!;
  const cell=page.getByRole("cell").filter({hasText:control.label}).first();
  const chooser=page.waitForEvent("filechooser");
  await cell.getByRole("button",{name:"画像を追加",exact:true}).click();
  await (await chooser).setFiles([tiff("BBBC007-a9-C01.tif","a9-1"),tiff("BBBC007-a9-C02.tif","a9-2"),tiff("BBBC007-f9620-C01.tif","f-1"),tiff("BBBC007-f9620-C02.tif","f-2"),tiff("test-truncated-DRAQ.tif","BAD")]);
  await expect(page.getByRole("status").filter({hasText:"登録：2 視野 · 読み取れない：1 件"})).toBeVisible();
  await expect.poll(()=>Object.keys(design().fields??{}).sort()).toEqual(["field-1","field-2"]);
  expect(Object.values(design().fields!).every(value=>value.group_id===control.id&&value.run_id===design().runs![0].id)).toBe(true);
  // The refused image keeps its group, so the n breakdown counts it there.
  expect(state.selection.entries.find(entry=>!entry.field_id)?.intake).toMatchObject({names:["test-truncated-DRAQ.tif"],state:"rejected",target:{group_id:control.id}});
  await expect(cell).toContainText("2 視野");
  expect(state.unexpected).toEqual([]);
  expect(state.pageErrors).toEqual([]);
});
