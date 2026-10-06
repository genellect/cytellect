import {expect, test} from "@playwright/test";

/** Transport/UI regression only. Synthetic response fixtures do not establish Fiji accuracy. */
test("real workspace uses saved pixels/results, never legacy confirmation flags, and persists corrections", async ({page, context}) => {
  const writes: Array<{path: string; body: Record<string, unknown>}> = [];
  let selection: {version: number; entries: Array<{id: string; field_id: string | null; revision_id: string | null; exclusion_reason: string | null}>} = {version: 0, entries: []};
  let revision = "r1"; let analysisCount = 0; let figureCount = 0; let proposalCount = 0;
  const channels = [{channel_id: "c1", label: "c1", stain: null}, {channel_id: "c2", label: "c2", stain: null}];
  const field = {id: "f1", workspace_id: "w1", metadata: {}, image_info: {shape: [32, 32], channels}};
  const jobs: Array<{id: string; state: string; revision_id: string; kind: string}> = [];
  const figureRevisions = new Map<string, string>();
  const figureSpecs = new Map<string, Record<string, unknown>>();
  await context.route("**/v1/**", async route => {
    const url = new URL(route.request().url()); const path = url.pathname; const method = route.request().method();
    const headers = {"Access-Control-Allow-Origin": new URL(page.url()).origin, "Access-Control-Allow-Credentials": "true", "Access-Control-Allow-Headers": "content-type,x-cytellect-request"};
    const json = (body: unknown, status = 200) => route.fulfill({status, headers, contentType: "application/json", body: JSON.stringify(body)});
    if (method === "OPTIONS") return route.fulfill({status: 204, headers});
    if (path.endsWith("/region-fields") && method === "POST") {
      const form = route.request().postDataBuffer()!.toString();
      expect(form).toContain('"version":"1.1.0"'); expect(form).toContain('"identity_source":"filename"'); expect(form).not.toContain("identity_confirmed");
      return json(field, 201);
    }
    let body: Record<string, unknown> = {};
    if (method === "POST") {body = route.request().postDataJSON() || {}; writes.push({path, body});}
    if (path === "/v1/session") return json({authenticated: true, retention_hours: 24, demo: false});
    if (path.endsWith("/selection")) {if (method === "POST") {if (body.version !== selection.version) return json({detail: "workspace_selection_changed"}, 409); selection = {...body as typeof selection, version: selection.version + 1};} return json(selection);}
    if (path === "/v1/workspaces/w1") return json({id: "w1", active_revision: revision});
    if (path.endsWith("/region-fields") && method === "GET") return json([field]);
    if (path.endsWith("/revisions")) return json(["r1", "r2"].map((id, index) => ({id, state: "succeeded", created: index + 1, config: {recipe: {id: "region-2d", version: "1.2.0", source: "stardist_nuclear", region_set_id: "nuclei", label: "核", defining_channel_id: "c2", nuclear_role_source: "user_selected_role"}, field_ids: ["f1"]}})));
    if (path === "/v1/workspaces") return json({id: "w1", title: "画像解析", active_revision: null});
    if (path.endsWith("/preview")) return route.fulfill({headers, contentType: "image/png", body: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aU1sAAAAASUVORK5CYII=", "base64")});
    if (path.endsWith("/region-analyses")) {analysisCount++; jobs.push({id: "a1", state: "succeeded", revision_id: "r1", kind: "analysis"}); return json({job_id: "a1", revision_id: "r1"}, 202);}
    if (path.endsWith("/region-reconfigure")) {revision = "r2"; jobs.push({id: "a2", state: "succeeded", revision_id: revision, kind: "analysis"}); return json({job_id: "a2", revision_id: revision}, 202);}
    if (path.endsWith("/current")) return json({});
    if (path.endsWith("/jobs")) return json(jobs);
    if (path.endsWith("/region-measurements")) {
      const rid = path.split("/")[3];
      return json({revision_id: rid, field_failures: [], exclusions: rid === "r2" ? [{field_id: "f1", region_id: 1, reason: "利用者の操作"}] : [], field_tables: {f1: {rows: [1, 2].flatMap(region => channels.map(channel => ({region_id: region, channel_id: channel.channel_id, area_px: region * 10, area_um2: null, mean: region * 30, median: region * 29, integrated: region * 300})))}}});
    }
    if (path.endsWith("/region-masks")) return json({regions: [{id: 1, points: [[3, 3], [12, 3], [12, 12], [3, 12]]}, {id: 2, points: [[18, 18], [28, 18], [28, 28], [18, 28]]}], metadata: {mask_revision_id: `m-${path.split("/")[3]}`}});
    if (path.endsWith("/descriptive-preview")) {const id = `s${++figureCount}`; const rid = path.split("/")[3]; figureRevisions.set(id, rid); figureSpecs.set(id, body); jobs.push({id, state: "succeeded", revision_id: rid, kind: "statistics"}); return json({job_id: id}, 202);}
    if (path.endsWith("/result")) {
      const id = path.split("/")[3]; const rid = figureRevisions.get(id); const excluded = rid === "r2"; const points = excluded ? [2] : [1, 2];
      return json({analysis_kind: "descriptive", revision_id: rid, spec: figureSpecs.get(id), metric: "area_px", unit: "pixel²", counts: {observations: points.length}, selection: {excluded: excluded ? 1 : 0}, field_summary: [{field_id: "f1", selected_rows: points.length, median: excluded ? 20 : 15, q1: excluded ? 20 : 12.5, q3: excluded ? 20 : 17.5, status: "selected"}], plot_data: points.map(id => ({field_id: "f1", region_id: id, value: id*10})), source_fields: [], excluded_failed_fields: [], warnings: [], figure: {source_files: ["figure.svg", "figure.pdf", "figure.png", "plot-data.csv", "methods.md"]}});
    }
    if (path.endsWith("/proposal-drafts")) {proposalCount++; if (proposalCount === 1) {expect(body.retry_failed).toBeUndefined(); return json({detail:"proposal_explicit_retry_required"},409);} expect(body.retry_failed).toBe(true); return json({proposal:{draft:{rationale:"公開テストの解析案",missing_information:[]},needs_confirmation:[]}});}
    if (path.includes("/files/")) return route.fulfill({headers, contentType: "text/plain", body: "synthetic transport fixture"});
    return json({detail: "unexpected_test_route"}, 404);
  });
  await page.goto("/workspace");
  await page.getByTestId("file-input").setInputFiles([{name: "A01_c1.tif", mimeType: "image/tiff", buffer: Buffer.from([1, 2, 3])}, {name: "A01_c2.tif", mimeType: "image/tiff", buffer: Buffer.from([4, 5, 6])}]);
  await expect(page.getByRole("button", {name: "解析を実行", exact: true})).toBeDisabled();
  await page.getByRole("radio", {name: "c2 を核検出に使う"}).click();
  await page.getByRole("button", {name: "解析を実行", exact: true}).click();
  await expect(page.getByRole("status").first()).toContainText("1 / 1");
  expect(analysisCount).toBe(1);
  await page.getByText("解析方法の提案", {exact:true}).click();
  await page.getByLabel("解析の目的", {exact:true}).fill("核面積を確認");
  await page.getByLabel("上記の情報を送信することに同意する").check();
  await page.getByRole("button", {name:"提案を作成",exact:true}).click();
  await expect(page.getByText(/再送すると追加のAPI利用料/)).toBeVisible();
  expect(proposalCount).toBe(1);
  await page.getByRole("button", {name:"費用を確認して再送",exact:true}).click();
  await expect(page.getByText("公開テストの解析案", {exact:true})).toBeVisible();
  expect(proposalCount).toBe(2);
  await page.getByText("解析方法の提案", {exact:true}).click();
  const run = writes.find(value => value.path.endsWith("/region-analyses"))!;
  expect(run.body).toMatchObject({recipe: {version: "1.2.0", nuclear_role_source: "user_selected_role"}, measurement: {mode: "raw_intensity"}});
  expect(JSON.stringify(writes)).not.toContain('"confirmed":true');
  await page.getByRole("button", {name: "グラフ", exact: true}).click();
  await expect(page.getByRole("img", {name: /area_px.*視野ごとの分布/})).toBeVisible();
  await page.locator('circle[data-region="1"]').click();
  await page.getByRole("button", {name: "対象から除外", exact: true}).click();
  await expect(page.getByRole("complementary", {name: "選択対象の操作"}).getByText("領域 1（除外）", {exact: true})).toBeVisible();
  await page.getByRole("button", {name: "グラフ", exact: true}).click();
  await expect(page.getByRole("img", {name: /area_px.*視野ごとの分布/})).toContainText("n = 1");
  await page.getByLabel("幅 (mm)").selectOption("183");
  await expect.poll(() => figureCount).toBeGreaterThan(2);
  expect(analysisCount).toBe(1);
  expect(writes.some(value => value.path.endsWith("/review"))).toBe(false);
  await page.getByRole("button", {name: "元に戻す", exact: true}).click();
  await expect.poll(() => selection.entries[0]?.revision_id).toBe("r1");
  const other = await context.newPage();
  await other.goto("/workspace?id=w1");
  await expect(other.getByRole("status").first()).toContainText("1 / 1");
  await other.getByRole("button", {name: /測定値 ·/}).click();
  await expect(other.getByRole("cell", {name: "採用", exact: true})).toHaveCount(2);
  // A different tab adopts r2; the stale r1 tab must not overwrite it.
  await page.getByRole("button", {name: "やり直す", exact: true}).click();
  await expect.poll(() => selection.entries[0]?.revision_id).toBe("r2");
  await expect(other.getByText("別のタブで採用状態が更新されました。表示中の測定値・図は旧版です。", {exact: false})).toBeVisible();
  await other.getByRole("button", {name: "領域 1 を選択", exact: true}).click();
  await other.getByRole("button", {name: "対象から除外", exact: true}).click();
  await expect(other.getByRole("button", {name: "最新の採用状態を読み込む"})).toBeVisible();
  expect(selection.entries[0].revision_id).toBe("r2");
  await other.close();
  await page.getByRole("button", {name: "操作パネル"}).click();
  await page.setViewportSize({width: 390, height: 844});
  await expect(page.getByRole("button", {name: "操作パネル"})).toBeInViewport();
  expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(0);
});

test("failed uploads and analyses remain visible and allow comparison only after reasoned exclusion", async ({page}) => {
  const channels = [{channel_id: "c1", label: "DAPI", stain: "DAPI"}];
  const fields = ["f1", "f2", "failed-field"].map(id => ({id, workspace_id: "w2", metadata: {}, image_info: {shape: [32, 32], channels}}));
  const recipe = {id: "region-2d", version: "1.2.0", source: "stardist_nuclear", region_set_id: "nuclei", label: "核", defining_channel_id: "c1", nuclear_role_source: "recorded_stain"};
  let selection = {version: 1, entries: [...fields.map((field, index) => ({id: field.id, field_id: field.id as string | null, revision_id: index < 2 ? `r${index + 1}` : null, exclusion_reason: null as string | null})), {id: "failed-upload", field_id: null, revision_id: null, exclusion_reason: null as string | null}]};
  let submitted: Record<string, unknown> | null = null;
  let statisticSpec: Record<string, unknown> | null = null;
  await page.route("**/v1/**", async route => {
    const path = new URL(route.request().url()).pathname; const method = route.request().method();
    const headers = {"Access-Control-Allow-Origin": new URL(page.url()).origin, "Access-Control-Allow-Credentials": "true", "Access-Control-Allow-Headers": "content-type,x-cytellect-request"};
    const json = (value: unknown, status = 200) => route.fulfill({status, headers, contentType: "application/json", body: JSON.stringify(value)});
    if (method === "OPTIONS") return route.fulfill({status: 204, headers});
    if (path === "/v1/session") return json({authenticated: true, retention_hours: 24, demo: false});
    if (path === "/v1/workspaces/w2") return json({id: "w2", active_revision: "r2"});
    if (path.endsWith("/selection")) {if (method === "POST") selection = {...route.request().postDataJSON(), version: selection.version + 1}; return json(selection);}
    if (path.endsWith("/region-fields")) return json(fields);
    if (path.endsWith("/revisions")) return json(fields.map((field, index) => ({id: `r${index + 1}`, state: index < 2 ? "succeeded" : "failed", created: index, config: {recipe, field_ids: [field.id]}})));
    if (path.endsWith("/jobs")) return json([...(submitted ? [{id: "cohort-job", revision_id: "cohort", kind: "analysis", state: "succeeded"}] : []), ...(statisticSpec ? [{id: "statistic-job", revision_id: "cohort", kind: "statistics", state: "succeeded"}] : [])]);
    if (path.endsWith("/review")) return json({});
    if (path.endsWith("/workspace-selection")) return json(submitted?.workspace_selection);
    if (path.endsWith("/common-statistics")) {
      if (method === "POST") {statisticSpec = route.request().postDataJSON(); return json({job_id: "statistic-job"}, 202);}
      return json({revision_id: "cohort", analysis_kind: "region-comparison", region_comparison_version: "2.0.0", spec: statisticSpec, metric: "area_px", unit: "pixel²", comparisons: [], counts: [], warnings: [], source_field_ledger: [], selection: {selected: 2, excluded: 0, missing: 0, out_of_scope: 0}, figure: {source_files: []}});
    }
    if (path.endsWith("/region-cohorts")) {submitted = route.request().postDataJSON(); return json({job_id: "cohort-job", revision_id: "cohort"}, 202);}
    if (path.endsWith("/region-measurements")) {const rid = path.split("/")[3]; const fid = rid === "r1" ? "f1" : "f2"; return json({revision_id: rid, field_failures: [], exclusions: [], field_tables: {[fid]: {rows: [{region_id: 1, channel_id: "c1", area_px: 16, area_um2: null, mean: 30, median: 30, integrated: 480}]}}});}
    if (path.endsWith("/region-masks")) return json({regions: [{id: 1, points: [[1, 1], [5, 1], [5, 5], [1, 5]]}], metadata: {mask_revision_id: "mask"}});
    if (path.endsWith("/preview")) return route.fulfill({headers, contentType: "image/png", body: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aU1sAAAAASUVORK5CYII=", "base64")});
    return json({detail: "unused_fixture_route"}, 404);
  });
  await page.goto("/workspace?id=w2");
  await expect(page.getByRole("status").first()).toContainText("2 / 4");
  await page.getByRole("button", {name: "群を比較", exact: true}).click();
  await expect(page.getByText("未完了の視野が 2 件あります。", {exact: false})).toBeVisible();
  for (const [name, reason] of [["視野 3 要確認", "画像処理失敗を確認"], ["未登録の視野 要確認", "原ファイルが破損"]]) {
    await page.getByRole("button", {name, exact: true}).click();
    await expect(page.getByRole("button", {name: "この視野を比較対象から除外"})).toBeDisabled();
    await page.getByLabel("視野の除外理由").fill(reason);
    await page.getByRole("button", {name: "この視野を比較対象から除外"}).click();
    await expect(page.getByText(`除外理由：${reason}`, {exact: true})).toBeVisible();
  }
  await page.reload();
  await expect(page.getByRole("button", {name: "視野 3 除外", exact: true})).toBeVisible();
  await expect(page.getByRole("button", {name: "未登録の視野 除外", exact: true})).toBeVisible();
  await page.getByRole("button", {name: "群を比較", exact: true}).click();
  await expect(page.getByText("未完了の視野が", {exact: false})).toHaveCount(0);
  for (let index = 1; index <= 2; index++) {
    for (const key of ["condition", "sample", "experimental_unit"]) await page.getByLabel(`視野 ${index} ${key}`, {exact: true}).fill(`${key}-${index}`);
  }
  await page.getByRole("button", {name: "比較対象を保存", exact: true}).click();
  await expect.poll(() => submitted).not.toBeNull();
  expect(submitted).toMatchObject({sources: [{field_id: "f1", revision_id: "r1"}, {field_id: "f2", revision_id: "r2"}], workspace_selection: {version: 3, entries: selection.entries}});
  await page.getByLabel("独立実験単位の定義", {exact: true}).fill("独立培養");
  for (const name of [/condition-1 と condition-2/, /各視野の画像・領域と除外を確認しました/, /入力した単位の独立性/, /領域の定義と面積の尺度/, /画素の大きさと空間サンプリングが同じ/, /保存測定表の値・欠測・除外/]) await page.getByRole("checkbox", {name}).check();
  await page.getByRole("button", {name: "比較と図を作成", exact: true}).click();
  await expect(page.getByRole("heading", {name: "保存された比較結果", exact: true})).toBeVisible();
  // Another tab changes server adoption after this figure completed.
  selection = {...selection, version: selection.version + 1, entries: selection.entries.map((entry, index) => index === 0 ? {...entry, exclusion_reason: "別タブで変更"} : entry)};
  await expect(page.getByRole("heading", {name: "保存された比較結果 · 設定変更前の結果", exact: true})).toBeVisible();
  await page.getByText("比較条件", {exact:true}).click();
  await expect(page.getByRole("button", {name: "比較と図を再実行", exact: true})).toBeDisabled();
});
