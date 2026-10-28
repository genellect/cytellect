import {expect,test} from "@playwright/test";
import type {ImportedField,WorkspaceSelection} from "../src/lib/workspace/api-adapter";

/** Transport/UI contract only: the bytes are not microscopy images. The ledger mirrors the API rules
 * (version check, entries never disappear) so a rejected import cannot be dropped silently. */
test("a rejected image is named, kept in the record and left out only with a reason",async({page,context})=>{
  const workspace={id:"w",title:"画像解析",active_revision:null,created:1,expires:9999999999,deleted:false};
  let fields:ImportedField[]=[];
  let selection:WorkspaceSelection={version:0,entries:[]};
  const unexpected:string[]=[],pageErrors:string[]=[];
  page.on("pageerror",error=>pageErrors.push(error.message));
  await context.route("**/v1/**",async route=>{
    const request=route.request(),path=new URL(request.url()).pathname,method=request.method();
    const headers={"Access-Control-Allow-Origin":new URL(page.url()).origin,"Access-Control-Allow-Credentials":"true","Access-Control-Allow-Headers":"content-type,x-cytellect-request","Access-Control-Allow-Methods":"GET,POST,PUT,DELETE,OPTIONS"};
    const json=(body:unknown,status=200)=>route.fulfill({status,headers,contentType:"application/json",body:JSON.stringify(body)});
    if(method==="OPTIONS")return route.fulfill({status:204,headers});
    if(path==="/v1/session")return json({authenticated:true,retention_hours:24,demo:false});
    if(path==="/v1/workspaces")return json([workspace]);
    if(path==="/v1/workspaces/w")return json(workspace);
    if(path.endsWith("/selection")){
      if(method==="POST"){
        const body=request.postDataJSON() as WorkspaceSelection;
        if(body.version!==selection.version)return json({detail:"workspace_selection_changed"},409);
        if(selection.entries.some(entry=>!body.entries.some(value=>value.id===entry.id)))return json({detail:"workspace_entries_cannot_disappear"},409);
        selection={...body,version:selection.version+1};
      }
      return json(selection);
    }
    if(path.endsWith("/region-fields")){
      if(method==="POST"){
        const upload=request.postDataBuffer()!.toString();
        if(upload.includes("labels"))return json({detail:"region_image_bit_depth_unsupported"},422);
        fields=[{id:"accepted",workspace_id:"w",metadata:{},image_info:{shape:[32,32],input_mode:"native",channels:[{channel_id:"c1",label:"c1",stain:null}]}}];
        return json(fields[0],201);
      }
      return json(fields);
    }
    if(path.endsWith("/channel-assignments"))return json({version:0,assignments:[],global_field_ids:[],groups:[]});
    if(path.endsWith("/field-links"))return json({version:0,entries:[]});
    if(path.endsWith("/analysis-spec"))return json({version:0,spec:null});
    if(path.endsWith("/revisions")||path.endsWith("/jobs")||path.endsWith("/runs"))return json([]);
    if(path.endsWith("/preview"))return route.fulfill({headers,contentType:"image/svg+xml",body:'<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"><rect width="32" height="32" fill="#182237"/></svg>'});
    unexpected.push(`${method} ${path}`);
    return json({detail:"unexpected_route"},404);
  });
  const loaded=page.waitForResponse(response=>new URL(response.url()).pathname.endsWith("/analysis-spec"));
  await page.goto("/workspace?id=w");
  await loaded;
  await expect(page.getByRole("status").first()).toHaveText("");
  await page.getByTestId("file-input").setInputFiles([{name:"A01_c1.tif",mimeType:"image/tiff",buffer:Buffer.from([1,2,3])},{name:"A01-labels.tif",mimeType:"image/tiff",buffer:Buffer.from([4,5,6])},{name:"A02-labels.tif",mimeType:"image/tiff",buffer:Buffer.from([7,8,9])}]);
  await page.getByRole("button",{name:/^形を決めずに登録/}).click();
  // The researcher's own file names and the reason, stated once for both, never the private batch folder.
  const alert=page.getByRole("alert").filter({hasText:"登録できなかった画像が 2 件あります。"});
  await expect(alert).toContainText(/A0[12]-labels\.tif、A0[12]-labels\.tif：8-bit または 16-bit の画像ではありません/);
  expect((await alert.textContent())?.match(/8-bit または 16-bit/g)).toHaveLength(1);
  await expect(page.getByText(/import-[0-9a-f]/)).toHaveCount(0);
  expect(selection.entries.filter(entry=>!entry.field_id)).toHaveLength(2);
  expect(selection.entries.filter(entry=>entry.field_id==="accepted")).toHaveLength(1);
  // Statistics say where the comparison is blocked before it is attempted.
  await page.getByRole("button",{name:"統計",exact:true}).click();
  await expect(page.getByRole("status").filter({hasText:"登録できなかった画像が 2 件あります。比較の前に、画面下の「取込」の一覧で理由を付けて除外してください。"})).toBeVisible();
  await page.getByText("取込 2件",{exact:true}).click();
  await expect(page.getByText("A01-labels.tif",{exact:true})).toBeVisible();
  await expect(page.getByText("A02-labels.tif",{exact:true})).toBeVisible();
  await expect(page.getByLabel("除外の理由").first()).toHaveValue(/^登録できない画像のため除外：8-bit/);
  await expect(page.getByLabel("登録できなかった 2 件をまとめて除外の理由")).toHaveValue(/^登録できない画像のため除外：8-bit/);
  // After a reload the entries are still there; only their names are not recorded by the API.
  const reloaded=page.waitForResponse(response=>new URL(response.url()).pathname.endsWith("/analysis-spec"));
  await page.reload();
  await reloaded;
  await page.getByText("取込 2件",{exact:true}).click();
  await expect(page.getByText("名前の記録がない登録",{exact:true})).toHaveCount(2);
  const reason=page.getByLabel("登録できなかった 2 件をまとめて除外の理由");
  await expect(reason).toHaveValue("");
  await expect(page.getByRole("button",{name:"まとめて除外",exact:true})).toBeDisabled();
  await reason.fill("整数ラベル画像で、測る画像ではない");
  await page.getByRole("button",{name:"まとめて除外",exact:true}).click();
  await expect(page.getByText(/^取込 \d+件$/)).toHaveCount(0);
  expect(selection.entries.filter(entry=>!entry.field_id).map(entry=>entry.exclusion_reason)).toEqual(["整数ラベル画像で、測る画像ではない","整数ラベル画像で、測る画像ではない"]);
  expect(selection.entries).toHaveLength(3);
  expect(unexpected).toEqual([]);
  expect(pageErrors).toEqual([]);
});
