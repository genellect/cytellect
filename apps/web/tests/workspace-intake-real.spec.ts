import {expect, test, type Page} from "@playwright/test";
import {execFileSync} from "node:child_process";
import {createHash} from "node:crypto";
import {mkdir, mkdtemp, readFile, writeFile} from "node:fs/promises";
import {tmpdir} from "node:os";
import path from "node:path";

/**
 * #284 W1 against the real API: the Issue's controls A, B and C and its mixed input, with the registered public
 * BBBC007 fields a9 and f9620 under the Issue's file names (C01 = DNA, C02 = actin, plan §11) and BBBC013 A01.
 * The truncated TIFF is the Issue's sample (the first 32 bytes of BBBC013 A01-dapi). The 32-bit label image is a
 * synthetic array of a9's size: only its type and size decide the outcome. No detection runs.
 */
const inputs = process.env.CYTELLECT_REAL_INPUTS, python = process.env.CYTELLECT_TEST_PYTHON, data = process.env.CYTELLECT_TEST_DATA_DIR;
const api = process.env.CYTELLECT_TEST_API_ORIGIN, origin = process.env.CYTELLECT_WEB_URL;
const bbbc013 = path.resolve(__dirname, "../../../fixtures/public/bbbc013");
type Payload = {name:string;mimeType:string;buffer:Buffer};
interface Entry {id:string;field_id:string|null;intake?:{names:string[];state:string;stage?:string;code?:string;target?:{group_id:string;run_id:string}}}

async function files() {
  const manifest = JSON.parse(await readFile(path.join(inputs!, "manifest.json"), "utf8"));
  const read = async (name:string) => {const bytes = await readFile(path.join(inputs!, name));expect(createHash("sha256").update(bytes).digest("hex")).toBe(manifest.files[name]);return bytes;};
  const tiff = (name:string, buffer:Buffer):Payload => ({name, mimeType:"image/tiff", buffer});
  const a9dna = await read("a9-dna.tif"), a9actin = await read("a9-actin.tif"), f9620dna = await read("f9620-dna.tif"), f9620actin = await read("f9620-actin.tif");
  const draq = await readFile(path.join(bbbc013, "A01-dapi.tif")), gfp = await readFile(path.join(bbbc013, "A01-gfp.tif"));
  const truncated = draq.subarray(0, 32);
  expect(createHash("sha256").update(truncated).digest("hex")).toBe("7dd18bc41cd5770f432436d7103a67e87122ee1edcf31695afe6115d0587e112");
  const mask = execFileSync(python!, ["-B", "-c", ["import io,sys,numpy as np,tifffile", "shape=tifffile.imread(sys.argv[1]).shape[:2]",
    "labels=np.zeros(shape,np.int32);labels[10:30,10:30]=1;out=io.BytesIO();tifffile.imwrite(out,labels);sys.stdout.buffer.write(out.getvalue())"].join("\n"), path.join(inputs!, "a9-dna.tif")], {env:process.env, stdio:["ignore", "pipe", "pipe"]});
  return {
    bbbc007: [tiff("BBBC007-a9-C01.tif", a9dna), tiff("BBBC007-a9-C02.tif", a9actin), tiff("BBBC007-f9620-C01.tif", f9620dna), tiff("BBBC007-f9620-C02.tif", f9620actin)],
    copy: tiff("BBBC007-a9-C01.tif", a9dna), truncated: tiff("test-truncated-DRAQ.tif", truncated),
    // A readable image with other bytes under a9's C01 name (BBBC013 A01's DRAQ): a name conflict, not a copy.
    conflict: tiff("BBBC007-a9_c01.tif", draq), mask: tiff("BBBC007-a9-核の手動輪郭.tif", mask),
    text: {name:"読み方.txt", mimeType:"text/plain", buffer:Buffer.from("BBBC007")}, a01: [tiff("A01-DRAQ.tif", draq), tiff("A01-GFP.tif", gfp)],
  };
}

async function signIn(page:Page) {
  // One-use token is captured only in memory, never logged or saved in evidence.
  const token = execFileSync(python!, ["-B", "-c", "import os;from pathlib import Path;from cytellect_api.db import Store;print(Store(Path(os.environ['CYTELLECT_TEST_DATA_DIR']),workspace_retention_mode=('manual' if (Path(os.environ['CYTELLECT_TEST_DATA_DIR'])/'.manual-workspace-retention').exists() else 'ttl')).invite(3600))"], {encoding:"utf8", env:process.env, stdio:["ignore", "pipe", "ignore"]}).trim();
  expect((await page.request.post(`${api}/v1/invitations/redeem`, {headers:{Origin:origin!, "X-Cytellect-Request":"1"}, data:{token}})).ok()).toBeTruthy();
  await page.goto("/workspace");
  await page.getByRole("button", {name:/新しいワークスペース/}).first().click();
  await expect(page.getByTestId("file-input")).toBeEnabled();
}
const workspaceId = (page:Page) => new URL(page.url()).searchParams.get("id")!;
async function entries(page:Page):Promise<Entry[]> {return (await (await page.request.get(`${api}/v1/workspaces/${workspaceId(page)}/selection`)).json()).entries;}
const status = (page:Page, text:string) => page.getByRole("status").filter({hasText:text});
const list = (page:Page) => page.getByRole("region", {name:"取り込みの一覧"});
const addListed = (page:Page) => list(page).getByRole("button", {name:"追加", exact:true}).click();
const fieldCards = (page:Page) => page.getByRole("complementary", {name:"視野一覧"}).getByRole("button").filter({hasText:/BBBC007|A01/});

test.describe("#284 W1, W4, W5 intake against the real API", () => {
  test.skip(!inputs || !python || !data || !api || !origin, "Requires the registered public inputs and an isolated API");
  test.beforeEach(() => {test.setTimeout(300000);});

  test("control A and input 5: the list adds up, a copy is not a field, an unreadable file is recorded, and nothing asks for a reason", async ({page}) => {
    const input = await files();await signIn(page);
    await page.getByTestId("file-input").setInputFiles([...input.bbbc007, input.copy, input.truncated, input.mask, input.text]);
    // Judged by the API before anything is registered (W4): the parts add up to the 8 files received.
    await expect(list(page).getByRole("status")).toHaveText("受け取り：8 · 画像：4（2 視野） · マスクの候補：1 · 同一内容：1 · 読み取れない：1 · 対象外：1", {timeout:120000});
    await expect(list(page).getByRole("row").filter({hasText:"BBBC007-a9-核の手動輪郭.tif"})).toContainText("寸法の一致：BBBC007-a9");
    await expect(list(page).getByRole("row").filter({hasText:"test-truncated-DRAQ.tif"})).toContainText("読み取り不可");
    await expect(list(page).getByRole("row").filter({hasText:"同一内容"})).toContainText("対応先：BBBC007-a9-C01.tif");
    await addListed(page);
    await expect(status(page, "登録：2 視野")).toBeVisible({timeout:120000});
    await expect(fieldCards(page)).toHaveCount(2);
    // What was not added stays in the list, also when the addition created the workspace (#284 input 5).
    await expect(list(page).getByRole("status").first()).toHaveText("受け取り：3 · 画像：0（0 視野） · マスクの候補：1 · 同一内容：1 · 対象外：1");
    await expect(page.getByRole("alert").filter({hasText:/\S/})).toHaveCount(0);
    await expect(page.getByLabel(/除外の理由/)).toHaveCount(0);
    const saved = await entries(page);
    expect(saved.filter(entry => entry.field_id).map(entry => entry.intake?.names).sort()).toEqual([["BBBC007-a9-C01.tif", "BBBC007-a9-C02.tif"], ["BBBC007-f9620-C01.tif", "BBBC007-f9620-C02.tif"]]);
    // Only the unreadable file is a row (stage inspect); the mask candidate is not missing data.
    expect(saved.filter(entry => !entry.field_id).map(entry => [entry.intake?.names[0], entry.intake?.state, entry.intake?.stage, entry.intake?.code]))
      .toEqual([["test-truncated-DRAQ.tif", "rejected", "inspect", "unsupported_or_invalid_region_image"]]);
    // A restart keeps the name and reason (#284 involvement 3).
    await page.reload();
    await page.getByRole("button", {name:"取込 1件", exact:true}).click();
    await expect(page.locator("li").filter({hasText:"test-truncated-DRAQ.tif：読み取り不可"})).toBeVisible();
    await expect(page.getByText(/名称不明|名前の記録なし/)).toHaveCount(0);
    await expect(fieldCards(page)).toHaveCount(2);
  });

  test("control B: a name conflict holds its own field only, and choosing the right files again registers it", async ({page}) => {
    const input = await files();await signIn(page);
    await page.getByTestId("file-input").setInputFiles([...input.bbbc007, input.conflict]);
    await expect(list(page).getByRole("status")).toHaveText("受け取り：5 · 画像：5（2 視野）", {timeout:120000});
    await addListed(page);
    await expect(status(page, "登録：1 視野 · 要確認：1 視野")).toBeVisible({timeout:120000});
    await expect(page.locator("li").filter({hasText:"要確認 · 同じ視野・チャンネルに 2 枚"})).toContainText("BBBC007-a9-C01.tif、BBBC007-a9_c01.tif、BBBC007-a9-C02.tif");
    await expect(fieldCards(page)).toHaveCount(1);
    await expect(fieldCards(page)).toContainText("BBBC007-f9620");
    await page.getByTestId("file-input").setInputFiles(input.bbbc007.slice(0, 2));
    await addListed(page);
    await expect(status(page, "登録：1 視野")).toBeVisible({timeout:120000});
    await expect(page.getByText(/要確認/)).toHaveCount(0);
    await expect(fieldCards(page)).toHaveCount(2);
    expect((await entries(page)).filter(entry => !entry.field_id)).toEqual([]);
  });

  test("control C: images added in a group's cell stay in that group with a refused image beside them, also after a reload", async ({page}) => {
    const input = await files();await signIn(page);
    await page.getByRole("navigation", {name:"作業の切替"}).getByRole("button", {name:"実験", exact:true}).click();
    await page.getByRole("button", {name:/^2 画面/}).click();
    const specification = async () => (await (await page.request.get(`${api}/v1/workspaces/${workspaceId(page)}/analysis-spec`)).json()).spec;
    await expect.poll(async () => (await specification())?.experiment?.groups?.length ?? 0, {timeout:60000}).toBe(2);
    const design = (await specification()).experiment;
    const control = design.groups.find((group:{id:string}) => group.id === design.control_group_id), treated = design.groups.find((group:{id:string}) => group.id !== design.control_group_id);
    const addTo = async (label:string, payloads:Payload[]) => {
      const chooser = page.waitForEvent("filechooser");
      await page.getByRole("cell").filter({hasText:label}).first().getByRole("button", {name:"画像を追加", exact:true}).click();
      await (await chooser).setFiles(payloads);
    };
    await addTo(control.label, [...input.bbbc007, input.truncated]);
    await expect(list(page).getByRole("status")).toHaveText("受け取り：5 · 画像：4（2 視野） · 読み取れない：1", {timeout:120000});
    await addListed(page);
    await expect(status(page, "登録：2 視野")).toBeVisible({timeout:120000});
    await addTo(treated.label, input.a01);
    await expect(list(page).getByRole("status")).toHaveText("受け取り：2 · 画像：2（1 視野）", {timeout:120000});
    await addListed(page);
    await expect(status(page, "登録：1 視野")).toBeVisible({timeout:120000});
    const placed = async () => {const fields = (await specification()).experiment.fields as Record<string, {group_id:string}>;
      return Object.values(fields).reduce<Record<string, number>>((count, value) => ({...count, [value.group_id]:(count[value.group_id] ?? 0) + 1}), {});};
    expect(await placed()).toEqual({[control.id]:2, [treated.id]:1});
    const refused = (await entries(page)).filter(entry => !entry.field_id);
    expect(refused.map(entry => [entry.intake?.names, entry.intake?.code, entry.intake?.target?.group_id])).toEqual([[["test-truncated-DRAQ.tif"], "unsupported_or_invalid_region_image", control.id]]);
    await page.reload();
    await page.getByRole("navigation", {name:"作業の切替"}).getByRole("button", {name:"実験", exact:true}).click();
    await expect(page.getByRole("cell").filter({hasText:control.label}).first()).toContainText("2 視野", {timeout:60000});
    await expect(page.getByRole("cell").filter({hasText:treated.label}).first()).toContainText("1 視野");
    expect(await placed()).toEqual({[control.id]:2, [treated.id]:1});
  });

  test("W6: a folder of a run with two groups is suggested as such and applied only with 「案を適用」", async ({page}) => {
    const input = await files();
    // The registered public images in a run/group folder layout (BBBC007 a9 as control, f9620 as treated): names only
    // decide. The folder names are ASCII: Playwright cannot hand Chromium a folder whose path holds other characters
    // (the files then cannot be read); Japanese folder names are covered by the unit tests of the suggestions.
    // A plain temporary folder: a folder upload with brackets in its path (the test title) does not complete.
    const root = path.join(await mkdtemp(path.join(tmpdir(), "cytellect-w6-")), "Rep1");
    for (const [group, payloads] of [["control", input.bbbc007.slice(0, 2)], ["treated", input.bbbc007.slice(2)]] as const) {
      await mkdir(path.join(root, group), {recursive: true});
      for (const payload of payloads) await writeFile(path.join(root, group, payload.name), payload.buffer);
    }
    await signIn(page);
    await page.getByTestId("folder-input").setInputFiles(root);
    await expect(list(page).getByRole("status")).toHaveText("受け取り：4 · 画像：4（2 視野）", {timeout:120000});
    await addListed(page);
    await expect(status(page, "登録：2 視野")).toBeVisible({timeout:120000});
    await page.getByRole("navigation", {name:"作業の切替"}).getByRole("button", {name:"実験", exact:true}).click();
    await expect(page.getByRole("status").filter({hasText:"フォルダーからの案：2 群（control、treated） · 実験回 1"})).toBeVisible();
    await page.getByRole("button", {name:/^2 画面/}).click();
    const table = page.getByRole("region", {name:"群・実験回が未割り当ての視野"});
    await expect(table.getByRole("cell").filter({hasText:"Rep1 · control"})).toBeVisible();
    await expect(table.getByRole("cell").filter({hasText:"Rep1 · treated"})).toBeVisible();
    const specification = async () => (await (await page.request.get(`${api}/v1/workspaces/${workspaceId(page)}/analysis-spec`)).json()).spec;
    expect(Object.keys((await specification())?.experiment?.fields ?? {})).toEqual([]);
    await table.getByRole("button", {name:"案を適用", exact:true}).click();
    await expect(table).toHaveCount(0);
    await expect.poll(async () => Object.keys((await specification()).experiment.fields ?? {}).length, {timeout:60000}).toBe(2);
    const design = (await specification()).experiment;
    expect(design.runs.map((run:{label:string}) => run.label)).toEqual(["Rep1"]);
    const byGroup = Object.fromEntries(design.groups.map((group:{id:string;label:string}) => [group.label, Object.values(design.fields as Record<string, {group_id:string}>).filter(value => value.group_id === group.id).length]));
    expect(byGroup).toEqual({control: 1, treated: 1});
  });
});
