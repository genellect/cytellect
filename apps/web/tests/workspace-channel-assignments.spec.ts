import {expect,test} from "@playwright/test";

test("stain assignments persist, name thumbnails and determine the actual nuclear input",async({page})=>{
  const channels=["c1","c2"].map(channel_id=>({channel_id,label:channel_id,stain:null}));
  const field={id:"field",workspace_id:"assignments",metadata:{},image_info:{shape:[32,32],channels}};
  const recipe={id:"region-2d",version:"1.2.0",source:"stardist_nuclear",region_set_id:"nuclei",label:"核",defining_channel_id:"c1",nuclear_role_source:"user_selected_role"};
  let assignments:{version:number;assignments:Array<{channel_id:string;stain:string|null;role:string}>}={version:0,assignments:[]};
  let runChannel="";
  await page.route("**/v1/**",async route=>{
    const path=new URL(route.request().url()).pathname,method=route.request().method();
    const headers={"Access-Control-Allow-Origin":new URL(page.url()).origin,"Access-Control-Allow-Credentials":"true","Access-Control-Allow-Headers":"content-type,x-cytellect-request"};
    const json=(body:unknown,status=200)=>route.fulfill({status,headers,contentType:"application/json",body:JSON.stringify(body)});
    if(method==="OPTIONS")return route.fulfill({status:204,headers});
    if(path==="/v1/session")return json({authenticated:true,retention_hours:24,demo:false});
    if(path==="/v1/workspaces/assignments")return json({id:"assignments",active_revision:"nuclei"});
    if(path.endsWith("/channel-assignments")){if(method==="PUT"){const body=route.request().postDataJSON();expect(body.version).toBe(assignments.version);assignments={...body,version:assignments.version+1};}return json(assignments);}
    if(path.endsWith("/selection"))return json({version:1,entries:[{id:"entry",field_id:"field",revision_id:"nuclei",target_revisions:{nuclei:"nuclei"},exclusion_reason:null}]});
    if(path.endsWith("/region-fields"))return json([field]);
    if(path.endsWith("/revisions"))return json([{id:"nuclei",state:"succeeded",created:1,config:{recipe,field_ids:["field"]}}]);
    if(path.endsWith("/jobs"))return json([]);
    if(path.endsWith("/region-measurements"))return json({revision_id:"nuclei",field_failures:[],exclusions:[],field_tables:{field:{rows:channels.map(channel=>({region_id:7,channel_id:channel.channel_id,area_px:64,mean:20,median:20,integrated:1280}))}}});
    if(path.endsWith("/region-masks"))return json({regions:[{id:7,points:[[4,4],[12,4],[12,12],[4,12]]}],metadata:{mask_revision_id:"mask-nuclei"}});
    if(path.endsWith("/preview"))return route.fulfill({headers,contentType:"image/png",body:Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aU1sAAAAASUVORK5CYII=","base64")});
    if(path.endsWith("/region-analyses")){runChannel=route.request().postDataJSON().recipe.defining_channel_id;return json({detail:"worker_process_failed"},500);}
    return json({detail:"unused_fixture_route"},404);
  });
  await page.goto("/workspace?id=assignments");
  const mapping=page.getByRole("form",{name:"チャンネルと染色"});
  await expect(mapping.getByLabel("c2 の染色")).toBeEnabled();
  await mapping.getByLabel("c1 の染色").fill("GFP");
  await mapping.getByLabel("c2 の染色").fill("DAPI");
  await mapping.getByRole("button",{name:"保存",exact:true}).click();
  await expect.poll(()=>assignments.version).toBe(1);
  expect(assignments.assignments).toEqual([{channel_id:"c1",stain:"GFP",role:"measure"},{channel_id:"c2",stain:"DAPI",role:"nuclear"}]);
  await expect.poll(()=>runChannel).toBe("c2");
  await expect(page.getByRole("navigation",{name:"画像とグラフ"}).getByRole("button",{name:"c2 · DAPI · 核検出",exact:true})).toBeVisible();
  await expect(page.locator("svg [data-region]")).toHaveCount(0);
  await page.reload();
  await expect(mapping.getByLabel("c1 の染色")).toHaveValue("GFP");
  await expect(mapping.getByLabel("c2 の染色")).toHaveValue("DAPI");
  await expect(mapping.getByRole("button",{name:"c2 を核検出に使う"})).toHaveAttribute("aria-pressed","true");
});
