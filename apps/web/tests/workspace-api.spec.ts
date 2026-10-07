import {expect,test,type BrowserContext,type Page} from "@playwright/test";
import type {WorkspaceSelection} from "../src/lib/workspace/api-adapter";

/** Transport/UI contract only: fixed response records and display pixels are not microscopy acceptance. */
async function savedWorkspace(context:BrowserContext,page:Page,failed=false){
  const writes:Array<{path:string;body:Record<string,unknown>}> = [];
  const fieldIds=failed?["f1","f2","failed1","failed2"]:["f1"];
  const fields=fieldIds.map((id,index)=>({id,workspace_id:"w",metadata:{display_name:`視野 ${index+1}`},image_info:{shape:[32,32],channels:[{channel_id:"c1",label:"DAPI",stain:"DAPI"}]}}));
  let selection:WorkspaceSelection={version:1,entries:fieldIds.map((id,index)=>({id,field_id:id,revision_id:index<2?`r${index+1}`:`bad${index}`,target_revisions:{nuclei:index<2?`r${index+1}`:`bad${index}`},exclusion_reason:null}))};
  let spec:{version:number;spec:Record<string,unknown>|null}={version:0,spec:null};
  let edited=false,statistics:Record<string,unknown>|null=null,cohort:Record<string,unknown>|null=null;
  const unexpected:string[]=[];
  const recipe={id:"region-2d",version:"1.7.0",source:"stardist_nuclear",region_set_id:"nuclei",label:"核",defining_channel_id:"c1",nuclear_role_source:"recorded_stain"};
  const revision=(id:string,fid:string,state="succeeded")=>({id,state,created:1,config:{recipe,field_ids:[fid],measurement:{version:"1.1.0",mode:"raw_intensity"},backgrounds:{}}});
  const revisions=()=>[...fieldIds.map((id,index)=>revision(index<2?`r${index+1}`:`bad${index}`,id,index<2?"succeeded":"failed")),...(edited?[revision("edited","f1")]:[])];
  await context.route("**/v1/**",async route=>{
    const req=route.request(),path=new URL(req.url()).pathname,method=req.method();
    const headers={"Access-Control-Allow-Origin":new URL(page.url()).origin,"Access-Control-Allow-Credentials":"true","Access-Control-Allow-Headers":"content-type,x-cytellect-request","Access-Control-Allow-Methods":"GET,POST,PUT,DELETE,OPTIONS"};
    const json=(body:unknown,status=200)=>route.fulfill({status,headers,contentType:"application/json",body:JSON.stringify(body)});
    if(method==="OPTIONS")return route.fulfill({status:204,headers});
    const body=method==="POST"||method==="PUT"?req.postDataJSON()||{}:{};
    if(method!=="GET")writes.push({path,body});
    if(path==="/v1/session")return json({authenticated:true,retention_hours:24,demo:false});
    if(path==="/v1/workspaces")return json([{id:"w",title:"Transport records",created:1,expires:9999999999,deleted:false}]);
    if(path==="/v1/workspaces/w")return json({id:"w",title:"Transport records",active_revision:selection.entries[0].revision_id});
    if(path.endsWith("/region-fields"))return json(fields);
    if(path.endsWith("/channel-assignments"))return json({version:1,assignments:[{channel_id:"c1",stain:"DAPI",role:"nuclear"}],global_field_ids:fieldIds,groups:[]});
    if(path.endsWith("/field-links"))return json({version:0,entries:[]});
    if(path.endsWith("/analysis-spec")){if(method==="PUT"){expect(body.version).toBe(spec.version);spec={version:spec.version+1,spec:body.spec};}return json(spec);}
    if(path.endsWith("/selection")){if(method==="POST"){if(body.version!==selection.version)return json({detail:"workspace_selection_changed"},409);selection={...body,version:selection.version+1,entries:body.entries.map((entry:WorkspaceSelection["entries"][number])=>({...entry,target_revisions:entry.revision_id?{nuclei:entry.revision_id}:entry.target_revisions}))};}return json(selection);}
    if(path.endsWith("/revisions"))return json(revisions());
    if(path.endsWith("/runs"))return json([]);
    if(path.endsWith("/jobs"))return json([...(edited?[{id:"editjob",kind:"analysis",state:"succeeded",revision_id:"edited"}]:[]),...(cohort?[{id:"cohortjob",kind:"analysis",state:"succeeded",revision_id:"cohort"}]:[]),...(statistics?[{id:"stats",kind:"statistics",state:"succeeded",revision_id:"cohort"}]:[])]);
    if(path.endsWith("/current"))return json({});
    if(path.endsWith("/region-edits")){expect(body.operation).toBe("delete");expect(body.expected_mask_revision_id).toBe("mask-r1");expect(body.ids).toEqual([1]);edited=true;return json({job_id:"editjob",revision_id:"edited"},202);}
    if(path.endsWith("/region-cohorts")){cohort=body;return json({job_id:"cohortjob",revision_id:"cohort"},202);}
    if(path.endsWith("/review"))return json({});
    if(path.endsWith("/common-statistics")){if(method==="POST"){statistics=body;return json({job_id:"stats"},202);}return json({revision_id:"cohort",source_kind:"region-2d",analysis_kind:"region-comparison",region_comparison_version:"2.0.0",spec:statistics,comparisons:[],counts:[],warnings:[],source_fields:[],figure:{source_files:[]}});}
    if(path.endsWith("/region-measurements")){const rid=path.split("/")[3],fid=rid==="r2"?"f2":"f1",ids=rid==="edited"?[2]:[1,2];return json({revision_id:rid,protocol_version:"3.0.0",measurement:{version:"1.1.0",mode:"raw_intensity"},field_failures:[],exclusions:[],field_tables:{[fid]:{rows:ids.map(region_id=>({region_id,channel_id:"c1",area_px:region_id*10,area_um2:null,mean:30,median:29,integrated:300}))}}});}
    if(path.endsWith("/region-masks")){const rid=path.split("/")[3];return json({regions:(rid==="edited"?[2]:[1,2]).map(id=>({id,points:id===1?[[3,3],[12,3],[12,12],[3,12]]:[[18,18],[28,18],[28,28],[18,28]]})),metadata:{mask_revision_id:`mask-${rid}`}});}
    if(path.endsWith("/preview"))return route.fulfill({headers,contentType:"image/svg+xml",body:'<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"><rect width="32" height="32" fill="#869fff"/></svg>'});
    const record=revisions().find(value=>path.endsWith(`/revisions/${value.id}`));if(record)return json(record);
    unexpected.push(`${method} ${path}`);return json({detail:"unexpected_transport_route"},404);
  });
  return {writes,unexpected,selection:()=>selection,cohort:()=>cohort};
}

test("saved structure edits preserve revision history and guard stale tabs",async({page,context})=>{
  const fixture=await savedWorkspace(context,page);
  await page.goto("/workspace?id=w");
  await page.getByRole("button",{name:"領域 1",exact:true}).click();
  await page.getByRole("button",{name:"選択領域を削除",exact:true}).click();
  await expect.poll(()=>fixture.selection().entries[0].target_revisions?.nuclei).toBe("edited");
  await expect(page.getByRole("button",{name:"領域 1",exact:true})).toHaveCount(0);
  await expect(page.getByRole("button",{name:"領域 2",exact:true})).toBeVisible();
  await page.getByRole("button",{name:"元に戻す",exact:true}).click();
  await expect.poll(()=>fixture.selection().entries[0].target_revisions?.nuclei).toBe("r1");
  await expect(page.getByRole("button",{name:"領域 1",exact:true})).toBeVisible();
  await page.getByRole("button",{name:"やり直す",exact:true}).click();
  await expect.poll(()=>fixture.selection().entries[0].target_revisions?.nuclei).toBe("edited");
  const other=await context.newPage();await other.goto("/workspace?id=w");
  await expect(other.getByRole("button",{name:"領域 1",exact:true})).toHaveCount(0);
  await expect(other.getByRole("button",{name:"領域 2",exact:true})).toBeVisible();
  await page.getByRole("button",{name:"元に戻す",exact:true}).click();
  await expect.poll(()=>fixture.selection().entries[0].target_revisions?.nuclei).toBe("r1");
  await other.getByRole("button",{name:"領域 2",exact:true}).click();
  await other.getByRole("button",{name:"選択領域を削除",exact:true}).click();
  await expect(other.locator("main").getByRole("alert")).toContainText("別の画面で採用状態が変わりました");
  expect(fixture.selection().entries[0].target_revisions?.nuclei).toBe("r1");
  expect(fixture.writes.filter(value=>value.path.endsWith("/region-edits"))).toHaveLength(1);
  expect(fixture.writes.some(value=>/proposal|region-analyses|\/runs/.test(value.path))).toBe(false);
  expect(fixture.unexpected).toEqual([]);await other.close();
});

test("failed saved entries remain visible until explicitly excluded from comparison",async({page,context})=>{
  const fixture=await savedWorkspace(context,page,true);await page.goto("/workspace?id=w");
  const navigation=page.getByRole("navigation",{name:"作業の切替"});
  await navigation.getByRole("button",{name:"統計",exact:true}).click();
  const panel=page.getByRole("region",{name:"測定結果の統計解析"});
  await panel.getByRole("combobox",{name:"解析",exact:true}).selectOption("comparison");
  await page.getByRole("complementary",{name:"解析対象"}).getByRole("combobox",{name:"指標",exact:true}).selectOption("area_px");
  await expect(panel.getByText("2 視野の測定が未完了です。",{exact:true})).toBeVisible();
  await expect(panel.getByRole("button",{name:"計算",exact:true})).toBeDisabled();
  await navigation.getByRole("button",{name:"画像",exact:true}).click();
  for(const number of [3,4]){
    await page.getByRole("complementary",{name:"視野一覧"}).getByRole("button").filter({hasText:`${number} 視野 ${number}`}).click();
    await page.getByRole("button",{name:"この視野を除外",exact:true}).click();
    await expect.poll(()=>fixture.selection().entries[number-1].exclusion_reason).toBe("利用者が解析対象から除外");
  }
  await page.reload();await expect(page.getByRole("button",{name:"領域 1",exact:true})).toBeVisible();await navigation.getByRole("button",{name:"統計",exact:true}).click();
  await expect(panel.getByText("2 視野の測定が未完了です。",{exact:true})).toHaveCount(0);
  await panel.getByRole("combobox",{name:"解析",exact:true}).selectOption("comparison");
  await page.getByRole("complementary",{name:"解析対象"}).getByRole("combobox",{name:"指標",exact:true}).selectOption("area_px");
  await panel.getByLabel("独立実験単位",{exact:true}).fill("Transport independent units");
  for(let i=0;i<2;i++)for(const key of ["condition","sample","experimental_unit"])await panel.locator(`input[aria-label$=" ${key}"]`).nth(i).fill(`${key}-${i}`);
  await panel.getByLabel("condition-0 / condition-1",{exact:true}).check();
  await panel.getByLabel("独立実験単位、撮影・画素条件、採否と欠測の扱いを確認した",{exact:true}).check();
  await panel.getByLabel("測定領域と採用する視野を確認した",{exact:true}).check();
  await expect(panel.getByRole("button",{name:"計算",exact:true})).toBeEnabled();
  await panel.getByRole("button",{name:"計算",exact:true}).click();
  await expect.poll(()=>fixture.cohort()).not.toBeNull();
  expect(fixture.cohort()).toMatchObject({sources:[{field_id:"f1",revision_id:"r1"},{field_id:"f2",revision_id:"r2"}],workspace_selection:{entries:fixture.selection().entries}});
  expect(fixture.unexpected).toEqual([]);
});
