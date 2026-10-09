import {expect, test} from "@playwright/test";
import {execFileSync} from "node:child_process";
import {mkdir, readFile, writeFile} from "node:fs/promises";
import path from "node:path";

/** Real API/Fiji with seeded synthetic images: execution and statistics, never biological validity. */
test("synthetic fields reach real independent-unit comparison and editable exports", async ({page}) => {
  test.skip(process.env.CYTELLECT_COMPARISON_REAL !== "1", "Explicit isolated synthetic comparison acceptance");
  test.setTimeout(1200000);
  const python = process.env.CYTELLECT_TEST_PYTHON!;
  const output = process.env.CYTELLECT_REAL_OUTPUT!;
  const api = process.env.CYTELLECT_TEST_API_ORIGIN!;
  const origin = process.env.CYTELLECT_WEB_URL!;
  for (const value of [python, output, api, origin, process.env.CYTELLECT_TEST_DATA_DIR]) expect(value).toBeTruthy();
  await mkdir(output, {recursive: true});
  execFileSync(python, ["-B", "-c", ["import sys,numpy as np,tifffile", "from pathlib import Path", "from cytellect_analysis.synthetic import synthetic_field", "root=Path(sys.argv[1]);root.mkdir(parents=True,exist_ok=True)", "for i in range(4):", " channels,_,_=synthetic_field(seed=i)", " tifffile.imwrite(root/f'f{i+1}_c1.tif',channels['dapi'])", " tifffile.imwrite(root/f'f{i+1}_c2.tif',(channels['gfp'].astype(np.uint32)+i*500).astype(np.uint16))"].join("\n"), path.join(output, "inputs")], {env: process.env, stdio: "pipe"});
  const resume = process.env.CYTELLECT_COMPARISON_RESUME;
  if (resume) {
    // Recovery is limited to this exact four-field synthetic fixture by raw-byte hashes.
    const session = execFileSync(python, ["-B", "-c", [
      "import os,sys,time,secrets,hashlib", "from pathlib import Path", "from cytellect_api.db import Store,workspaces,fields,sessions,digest",
      "store=Store(Path(os.environ['CYTELLECT_TEST_DATA_DIR']));wid=sys.argv[1];w=store.one(workspaces,id=wid)",
      "assert w and not w['deleted']; fs=store.rows(fields,workspace_id=wid);assert len(fs)==4",
      "hashes=lambda files: sorted(hashlib.sha256(p.read_bytes()).hexdigest() for p in files)",
      "assert hashes(store.safe_path('workspaces',wid,'fields').glob('*/*.tif'))==hashes(Path(sys.argv[2]).glob('*.tif'))",
      "token=secrets.token_urlsafe(32)", "with store.transaction() as conn: conn.execute(sessions.insert().values(digest=digest(token),owner=w['owner'],expires=time.time()+1800,revoked=False))", "print(token)"
    ].join("\n"), resume, path.join(output, "inputs")], {encoding: "utf8", env: process.env, stdio: ["ignore", "pipe", "ignore"]}).trim();
    await page.context().addCookies([{name: "cytellect_dev", value: session, url: api, httpOnly: true, sameSite: "Strict"}]);
  } else {
    const token = execFileSync(python, ["-B", "-c", "import os;from pathlib import Path;from cytellect_api.db import Store;print(Store(Path(os.environ['CYTELLECT_TEST_DATA_DIR'])).invite(3600))"], {encoding: "utf8", env: process.env, stdio: ["ignore", "pipe", "ignore"]}).trim();
    expect((await page.request.post(`${api}/v1/invitations/redeem`, {headers: {Origin: origin, "X-Cytellect-Request": "1"}, data: {token}})).ok()).toBeTruthy();
  }
  const writes: string[] = []; page.on("request", request => {if (request.method() === "POST") writes.push(new URL(request.url()).pathname);});
  const files = [1,2,3,4].flatMap(i => [1,2].map(c => path.join(output, "inputs", `f${i}_c${c}.tif`)));
  await page.goto(resume ? `/workspace?id=${resume}` : "/workspace");
  if (!resume) {
    await expect(page.getByTestId("file-input")).toBeEnabled();
    await page.getByTestId("file-input").setInputFiles(files);
    await expect(page.getByRole("complementary", {name:"視野一覧"}).getByRole("button").filter({hasText:/未測定/})).toHaveCount(4, {timeout:120000});
    await page.getByRole("button", {name:"染色対応", exact:true}).click();
    await page.getByLabel("c1の染色名", {exact:true}).fill("DAPI");
    await page.getByLabel("c1の役割", {exact:true}).selectOption("nuclear");
    await page.getByLabel("c2の染色名", {exact:true}).fill("GFP");
    await page.getByLabel("c2の役割", {exact:true}).selectOption("measure");
    await page.getByRole("button", {name:"保存", exact:true}).click();
    await expect(page.getByRole("button", {name:"測定", exact:true})).toBeEnabled({timeout:900000});
    await page.getByLabel("測定する視野", {exact:true}).selectOption("all");
    await page.getByRole("button", {name:"測定", exact:true}).click();
  }
  await expect(page.getByRole("complementary", {name:"視野一覧"}).getByRole("button").filter({hasText:/核\s+\d/})).toHaveCount(4, {timeout:900000});
  await expect(page).toHaveURL(/[?&]id=[^&]+/);
  const workspace = new URL(page.url()).searchParams.get("id")!;
  if(!resume){const response=await page.request.get(`${api}/v1/workspaces/${workspace}/runs`);expect(response.status()).toBe(200);const runs=await response.json();expect(Array.isArray(runs)).toBe(true);expect(runs.some((run:{state:string;steps:unknown[]})=>run.state==="adopted"&&run.steps.length===4)).toBeTruthy();}
  expect(writes.filter(value => value.endsWith("/review"))).toHaveLength(0);
  await page.getByRole("navigation", {name:"作業の切替"}).getByRole("button", {name:"統計", exact:true}).click();
  const panel = page.getByRole("region", {name:"測定結果の統計解析"});
  const options=page.getByRole("complementary", {name:"解析対象"});
  await options.getByRole("combobox", {name:"領域",exact:true}).selectOption("nuclei");
  await options.getByRole("combobox", {name:"指標",exact:true}).selectOption("mean");
  await options.getByRole("combobox", {name:"染色",exact:true}).selectOption("c2");
  await panel.getByRole("combobox", {name:"解析",exact:true}).selectOption("comparison");
  await panel.getByLabel("独立実験単位", {exact:true}).fill("Synthetic independent-unit execution fixture; not biological replicates");
  for (let i = 0; i < 4; i++) {
    await panel.locator('input[aria-label$=" condition"]').nth(i).fill(i < 2 ? "A" : "B");
    await panel.locator('input[aria-label$=" sample"]').nth(i).fill(`synthetic-sample-${i}`);
    await panel.locator('input[aria-label$=" experimental_unit"]').nth(i).fill(`synthetic-unit-${i}`);
    await panel.locator('input[aria-label$=" acquisition_date"]').nth(i).fill("synthetic-batch");
  }
  // Source navigation preserves the editable experimental metadata.
  await panel.locator("details").filter({has:page.getByText("実験情報", {exact:true})}).getByRole("button").first().click();
  await page.getByRole("button", {name:"元の結果へ戻る", exact:true}).click();
  await expect(panel.locator('input[aria-label$=" condition"]').first()).toHaveValue("A");
  expect(writes.filter(value => value.endsWith("/review"))).toHaveLength(0);
  await panel.getByLabel("A / B", {exact:true}).check();
  await panel.getByLabel("独立実験単位、撮影・画素条件、採否と欠測の扱いを確認した", {exact:true}).check();
  await panel.getByLabel("測定領域と採用する視野を確認した", {exact:true}).check();
  await panel.getByRole("button", {name:"計算", exact:true}).click();
  // Include operation errors rather than reporting only a missing-table timeout.
  await expect.poll(async()=>{
    const errors=await panel.getByRole("alert").allTextContents();
    expect(errors).toEqual([]);
    return panel.getByText("Welch t-test", {exact:true}).count();
  },{timeout:120000}).toBeGreaterThan(0);
  await expect(panel.getByText("Welch t-test", {exact:true}).first()).toBeVisible();
  const jobs = await (await page.request.get(`${api}/v1/workspaces/${workspace}/jobs`)).json();
  const job = jobs.find((value: {analysis_mode?: string; analysis_version?: string; state: string}) => value.analysis_mode === "region-experimental-unit" && value.analysis_version === "2.0.0" && value.state === "succeeded");
  expect(job).toBeTruthy();
  const result = await (await page.request.get(`${api}/v1/jobs/${job.id}/common-statistics`)).json();
  expect(result.spec.test).toBe("welch-t");
  expect(result.method_settings.test).toBe("welch-t");
  expect(result.comparisons.map((row:{method:string})=>row.method)).toEqual(["Welch t-test"]);
  expect(result.counts.map((row: {experimental_units: number}) => row.experimental_units)).toEqual([2,2]);
  const report = await (await page.request.get(`${api}/v1/revisions/${job.revision_id}/region-measurements`)).json();
  for (const field of result.field_summary) {
    const values = report.field_tables[field.field_id].rows.filter((row: {channel_id: string}) => row.channel_id === "c2").map((row: {mean: number}) => row.mean).sort((a: number,b: number) => a-b);
    const median = values.length % 2 ? values[(values.length - 1)/2] : (values[values.length/2-1]+values[values.length/2])/2;
    expect(field.value ?? field.median ?? field.field_median).toBeCloseTo(median, 10);
  }
  const sizes: Record<string, number> = {};
  for (const name of ["figure.svg", "figure.pdf", "experimental-units.csv", "comparisons.csv", "methods.md"]) {
    const response = await page.request.get(`${api}/v1/jobs/${job.id}/files/${name}`); expect(response.ok()).toBeTruthy();
    const bytes = await response.body(); sizes[name] = bytes.length;
    if (name === "figure.svg") expect(bytes.toString()).toContain("<text");
    if (name === "figure.pdf") expect(bytes.subarray(0,5).toString()).toBe("%PDF-");
    await writeFile(path.join(output, name), bytes);
  }
  await page.screenshot({path:path.join(output,"comparison.png"),fullPage:true});
  const statisticsPosts=()=>writes.filter(value=>value.endsWith("/common-statistics")||value.endsWith("/descriptive"));
  const beforeFigure=statisticsPosts().length;
  await page.getByRole("navigation", {name:"作業の切替"}).getByRole("button", {name:"グラフ", exact:true}).click();
  const figurePanel=page.getByRole("region", {name:"図の作成・保存"});
  await figurePanel.getByLabel("幅 / mm", {exact:true}).fill("120");
  await figurePanel.getByRole("button", {name:"図を更新", exact:true}).click();
  await expect(figurePanel.getByRole("button", {name:"図を更新", exact:true})).toBeEnabled({timeout:120000});
  expect(statisticsPosts()).toHaveLength(beforeFigure);
  expect(writes.some(value=>value.endsWith("/figure-render"))).toBeTruthy();
  await expect(figurePanel.getByLabel("元画像を含める",{exact:true})).not.toBeChecked();
  await figurePanel.getByLabel("元画像を含める",{exact:true}).check();
  const exported=page.waitForResponse(response=>new URL(response.url()).pathname.endsWith("/export")&&response.request().method()==="POST");
  const downloaded=page.waitForEvent("download",{timeout:120000});
  await figurePanel.getByRole("button", {name:"保存", exact:true}).click();
  const exportResponse=await exported;expect(exportResponse.status()).toBe(202);
  expect(new URL(exportResponse.url()).searchParams.get("include_raw")).toBe("true");
  const publication=await downloaded;
  await publication.saveAs(path.join(output,"publication.zip"));
  await expect(figurePanel.getByRole("button", {name:"保存", exact:true})).toBeEnabled({timeout:120000});
  const replay=JSON.parse(execFileSync(python,["-B","-c",[
    "import sys,json,io,zipfile,hashlib", "from pathlib import Path",
    "from cytellect_analysis.region_exports import replay_region_bundle",
    "root=Path(sys.argv[1]);bundle=root/'replay-bundle';bundle.mkdir(exist_ok=True)",
    "with zipfile.ZipFile(root/'publication.zip') as publication:",
    " receipt=json.loads(publication.read('manifest.json'))",
    " assert all(hashlib.sha256(publication.read(name)).hexdigest()==digest for name,digest in receipt['files'].items())",
    " analysis=publication.read('analysis.zip')",
    "with zipfile.ZipFile(io.BytesIO(analysis)) as archive:",
    " assert json.loads(archive.read('manifest.json'))['raw_included'] is True",
    " assert all((bundle/name).resolve().is_relative_to(bundle.resolve()) for name in archive.namelist())",
    " archive.extractall(bundle)",
    "replay=replay_region_bundle(bundle,bundle/'raw',root/'replayed')",
    "assert replay['matched_saved_measurements'] and replay['matched_saved_comparisons'] and replay['matched_saved_descriptions']",
    "assert 'matched_saved_associations' not in replay  # This workflow requested comparison, not association.",
    "print(json.dumps(replay))"
  ].join("\n"),output],{encoding:"utf8",env:process.env,stdio:["ignore","pipe","ignore"]}));

  expect(statisticsPosts()).toHaveLength(beforeFigure);
  await page.reload();
  await page.getByRole("navigation", {name:"作業の切替"}).getByRole("button", {name:"統計", exact:true}).click();
  await expect(panel.locator('input[aria-label$=" condition"]').first()).toHaveValue("A");
  await expect(panel.locator('input[aria-label$=" experimental_unit"]').first()).toHaveValue("synthetic-unit-0");
  await expect(panel.getByRole("button", {name:"計算", exact:true})).toBeDisabled();
  await writeFile(path.join(output, "receipt.json"), JSON.stringify({recovery_bootstrap: !!resume, scope: "seeded synthetic images with real Fiji/API/browser; independent-unit arithmetic and editable export acceptance; no biological validation", workspace, job: job.id, revision: job.revision_id, counts: result.counts, comparisons: result.comparisons, replay, sizes, input_bytes: (await readFile(files[0])).length}, null, 2));
});
