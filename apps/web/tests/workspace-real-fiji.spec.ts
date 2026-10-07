import {expect, test} from "@playwright/test";
import {execFileSync} from "node:child_process";
import {createHash} from "node:crypto";
import {mkdir, readFile, writeFile} from "node:fs/promises";
import path from "node:path";

/** Opt-in registered-public-image acceptance; no detection or measurement mocks. */
test("registered BBBC007 bytes pass real Fiji, raw measurement, correction and vector exports", async ({page}) => {
  const inputs = process.env.CYTELLECT_REAL_INPUTS;
  const output = process.env.CYTELLECT_REAL_OUTPUT;
  const python = process.env.CYTELLECT_TEST_PYTHON;
  const data = process.env.CYTELLECT_TEST_DATA_DIR;
  const api = process.env.CYTELLECT_TEST_API_ORIGIN;
  if (process.env.CYTELLECT_REQUIRE_REAL_FIJI === "1") {
    for (const value of [inputs, output, python, data, api, process.env.CYTELLECT_WEB_URL]) expect(value).toBeTruthy();
  }
  test.skip(!inputs || !output || !python || !data || !api, "Requires explicitly configured isolated Fiji runtime and registered public inputs");
  await mkdir(output!, {recursive: true});
  const manifest = JSON.parse(await readFile(path.join(inputs!, "manifest.json"), "utf8"));
  const original = ["a9-actin.tif", "a9-dna.tif"];
  const bytes = await Promise.all(original.map(name => readFile(path.join(inputs!, name))));
  bytes.forEach((value, index) => expect(createHash("sha256").update(value).digest("hex")).toBe(manifest.files[original[index]]));
  // One-use token is captured only in memory, never logged or saved in evidence.
  const token = execFileSync(python!, ["-B", "-c", "import os;from pathlib import Path;from cytellect_api.db import Store;print(Store(Path(os.environ['CYTELLECT_TEST_DATA_DIR'])).invite(3600))"], {encoding: "utf8", env: process.env, stdio: ["ignore", "pipe", "ignore"]}).trim();
  const origin = process.env.CYTELLECT_WEB_URL!;
  const redeemed = await page.request.post(`${api}/v1/invitations/redeem`, {headers: {Origin: origin, "X-Cytellect-Request": "1"}, data: {token}});
  expect(redeemed.ok()).toBeTruthy();
  await page.goto("/workspace");
  const uploaded = page.waitForResponse(response => new URL(response.url()).pathname.endsWith("/region-fields") && response.request().method() === "POST");
  await page.getByTestId("file-input").setInputFiles(bytes.map((buffer, index) => ({name: `a9_c${index + 1}.tif`, mimeType: "image/tiff", buffer})));
  const upload = await uploaded; expect(upload.status()).toBe(201); const field = await upload.json();
  expect(field.image_info.channels.map((value: {stain: string | null}) => value.stain)).toEqual([null, null]);
  const method = page.getByRole("region", {name: "解析方法"});
  const accepted = page.waitForResponse(response => new URL(response.url()).pathname.endsWith("/region-analyses") && response.request().method() === "POST");
  await method.getByRole("button", {name: "c2 で核を検出", exact: true}).click();
  const acceptedResponse = await accepted; expect(acceptedResponse.status()).toBe(202); const initial = await acceptedResponse.json();
  await expect(method).toContainText("1/1 視野", {timeout: 240000});
  const measurementResponse = await page.request.get(`${api}/v1/revisions/${initial.revision_id}/region-measurements`);
  expect(measurementResponse.ok()).toBeTruthy(); const report = await measurementResponse.json();
  expect(report.protocol_version).toBe("3.0.0");
  expect(report.field_failures).toEqual([]); expect(report.field_tables[field.id].rows.length).toBeGreaterThan(0);
  expect(report.recipe).toMatchObject({version: "1.7.0", detection_scale: "nuclear-size/1.0.0", defining_channel_id: "c2", nuclear_role_source: "user_selected_role"});
  const reference = JSON.parse(execFileSync(python!, ["-B", "-c", [
    "import json,sys,numpy as np,tifffile",
    "from pathlib import Path",
    "from cytellect_api.db import Store,revisions",
    "store=Store(Path(sys.argv[1]));rev=store.one(revisions,id=sys.argv[2]);root=store.safe_path(rev['result_dir'])",
    "report=json.loads((root/'measurements.json').read_text());fid=sys.argv[3];mask=np.load(root/fid/'labels.npy',allow_pickle=False)",
    "images={'c1':tifffile.imread(Path(sys.argv[4])/'a9-actin.tif'),'c2':tifffile.imread(Path(sys.argv[4])/'a9-dna.tif')}",
    "errors=[]",
    "for row in report['field_tables'][fid]['rows']:",
    " pixels=images[row['channel_id']][mask==row['region_id']].astype(np.float64)",
    " assert row['area_px']==pixels.size",
    " assert row['mean_corrected'] is None and row['integrated_corrected'] is None",
    " errors.extend([abs(row['mean']-float(np.mean(pixels))),abs(row['median']-float(np.median(pixels))),abs(row['integrated']-float(np.sum(pixels)))])",
    "assert max(errors)==0",
    "print(json.dumps({'rows':len(report['field_tables'][fid]['rows']),'max_absolute_error':max(errors),'label_count':int(len(np.unique(mask))-1)}))",
  ].join("\n"), data!, initial.revision_id, field.id, inputs!], {encoding: "utf8", env: process.env, stdio: ["ignore", "pipe", "pipe"]}));
  await page.getByRole("button", {name: "グラフ", exact: true}).click();
  await page.getByRole("button", {name: "図を作成", exact: true}).click();
  await expect(page.getByRole("img", {name: "保存するグラフ"})).toBeVisible({timeout: 120000});
  await page.screenshot({path: path.join(output!, "bbbc007-before.png"), fullPage: true});
  const initialLabels = reference.label_count;
  const firstRegion = report.field_tables[field.id].rows[0].region_id;
  await page.getByRole("button", {name: "方法", exact: true}).click();
  await page.locator(`[data-region="${firstRegion}"]`).first().click();
  const edited = page.waitForResponse(response => new URL(response.url()).pathname.endsWith("/region-reconfigure") && response.request().method() === "POST");
  await page.getByRole("button", {name: "対象から除外", exact: true}).click();
  const editedResponse = await edited; expect(editedResponse.status()).toBe(202); const corrected = await editedResponse.json();
  // The figure from the uncorrected revision is not reused; it is rebuilt from the corrected one.
  await page.getByRole("button", {name: "グラフ", exact: true}).click();
  await expect(page.getByText("設定を変更しました。「図を作成」で反映します。")).toBeVisible({timeout: 120000});
  await page.getByRole("button", {name: "図を作成", exact: true}).click();
  await expect(page.getByRole("img", {name: "保存するグラフ"})).toBeVisible({timeout: 120000});
  const allJobs = await (await page.request.get(`${api}/v1/workspaces/${field.workspace_id}/jobs`)).json();
  const figureJob = allJobs.filter((job: {revision_id: string; kind: string; state: string}) => job.revision_id === corrected.revision_id && job.kind === "statistics" && job.state === "succeeded").at(-1);
  expect(figureJob).toBeTruthy();
  const sizes: Record<string, number> = {};
  for (const name of ["figure.svg", "figure.pdf", "plot-data.csv", "methods.md"]) {
    const response = await page.request.get(`${api}/v1/jobs/${figureJob.id}/files/${name}`); expect(response.ok()).toBeTruthy();
    const body = await response.body(); sizes[name] = body.length; expect(body.length).toBeGreaterThan(50);
    if (name.endsWith(".svg")) {expect(body.toString()).toContain("<svg"); expect(body.toString()).toContain("<text");}
    if (name.endsWith(".pdf")) expect(body.subarray(0, 5).toString()).toBe("%PDF-");
    if (name.endsWith(".csv")) expect(body.toString().trim().split(/\r?\n/).length - 1).toBe(initialLabels - 1);
    if (name === "methods.md") expect(body.toString()).toContain("Regions have not completed visual review");
    await writeFile(path.join(output!, name), body);
  }
  await page.screenshot({path: path.join(output!, "bbbc007-after.png"), fullPage: true});
  await writeFile(path.join(output!, "receipt.json"), JSON.stringify({dataset: "BBBC007", input_sha256: original.map(name => manifest.files[name]), workspace: field.workspace_id, initial_revision: initial.revision_id, corrected_revision: corrected.revision_id, reference, exported_bytes: sizes, scope: "actual Fiji and same-mask raw arithmetic/export acceptance; not detector accuracy or biological validation"}, null, 2));
});
