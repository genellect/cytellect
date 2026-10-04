import {test,expect,type Page,type Locator,type APIResponse} from "@playwright/test";
import {execFileSync} from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import {createRegionWorkspace,workspaceTestRuntime} from "./workspace-session";

const root=path.resolve(__dirname,"../../..");const {api,python,dataDir}=workspaceTestRuntime();const evidence=process.env.CYTELLECT_SCREENSHOT_DIR;
type Metadata={condition:string;sample:string;experimental_unit:string;acquisition_date:string;pair:string|null;repeat_length:null};
type PracticeField={field_id:string;independent:Metadata;paired:Metadata};
type SavedValue={condition:string;experimental_unit:string;sample?:string;field_id?:string;value:number};
async function json(response:Pick<APIResponse,"ok"|"json">){expect(response.ok()).toBeTruthy();return response.json();}
async function post(page:Page,url:string,data:unknown){return json(await page.request.post(api+url,{data,headers:{Origin:new URL(page.url()).origin,"X-Cytellect-Request":"1"}}));}
async function waitJob(page:Page,id:string){await expect.poll(async()=>{const job=await json(await page.request.get(`${api}/v1/jobs/${id}`));if(["failed","cancelled"].includes(job.state))throw Error(job.error);return job.state;},{timeout:120000,intervals:[500]}).toBe("succeeded");}
async function open(details:Locator){if(!await details.evaluate(element=>(element as HTMLDetailsElement).open))await details.locator(":scope>summary").click();return details;}
const byLabel=(parent:Page|Locator,label:string)=>parent.getByLabel(label,{exact:true});
async function shot(page:Page,name:string,element?:Locator){if(evidence){fs.mkdirSync(evidence,{recursive:true});if(element)await element.screenshot({path:path.join(evidence,name)});else await page.screenshot({path:path.join(evidence,name),fullPage:true});}}
async function comparison(page:Page,revisionId:string,kind:"independent"|"paired"){
 const created=await post(page,`/v1/revisions/${revisionId}/region-comparisons`,{mode:"region-experimental-unit",version:"1.0.0",selection:{source:"region",region_set_id:"regions",channel_id:"signal",metric:"mean_corrected"},design:{kind,confirmed:true,unit_definition:"Explicit artificial practice units; no biological observations",pairing_basis:kind==="paired"?"Artificial P-1 to P-3 mappings from the practice record card":null},conditions:["A","B"],comparison_family:{family_id:"primary",kind:"control",control:"A",contrasts:[["A","B"]]},acquisition_review:{confirmed:true,basis:"same-settings",field_batches:{},spatial_sampling_confirmed:true},missingness_confirmed:true,plot:{kind:kind==="paired"?"paired":"distribution",preset:"nature-double",language:"en",width_inches:7,height_inches:3,font_size:7,x_label:"",y_label:"",group_order:["A","B"]}});
 await waitJob(page,created.job_id);return {jobId:created.job_id,result:await json(await page.request.get(`${api}/v1/jobs/${created.job_id}/region-comparison`))};
}
async function workbench(page:Page,title:string){await page.reload();await page.getByRole("button",{name:new RegExp(title)}).click();}
async function hierarchy(page:Page,savedRevisionNumber?:number){await page.getByRole("button",{name:/03 統計解析/}).click();if(savedRevisionNumber){const history=page.locator("details").filter({has:page.locator(":scope>summary",{hasText:"比較の履歴"})});await open(history);await history.getByRole("button",{name:new RegExp(`解析版 ${savedRevisionNumber} · 作成済み`)}).click();}const view=byLabel(page,"実験単位から視野への集計");await expect(view).toBeVisible();return view;}
async function unitTree(view:Locator,condition:string,unit:string){
 const unitNode=await open(byLabel(view,`${condition} 実験単位 ${unit}`));
 const first=await open(byLabel(unitNode,`${condition} 実験単位 ${unit} 試料 ${condition}1-s1`));
 const second=await open(byLabel(unitNode,`${condition} 実験単位 ${unit} 試料 ${condition}1-s2`));return {unit:unitNode,first,second};
}
async function preview(page:Page){await expect.poll(()=>page.getByTestId("image-canvas").locator("canvas").first().evaluate(element=>{const canvas=element as HTMLCanvasElement;const pixels=canvas.getContext("2d")!.getImageData(0,0,canvas.width,canvas.height).data;let opaque=0,count=0;for(let i=3;i<pixels.length;i+=64){count++;if(pixels[i]>250)opaque++;}return opaque/count;})).toBeGreaterThan(.3);}

async function verifyReadiness(page:Page,fixture:string,practice:PracticeField[]){
 const title="Artificial comparison readiness";const workspace=await post(page,"/v1/workspaces",{title});
 const headers={Origin:new URL(page.url()).origin,"X-Cytellect-Request":"1"};const fields:{id:string}[]=[];
 for(const [index,row] of practice.slice(0,6).entries()){
  // Reuse only known artificial pixels. A/B/C assignments are software fixtures,
  // not biological replicates or claims about the underlying practice design.
  fields.push(await json(await page.request.post(`${api}/v1/workspaces/${workspace.id}/region-fields`,{headers,multipart:{
   specification:JSON.stringify({version:"1.0.0",channels:[{channel_id:"signal",label:"練習信号",stain:null,identity_confirmed:true}],metadata:{condition:["A","B","C"][Math.floor(index/2)],sample:index===0?null:`practice-s${index}`,experimental_unit:`practice-u${index}`,acquisition_date:index===2?null:"practice-batch",pair:null,repeat_length:null}}),
   ch0:{name:"artificial-signal.tif",mimeType:"image/tiff",buffer:fs.readFileSync(path.join(fixture,"participant/images",`${row.field_id}-signal.tif`))},
   labels:{name:"artificial-labels.tif",mimeType:"image/tiff",buffer:fs.readFileSync(path.join(fixture,"participant/masks",`${row.field_id}-labels.tif`))},
  }})));
 }
 const bg={polygon:[[0,0],[12,0],[12,12],[0,12]],confirmed:true};
 const initial=await post(page,`/v1/workspaces/${workspace.id}/region-analyses`,{recipe:{id:"region-2d",version:"1.0.0",region_set_id:"regions",label:"人工領域",source:"imported"},backgrounds:Object.fromEntries(fields.map(field=>[field.id,{signal:bg}])),exclusions:[]});
 await waitJob(page,initial.job_id);await post(page,`/v1/revisions/${initial.revision_id}/review`,{});
 await page.setViewportSize({width:1440,height:1000});await workbench(page,title);await page.getByRole("button",{name:/03 統計解析/}).click();
 const panel=byLabel(page,"統計解析");const readiness=byLabel(page,"比較の前に確認すること");const submit=panel.getByRole("button",{name:"比較と図を作成",exact:true});
 const conditions=panel.getByRole("group",{name:"比較に含める条件",exact:true});
 const confirm=async()=>{
  await panel.getByRole("checkbox",{name:"独立性と、必要な対応関係を実験記録で確認しました。",exact:true}).check();
  await panel.getByRole("checkbox",{name:"撮影・標識・背景と非飽和の信号を比較できると確認しました。",exact:true}).check();
  await panel.getByRole("checkbox",{name:"除外・欠測と比較対象を確認しました。",exact:true}).check();
 };
 const choose=async()=>{
  await byLabel(panel,"比較する測定値").selectOption("signal-mean_corrected");
  await byLabel(panel,"実験デザイン").selectOption("independent");await byLabel(panel,"独立実験単位の定義").fill("Artificial independent units for software checks only");
  for(const condition of ["A","B","C"])await conditions.getByRole("checkbox",{name:condition,exact:true}).check();
  await byLabel(panel,"比較する組み合わせ").selectOption("planned");await panel.getByRole("checkbox",{name:"A と B",exact:true}).check();await confirm();
 };
 let comparisonPosts=0;page.on("request",request=>{if(request.method()==="POST"&&new URL(request.url()).pathname.endsWith("/region-comparisons"))comparisonPosts++;});
 await choose();await expect(submit).toBeDisabled();await expect(readiness).toContainText("「C」を使う比較がありません");
 await expect(readiness).toContainText("視野 1：試料が未記録");await expect(readiness).toContainText("視野 3：撮影日／バッチが未記録");
 await readiness.getByRole("button",{name:"比較の組み合わせへ",exact:true}).click();await expect(panel.getByRole("checkbox",{name:"A と B",exact:true})).toBeFocused();await expect(conditions.getByRole("checkbox",{name:"C",exact:true})).toBeChecked();
 await shot(page,"comparison-readiness-missing-desktop.png",readiness);await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await shot(page,"comparison-readiness-missing-mobile.png");
 await readiness.getByRole("button",{name:"視野 1 の試料へ",exact:true}).click();await expect(byLabel(page,"視野 1 の試料")).toBeFocused();await byLabel(page,"視野 1 の試料").fill("practice-s0");
 await expect(readiness).toContainText("入力した実験情報を新しい解析版に保存");await expect(readiness).not.toContainText("視野 1：試料が未記録");
 await byLabel(page,"視野 3 の撮影日／バッチ").fill("practice-batch");await readiness.getByRole("button",{name:"実験情報を保存する操作へ",exact:true}).click();
 const save=panel.getByRole("button",{name:"実験情報を新しい解析版に保存",exact:true});await expect(save).toBeFocused();
 const saving=page.waitForResponse(response=>new URL(response.url()).pathname.endsWith("/region-metadata")&&response.request().method()==="POST");await save.click();const discard=page.getByRole("dialog",{name:"未保存の変更を確認"});await expect(discard).toContainText("比較条件");await discard.getByRole("button",{name:"変更を破棄して続ける",exact:true}).click();const child=await json(await saving);await waitJob(page,child.job_id);
 await expect.poll(async()=>byLabel(page,"比較の前に確認すること").textContent()).toContain("この解析版の品質確認を完了");
 const old=await json(await page.request.get(`${api}/v1/revisions/${initial.revision_id}`));expect(old.config.field_snapshot[fields[0].id].metadata.sample).toBeNull();expect(old.config.field_snapshot[fields[2].id].metadata.acquisition_date).toBeNull();
 await readiness.getByRole("button",{name:"画像と品質確認へ",exact:true}).click();await expect(page.getByTestId("image-canvas")).toBeVisible();
 await post(page,`/v1/revisions/${child.revision_id}/review`,{});await workbench(page,title);await page.getByRole("button",{name:/03 統計解析/}).click();await choose();
 await expect(readiness.locator("li")).toHaveCount(1);await expect(submit).toBeDisabled();
 await panel.getByRole("checkbox",{name:"B と C",exact:true}).check();await confirm();await expect(submit).toBeEnabled();await expect(readiness).toBeHidden();
 await byLabel(panel,"比較する組み合わせ").selectOption("control");await byLabel(panel,"対照群").selectOption("A");await conditions.getByRole("checkbox",{name:"A",exact:true}).uncheck();await confirm();
 await expect(readiness).toContainText("対照群「A」が比較対象から外れています");await expect(byLabel(panel,"対照群")).toHaveValue("A");await expect(submit).toBeDisabled();
 await readiness.getByRole("button",{name:"対照群を確認する",exact:true}).click();await expect(byLabel(panel,"対照群")).toBeFocused();await shot(page,"comparison-readiness-stale-control-mobile.png");
 await conditions.getByRole("checkbox",{name:"A",exact:true}).check();await byLabel(panel,"比較する組み合わせ").selectOption("planned");await conditions.getByRole("checkbox",{name:"C",exact:true}).uncheck();
 await expect(readiness).toContainText("事前に決めた比較の組み合わせを選んで");await panel.getByRole("checkbox",{name:"B と A",exact:true}).check();await confirm();await expect(submit).toBeEnabled();expect(comparisonPosts).toBe(0);
 const creating=page.waitForResponse(response=>new URL(response.url()).pathname.endsWith("/region-comparisons")&&response.request().method()==="POST");await submit.click();const response=await creating;
 const body=response.request().postDataJSON();expect(body.conditions).toEqual(["B","A"]);expect(body.comparison_family.contrasts).toEqual([["B","A"]]);
 const job=await json(response);await waitJob(page,job.job_id);await expect(byLabel(page,"保存済みの群間比較")).toBeVisible();expect(comparisonPosts).toBe(1);
 if(evidence)fs.writeFileSync(path.join(evidence,"comparison-readiness-receipt.json"),JSON.stringify({scope:"Artificial six-field A/B/C software choices; source-runtime only, no biological or human-usability validation",unusedConditionNamed:true,scopeNotAutomaticallyChanged:true,staleControlRetained:true,exactMetadataFocus:true,draftNotTreatedAsSaved:true,priorMetadataUnchanged:true,newRevisionRequiresReview:true,explicitAcknowledgementsPreserved:true,invalidComparisonRequests:0,submittedConditions:body.conditions,submittedContrasts:body.comparison_family.contrasts},null,2));
}

test("saved comparisons expose exact unit sample field values and protected historical measurement sources",async({page})=>{
 test.setTimeout(240000);if(!dataDir)throw Error("Isolated runtime data directory required");const errors:string[]=[];page.on("pageerror",error=>errors.push(error.message));
 const title="Artificial comparison hierarchy";const workspace=await createRegionWorkspace(page,title);const fixture=fs.mkdtempSync(path.join(dataDir,"comparison-hierarchy-"));
 const prepared=JSON.parse(execFileSync(python,["-c","import sys,json,runpy;from pathlib import Path;m=runpy.run_path(sys.argv[1]);m['prepare'](Path(sys.argv[2]));print(json.dumps({'fields':[{'field_id':r['field_id'],'independent':m['metadata'](r,'independent'),'paired':m['metadata'](r,'paired')} for r in m['records']()],'reference':m['reference']()}))",path.join(root,"scripts/prepare_usability_practice.py"),fixture],{encoding:"utf8"})) as {fields:PracticeField[];reference:{field_medians:number[];sample_means:Record<string,number>;unit_values:{A:number[];B:number[]};paired_complete_pairs:number}};
 // These constants come from the independently hand-derived practice reference, not a reimplementation of aggregation.
 expect(prepared.reference.field_medians.slice(0,3)).toEqual([2,4,10]);expect(prepared.reference.sample_means["A1-s1"]).toBe(3);expect(prepared.reference.sample_means["A1-s2"]).toBe(10);expect(prepared.reference.unit_values.A[0]).toBe(6.5);
 const fields:{id:string;metadata:Metadata}[]=[];const headers={Origin:new URL(page.url()).origin,"X-Cytellect-Request":"1"};
 for(const row of prepared.fields){
  const image=fs.readFileSync(path.join(fixture,"participant/images",`${row.field_id}-signal.tif`));
  // A byte-identical second artificial channel tests display restoration only; it is never a biological marker.
  fields.push(await json(await page.request.post(`${api}/v1/workspaces/${workspace.id}/region-fields`,{headers,multipart:{specification:JSON.stringify({version:"1.0.0",channels:[{channel_id:"signal",label:"練習信号",stain:null,identity_confirmed:true},{channel_id:"reference",label:"表示用参照",stain:null,identity_confirmed:true}],metadata:row.independent}),ch0:{name:`${row.field_id}-signal.tif`,mimeType:"image/tiff",buffer:image},ch1:{name:`${row.field_id}-display-copy.tif`,mimeType:"image/tiff",buffer:image},labels:{name:`${row.field_id}-labels.tif`,mimeType:"image/tiff",buffer:fs.readFileSync(path.join(fixture,"participant/masks",`${row.field_id}-labels.tif`))}}})));
 }
 const background={polygon:[[0,0],[12,0],[12,12],[0,12]],confirmed:true};
 const initial=await post(page,`/v1/workspaces/${workspace.id}/region-analyses`,{recipe:{id:"region-2d",version:"1.0.0",region_set_id:"regions",label:"人工領域",source:"imported"},backgrounds:Object.fromEntries(fields.map(field=>[field.id,{signal:background,reference:background}])),exclusions:[]});await waitJob(page,initial.job_id);await post(page,`/v1/revisions/${initial.revision_id}/review`,{});
 const independent=await comparison(page,initial.revision_id,"independent");const unitA=independent.result.unit_summary.find((row:SavedValue)=>row.condition==="A"&&row.experimental_unit==="U-A1");expect(unitA.value).toBe(6.5);
 expect(independent.result.sample_summary.filter((row:SavedValue)=>row.condition==="A"&&row.experimental_unit==="U-A1").map((row:SavedValue)=>row.value)).toEqual([3,10]);
 for(let i=0;i<3;i++)expect(independent.result.field_summary.find((row:SavedValue)=>row.field_id===fields[i].id).value).toBe([2,4,10][i]);
 await workbench(page,title);let view=await hierarchy(page);const mutations:string[]=[];page.on("request",request=>{if(request.method()==="POST")mutations.push(new URL(request.url()).pathname);});
 let nodes=await unitTree(view,"A","U-A1");await expect(nodes.unit.locator(":scope>summary strong")).toHaveText("6.5");await expect(nodes.first.locator(":scope>summary strong")).toHaveText("3");await expect(nodes.second.locator(":scope>summary strong")).toHaveText("10");
 for(let i=0;i<3;i++){const field=byLabel(view,`集計の視野 ${i+1}`);await expect(field.locator("strong")).toHaveText(String([2,4,10][i]));}
 expect(await view.locator("details[aria-label]").evaluateAll(elements=>elements.map(element=>element.getAttribute("aria-label")).filter(label=>!!label&&/^[AB] 実験単位 U-[AB]\d+$/.test(label)))).toEqual(["A 実験単位 U-A1","A 実験単位 U-A2","A 実験単位 U-A3","B 実験単位 U-B1","B 実験単位 U-B2","B 実験単位 U-B3"]);
 expect(await nodes.unit.locator("article[aria-label]").evaluateAll(elements=>elements.map(element=>element.getAttribute("aria-label")))).toEqual(["集計の視野 1","集計の視野 2","集計の視野 3"]);
 expect(await page.getByRole("button",{name:"比較と図を作成",exact:true}).evaluate(element=>element.parentElement!.getBoundingClientRect().bottom-element.getBoundingClientRect().bottom)).toBeLessThan(80);
 expect(mutations).toEqual([]);await shot(page,"comparison-hierarchy-independent-desktop.png");await shot(page,"comparison-hierarchy-independent-detail-desktop.png",view);await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await shot(page,"comparison-hierarchy-independent-mobile.png");await shot(page,"comparison-hierarchy-independent-detail-mobile.png",view);await page.setViewportSize({width:1440,height:1000});
 const pairedMetadata=await post(page,`/v1/revisions/${initial.revision_id}/region-metadata`,{version:"1.0.0",fields:Object.fromEntries(fields.map((field,i)=>[field.id,prepared.fields[i].paired]))});await waitJob(page,pairedMetadata.job_id);await post(page,`/v1/revisions/${pairedMetadata.revision_id}/review`,{});const paired=await comparison(page,pairedMetadata.revision_id,"paired");
 expect(paired.result.pair_ledger).toHaveLength(3);expect(paired.result.pair_ledger.find((row:{pair:string})=>row.pair==="P-1")).toMatchObject({units:{A:"M-1",B:"M-1"},status:"selected"});
 expect(paired.result.unit_summary.find((row:SavedValue)=>row.condition==="A"&&row.experimental_unit==="M-1").value).toBe(6.5);expect(paired.result.unit_summary.find((row:SavedValue)=>row.condition==="B"&&row.experimental_unit==="M-1").value).toBe(9.5);expect(paired.result.counts.map((row:{complete_pairs:number})=>row.complete_pairs)).toEqual([3,3]);
 const savedMask=await json(await page.request.get(`${api}/v1/revisions/${pairedMetadata.revision_id}/region-masks?field_id=${fields[0].id}`));expect(savedMask.metadata.mask_revision_id).toBe(initial.revision_id);
 const newer=await post(page,`/v1/revisions/${pairedMetadata.revision_id}/region-metadata`,{version:"1.0.0",fields:Object.fromEntries(fields.map((field,i)=>[field.id,{...prepared.fields[i].paired,...(i===0?{condition:"Changed condition",sample:"Changed sample",experimental_unit:"Changed unit"}:{})}]))});await waitJob(page,newer.job_id);
 const edited=await post(page,`/v1/revisions/${newer.revision_id}/region-edits`,{field_id:fields[0].id,region_set_id:"regions",operation:"delete",ids:[3],polygon:[],expected_mask_revision_id:savedMask.metadata.mask_revision_id});await waitJob(page,edited.job_id);
 await workbench(page,title);await page.getByRole("button",{name:"表示用参照",exact:true}).click();view=await hierarchy(page,2);const pair=await open(byLabel(view,"対応ペア P-1"));nodes=await unitTree(pair,"A","M-1");const pairedB=await open(byLabel(pair,"B 実験単位 M-1"));
 await expect(nodes.unit.locator(":scope>summary strong")).toHaveText("6.5");await expect(pairedB.locator(":scope>summary strong")).toHaveText("9.5");await expect(view).not.toContainText("Changed sample");await expect(byLabel(page,"保存済みの群間比較")).toContainText("旧版の結果");
 const metadataDetails=page.locator("details").filter({has:page.locator(":scope>summary",{hasText:"視野と実験単位の対応"})});await open(metadataDetails);await expect(byLabel(page,"視野 1 の試料")).toHaveValue("Changed sample");await byLabel(page,"視野 1 の試料").fill("Unsaved metadata draft");
 const sourceButton=byLabel(view,"集計の視野 1 を保存済み画像で確認");await expect(sourceButton).toBeDisabled();await expect(byLabel(page,"視野 1 の試料")).toHaveValue("Unsaved metadata draft");await expect(nodes.unit.locator(":scope>summary strong")).toHaveText("6.5");
 // Explicit reload discards this test draft; navigation itself must never do so.
 await workbench(page,title);await page.getByRole("button",{name:"表示用参照",exact:true}).click();view=await hierarchy(page,2);await unitTree(await open(byLabel(view,"対応ペア P-1")),"A","M-1");
 const maskUrl=`**/v1/revisions/${pairedMetadata.revision_id}/region-masks?field_id=${fields[0].id}`;await page.route(maskUrl,route=>route.fulfill({status:503,contentType:"application/json",body:JSON.stringify({detail:"artifact_unavailable"})}));
 let adoptionRequests=0;page.on("request",request=>{if(request.method()==="POST"&&new URL(request.url()).pathname===`/v1/workspaces/${workspace.id}/current`)adoptionRequests++;});
 await byLabel(view,"集計の視野 1 を保存済み画像で確認").click();await expect(page.locator("main").getByRole("alert")).toContainText("保存済みの画像を開けませんでした");await expect(byLabel(view,"集計の視野 1 を保存済み画像で確認")).toBeEnabled();expect(adoptionRequests).toBe(0);expect((await json(await page.request.get(`${api}/v1/workspaces/${workspace.id}`))).active_revision).toBe(edited.revision_id);await expect(byLabel(page,"保存済み比較の視野")).toHaveCount(0);await page.unroute(maskUrl);
 await byLabel(view,"集計の視野 1 を保存済み画像で確認").click();await expect(byLabel(page,"保存済み比較の視野")).toContainText("測定チャンネル: 練習信号");await expect(page.getByRole("button",{name:"練習信号",exact:true})).toHaveClass(/segmentActive/);await expect(byLabel(page,"選択した領域ID")).toHaveValue("");await preview(page);
 expect((await json(await page.request.get(`${api}/v1/workspaces/${workspace.id}`))).active_revision).toBe(pairedMetadata.revision_id);expect(await json(await page.request.get(`${api}/v1/revisions/${pairedMetadata.revision_id}/region-masks?field_id=${fields[0].id}`))).toEqual(savedMask);await shot(page,"comparison-hierarchy-source-desktop.png");
 await page.getByRole("button",{name:"追加",exact:true}).click();await page.getByText("座標から多角形を指定",{exact:true}).click();await page.getByRole("textbox",{name:"頂点（x,y を空白または改行で区切る）",exact:true}).fill("10,60 20,60 20,70");await page.getByRole("button",{name:"座標を反映",exact:true}).click();view=await hierarchy(page);await unitTree(await open(byLabel(view,"対応ペア P-1")),"A","M-1");await expect(byLabel(view,"集計の視野 1 を保存済み画像で確認")).toBeDisabled();await page.getByRole("button",{name:/01 画像と領域/}).click();await open(page.locator("details").filter({has:page.locator(":scope>summary",{hasText:"座標から多角形を指定"})}));await expect(page.getByRole("textbox",{name:"頂点（x,y を空白または改行で区切る）",exact:true})).toHaveValue("10,60 20,60 20,70");await expect(page.getByRole("button",{name:/領域を保存・再測定 · 3 点/})).toBeVisible();await page.getByRole("button",{name:"頂点を消去",exact:true}).click();await page.getByRole("button",{name:"選択",exact:true}).click();
 view=await hierarchy(page);await unitTree(await open(byLabel(view,"対応ペア P-1")),"A","M-1");await open(byLabel(view,"B 実験単位 M-1"));expect(await view.locator("details[aria-label]").evaluateAll(elements=>elements.map(element=>element.getAttribute("aria-label")).filter(label=>label?.startsWith("対応ペア ")))).toEqual(["対応ペア P-1","対応ペア P-2","対応ペア P-3"]);await shot(page,"comparison-hierarchy-paired-desktop.png");await shot(page,"comparison-hierarchy-paired-detail-desktop.png",view);await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await shot(page,"comparison-hierarchy-paired-mobile.png");await shot(page,"comparison-hierarchy-paired-detail-mobile.png",view);expect(errors).toEqual([]);
 if(evidence)fs.writeFileSync(path.join(evidence,"comparison-hierarchy-receipt.json"),JSON.stringify({scope:"Artificial 12-field practice fixture; no biological observations, human usability or installed-release acceptance",reference:{fields:[2,4,10],samples:[3,10],unitA:6.5,pairedUnitB:9.5,completePairs:3},measurementChannel:"signal",auxiliaryChannel:"Identical artificial pixels for display-channel restoration only",serverSavedValuesRendered:true,expansionMutations:0,pairedConditionIdentitiesDistinct:true,newerMetadataDoesNotReplaceSavedMembership:true,metadataAndPolygonDraftsRetained:true,failedHistoricalSourceDoesNotAdopt:true,sourceChannelAndReusedMaskRestored:true,aggregateFieldDoesNotSelectOneRegion:true,pageErrors:errors},null,2));
 await verifyReadiness(page,fixture,prepared.fields);expect(errors).toEqual([]);
});
