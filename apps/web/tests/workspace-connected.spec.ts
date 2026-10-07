import {mkdir} from "node:fs/promises";
import {expect, test} from "@playwright/test";
import type {ChannelAssignments, ImportedField, Recipe, WorkspaceRun, WorkspaceSelection} from "../src/lib/workspace/api-adapter";

/** Synthetic transport acceptance. This does not validate biological segmentation. */
for (const viewport of [{width:1920,height:1080},{width:1440,height:900},{width:1280,height:720},{width:1280,height:554}]) test(`connected workspace imports, maps stains, previews, adopts and opens full-size result modes ${viewport.width}x${viewport.height}`, async ({page, context}) => {
  test.setTimeout(180_000);
  await page.setViewportSize(viewport);
  const evidence=test.info().outputPath("connected");
  await mkdir(evidence,{recursive:true});
  let created = false;
  let newerWorkspace = false;
  let fields: ImportedField[] = [];
  let selection: WorkspaceSelection = {version: 0, entries: []};
  let assignments: ChannelAssignments = {version: 0, assignments: [], global_field_ids: [], groups: []};
  let specification: {version: number; spec: Record<string, unknown> | null} = {version: 0, spec: null};
  let run: WorkspaceRun | null = null;
  let runCount = 0;
  let workspaceReads = 0;
  const writes: string[] = [];
  const unexpected: string[] = [];
  const pageErrors: string[] = [];
  page.on("pageerror", error => pageErrors.push(error.message));
  const workspace = {id: "synthetic-workspace", title: "画像解析", active_revision: null, created: 1, expires: 9999999999, deleted: false};
  const recipe: Recipe = {id: "region-2d", version: "1.7.0", source: "stardist_nuclear", region_set_id: "nuclei", label: "核", defining_channel_id: "c1", nuclear_role_source: "user_selected_role"};
  const revision = () => ({id: "synthetic-revision", state: "succeeded", created: 2, config: {recipe, field_ids: ["synthetic-field"], measurement: {version: "1.1.0", mode: "raw_intensity"}, backgrounds: {}, channel_assignments: assignments}});
  await context.route("**/v1/**", async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const method = request.method();
    const headers = {"Access-Control-Allow-Origin": new URL(page.url()).origin, "Access-Control-Allow-Credentials": "true", "Access-Control-Allow-Headers": "content-type,x-cytellect-request", "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS"};
    const json = (body: unknown, status = 200) => route.fulfill({status, headers, contentType: "application/json", body: JSON.stringify(body)});
    if (method === "OPTIONS") return route.fulfill({status: 204, headers});
    if (method !== "GET") writes.push(`${method} ${path}`);
    if (path === "/v1/session") return json({authenticated: true, retention_hours: 24, demo: false});
    if (path === "/v1/workspaces") {if (method === "POST") {created = true; return json(workspace, 201);} workspaceReads++; return json(created ? [...(newerWorkspace?[{...workspace,id:"different-workspace",title:"別の作業"}]:[]),workspace] : []);}
    if (path.endsWith("/synthetic-workspace")) return json(workspace);
    if (path.endsWith("/selection")) {
      if (method === "POST") {const body = request.postDataJSON(); expect(body.version).toBe(selection.version); selection = {...body, version: selection.version + 1};}
      return json(selection);
    }
    if (path.endsWith("/region-fields")) {
      if (method === "POST") {
        expect(request.postDataBuffer()!.toString()).toContain('"identity_source":"filename"');
        fields = [{id: "synthetic-field", workspace_id: workspace.id, metadata: {display_name: "Synthetic field"}, image_info: {shape: [80, 160], input_mode: "native", channels: [{channel_id: "c1", label: "c1", stain: null}, {channel_id: "c2", label: "c2", stain: null}]}}];
        return json(fields[0], 201);
      }
      return json(fields);
    }
    if (path.endsWith("/channel-assignments")) {
      if (method === "PUT") {
        const body = request.postDataJSON(); expect(body.field_ids).toEqual(["synthetic-field"]);
        assignments = {version: assignments.version + 1, assignments: [], global_field_ids: [], groups: [{id: "synthetic-group", field_ids: body.field_ids, channel_ids: ["c1", "c2"], assignments: body.assignments}]};
      }
      return json(assignments);
    }
    if (path.endsWith("/field-links")) return json({version: 0, entries: []});
    if (path.endsWith("/analysis-spec")) {
      if (method === "PUT") {const body = request.postDataJSON(); expect(body.version).toBe(specification.version); specification = {version: specification.version + 1, spec: body.spec};}
      return json(specification);
    }
    if (path.endsWith("/revisions")) return json(run ? [revision()] : []);
    if (path.endsWith("/jobs")) return json([{id:"historical-figure",kind:"statistics",state:"succeeded",created:1,revision_id:"historical-revision"}]);
    if(path.endsWith("/jobs/historical-figure/result"))return json({source_kind:"region-2d",analysis_kind:"descriptive",revision_id:"historical-revision",spec:{plot:{}},source_fields:[{field_id:"synthetic-field",region_set:{region_set_id:"nuclei"}}],warnings:[],plot_data:[],field_summary:[],figure:{source_files:["figure.svg"]}});
    if(path.endsWith("/jobs/historical-figure/files/figure.svg"))return route.fulfill({headers,contentType:"image/svg+xml",body:'<svg xmlns="http://www.w3.org/2000/svg" width="500" height="300"><rect width="500" height="300" fill="white"/><text x="40" y="60">Synthetic saved figure</text></svg>'});
    if (path.endsWith("/preview")) return route.fulfill({headers, contentType: "image/svg+xml", body: '<svg xmlns="http://www.w3.org/2000/svg" width="160" height="80"><rect width="160" height="80" fill="#182237"/><ellipse cx="60" cy="40" rx="20" ry="15" fill="#869fff"/></svg>'});
    if (path.endsWith("/runs")) {
      if (method === "POST") {
        const body = request.postDataJSON(); expect(body.purpose).toBe("preview"); expect(body.field_ids).toEqual(["synthetic-field"]);
        runCount++;
        run = {id: "synthetic-run", workspace_id: workspace.id, spec_version: body.spec_version, target: "nuclei", state: "succeeded", created: 2, updated: 2, steps: [{field_id: "synthetic-field", target: "nuclei", state: "succeeded", revision_id: "synthetic-revision", job_id: "synthetic-job", recipe, error: null}]};
        return json(run, 202);
      }
      return json(run ? [run] : []);
    }
    if (path.endsWith("/runs/synthetic-run")) return json(run);
    if (path.endsWith("/runs/synthetic-run/accept")) {
      expect(run?.state).toBe("succeeded");
      run = {...run!, state: "adopted"};
      selection = {version: selection.version + 1, entries: selection.entries.map(entry => ({...entry, revision_id: "synthetic-revision", target_revisions: {nuclei: "synthetic-revision"}}))};
      return json(run);
    }
    if (path.endsWith("/region-measurements")) return json({revision_id: path.includes("historical-revision")?"historical-revision":"synthetic-revision", protocol_version: "3.0.0", field_failures: [], exclusions: [], field_tables: {"synthetic-field": {rows: ["c1", "c2"].map(channel_id => ({region_id: path.includes("historical-revision")?7:1, channel_id, area_px: 600, area_um2: null, mean: 120, median: 110, integrated: 72000}))}}});
    if (path.endsWith("/region-masks")) return json({regions: [{id: path.includes("historical-revision")?7:1, points: [[40, 25], [80, 25], [80, 55], [40, 55]]}], metadata: {mask_revision_id: "synthetic-mask"}});
    if(path.endsWith("/revisions/historical-revision"))return json({...revision(),id:"historical-revision"});
    if (path.endsWith("/revisions/synthetic-revision")) return json(revision());
    unexpected.push(`${method} ${path}`);
    return json({detail: "unexpected_synthetic_route"}, 404);
  });
  const loaded = page.waitForResponse(response => new URL(response.url()).pathname === "/v1/workspaces" && response.request().method() === "GET");
  await page.goto("/workspace-review");
  await loaded;
  await expect(page.getByRole("heading", {name: "画像解析", exact: true, level: 1})).toBeVisible();
  await expect(page.getByRole("button", {name: "画像を追加", exact: true})).toBeEnabled();
  await page.getByTestId("file-input").setInputFiles([{name: "A01_c1.tif", mimeType: "image/tiff", buffer: Buffer.from([1, 2, 3])}, {name: "A01_c2.tif", mimeType: "image/tiff", buffer: Buffer.from([4, 5, 6])}]);
  await expect(page.getByRole("button", {name: "染色対応", exact: true})).toBeEnabled();
  await expect(page).toHaveURL(/[?&]id=synthetic-workspace(?:&|$)/);
  expect(runCount).toBe(0);
  expect(writes.some(value => /proposal|analyses|\/runs/.test(value))).toBe(false);
  await page.getByRole("combobox", {name:"背景補正",exact:true}).selectOption("confirmed_roi");
  await page.getByRole("button", {name:"背景を描く",exact:true}).click();
  const drawing=page.locator('[data-drawing="true"]');
  await expect(drawing).toBeVisible();
  for(const position of [{x:10,y:10},{x:30,y:10},{x:30,y:30}]) await drawing.click({position});
  await expect(page.getByRole("button", {name:"描画を保存",exact:true})).toBeEnabled();
  await page.getByRole("button", {name:"描画を取り消す",exact:true}).click();
  await page.getByRole("combobox", {name:"背景補正",exact:true}).selectOption("raw");
  await page.getByRole("button", {name: "染色対応", exact: true}).click();
  await page.getByLabel("c1の染色名").fill("DAPI");
  await page.getByLabel("c1の役割").selectOption("nuclear");
  await page.getByLabel("c2の染色名").fill("GFP");
  await page.getByLabel("c2の役割").selectOption("measure");
  await page.getByRole("button", {name: "保存", exact: true}).click();
  await expect(page.getByText("核 · 検出候補", {exact: true})).toBeVisible();
  expect(selection.entries[0]?.revision_id).toBeNull();
  expect(runCount).toBe(1);
  await expect(page.getByRole("button", {name: "DAPI · c1", exact: true})).toBeVisible();
  await expect(page.getByRole("button", {name: "GFP · c2", exact: true})).toBeVisible();
  const image = page.getByRole("img", {name: /DAPI/}).first();
  await expect(image).toBeVisible();
  const dimensions = await image.evaluate(element => {
    const imageRect = element.querySelector("image")!.getBoundingClientRect();
    const viewport = element.closest('[data-dragging]')!.getBoundingClientRect();
    return {ratio: imageRect.width / imageRect.height, width: imageRect.width, viewportWidth: viewport.width, height: imageRect.height, viewportHeight: viewport.height};
  });
  expect(dimensions.ratio).toBeCloseTo(2, 1);
  expect(dimensions.width / dimensions.viewportWidth).toBeGreaterThan(.95);
  expect(dimensions.height / dimensions.viewportHeight).toBeGreaterThan(.95);
  await page.screenshot({path:`${evidence}/${viewport.width}x${viewport.height}-image.png`});
  await page.getByRole("button", {name: "候補を採用", exact: true}).click();
  await expect.poll(() => selection.entries[0]?.target_revisions?.nuclei).toBe("synthetic-revision");
  await expect(page.getByText("核 · 検出候補", {exact: true})).toHaveCount(0);
  expect(runCount).toBe(1);
  await page.getByRole("button", {name: /^測定値/}).click();
  await expect(page.getByRole("cell", {name: "600", exact: true}).first()).toBeVisible();
  await page.getByRole("button", {name: "統計", exact: true}).click();
  const statistics = page.getByRole("region", {name: "測定結果の統計解析"});
  await expect(statistics).toBeVisible();
  expect((await statistics.boundingBox())!.width).toBeGreaterThan(800);
  await expect(image).not.toBeVisible();
  await page.getByRole("button", {name: "グラフ", exact: true}).first().click();
  const figure = page.getByRole("region", {name: "図の作成・保存"});
  await expect(figure).toBeVisible();
  expect((await figure.boundingBox())!.width).toBeGreaterThan(800);
  await page.screenshot({path:`${evidence}/${viewport.width}x${viewport.height}-figure.png`});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth-window.innerWidth)).toBe(0);
  await page.getByRole("combobox",{name:"保存した図"}).selectOption("historical-figure");
  await expect(page.getByText("Synthetic saved figure",{exact:true})).toBeVisible();
  await page.screenshot({path:`${evidence}/${viewport.width}x${viewport.height}-saved-figure.png`});
  await page.getByText("元の視野（保存時の解析版）",{exact:true}).click();
  const adoptedVersion=selection.version;
  await page.getByRole("button",{name:"A01",exact:true}).click();
  await expect(page.getByText("核 · 図の保存時の版",{exact:true})).toBeVisible();
  await expect(page.getByRole("button",{name:"領域 7",exact:true})).toBeVisible();
  await page.getByRole("button",{name:"領域 7",exact:true}).click();
  await expect(page.getByRole("button",{name:"領域を描く",exact:true})).toHaveCount(0);
  expect(selection.version).toBe(adoptedVersion);
  await page.getByRole("button",{name:"元の結果へ戻る",exact:true}).click();
  await expect(figure).toBeVisible();
  await expect(page.getByRole("combobox",{name:"保存した図"})).toHaveValue("historical-figure");
  // A newer workspace in another tab must not change this tab's saved source.
  newerWorkspace = true;
  const savedWrites = writes.length;
  await page.reload();
  await expect(page).toHaveURL(/[?&]id=synthetic-workspace(?:&|$)/);
  await expect(page.getByRole("button",{name:"DAPI · c1",exact:true})).toBeVisible();
  await expect(page.getByRole("button",{name:"領域 1",exact:true})).toBeVisible();
  expect(runCount).toBe(1);
  expect(writes).toHaveLength(savedWrites);
  const beforeNew=workspaceReads;
  await page.getByRole("button",{name:"新しいワークスペース",exact:true}).click();
  await expect(page).not.toHaveURL(/[?&]id=/);
  await expect(page.getByRole("button",{name:"画像を追加",exact:true})).toBeVisible();
  await expect(page.getByRole("button",{name:"DAPI · c1",exact:true})).toHaveCount(0);
  expect(workspaceReads).toBe(beforeNew);
  expect(writes).toHaveLength(savedWrites);
  expect(unexpected).toEqual([]);
  expect(pageErrors).toEqual([]);
});
