import {expect,test,type BrowserContext,type Page} from "@playwright/test";

/** The image view of the production workspace (/workspace) on fixed API records: two fields stained
 * with DAPI (nuclear) and NPM1, with adopted nuclei and nucleoli. Transport and display only; the fixed
 * records and display pixels are not microscopy acceptance. */
async function imageWorkspace(context:BrowserContext,page:Page){
  const unexpected:string[]=[];
  const fieldIds=["f1","f2"];
  const channels=[{channel_id:"c1",label:"DAPI",stain:"DAPI"},{channel_id:"c2",label:"NPM1",stain:"NPM1"}];
  const fields=fieldIds.map((id,index)=>({id,workspace_id:"w",metadata:{display_name:`視野 ${index+1}`},image_info:{shape:[32,32],channels}}));
  const nuclear={id:"region-2d",version:"1.7.0",source:"stardist_nuclear",region_set_id:"nuclei",label:"核",defining_channel_id:"c1",nuclear_role_source:"recorded_stain"};
  const nucleolar={id:"region-2d",version:"1.4.0",source:"fiji_nuclear_compartment",region_set_id:"nucleoli",label:"核小体",compartment:"nucleoli",defining_channel_id:"c2"};
  const revision=(id:string,fid:string,recipe:Record<string,unknown>)=>({id,state:"succeeded",created:1,config:{recipe,field_ids:[fid],measurement:{version:"1.1.0",mode:"raw_intensity"},backgrounds:{}}});
  const revisions=[revision("r1","f1",nuclear),revision("r2","f2",nuclear),
    revision("n1","f1",{...nucleolar,nuclear_revision_id:"r1",nuclear_channel_id:"c1"}),revision("n2","f2",{...nucleolar,nuclear_revision_id:"r2",nuclear_channel_id:"c1"})];
  const selection={version:1,entries:fieldIds.map((id,index)=>({id,field_id:id,revision_id:`n${index+1}`,target_revisions:{nuclei:`r${index+1}`,nucleoli:`n${index+1}`},exclusion_reason:null}))};
  // Each field and channel has its own mean, so a table shows which stain and field its rows measure.
  const mean=(fid:string,channel:string)=>(fid==="f1"?100:200)+(channel==="c1"?11:22);
  const outlines:Record<string,number[][][]>={nuclei:[[[2,2],[14,2],[14,14],[2,14]],[[17,17],[30,17],[30,30],[17,30]]],nucleoli:[[[6,6],[10,6],[10,10],[6,10]],[[21,21],[26,21],[26,26],[21,26]]]};
  await context.route("**/v1/**",async route=>{
    const req=route.request(),url=new URL(req.url()),path=url.pathname,method=req.method();
    const headers={"Access-Control-Allow-Origin":new URL(page.url()).origin,"Access-Control-Allow-Credentials":"true","Access-Control-Allow-Headers":"content-type,x-cytellect-request","Access-Control-Allow-Methods":"GET,POST,PUT,DELETE,OPTIONS"};
    const json=(body:unknown,status=200)=>route.fulfill({status,headers,contentType:"application/json",body:JSON.stringify(body)});
    if(method==="OPTIONS")return route.fulfill({status:204,headers});
    if(path==="/v1/session")return json({authenticated:true,retention_hours:24,demo:false});
    if(path==="/v1/workspaces")return json([{id:"w",title:"Image records",created:1,expires:9999999999,deleted:false}]);
    if(path==="/v1/workspaces/w")return json({id:"w",title:"Image records",active_revision:"n2"});
    if(path.endsWith("/region-fields"))return json(fields);
    if(path.endsWith("/channel-assignments"))return json({version:1,assignments:[{channel_id:"c1",stain:"DAPI",role:"nuclear"},{channel_id:"c2",stain:"NPM1",role:"measure"}],global_field_ids:fieldIds,groups:[]});
    if(path.endsWith("/field-links"))return json({version:0,entries:[]});
    if(path.endsWith("/analysis-spec"))return json({version:0,spec:null});
    if(path.endsWith("/selection"))return json(selection);
    if(path.endsWith("/revisions"))return json(revisions);
    if(path.endsWith("/runs")||path.endsWith("/jobs"))return json([]);
    if(path.endsWith("/region-measurements")){const rid=path.split("/")[3],fid=rid.endsWith("2")?"f2":"f1";
      return json({revision_id:rid,protocol_version:"3.0.0",measurement:{version:"1.1.0",mode:"raw_intensity"},field_failures:[],exclusions:[],field_tables:{[fid]:{rows:[1,2].flatMap(region_id=>["c1","c2"].map(channel_id=>({region_id,channel_id,area_px:region_id*10,area_um2:null,mean:mean(fid,channel_id),median:mean(fid,channel_id),integrated:mean(fid,channel_id)*10})))}}});}
    if(path.endsWith("/region-masks")){const rid=path.split("/")[3];return json({regions:outlines[rid.startsWith("n")?"nucleoli":"nuclei"].map((points,index)=>({id:index+1,points})),metadata:{mask_revision_id:`mask-${rid}`}});}
    if(path.endsWith("/preview"))return route.fulfill({headers,contentType:"image/svg+xml",body:`<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"><rect width="32" height="32" fill="${url.searchParams.get("channel_id")==="c1"?"#555":"#999"}"/></svg>`});
    const record=revisions.find(value=>path.endsWith(`/revisions/${value.id}`));if(record)return json(record);
    unexpected.push(`${method} ${path}${url.search}`);return json({detail:"unexpected_transport_route"},404);
  });
  return {unexpected};
}

test("the table beside one image names the stain and field of its rows, also when a comparison shows another plane",async({page,context})=>{
  const fixture=await imageWorkspace(context,page);
  await page.goto("/workspace?id=w");
  const bar=page.locator("[class*=channelBar]");
  await bar.getByRole("button",{name:"DAPI · c1",exact:true}).click();
  // The table sits beside the image when the settings panel leaves it room.
  await page.getByRole("button",{name:"パネルを閉じる",exact:true}).click();
  const side=page.locator("[class*=sideMeasurements]");
  const heading=side.getByRole("heading",{level:3});
  await expect(heading).toHaveText("核の測定値 · DAPI");
  await expect(side.locator("tbody tr").first()).toContainText("111");
  // A comparison that shows only NPM1 of the same field: the rows stay DAPI's, and so does the caption.
  await bar.getByRole("button",{name:"画像を比較",exact:true}).click();
  for(const plane of ["視野 1 · DAPI","視野 2 · DAPI","視野 2 · NPM1"]){const box=page.getByRole("checkbox",{name:plane,exact:true});if(await box.isChecked())await box.uncheck();}
  await page.getByRole("checkbox",{name:"視野 1 · NPM1",exact:true}).check();
  await expect(page.locator("svg[aria-label='視野 1 NPM1']")).toBeVisible();
  await expect(heading).toHaveText("核の測定値 · DAPI");
  await expect(side.locator("tbody tr").first()).toContainText("111");
  await expect(side.locator("tbody")).not.toContainText("122");
  // Another field's plane: the caption also names the field the rows come from.
  await page.getByRole("checkbox",{name:"視野 1 · NPM1",exact:true}).uncheck();
  await page.getByRole("checkbox",{name:"視野 2 · NPM1",exact:true}).check();
  await expect(page.locator("svg[aria-label='視野 2 NPM1']")).toBeVisible();
  await expect(heading).toHaveText("核の測定値 · 視野 1 · DAPI");
  await expect(side.locator("tbody tr").first()).toContainText("111");
  // Choosing an outline in the shown plane selects that field and stain; rows and caption follow it.
  await page.locator("svg[aria-label='視野 2 NPM1'] path[data-region='1']").click();
  await expect(heading).toHaveText("核の測定値 · NPM1");
  await expect(side.locator("tbody tr").first()).toContainText("222");
  expect(fixture.unexpected).toEqual([]);
});
