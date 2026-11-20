import {nucleusTableFixture} from "./nucleus-table-fixture";
import {expect,test,type BrowserContext,type Page} from "@playwright/test";

/**
 * #257 RP-04, NS-01, A-4 on the connected workspace (transport contract only: fixed response records, not microscopy):
 * the primary measure is declared on 実験 (directly or from the 核小体ストレス theme) and every result names its role;
 * the theme lists each measure's stain, region and observation; the image table loads shape and pixel-signal values
 * from the API on request.
 */
async function workspace(context:BrowserContext,page:Page){
  const writes:Array<{path:string;body:Record<string,unknown>}>=[];
  const unexpected:string[]=[];
  const channels=[{channel_id:"c1",label:"Hoechst",stain:"Hoechst"},{channel_id:"c2",label:"NPM1",stain:"NPM1"}];
  const fields=[{id:"f1",workspace_id:"w",metadata:{display_name:"視野 1"},image_info:{shape:[32,32],channels}}];
  let spec:{version:number;spec:Record<string,unknown>|null}={version:0,spec:null};
  const featureRequests:string[]=[];
  const recipe={id:"region-2d",version:"1.7.0",source:"stardist_nuclear",region_set_id:"nuclei",label:"核",defining_channel_id:"c1",nuclear_role_source:"recorded_stain"};
  const revision={id:"r1",state:"succeeded",created:1,config:{recipe,field_ids:["f1"],measurement:{version:"1.1.0",mode:"raw_intensity"},backgrounds:{}}};
  await context.route("**/v1/**",async route=>{
    const req=route.request(),url=new URL(req.url()),path=url.pathname,method=req.method();
    const headers={"Access-Control-Allow-Origin":new URL(page.url()).origin,"Access-Control-Allow-Credentials":"true","Access-Control-Allow-Headers":"content-type,x-cytellect-request","Access-Control-Allow-Methods":"GET,POST,PUT,DELETE,OPTIONS"};
    const json=(body:unknown,status=200)=>route.fulfill({status,headers,contentType:"application/json",body:JSON.stringify(body)});
    if(method==="OPTIONS")return route.fulfill({status:204,headers});
    const body=method==="POST"||method==="PUT"?req.postDataJSON()||{}:{};
    if(method!=="GET")writes.push({path,body});
    if(path==="/v1/session")return json({authenticated:true,retention_hours:24,demo:false});
    if(path==="/v1/workspaces")return json([{id:"w",title:"Transport records",created:1,expires:9999999999,deleted:false}]);
    if(path==="/v1/workspaces/w")return json({id:"w",title:"Transport records",active_revision:"r1"});
    if(path.endsWith("/region-fields"))return json(fields);
    if(path.endsWith("/channel-assignments"))return json({version:1,assignments:[{channel_id:"c1",stain:"Hoechst",role:"nuclear"},{channel_id:"c2",stain:"NPM1",role:"marker"}],global_field_ids:["f1"],groups:[]});
    if(path.endsWith("/field-links"))return json({version:0,entries:[]});
    if(path.endsWith("/analysis-spec")){
      if(method==="PUT"){
        // The server keeps or renews the declaration time (tests/test_analysis_spec.py); here a fixed time stands in.
        const sent=body.spec as Record<string,unknown>;
        const primary=sent.primary_outcome as Record<string,unknown>|undefined;
        spec={version:spec.version+1,spec:primary?{...sent,primary_outcome:{...primary,declared_at:1_800_000_000}}:sent};
      }
      return json(spec);
    }
    if(path.endsWith("/selection"))return json({version:1,entries:[{id:"f1",field_id:"f1",revision_id:"r1",target_revisions:{nuclei:"r1"},exclusion_reason:null}]});
    if(path.endsWith("/revisions"))return json([revision]);
    if(path.endsWith("/runs")||path.endsWith("/jobs"))return json([]);
    if(path.endsWith("/current"))return json({});
    if(path.endsWith("/region-measurements"))return json({revision_id:"r1",protocol_version:"3.0.0",measurement:{version:"1.1.0",mode:"raw_intensity"},field_failures:[],exclusions:[],
      field_tables:{f1:{rows:[1,2].flatMap(region_id=>channels.map(ch=>({region_id,channel_id:ch.channel_id,area_px:region_id===1?120:40,area_um2:null,mean:30,median:29,integrated:300})))}}});
    if(path.endsWith("/nucleus-table"))return json(nucleusTableFixture({fieldId:"f1",revision:"r1",channels,nuclei:[1,2]}));
    if(path.endsWith("/region-features")){
      featureRequests.push(url.search);
      const values=(solidity:number|null,reason:string|null)=>({solidity:{value:solidity,missing_reason:reason},axis_ratio:{value:solidity===null?null:1.25,missing_reason:reason},eccentricity:{value:solidity===null?null:0.6,missing_reason:reason}});
      return json({protocol:"region-features/1.0.0",field_id:"f1",region_set_id:"nuclei",mask_revision_id:"mask-r1",channel_id:url.searchParams.get("channel_id"),minimum_area_px:96,
        metrics:["solidity","axis_ratio","eccentricity"],thresholds:{},rows:[{region_id:1,area_px:120,excluded:false,values:values(0.92,null)},{region_id:2,area_px:40,excluded:false,values:values(null,"below_minimum_area")}]});
    }
    if(path.endsWith("/region-masks"))return json({regions:[1,2].map(id=>({id,points:id===1?[[3,3],[14,3],[14,14],[3,14]]:[[18,18],[24,18],[24,24],[18,24]]})),metadata:{mask_revision_id:"mask-r1"}});
    if(path.endsWith("/preview"))return route.fulfill({headers,contentType:"image/svg+xml",body:'<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"><rect width="32" height="32" fill="#869fff"/></svg>'});
    if(path.endsWith("/revisions/r1"))return json(revision);
    unexpected.push(`${method} ${path}`);return json({detail:"unexpected_transport_route"},404);
  });
  return {writes,unexpected,featureRequests,spec:()=>spec};
}

test("the primary measure is declared before results and every result names its role",async({page,context})=>{
  const fixture=await workspace(context,page);
  await page.goto("/workspace?id=w");
  const navigation=page.getByRole("navigation",{name:"作業の切替"});
  await navigation.getByRole("button",{name:"実験",exact:true}).click();
  // The declaration belongs to the experiment view once the form is chosen.
  await page.getByRole("button",{name:/^対照と処理を比べる/}).click();
  const primary=page.getByRole("region",{name:"主要指標"});
  await expect(primary).toContainText("結果を見る前に");
  // The theme names each measure's stain, region and observation before any comparison (NS-01).
  await page.getByText("研究テーマから指標を選ぶ：核小体ストレス").click();
  const theme=page.getByRole("table",{name:"核小体ストレスの指標"});
  const cv=theme.getByRole("row").filter({hasText:"核内で信号はどれだけ偏っているか"});
  await expect(cv).toContainText("核の画素の変動係数（CV、背景補正、NPM1）");
  await expect(cv.getByRole("cell",{name:"核ごと",exact:true})).toBeVisible();
  const eu=theme.getByRole("row").filter({hasText:"新生 RNA の取り込みも変わったか"});
  await expect(eu).toContainText("5-EU または EU（未登録）");
  await expect(eu.getByRole("button",{name:"主要指標にする"})).toBeDisabled();
  await cv.getByRole("button",{name:"主要指標にする"}).click();
  await expect.poll(()=>(fixture.spec().spec as {primary_outcome?:unknown}|null)?.primary_outcome).toMatchObject({metric:"cv_corrected",region_set_id:"nuclei",channel_id:"c2"});
  await expect(primary).toContainText("主要指標：核の画素の変動係数（CV、背景補正、NPM1）");
  // Statistics: the chosen condition says whether it is the primary measure.
  await navigation.getByRole("button",{name:"統計",exact:true}).click();
  const current=page.getByText(/^計算する条件：/);
  await expect(current.locator("[data-outcome-role]")).toHaveText("探索的な指標（主要指標：核の画素の変動係数（CV、背景補正、NPM1））");
  const side=page.getByRole("complementary",{name:"解析対象"});
  await side.getByRole("combobox",{name:"対象",exact:true}).selectOption("nuclei");
  await side.getByRole("combobox",{name:"指標",exact:true}).selectOption("cv_corrected");
  await side.getByRole("combobox",{name:"染色",exact:true}).selectOption("c2");
  await expect(current.locator("[data-outcome-role]")).toHaveText("主要指標");
  expect(fixture.unexpected).toEqual([]);
});

test("the image table loads shape values on request, with the reason a region has none",async({page,context})=>{
  const fixture=await workspace(context,page);
  await page.goto("/workspace?id=w");
  await page.getByRole("group",{name:"表の切り替え"}).getByRole("button",{name:"このチャンネル"}).click();
  // Nothing is asked of the API until the researcher wants the columns.
  expect(fixture.featureRequests).toEqual([]);
  await page.getByRole("button",{name:"形と信号の値を表示"}).click();
  const table=page.getByRole("table").filter({has:page.getByRole("columnheader",{name:"ソリディティ"})});
  await expect(table.getByRole("columnheader",{name:"長短軸比"})).toBeVisible();
  const small=table.getByRole("row").filter({has:page.getByRole("button",{name:"2",exact:true})});
  await expect(small.getByRole("cell",{name:"—"}).first()).toHaveAttribute("title","面積が最小面積より小さいため、形を測っていません");
  await expect(table.getByRole("row").filter({has:page.getByRole("button",{name:"1",exact:true})})).toContainText("0.92");
  expect(fixture.featureRequests).toHaveLength(1);
  expect(fixture.unexpected).toEqual([]);
});
