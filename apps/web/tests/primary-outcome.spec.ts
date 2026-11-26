import {aiReadFixture} from "./ai-read-fixture";
import {nucleusTableFixture} from "./nucleus-table-fixture";
import {expect,test,type BrowserContext,type Page} from "@playwright/test";

/**
 * #257 RP-04 on the connected workspace (transport contract only: fixed response records, not microscopy).
 * The star beside the metric declares the chosen condition; results show 主要 or 探索 only once a declaration exists,
 * and a saved figure is judged by the time of the statistics it re-draws (calculated_at), never by the re-render's own
 * creation: 解析 -> 宣言 -> 図の描き直し -> 開き直す shows the result as exploratory.
 */
async function workspace(context:BrowserContext,page:Page,{declaredAt,calculatedAt}:{declaredAt:number|null;calculatedAt:number}){
  const unexpected:string[]=[];
  const channels=[{channel_id:"c1",label:"Hoechst",stain:"Hoechst"},{channel_id:"c2",label:"NPM1",stain:"NPM1"}];
  const fields=[{id:"f1",workspace_id:"w",metadata:{display_name:"視野 1"},image_info:{shape:[32,32],channels}}];
  const primary={version:"1.0.0",metric:"area_px",region_set_id:"nuclei",channel_id:null,declared_at:declaredAt};
  // The server's default spec (AnalysisSpec(channel_assignment_version=1)), with the declaration when there is one.
  const defaults={schema_version:"1.0.0",channel_assignment_version:1,target:"nuclei",settings:{nuclearMaxSide:null,nuclearProbability:0.5,nuclearNms:0.3,
    nucleolarDefinition:{source:"dapi_poor",marker:"",pixelUm:null,relative:0.7,algorithm:null},cellDefinition:{source:"manual",channel:""},nucleolarSigma:null,
    nucleolarRim:null,nucleolarMinimumArea:null,nucleolarMaximumArea:null,background:"raw"},processing:null,measurement:null,backgrounds:{},confirmed_channel_ids:[],
    metrics:[],selection:{field_ids:[],gfp:null},statistics:null,additional_analyses:[],figure_proposals:[],figure:null,figure_presentation:null,experiment:null};
  let spec:{version:number;spec:Record<string,unknown>|null}={version:1,spec:{...defaults,...(declaredAt===null?{}:{primary_outcome:primary})}};
  const recipe={id:"region-2d",version:"1.7.0",source:"stardist_nuclear",region_set_id:"nuclei",label:"核",defining_channel_id:"c1",nuclear_role_source:"recorded_stain"};
  const revision={id:"r1",state:"succeeded",created:1,config:{recipe,field_ids:["f1"],measurement:{version:"1.1.0",mode:"raw_intensity"},backgrounds:{}}};
  // A statistics job calculated at `calculatedAt`, re-drawn (a figure-render job) at 3000, after any declaration.
  const jobs=[{id:"stats-1",kind:"statistics",state:"succeeded",created:calculatedAt,calculated_at:calculatedAt,revision_id:"r1",error:null,attempts:1},
    {id:"figure-1",kind:"figure-render",state:"succeeded",created:3000,calculated_at:calculatedAt,revision_id:"r1",error:null,attempts:1}];
  const result=(job:string)=>({source_kind:"region-2d",analysis_kind:"descriptive",revision_id:"r1",metric:"area_px",unit:"pixel²",
    ...(job==="figure-1"?{source_job_id:"stats-1"}:{}),spec:{mode:"descriptive",selection:{source:"region",region_set_id:"nuclei",channel_id:null,metric:"area_px"},plot:{}},
    source_fields:[{field_id:"f1",region_set:{region_set_id:"nuclei"}}],warnings:[],plot_data:[],field_summary:[],figure:{source_files:["figure.svg"]}});
  await context.route("**/v1/**",async route=>{
    if(await aiReadFixture(route))return;
    const req=route.request(),url=new URL(req.url()),path=url.pathname,method=req.method();
    const headers={"Access-Control-Allow-Origin":new URL(page.url()).origin,"Access-Control-Allow-Credentials":"true","Access-Control-Allow-Headers":"content-type,x-cytellect-request","Access-Control-Allow-Methods":"GET,POST,PUT,DELETE,OPTIONS"};
    const json=(body:unknown,status=200)=>route.fulfill({status,headers,contentType:"application/json",body:JSON.stringify(body)});
    if(method==="OPTIONS")return route.fulfill({status:204,headers});
    if(path==="/v1/session")return json({authenticated:true,retention_hours:24,demo:false});
    if(path==="/v1/workspaces")return json([{id:"w",title:"Transport records",created:1,expires:9999999999,deleted:false}]);
    if(path==="/v1/workspaces/w")return json({id:"w",title:"Transport records",active_revision:"r1"});
    if(path.endsWith("/region-fields"))return json(fields);
    if(path.endsWith("/channel-assignments"))return json({version:1,assignments:[{channel_id:"c1",stain:"Hoechst",role:"nuclear"},{channel_id:"c2",stain:"NPM1",role:"marker"}],global_field_ids:["f1"],groups:[]});
    if(path.endsWith("/field-links"))return json({version:0,entries:[]});
    if(path.endsWith("/analysis-spec")){
      if(method==="PUT"){
        // The server keeps or renews the declaration time (tests/test_primary_outcome.py); a fixed time stands in.
        const sent=(req.postDataJSON() as {spec:Record<string,unknown>}).spec;
        const declared=sent.primary_outcome as Record<string,unknown>|undefined;
        spec={version:spec.version+1,spec:declared?{...sent,primary_outcome:{...declared,declared_at:4000}}:sent};
      }
      return json(spec);
    }
    if(path.endsWith("/selection"))return json({version:1,entries:[{id:"f1",field_id:"f1",revision_id:"r1",target_revisions:{nuclei:"r1"},exclusion_reason:null}]});
    if(path.endsWith("/revisions"))return json([revision]);
    if(path.endsWith("/runs"))return json([]);
    if(path.endsWith("/workspaces/w/jobs"))return json(jobs);
    for(const job of jobs){
      if(path===`/v1/jobs/${job.id}/result`)return json(result(job.id));
      if(path===`/v1/jobs/${job.id}/files/figure.svg`)return route.fulfill({headers,contentType:"image/svg+xml",body:'<svg xmlns="http://www.w3.org/2000/svg" width="500" height="300"><rect width="500" height="300" fill="white"/><text x="40" y="60">Saved figure</text></svg>'});
    }
    if(path.endsWith("/current"))return json({});
    if(path.endsWith("/region-measurements"))return json({revision_id:"r1",protocol_version:"3.0.0",measurement:{version:"1.1.0",mode:"raw_intensity"},field_failures:[],exclusions:[],
      field_tables:{f1:{rows:[1,2].flatMap(region_id=>channels.map(ch=>({region_id,channel_id:ch.channel_id,area_px:region_id===1?120:40,area_um2:null,mean:30,median:29,integrated:300})))}}});
    if(path.endsWith("/nucleus-table"))return json(nucleusTableFixture({fieldId:"f1",revision:"r1",channels,nuclei:[1,2]}));
    if(path.endsWith("/region-masks"))return json({regions:[1,2].map(id=>({id,points:id===1?[[3,3],[14,3],[14,14],[3,14]]:[[18,18],[24,18],[24,24],[18,24]]})),metadata:{mask_revision_id:"mask-r1"}});
    if(path.endsWith("/preview"))return route.fulfill({headers,contentType:"image/svg+xml",body:'<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"><rect width="32" height="32" fill="#869fff"/></svg>'});
    if(path.endsWith("/revisions/r1"))return json(revision);
    // A comparison saved without a workspace selection (#284 W1: the n breakdown reads it when present).
    if(path.endsWith("/workspace-selection"))return json({detail:"workspace_selection_not_found"},404);
    // The conversation of the workspace (#284 W2), read when it opens.
    if(path.endsWith("/assistant-messages"))return json({messages:[]});
    unexpected.push(`${method} ${path}`);return json({detail:"unexpected_transport_route"},404);
  });
  return {unexpected,spec:()=>spec};
}

const heading=(page:Page)=>page.getByRole("region",{name:"図の作成・保存"}).locator("p").filter({hasText:"面積"}).first();

for(const [name,calculatedAt,role] of [["before",1000,"探索"],["after",2500,"主要"]] as const)
  test(`a re-drawn figure is judged by its statistics' time (${name} the declaration)`,async({page,context})=>{
    const fixture=await workspace(context,page,{declaredAt:2000,calculatedAt});
    await page.goto("/workspace?id=w");
    await page.getByRole("navigation",{name:"作業の切替"}).getByRole("button",{name:"グラフ",exact:true}).click();
    await expect(page.getByRole("combobox",{name:"保存した図"})).toHaveValue("stats-1");
    await expect(heading(page).locator("[data-outcome-role]")).toHaveText(role);
    expect(fixture.unexpected).toEqual([]);
  });

test("nothing is marked without a declaration, and the star declares the chosen condition",async({page,context})=>{
  const fixture=await workspace(context,page,{declaredAt:null,calculatedAt:1000});
  await page.goto("/workspace?id=w");
  await page.getByRole("navigation",{name:"作業の切替"}).getByRole("button",{name:"グラフ",exact:true}).click();
  await expect(page.getByRole("combobox",{name:"保存した図"})).toHaveValue("stats-1");
  await expect(page.locator("[data-outcome-role]")).toHaveCount(0);
  const star=page.getByRole("complementary",{name:"解析対象"}).getByRole("button",{name:"主要指標",exact:true});
  await expect(star).toHaveAttribute("aria-pressed","false");
  await star.click();
  await expect.poll(()=>(fixture.spec().spec as {primary_outcome?:unknown}|null)?.primary_outcome).toMatchObject({metric:"area_px",region_set_id:"nuclei",channel_id:null});
  await expect(star).toHaveAttribute("aria-pressed","true");
  // Declared at 4000, after the saved result's statistics (1000): the shown result is exploratory.
  await expect(heading(page).locator("[data-outcome-role]")).toHaveText("探索");
  // NS-01: the registered stains give the nucleolar measures (NPM1) but not the 5-EU one.
  const theme=page.getByRole("complementary",{name:"解析対象"}).locator("details").filter({hasText:"核小体ストレス"});
  await theme.locator("summary").click();
  const list=theme.getByRole("list",{name:"核小体ストレスの指標"});
  await expect(list.getByRole("listitem").filter({hasText:"最大の核小体の割合"})).toContainText("染色：NPM1");
  await expect(list.getByRole("listitem").filter({hasText:"核小体の平均輝度（5-EU）"})).toContainText("染色：5-EU（未登録）");
  // Issue E-7: the theme is an entry for choosing these measures. A registered row chooses its measure in the selector
  // above; an unregistered row is not a control.
  const largest=list.getByRole("button",{name:/最大の核小体の割合/});
  await expect(largest).toHaveAttribute("aria-pressed","false");
  await largest.click();
  await expect(largest).toHaveAttribute("aria-pressed","true");
  await expect(page.getByRole("complementary",{name:"解析対象"}).getByRole("radio",{name:"核小体"})).toHaveAttribute("aria-checked","true");
  await expect(list.getByRole("button",{name:/核小体の平均輝度（5-EU）/})).toHaveCount(0);
  await page.screenshot({path:test.info().outputPath("primary-outcome.png")});
  expect(fixture.unexpected).toEqual([]);
});
