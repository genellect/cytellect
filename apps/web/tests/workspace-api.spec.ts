import {expect, test} from "@playwright/test";

/** Transport/UI regression only. Synthetic response fixtures do not establish Fiji accuracy. */
test("real workspace uses saved pixels/results, never legacy confirmation flags, and persists corrections", async ({page}) => {
  const writes: Array<{path: string; body: Record<string, unknown>}> = [];
  let revision = "r1"; let analysisCount = 0; let figureCount = 0;
  const channels = [{channel_id: "c1", label: "c1", stain: null}, {channel_id: "c2", label: "c2", stain: null}];
  const field = {id: "f1", workspace_id: "w1", metadata: {}, image_info: {shape: [32, 32], channels}};
  const jobs: Array<{id: string; state: string; revision_id: string; kind: string}> = [];
  const figureRevisions = new Map<string, string>();
  const figureSpecs = new Map<string, Record<string, unknown>>();
  await page.route("**/v1/**", async route => {
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
    if (path.endsWith("/proposal-drafts")) return json({detail: "proposal_service_disabled"}, 503);
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
  await page.getByRole("button", {name: "操作パネル"}).click();
  await page.setViewportSize({width: 390, height: 844});
  await expect(page.getByRole("button", {name: "操作パネル"})).toBeInViewport();
  expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(0);
});
