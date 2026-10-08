import {expect,test} from "@playwright/test";

test("stain assignments persist, name thumbnails and determine the actual nuclear input",async({page})=>{
  const channels=["c1","c2"].map(channel_id=>({channel_id,label:channel_id,stain:null}));
  const field={id:"field",workspace_id:"assignments",metadata:{},image_info:{shape:[32,32],channels}};
  const recipe={id:"region-2d",version:"1.2.0",source:"stardist_nuclear",region_set_id:"nuclei",label:"核",defining_channel_id:"c1",nuclear_role_source:"user_selected_role"};
  let assignments:{version:number;assignments:Array<{channel_id:string;stain:string|null;role:string}>}={version:0,assignments:[]};
  let specification:{version:number;spec:unknown}={version:0,spec:null};
  let runChannel="";
  let preview:Record<string,unknown>|null=null;
  const unexpected:string[]=[];
  await page.route("**/v1/**",async route=>{
    const path=new URL(route.request().url()).pathname,method=route.request().method();
    const headers={"Access-Control-Allow-Origin":new URL(page.url()).origin,"Access-Control-Allow-Credentials":"true","Access-Control-Allow-Headers":"content-type,x-cytellect-request"};
    const json=(body:unknown,status=200)=>route.fulfill({status,headers,contentType:"application/json",body:JSON.stringify(body)});
    if(method==="OPTIONS")return route.fulfill({status:204,headers});
    if(path==="/v1/session")return json({authenticated:true,retention_hours:24,demo:false});
    if(path==="/v1/workspaces/assignments")return json({id:"assignments",active_revision:"nuclei"});
    if(path.endsWith("/channel-assignments")){if(method==="PUT"){const body=route.request().postDataJSON();expect(body.version).toBe(assignments.version);assignments={...body,version:assignments.version+1};}return json(assignments);}
    if(path.endsWith("/field-links"))return json({version:0,entries:[]});
    if(path.endsWith("/analysis-spec")){if(method==="PUT"){const body=route.request().postDataJSON();expect(body.version).toBe(specification.version);specification={version:specification.version+1,spec:body.spec};}return json(specification);}
    if(path.endsWith("/runs")){if(method==="GET")return json(preview?[preview]:[]);const body=route.request().postDataJSON();expect(body).toMatchObject({target:"nuclei",field_ids:["field"],purpose:"preview",spec_version:specification.version});runChannel=assignments.assignments.find(value=>value.role==="nuclear")!.channel_id;preview={id:"failed-preview",workspace_id:"assignments",spec_version:specification.version,target:"nuclei",state:"failed",created:2,updated:2,steps:[{field_id:"field",target:"nuclei",state:"failed",revision_id:null,job_id:null,recipe:null,error:"worker_process_failed"}]};return json(preview);}
    if(path.endsWith("/runs/failed-preview"))return json(preview);
    if(path.endsWith("/selection"))return json({version:1,entries:[{id:"entry",field_id:"field",revision_id:"nuclei",target_revisions:{nuclei:"nuclei"},exclusion_reason:null}]});
    if(path.endsWith("/region-fields"))return json([field]);
    if(path.endsWith("/revisions"))return json([{id:"nuclei",state:"succeeded",created:1,config:{recipe,field_ids:["field"]}}]);
    if(path.endsWith("/jobs"))return json([]);
    if(path.endsWith("/region-measurements"))return json({revision_id:"nuclei",field_failures:[],exclusions:[],field_tables:{field:{rows:channels.map(channel=>({region_id:7,channel_id:channel.channel_id,area_px:64,mean:20,median:20,integrated:1280}))}}});
    if(path.endsWith("/region-masks"))return json({regions:[{id:7,points:[[4,4],[12,4],[12,12],[4,12]]}],metadata:{mask_revision_id:"mask-nuclei"}});
    if(path.endsWith("/preview"))return route.fulfill({headers,contentType:"image/png",body:Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aU1sAAAAASUVORK5CYII=","base64")});
    unexpected.push(`${method} ${path}`);
    return json({detail:"unused_fixture_route"},404);
  });
  await page.goto("/workspace?id=assignments");
  await expect(page.getByRole("button",{name:"染色対応",exact:true})).toBeEnabled();
  await page.getByRole("button",{name:"染色対応",exact:true}).click();
  await page.getByLabel("c1の染色名").fill("GFP");
  await page.getByLabel("c1の役割").selectOption("measure");
  await page.getByLabel("c2の染色名").fill("DAPI");
  await page.getByLabel("c2の役割").selectOption("nuclear");
  await page.getByRole("button",{name:"保存",exact:true}).click();
  await expect.poll(()=>assignments.version).toBe(1);
  expect(assignments.assignments).toEqual([{channel_id:"c1",stain:"GFP",role:"measure"},{channel_id:"c2",stain:"DAPI",role:"nuclear"}]);
  await expect.poll(()=>runChannel).toBe("c2");
  await expect(page.getByRole("button",{name:"DAPI · c2",exact:true})).toBeVisible();
  await expect(page.getByRole("button",{name:"GFP · c1",exact:true})).toBeVisible();
  await expect(page.locator("svg [data-region]")).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole("button",{name:"染色対応",exact:true})).toBeEnabled();
  await page.getByRole("button",{name:"染色対応",exact:true}).click();
  await expect(page.getByLabel("c1の染色名")).toHaveValue("GFP");
  await expect(page.getByLabel("c2の染色名")).toHaveValue("DAPI");
  await expect(page.getByLabel("c2の役割")).toHaveValue("nuclear");
  expect(unexpected).toEqual([]);
});
