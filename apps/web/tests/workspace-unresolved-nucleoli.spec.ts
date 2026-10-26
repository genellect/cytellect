import {expect,test,type BrowserContext,type Page} from "@playwright/test";
import type {WorkspaceSelection} from "../src/lib/workspace/api-adapter";

/** Requirements Q-05 (genellect/cytellect#109), transport and UI only: a nucleus whose nucleolus could not
 * be established is listed by group, unit and reason before the calculation; the comparison runs once
 * the list is confirmed, the policy and the exact per-field list are sent, and the result states the
 * denominators and the warning beside it. Fixed response records, not microscopy acceptance. */
async function nucleolarWorkspace(context:BrowserContext,page:Page){
  const writes:Array<{path:string;body:Record<string,unknown>}> = [];
  const unexpected:string[]=[];
  const fieldIds=["f1","f2"];
  const fields=fieldIds.map((id,index)=>({id,workspace_id:"w",metadata:{display_name:`視野 ${index+1}`},image_info:{shape:[32,32],channels:[{channel_id:"c1",label:"DAPI",stain:"DAPI"},{channel_id:"c2",label:"NPM1",stain:"NPM1"}]}}));
  const nuclear={id:"region-2d",version:"1.7.0",source:"stardist_nuclear",region_set_id:"nuclei",label:"核",defining_channel_id:"c1",nuclear_role_source:"recorded_stain"};
  const nucleolar={id:"region-2d",version:"1.4.0",source:"fiji_nuclear_compartment",region_set_id:"nucleoli",label:"核小体",compartment:"nucleoli",defining_channel_id:"c2"};
  let selection:WorkspaceSelection={version:1,entries:fieldIds.map((id,index)=>({id,field_id:id,revision_id:`n${index+1}`,target_revisions:{nuclei:`r${index+1}`,nucleoli:`n${index+1}`},exclusion_reason:null}))};
  let spec:{version:number;spec:Record<string,unknown>|null}={version:0,spec:null};
  let statistics:Record<string,unknown>|null=null,cohort:Record<string,unknown>|null=null,review:Record<string,unknown>|null=null;
  const revision=(id:string,fid:string,recipe:Record<string,unknown>)=>({id,state:"succeeded",created:1,config:{recipe,field_ids:[fid],measurement:{version:"1.1.0",mode:"raw_intensity"},backgrounds:{}}});
  // A nucleolar result is shown only on its own parent nuclear revision and nuclear channel.
  const revisions=[revision("r1","f1",nuclear),revision("r2","f2",nuclear),
    revision("n1","f1",{...nucleolar,nuclear_revision_id:"r1",nuclear_channel_id:"c1"}),revision("n2","f2",{...nucleolar,nuclear_revision_id:"r2",nuclear_channel_id:"c1"})];
  const ledgers:Record<string,Record<string,unknown>>={n1:{f1:{nuclei:3,resolved:2,missing:{no_candidate:1},excluded:0}},n2:{f2:{nuclei:2,resolved:2,missing:{},excluded:0}}};
  const missing={policy:"unresolved-as-missing/1.0.0",warning_points:10,
    rows:[{condition:"A",experimental_unit:"unit-0",run:null,fields:1,nuclei:3,resolved:2,missing:1,excluded:0,reasons:{no_candidate:1}},
          {condition:"B",experimental_unit:"unit-1",run:null,fields:1,nuclei:2,resolved:2,missing:0,excluded:0,reasons:{}}],
    warnings:[{run:null,difference_points:33.3,fractions:{A:0.3333,B:0}}]};
  await context.route("**/v1/**",async route=>{
    const req=route.request(),url=new URL(req.url()),path=url.pathname,method=req.method();
    const headers={"Access-Control-Allow-Origin":new URL(page.url()).origin,"Access-Control-Allow-Credentials":"true","Access-Control-Allow-Headers":"content-type,x-cytellect-request","Access-Control-Allow-Methods":"GET,POST,PUT,DELETE,OPTIONS"};
    const json=(body:unknown,status=200)=>route.fulfill({status,headers,contentType:"application/json",body:JSON.stringify(body)});
    if(method==="OPTIONS")return route.fulfill({status:204,headers});
    const body=method==="POST"||method==="PUT"?req.postDataJSON()||{}:{};
    if(method!=="GET")writes.push({path,body});
    if(path==="/v1/session")return json({authenticated:true,retention_hours:24,demo:false});
    if(path==="/v1/workspaces")return json([{id:"w",title:"Nucleolar records",created:1,expires:9999999999,deleted:false}]);
    if(path==="/v1/workspaces/w")return json({id:"w",title:"Nucleolar records",active_revision:"n2"});
    if(path.endsWith("/region-fields"))return json(fields);
    if(path.endsWith("/channel-assignments"))return json({version:1,assignments:[{channel_id:"c1",stain:"DAPI",role:"nuclear"},{channel_id:"c2",stain:"NPM1",role:"measure"}],global_field_ids:fieldIds,groups:[]});
    if(path.endsWith("/field-links"))return json({version:0,entries:[]});
    if(path.endsWith("/analysis-spec")){if(method==="PUT"){spec={version:spec.version+1,spec:body.spec};}return json(spec);}
    if(path.endsWith("/selection")){if(method==="POST"){selection={...body,version:selection.version+1};}return json(selection);}
    if(path.endsWith("/revisions"))return json(revisions);
    if(path.endsWith("/runs"))return json([]);
    if(path.endsWith("/jobs"))return json([...(cohort?[{id:"cohortjob",kind:"analysis",state:"succeeded",revision_id:"cohort"}]:[]),...(statistics?[{id:"stats",kind:"statistics",state:"succeeded",revision_id:"cohort"}]:[])]);
    if(path.endsWith("/current"))return json({});
    if(path.endsWith("/compartment-ledger")){const rid=path.split("/")[3];return json({policy:"unresolved-as-missing/1.0.0",fields:ledgers[rid]});}
    if(path.endsWith("/region-cohorts")){cohort=body;return json({job_id:"cohortjob",revision_id:"cohort"},202);}
    if(path.endsWith("/review")){review=body;return json({reviewed:true});}
    if(path.endsWith("/common-statistics")){if(method==="POST"){statistics=body;return json({job_id:"stats"},202);}
      return json({revision_id:"cohort",source_kind:"region-2d",analysis_kind:"region-comparison",region_comparison_version:"2.0.0",spec:statistics,comparisons:[],counts:[],warnings:["compartment_missing_rate_differs"],source_fields:[],estimates:null,compartment_missing:missing,figure:{source_files:[]}});}
    if(path.endsWith("/region-measurements")){const rid=path.split("/")[3],fid=rid.endsWith("2")?"f2":"f1";return json({revision_id:rid,protocol_version:"3.0.0",measurement:{version:"1.1.0",mode:"raw_intensity"},field_failures:[],exclusions:[],field_tables:{[fid]:{rows:[1,2].map(region_id=>({region_id,channel_id:"c2",area_px:region_id*10,area_um2:null,mean:30,median:29,integrated:300}))}}});}
    if(path.endsWith("/region-masks")){const rid=path.split("/")[3];return json({regions:[1,2].map(id=>({id,points:id===1?[[3,3],[12,3],[12,12],[3,12]]:[[18,18],[28,18],[28,28],[18,28]]})),metadata:{mask_revision_id:`mask-${rid}`}});}
    if(path.endsWith("/preview"))return route.fulfill({headers,contentType:"image/svg+xml",body:'<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"><rect width="32" height="32" fill="#869fff"/></svg>'});
    const record=revisions.find(value=>path.endsWith(`/revisions/${value.id}`));if(record)return json(record);
    unexpected.push(`${method} ${path}${url.search}`);return json({detail:"unexpected_transport_route"},404);
  });
  return {writes,unexpected,cohort:()=>cohort,review:()=>review};
}

test("unresolved nucleoli are confirmed by group, unit and reason, then kept as missing beside the result",async({page,context})=>{
  const fixture=await nucleolarWorkspace(context,page);
  await page.goto("/workspace?id=w");
  const navigation=page.getByRole("navigation",{name:"作業の切替"});
  await navigation.getByRole("button",{name:"統計",exact:true}).click();
  const side=page.getByRole("complementary",{name:"解析対象"});
  await side.getByRole("combobox",{name:"領域",exact:true}).selectOption("nucleoli");
  await side.getByRole("combobox",{name:"指標",exact:true}).selectOption("area_px");
  const panel=page.getByRole("region",{name:"測定結果の統計解析"});
  await panel.getByRole("combobox",{name:"解析",exact:true}).selectOption("comparison");
  await panel.getByLabel("独立実験単位",{exact:true}).fill("Transport independent units");
  for(let i=0;i<2;i++)for(const [key,value] of [["condition",i?"B":"A"],["sample",`sample-${i}`],["experimental_unit",`unit-${i}`]])await panel.locator(`input[aria-label$=" ${key}"]`).nth(i).fill(value);
  await panel.getByLabel("A / B",{exact:true}).check();
  await panel.getByLabel("独立実験単位、撮影・画素条件、採否と欠測の扱いを確認した",{exact:true}).check();
  await panel.getByLabel("測定領域と採用する視野を確認した",{exact:true}).check();
  // The list names each group and unit with its missing nuclei over all nuclei and the reason.
  const list=panel.getByRole("region",{name:"核小体を確定できない核"});
  await expect(list).toBeVisible();
  await expect(list.getByRole("row").filter({hasText:"unit-0"})).toContainText("1 / 3（33.3%）");
  await expect(list.getByRole("row").filter({hasText:"unit-0"})).toContainText("核小体が見つからない 1");
  await expect(list.getByRole("row").filter({hasText:"unit-1"})).toContainText("0 / 2");
  const calculate=panel.getByRole("button",{name:"計算",exact:true});
  await expect(calculate).toBeDisabled();
  await list.getByLabel("この一覧を確認し、欠測として残して計算する",{exact:true}).check();
  await expect(calculate).toBeEnabled();
  await calculate.click();
  await expect.poll(()=>fixture.review()).not.toBeNull();
  expect(fixture.cohort()).toMatchObject({compartment_missing:"unresolved-as-missing/1.0.0"});
  expect(fixture.review()).toEqual({accept_invalidated_fields:[],compartment_missing:{policy:"unresolved-as-missing/1.0.0",confirmed:{f1:{no_candidate:1}}}});
  // Beside the result: what the values describe, the denominators and the within-run warning.
  const shown=page.getByRole("group",{name:"核小体を確定できない核の内訳"});
  await expect(shown).toContainText("核小体を確定できた核についての値です。");
  await expect(shown.getByRole("row").filter({hasText:"unit-0"})).toContainText("1 / 3（33.3%）");
  await expect(shown.getByRole("status")).toContainText("群の間の欠測の割合が 33.3 ポイント違います（基準 10 ポイント）");
  expect(fixture.unexpected).toEqual([]);
});
