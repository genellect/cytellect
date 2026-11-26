import {aiReadFixture} from "./ai-read-fixture";
import {appAlerts} from "./app-alerts";
import {nucleusTableFixture} from "./nucleus-table-fixture";
import {expect,test,type BrowserContext,type Page} from "@playwright/test";

/** The production workspace (/workspace) on fixed API records: two fields stained with DAPI (nuclear) and
 * NPM1, with adopted nuclei and nucleoli; optionally a two-group design (`pair`), two saved comparisons
 * (`saved`) and image intake. Transport and display only; the fixed records and display pixels are not
 * microscopy acceptance. */
async function imageWorkspace(context:BrowserContext,page:Page,options:{pair?:boolean;saved?:boolean;aiState?:"unconfigured";previous?:boolean;serviceCheck?:"compatible"|"incompatible"}={}){
  const unexpected:string[]=[],uploads:string[][]=[],discussions:Record<string,unknown>[]=[];
  const checks:Record<string,unknown>[]=[];
  const fieldIds=["f1","f2"];
  const channels=[{channel_id:"c1",label:"DAPI",stain:"DAPI"},{channel_id:"c2",label:"NPM1",stain:"NPM1"}];
  const fields=fieldIds.map((id,index)=>({id,workspace_id:"w",metadata:{display_name:`視野 ${index+1}`},image_info:{shape:[32,32],channels}}));
  const nuclear={id:"region-2d",version:"1.7.0",source:"stardist_nuclear",region_set_id:"nuclei",label:"核",defining_channel_id:"c1",nuclear_role_source:"recorded_stain"};
  // The NCL-threshold nucleoli of NPM1 (c2): the settings the screen restores from them rebuild the same recipe, so they are current.
  const nucleolar={id:"region-2d",version:"1.4.0",source:"fiji_nuclear_compartment",region_set_id:"nucleoli",label:"核小体",compartment:"nucleoli",defining_channel_id:"c2",
    detector:{engine:"fiji-nucleolar-compartments",protocol_version:"1.1.0",threshold_method:"otsu",threshold:null,smoothing_sigma_px:0,minimum_area_px:1,maximum_area_px:null,split_touching:false}};
  const revision=(id:string,fid:string,recipe:Record<string,unknown>)=>({id,state:"succeeded",created:1,config:{recipe,field_ids:[fid],measurement:{version:"1.1.0",mode:"raw_intensity"},backgrounds:{}}});
  const revisions=[revision("r1","f1",nuclear),revision("r2","f2",nuclear),
    revision("n1","f1",{...nucleolar,nuclear_revision_id:"r1",nuclear_channel_id:"c1"}),revision("n2","f2",{...nucleolar,nuclear_revision_id:"r2",nuclear_channel_id:"c1"})];
  let selection={version:1,entries:fieldIds.map((id,index)=>({id,field_id:id,revision_id:`n${index+1}`,target_revisions:{nuclei:`r${index+1}`,nucleoli:`n${index+1}`},exclusion_reason:null}))};
  // Each field and channel has its own mean, so a table shows which stain and field its rows measure.
  const mean=(fid:string,channel:string)=>(fid==="f1"?100:200)+(channel==="c1"?11:22);
  const outlines:Record<string,number[][][]>={nuclei:[[[2,2],[14,2],[14,14],[2,14]],[[17,17],[30,17],[30,30],[17,30]]],nucleoli:[[[6,6],[10,6],[10,10],[6,10]],[[21,21],[26,21],[26,26],[21,26]]]};
  // Two groups of one run, one field each: the view opens side by side.
  const experiment={version:"1.0.0",layout:"pair",groups:[{id:"control",label:"対照"},{id:"treatment",label:"処理"}],control_group_id:"control",
    runs:[{id:"run1",label:"Run1",performed_on:null,acquired_on:"2026-01-01"}],independence_confirmed:true,fields:{f1:{group_id:"control",run_id:"run1",sample:null,acquired_on:null},f2:{group_id:"treatment",run_id:"run1",sample:null,acquired_on:null}}};
  const spec=options.pair?{channel_assignment_version:1,target:"nuclei",settings:{nucleolarDefinition:{source:"ncl",marker:"c2",algorithm:"legacy"}},processing:null,measurement:null,experiment}:null;
  // Two saved comparisons of the nuclei, the newer of the mean NPM1 intensity; the numbers only feed the text.
  const interval=(estimate:number)=>({estimate,ci_low:estimate-5,ci_high:estimate+5,confidence_level:.95,basis:"basis",unavailable_reason:null});
  const comparison=(job:string,metric:string,channel:string|null,created:number)=>({job,created,result:{revision_id:"cohort",source_kind:"region-2d",analysis_kind:"region-comparison",
    spec:{plot:{},conditions:["対照","処理"],selection:{source:"region",metric,channel_id:channel,region_set_id:"nuclei"}},source_fields:fieldIds.map(field_id=>({field_id,region_set:{region_set_id:"nuclei"}})),
    comparisons:[{method:"Welch t-test",p_value:.2}],counts:[],warnings:[],plot_data:[],figure:{source_files:["figure.svg"]},
    estimates:{protocol:"comparison-estimates/1.0.0",direction:"treatment_minus_control",control:"対照",treatment:"処理",design:"independent",test:"welch-t",metric,scale:"difference",n_control:3,n_treatment:3,n_pairs:null,
      difference:interval(10),ratio:interval(1.1),groups:[{condition:"対照",n:3,mean:100,sd:5,ci_low:90,ci_high:110,unavailable_reason:null},{condition:"処理",n:3,mean:110,sd:5,ci_low:100,ci_high:120,unavailable_reason:null}],runs:[]}}});
  const saved=options.saved?[comparison("saved-area","area_px",null,2),comparison("saved-mean","mean","c2",3)]:[];
  await context.route("**/v1/**",async route=>{
    const req=route.request(),url=new URL(req.url()),path=url.pathname,method=req.method();
    const headers={"Access-Control-Allow-Origin":new URL(page.url()).origin,"Access-Control-Allow-Credentials":"true","Access-Control-Allow-Headers":"content-type,x-cytellect-request","Access-Control-Allow-Methods":"GET,POST,PUT,DELETE,OPTIONS"};
    const json=(body:unknown,status=200)=>route.fulfill({status,headers,contentType:"application/json",body:JSON.stringify(body)});
    if(method==="OPTIONS")return route.fulfill({status:204,headers});
    if(path==="/v1/ai/check"&&method==="POST"){checks.push(req.postDataJSON());return json({state:options.serviceCheck??"compatible"});}
    if(path==="/v1/ai/status"&&options.aiState)return json({state:options.aiState,source:"none"});
    if(path.endsWith("/discussion-history")&&options.previous)return json({current:null,previous:{job_id:"previous-mean",created:1,
      discussion:{protocol:"result-discussion/1.1.0",origin:"model",context_sha256:"a".repeat(64),prompt_version:"2026-11-16.1",model:"stand-in-model",
        draft:{protocol:"result-discussion/1.1.0",implications:["前回の結果に対する解釈。"],alternatives:[],next_steps:[]}}}});
    if(await aiReadFixture(route))return;
    if(method==="POST"&&path==="/v1/workspaces/w/selection"){selection={...req.postDataJSON(),version:selection.version+1};return json(selection);}
    // A new field from added images; its stains come from the existing assignment.
    if(method==="POST"&&path==="/v1/workspaces/w/region-fields"){uploads.push([...req.postDataBuffer()!.toString("latin1").matchAll(/filename="([^"]+)"/g)].map(match=>match[1]));
      fields.push({id:"f3",workspace_id:"w",metadata:{display_name:"視野 3"},image_info:{shape:[32,32],channels}});fieldIds.push("f3");return json(fields.at(-1),201);}
    if(path==="/v1/session")return json({authenticated:true,retention_hours:24,demo:false});
    if(path==="/v1/workspaces")return json([{id:"w",title:"Image records",created:1,expires:9999999999,deleted:false}]);
    if(path==="/v1/workspaces/w")return json({id:"w",title:"Image records",active_revision:"n2"});
    if(path.endsWith("/region-fields"))return json(fields);
    if(path.endsWith("/channel-assignments"))return json({version:1,assignments:[{channel_id:"c1",stain:"DAPI",role:"nuclear"},{channel_id:"c2",stain:"NPM1",role:"measure"}],global_field_ids:fieldIds,groups:[]});
    if(path.endsWith("/field-links"))return json({version:0,entries:[]});
    if(path.endsWith("/analysis-spec"))return json({version:spec?1:0,spec});
    if(path.endsWith("/selection"))return json(selection);
    if(path.endsWith("/revisions"))return json(revisions);
    if(path.endsWith("/runs"))return json([]);
    if(path.endsWith("/jobs"))return json(saved.map(value=>({id:value.job,kind:"statistics",state:"succeeded",created:value.created,revision_id:"cohort"})));
    const result=saved.find(value=>path===`/v1/jobs/${value.job}/result`);if(result)return json(result.result);
    // No discussion has been made for a saved comparison (the API answers null; AC-06).
    if(method==="GET"&&saved.some(value=>path===`/v1/jobs/${value.job}/discussion`))return json(null);
    // A discussion request is recorded and answered with a stand-in draft; no model is called.
    if(method==="POST"&&saved.some(value=>path===`/v1/jobs/${value.job}/discussion`)){discussions.push(req.postDataJSON());
      return json({job_id:path.split("/")[3],created:1,discussion:{protocol:"result-discussion/1.1.0",origin:"model",context_sha256:"a".repeat(64),prompt_version:"2026-11-16.1",model:"stand-in-model",
        draft:{protocol:"result-discussion/1.1.0",implications:["検定は行っていないため、有意差の有無はこの結果からは言えない。"],alternatives:[],next_steps:[]}}});}
    const figure=saved.find(value=>path===`/v1/jobs/${value.job}/files/figure.svg`);
    if(figure)return route.fulfill({headers,contentType:"image/svg+xml",body:`<svg xmlns="http://www.w3.org/2000/svg" width="400" height="200"><text x="20" y="40">Saved figure ${figure.job}</text></svg>`});
    if(path.endsWith("/region-measurements")){const rid=path.split("/")[3],fid=rid.endsWith("2")?"f2":"f1";
      return json({revision_id:rid,protocol_version:"3.0.0",measurement:{version:"1.1.0",mode:"raw_intensity"},field_failures:[],exclusions:[],field_tables:{[fid]:{rows:[1,2].flatMap(region_id=>["c1","c2"].map(channel_id=>({region_id,channel_id,area_px:region_id*10,area_um2:null,mean:mean(fid,channel_id),median:mean(fid,channel_id),integrated:mean(fid,channel_id)*10})))}}});}
    if(path.endsWith("/compartment-ledger")){const rid=path.split("/")[3];return json({policy:"unresolved-as-missing/1.0.0",fields:{[rid.endsWith("2")?"f2":"f1"]:{nuclei:2,resolved:2,missing:{},excluded:0}}});}
    // The nucleus table (the default table of the nuclei): one row per nucleus, every stain, no nucleoli.
    if(path.endsWith("/nucleus-table")){const fid=url.searchParams.get("field_id")??"f1";return json(nucleusTableFixture({fieldId:fid,revision:path.split("/")[3],channels,nuclei:[1,2],mean:channel=>mean(fid,channel)}));}
    if(path.endsWith("/region-masks")){const rid=path.split("/")[3];return json({regions:outlines[rid.startsWith("n")?"nucleoli":"nuclei"].map((points,index)=>({id:index+1,points})),metadata:{mask_revision_id:`mask-${rid}`}});}
    if(path.endsWith("/preview"))return route.fulfill({headers,contentType:"image/svg+xml",body:`<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"><rect width="32" height="32" fill="${url.searchParams.get("channel_id")==="c1"?"#555":"#999"}"/></svg>`});
    const record=revisions.find(value=>path.endsWith(`/revisions/${value.id}`));if(record)return json(record);
    // A comparison saved without a workspace selection (#284 W1: the n breakdown reads it when present).
    if(path.endsWith("/workspace-selection"))return json({detail:"workspace_selection_not_found"},404);
    unexpected.push(`${method} ${path}${url.search}`);return json({detail:"unexpected_transport_route"},404);
  });
  return {unexpected,uploads,discussions,checks};
}

test("a failed AI instruction can be resent explicitly, with one confirmation and no automatic retry",async({context,page})=>{
  await context.addInitScript(()=>localStorage.setItem("cytellect.ai.proposal-scope-seen.v2","1"));
  const requests:Array<{goal:string;retry_failed?:boolean}>=[];
  await page.route("**/v1/workspaces/w/proposal-drafts",async route=>{
    const headers={"Access-Control-Allow-Origin":new URL(page.url()).origin,"Access-Control-Allow-Credentials":"true",
      "Access-Control-Allow-Headers":"content-type,x-cytellect-request","Access-Control-Allow-Methods":"POST,OPTIONS"};
    if(route.request().method()==="OPTIONS")return route.fulfill({status:204,headers});
    const body=route.request().postDataJSON();requests.push(body);
    const code=requests.length===1||body.retry_failed?"proposal_service_unavailable":"proposal_explicit_retry_required";
    await route.fulfill({status:code==="proposal_explicit_retry_required"?409:503,headers,contentType:"application/json",body:JSON.stringify({detail:code})});
  });
  await imageWorkspace(context,page);
  await page.goto("/workspace?id=w");
  await page.getByRole("textbox",{name:"AIへの指示"}).fill("same instruction");
  const send=page.getByRole("button",{name:"AIへ送信",exact:true});
  await send.click();await expect(appAlerts(page)).toContainText("AI のサービスに接続できません。接続状態を確認してください。");
  expect(requests).toHaveLength(1);
  await send.click();
  const confirm=page.getByRole("group",{name:"AIへの再送の確認"});
  await expect(confirm).toBeVisible();
  await expect(page.getByText("前回の依頼が未完了です。再送には課金される場合があります。",{exact:true})).toHaveCount(1);
  await confirm.getByRole("button",{name:"キャンセル"}).click();
  expect(requests).toHaveLength(2);
  await send.click();await expect(confirm).toBeVisible();
  await confirm.getByRole("button",{name:"再送",exact:true}).click();
  await expect(confirm).toHaveCount(0);await expect(send).toBeEnabled();
  expect(requests).toHaveLength(4);
  expect(requests.map(value=>value.goal)).toEqual(Array(4).fill("same instruction"));
  expect(requests.map(value=>value.retry_failed)).toEqual([undefined,undefined,undefined,true]);
});

test("the table beside one image names what it lists, its stain and the field of its rows, also when a comparison shows another plane",async({page,context})=>{
  const fixture=await imageWorkspace(context,page);
  await page.goto("/workspace?id=w");
  const bar=page.locator("[class*=channelBar]");
  await bar.getByRole("button",{name:"DAPI · c1",exact:true}).click();
  // The table sits beside the image: the settings panel starts closed and leaves it room.
  await expect(page.getByRole("complementary",{name:"画像解析",exact:true})).toHaveCount(0);
  const side=page.locator("[class*=sideMeasurements]");
  const heading=side.getByRole("heading",{level:3});
  // The nuclei open on their nucleus table (every stain per nucleus); one stain's rows are a click away (MV-07).
  await expect(heading).toHaveText("核ごと · すべての染色");
  await expect(side.getByRole("table",{name:"核ごとの表"}).locator("tbody tr")).toHaveCount(2);
  await side.getByRole("button",{name:"このチャンネル",exact:true}).click();
  await expect(heading).toHaveText("核ごと · DAPI（原値）");
  await expect(side.locator("tbody tr").first()).toContainText("111");
  // A comparison that shows only NPM1 of the same field: the rows stay DAPI's, and so does the caption.
  await bar.getByRole("button",{name:"画像を比較",exact:true}).click();
  for(const plane of ["視野 1 · DAPI","視野 2 · DAPI","視野 2 · NPM1"]){const box=page.getByRole("checkbox",{name:plane,exact:true});if(await box.isChecked())await box.uncheck();}
  await page.getByRole("checkbox",{name:"視野 1 · NPM1",exact:true}).check();
  await expect(page.locator("svg[aria-label='視野 1 NPM1']")).toBeVisible();
  await expect(heading).toHaveText("核ごと · DAPI（原値）");
  await expect(side.locator("tbody tr").first()).toContainText("111");
  await expect(side.locator("tbody")).not.toContainText("122");
  // Another field's plane: the caption also names the field the rows come from.
  await page.getByRole("checkbox",{name:"視野 1 · NPM1",exact:true}).uncheck();
  await page.getByRole("checkbox",{name:"視野 2 · NPM1",exact:true}).check();
  await expect(page.locator("svg[aria-label='視野 2 NPM1']")).toBeVisible();
  await expect(heading).toHaveText("視野 1 · 核ごと · DAPI（原値）");
  await expect(side.locator("tbody tr").first()).toContainText("111");
  // Choosing an outline in the shown plane selects that field and stain; rows and caption follow it.
  await page.locator("svg[aria-label='視野 2 NPM1'] path[data-region='1']").click();
  await expect(heading).toHaveText("核ごと · NPM1（原値）");
  await expect(side.locator("tbody tr").first()).toContainText("222");
  expect(fixture.unexpected).toEqual([]);
});

test("several stains open as a colour merge in their stain colours, and choosing one stain shows it alone",async({page,context})=>{
  const fixture=await imageWorkspace(context,page);
  await page.goto("/workspace?id=w");
  const bar=page.locator("[class*=channelBar]");
  const merge=bar.getByRole("button",{name:"重ねて表示",exact:true});
  await expect(merge).toHaveAttribute("aria-pressed","true");
  // The nuclear stain of the adopted nuclei (DAPI) is blue and NPM1 has its own colour; the measured channel stays DAPI.
  const frame=page.locator("div[data-composite]");
  await expect(frame.locator("svg[aria-label='視野 1 DAPI']")).toBeVisible();
  expect(await frame.locator("filter").evaluateAll(filters=>filters.map(filter=>filter.id.split("-").at(-1)))).toEqual(["3f86ff","4fd36a"]);
  await expect(bar.locator("button[data-channel][aria-pressed=true]")).toHaveCount(0);
  await bar.getByRole("button",{name:"NPM1 · c2",exact:true}).click();
  await expect(merge).toHaveAttribute("aria-pressed","false");
  await expect(frame).toHaveCount(0);
  await expect(page.locator("svg[aria-label='視野 1 NPM1']")).toBeVisible();
  await merge.click();
  await expect(frame.locator("filter")).toHaveCount(2);
  expect(fixture.unexpected).toEqual([]);
});

test("nucleoli open on the marker with the nuclei outlined faintly, in one field and side by side",async({page,context})=>{
  const fixture=await imageWorkspace(context,page,{pair:true});
  await page.goto("/workspace?id=w");
  const bar=page.locator("[class*=channelBar]");
  await expect(bar.getByRole("button",{name:"2 画面",exact:true})).toHaveAttribute("aria-pressed","true");
  await bar.getByRole("combobox",{name:"領域",exact:true}).selectOption("nucleoli");
  // Each pane shows NPM1, the nucleolar marker, with its nucleoli and the nuclei they belong to.
  for(const name of ["対照（対照）","処理"]){
    const pane=page.getByRole("region",{name,exact:true});
    await expect(pane.locator("svg[role=group]")).toBeVisible();
    await expect(pane.locator("svg path[data-region]")).toHaveCount(2);
    await expect(pane.locator("svg polygon[class*=context]")).toHaveCount(2);
  }
  await expect(bar.getByRole("button",{name:"NPM1 · c2",exact:true})).toHaveAttribute("aria-pressed","true");
  // One field: the same marker and nuclei, over the colour merge.
  await bar.getByRole("button",{name:"2 画面",exact:true}).click();
  await expect(page.locator("div[data-composite] svg[aria-label='視野 1 NPM1']")).toBeVisible();
  await expect(page.locator("svg path[data-region]")).toHaveCount(2);
  await expect(page.locator("svg polygon[class*=context]")).toHaveCount(2);
  expect(fixture.unexpected).toEqual([]);
});

test("side by side, each pane offers the outline tools of one field",async({page,context})=>{
  const fixture=await imageWorkspace(context,page,{pair:true});
  await page.goto("/workspace?id=w");
  const control=page.getByRole("region",{name:"対照（対照）",exact:true});
  await expect(control.getByRole("toolbar",{name:/の領域編集$/})).toBeVisible();
  await control.getByRole("region",{name:/の測定値$/}).locator("tbody button").first().click();
  for(const name of ["領域を描画","輪郭を再描画","領域を分割","領域を結合","選択領域を削除"])await expect(control.getByRole("button",{name,exact:true})).toBeVisible();
  await expect(page.getByRole("region",{name:"処理",exact:true}).getByRole("button",{name:"領域を描画",exact:true})).toBeVisible();
  expect(fixture.unexpected).toEqual([]);
});

test("a drop of image files adds them as the 画像 button does",async({page,context})=>{
  const fixture=await imageWorkspace(context,page);
  await page.goto("/workspace?id=w");
  const cards=page.locator("[class*=fieldCard]");
  await expect(cards).toHaveCount(2);
  const transfer=await page.evaluateHandle(()=>{const value=new DataTransfer();// Two channels have different bytes: a file with the same bytes as another is a copy, not a field (#284 control A).
    ["A03_c1.tif","A03_c2.tif"].forEach((name,index)=>value.items.add(new File([new Uint8Array([1,2,3+index])],name,{type:"image/tiff"})));return value;});
  const main=page.locator("main");
  await main.dispatchEvent("dragover",{dataTransfer:transfer});
  await main.dispatchEvent("drop",{dataTransfer:transfer});
  await expect.poll(()=>fixture.uploads).toEqual([["A03_c1.tif","A03_c2.tif"]]);
  await expect(cards).toHaveCount(3);
  await expect(page.getByRole("dialog",{name:"画像の追加"})).toHaveCount(0);
  await expect(appAlerts(page).filter({hasText:/./})).toHaveCount(0);
  expect(fixture.unexpected).toEqual([]);
});

test("the AI composer opens the AI panel when focused, without the demo's examples",async({page,context})=>{
  const fixture=await imageWorkspace(context,page);
  await page.goto("/workspace?id=w");
  await expect(page.locator("[class*=fieldCard]")).toHaveCount(2);
  await expect(page.getByRole("complementary",{name:"画像解析"})).toHaveCount(0);
  await page.getByLabel("AIへの指示",{exact:true}).click();
  await expect(page.getByRole("complementary",{name:"AI"})).toBeVisible();
  await expect(page.getByLabel("AIへの指示",{exact:true})).toHaveAttribute("placeholder","AIに指示");
  await expect(page.getByRole("group",{name:"指示の例"})).toHaveCount(0);
  expect(fixture.unexpected).toEqual([]);
});

test("before the first proposal after the scope widened, the AI panel asks once what is sent; cancelling sends nothing",async({page,context})=>{
  const fixture=await imageWorkspace(context,page);
  const proposals:string[]=[];
  page.on("request",request=>{if(request.method()==="POST"&&new URL(request.url()).pathname.endsWith("/proposal-drafts"))proposals.push(request.postData()??"");});
  await page.goto("/workspace?id=w");
  await expect(page.locator("[class*=fieldCard]")).toHaveCount(2);
  await page.getByLabel("AIへの指示",{exact:true}).fill("核小体の面積を比べたい");
  await page.getByRole("button",{name:"AIへ送信"}).click();
  const scope=page.getByRole("group",{name:"AIに送る内容の確認"});
  await expect(scope).toContainText("代表的な視野の縮小画像");
  await scope.getByRole("button",{name:"キャンセル"}).click();
  await expect(scope).toHaveCount(0);
  expect(proposals).toEqual([]);
  // Sending without previews turns the setting off and records the confirmation, so the next request asks no more.
  await page.getByRole("button",{name:"AIへ送信"}).click();
  await page.getByRole("group",{name:"AIに送る内容の確認"}).getByRole("button",{name:"縮小画像なしで送信"}).click();
  expect(await page.evaluate(()=>[localStorage.getItem("cytellect.ai.include-previews"),localStorage.getItem("cytellect.ai.proposal-scope-seen.v2")])).toEqual(["0","1"]);
  expect(fixture.unexpected.filter(route=>!route.includes("proposal")&&!route.includes("analysis-spec"))).toEqual([]);
});

test("statistics open on the latest saved comparison, the saved comparisons switch, and ?step= opens a tab",async({page,context})=>{
  const fixture=await imageWorkspace(context,page,{saved:true});
  await page.goto("/workspace?id=w&step=statistics");
  const navigation=page.getByRole("navigation",{name:"作業の切替"});
  await expect(navigation.getByRole("button",{name:"統計",exact:true})).toHaveAttribute("aria-current","page");
  const results=page.getByRole("region",{name:"測定結果の統計解析"});
  const summary=results.getByRole("region",{name:"結果のまとめ"});
  await expect(summary).toContainText("核の平均輝度（NPM1）");
  await expect(results.getByRole("status").filter({hasText:/前の結果|記録した結果/})).toHaveCount(0);
  const switcher=results.getByRole("group",{name:"保存した比較"});
  await expect(switcher.getByRole("button")).toHaveCount(2);
  await switcher.getByRole("button",{name:/面積/}).click();
  await expect(summary).toContainText("核の面積");
  await expect(page.getByRole("complementary",{name:"解析対象"}).getByRole("combobox",{name:"指標",exact:true})).toHaveValue("area_px");
  await expect(results.getByRole("status").filter({hasText:/前の結果|記録した結果/})).toHaveCount(0);
  // A figure link opens the figure tab on the latest saved figure.
  await page.goto("/workspace?id=w&step=figure");
  await expect(navigation.getByRole("button",{name:"グラフ",exact:true})).toHaveAttribute("aria-current","page");
  await expect(page.getByRole("combobox",{name:"保存した図"})).toHaveValue("saved-mean");
  await expect(page.getByText("Saved figure saved-mean",{exact:true})).toBeVisible();
  expect(fixture.unexpected).toEqual([]);
});

test("a discussion is sent the summary the screen shows and starts from the goal written to the AI",async({page,context})=>{
  const fixture=await imageWorkspace(context,page,{saved:true});
  await page.addInitScript(()=>localStorage.setItem("cytellect.ai.goal.w","NPM1 の核小体への局在が処理で変わるかを確かめる"));
  await page.goto("/workspace?id=w&step=statistics");
  const results=page.getByRole("region",{name:"測定結果の統計解析"});
  const heading=await results.getByRole("region",{name:"結果のまとめ"}).getByRole("heading",{level:3}).innerText();
  const panel=results.getByRole("region",{name:"考察"});
  await expect(panel.getByRole("textbox",{name:"実験の目的（任意）"})).toHaveValue("NPM1 の核小体への局在が処理で変わるかを確かめる");
  await panel.getByRole("button",{name:"考察を生成"}).click();
  // The draft is shown as written, with no note added to it (plan §8).
  await expect(panel).toContainText("検定は行っていないため、有意差の有無はこの結果からは言えない。");
  expect(fixture.discussions).toHaveLength(1);
  const [sent]=fixture.discussions as [{summary:{heading:string;points:string[]};experiment:{purpose:string}}];
  expect(sent.summary.heading).toBe(heading);
  expect(sent.summary.points.length).toBeGreaterThan(0);
  expect(sent.experiment.purpose).toBe("NPM1 の核小体への局在が処理で変わるかを確かめる");
  expect(fixture.unexpected).toEqual([]);
});

test("unconfigured AI explains setup beside disabled actions without sending a request",async({page,context})=>{
  const fixture=await imageWorkspace(context,page,{saved:true,aiState:"unconfigured"});
  await page.goto("/workspace?id=w&step=statistics");
  const panel=page.getByRole("region",{name:"考察",exact:true});
  await expect(panel).toContainText("AI は未設定");
  await expect(panel.getByRole("button",{name:"考察を生成"})).toBeDisabled();
  await expect(page.getByRole("textbox",{name:"AIへの指示"})).toBeDisabled();
  await page.getByRole("button",{name:"AI の設定",exact:true}).click();
  const settings=page.getByRole("complementary",{name:"AI",exact:true}).locator("details").filter({has:page.locator("summary").filter({hasText:/^AI の設定$/})});
  await settings.getByText("AI の設定",{exact:true}).click();
  await expect(settings).toContainText("Docker・開発環境");
  await expect(settings).toContainText("送信内容：保存済みの結果");
  await expect(settings.getByRole("checkbox")).toBeChecked();
  await settings.getByRole("checkbox").uncheck();
  expect(await page.evaluate(()=>localStorage.getItem("cytellect.ai.include-previews"))).toBe("0");
  expect(fixture.discussions).toHaveLength(0);
  expect(fixture.unexpected).toEqual([]);
});

test("a recalculated comparison keeps the previous discussion separate and generates once on request",async({page,context})=>{
  const fixture=await imageWorkspace(context,page,{saved:true,previous:true});
  await page.goto("/workspace?id=w&step=statistics");
  const previous=page.getByRole("region",{name:"前の結果の考察",exact:true});
  const current=page.getByRole("region",{name:"考察",exact:true});
  await expect(previous).toContainText("前回の結果に対する解釈。");
  await expect(current.getByRole("button",{name:"考察を生成"})).toBeEnabled();
  expect(fixture.discussions).toHaveLength(0);
  await current.getByRole("button",{name:"考察を生成"}).click();
  await expect(current).toContainText("検定は行っていないため");
  expect(fixture.discussions).toHaveLength(1);
  expect(fixture.unexpected).toEqual([]);
});

test("service compatibility is checked only on request and an incompatible service disables sending",async({page,context})=>{
  const fixture=await imageWorkspace(context,page,{saved:true,serviceCheck:"incompatible"});
  await page.goto("/workspace?id=w&step=statistics");
  const instruction=page.getByRole("textbox",{name:"AIへの指示"});
  await expect(instruction).toBeEnabled();
  await instruction.click();
  const settings=page.getByRole("complementary",{name:"AI",exact:true}).locator("details").filter({has:page.locator("summary").filter({hasText:/^AI の設定$/})});
  await settings.getByText("AI の設定",{exact:true}).click();
  expect(fixture.checks).toEqual([]);
  await settings.getByRole("button",{name:"サービスの対応を確認"}).click();
  await expect(settings).toContainText("このアプリに対応していません");
  await expect(instruction).toBeDisabled();
  await expect(page.getByRole("region",{name:"考察",exact:true}).getByRole("button",{name:"考察を生成"})).toBeDisabled();
  expect(fixture.checks).toEqual([{}]);
  expect(fixture.discussions).toEqual([]);
  expect(fixture.unexpected).toEqual([]);
});
