import {expect, test} from "@playwright/test";
import {execFileSync} from "node:child_process";
import {createHash} from "node:crypto";
import {mkdir, readFile} from "node:fs/promises";
import path from "node:path";

/** Nuclei-first workspace: adding images and naming the nuclear channel detects nuclei on every field
 *  without a separate run step; the method card shows the state, and viewing never writes adoption. */
test("nuclei are detected automatically and the method card reports each step", async ({page}) => {
  const inputs = process.env.CYTELLECT_REAL_INPUTS;
  const output = process.env.CYTELLECT_REAL_OUTPUT;
  const python = process.env.CYTELLECT_TEST_PYTHON;
  const data = process.env.CYTELLECT_TEST_DATA_DIR;
  const api = process.env.CYTELLECT_TEST_API_ORIGIN;
  if (process.env.CYTELLECT_REQUIRE_REAL_FIJI === "1") for (const value of [inputs, output, python, data, api]) expect(value).toBeTruthy();
  test.skip(!inputs || !output || !python || !data || !api, "Requires explicitly configured isolated Fiji runtime and registered public inputs");
  await mkdir(output!, {recursive: true});
  const manifest = JSON.parse(await readFile(path.join(inputs!, "manifest.json"), "utf8"));
  const original = ["a9-actin.tif", "a9-dna.tif"];
  const bytes = await Promise.all(original.map(name => readFile(path.join(inputs!, name))));
  bytes.forEach((value, index) => expect(createHash("sha256").update(value).digest("hex")).toBe(manifest.files[original[index]]));
  const token = execFileSync(python!, ["-B", "-c", "import os;from pathlib import Path;from cytellect_api.db import Store;print(Store(Path(os.environ['CYTELLECT_TEST_DATA_DIR'])).invite(3600))"], {encoding: "utf8", env: process.env, stdio: ["ignore", "pipe", "ignore"]}).trim();
  const redeemed = await page.request.post(`${api}/v1/invitations/redeem`, {headers: {Origin: process.env.CYTELLECT_WEB_URL!, "X-Cytellect-Request": "1"}, data: {token}});
  expect(redeemed.ok()).toBeTruthy();
  await page.goto("/workspace");
  const selectionWrites: string[] = [];
  page.on("request", request => {if (request.method() === "POST" && new URL(request.url()).pathname.endsWith("/selection")) selectionWrites.push(request.url());});
  await page.getByTestId("file-input").setInputFiles(bytes.map((buffer, index) => ({name: `a9_c${index + 1}.tif`, mimeType: "image/tiff", buffer})));
  const method = page.getByRole("region", {name: "解析方法"});
  await expect(method.getByText("何を調べますか")).toBeVisible();
  await expect(method.getByText("DAPI の暗い部分を核小体とする")).toBeVisible();
  // The only setup decision: which channel stains nuclei (no stain is inferred from c1/c2).
  const accepted = page.waitForResponse(response => new URL(response.url()).pathname.endsWith("/region-analyses") && response.request().method() === "POST");
  await method.getByRole("button", {name: "c2 で核を検出"}).click();
  expect((await accepted).status()).toBe(202);
  await expect(method.getByText("1/1 視野").first()).toBeVisible({timeout: 300000});
  await page.screenshot({path: path.join(output!, "method-card-desktop.png")});
  // Switching what is viewed must not write adoption.
  const before = selectionWrites.length;
  await method.getByRole("button", {name: "輪郭を見る"}).first().click();
  await page.waitForTimeout(500);
  expect(selectionWrites.length).toBe(before);
  await method.getByRole("button", {name: "手法の詳細と文献"}).click();
  const sheet = page.getByRole("dialog", {name: "手法の詳細と文献"});
  await expect(sheet.getByRole("link", {name: /Kodiha M et al/})).toHaveAttribute("href", "https://doi.org/10.1186/1471-2121-12-25");
  await expect(sheet.getByRole("link", {name: /Schmidt U et al/})).toBeVisible();
  await page.screenshot({path: path.join(output!, "method-sheet-desktop.png")});
});
