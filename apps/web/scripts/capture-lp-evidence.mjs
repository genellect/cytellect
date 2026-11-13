// Captures the landing page's product evidence from the public demo.
//
// Each asset is a whole demo screen, or the part of one that shows what a feature is worth
// (docs/lp-art-direction.md, section 5). Nothing on the screen is edited: the script only chooses
// the scene, the screen, the viewport and the rectangle. Rerun it whenever the demo is rebuilt.
//
//   cd apps/web && node scripts/capture-lp-evidence.mjs --base https://cytellect.app
//
// Writes public/marketing/lp-*.webp, their record public/marketing/lp-evidence.json, and the
// matching entries of fixtures/public/allowlist.json.
import { chromium } from "@playwright/test";
import { createHash } from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const web = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const repo = path.resolve(web, "../..");
const out = path.join(web, "public/marketing");
const flag = name => { const at = process.argv.indexOf(name); return at < 0 ? undefined : process.argv[at + 1]; };
const base = (flag("--base") ?? process.env.CYTELLECT_WEB_URL ?? "http://localhost:3000").replace(/\/$/, "");

const PLK1 = "cpg0016-jump-source13-plk1";
const OXALIPLATIN = "zenodo-6643470-oxaliplatin";

/** Whole screens are captured at this size: wide enough for the desktop layout, and short enough that the
 *  screen ends above the parts a visitor would need to scroll to. */
const SCREEN = [1600, 790];

/** A stage on the landing page shows one feature in two layers: the whole screen behind, so the visitor
 *  sees where it is, and the part that matters in front, large enough to read. `screen` shots are the
 *  whole viewport; the others are one element, cut by `crop` (measured in the page, relative to the
 *  element, in CSS pixels). */
const SHOTS = [
  { file: "lp-screen-statistics.webp", scene: PLK1, step: "statistics", viewport: SCREEN, scale: 1.5, screen: true,
    region: "統計の画面" },
  { file: "lp-focus-conclusion.webp", scene: PLK1, step: "statistics", viewport: [1600, 1000], scale: 3,
    region: "結果のまとめ：結論の一文、指標の意味、要点",
    element: 'section[aria-label="結果のまとめ"]',
    crop: root => ({ bottom: root.querySelector("ul").getBoundingClientRect().bottom - root.getBoundingClientRect().top + 16 }) },
  { file: "lp-focus-discussion.webp", scene: PLK1, step: "statistics", viewport: [1600, 1000], scale: 3,
    region: "考察：解釈、限界・代替説明、追加検証",
    element: 'section[aria-label="考察"]',
    crop: root => ({ top: root.querySelector(":scope > div").getBoundingClientRect().top - root.getBoundingClientRect().top - 8 }) },
  { file: "lp-focus-table.webp", scene: OXALIPLATIN, step: "image", viewport: [2800, 1000], scale: 2,
    region: "核ごとの表",
    prepare: async page => { await page.getByRole("button", { name: "2 画面", exact: true }).click(); },
    element: 'table[aria-label="核ごとの表"]' },
  { file: "lp-screen-ai.webp", scene: PLK1, step: "statistics", viewport: SCREEN, scale: 1.5, screen: true,
    region: "統計の画面と AI のパネル", prepare: askAssistant },
  { file: "lp-focus-ai.webp", scene: PLK1, step: "statistics", viewport: SCREEN, scale: 3,
    region: "AI：指示の一文と、組み立てた設定の説明", prepare: askAssistant,
    element: 'aside[aria-label="AI"]',
    crop: root => {
      const top = root.getBoundingClientRect().top, answer = root.querySelector("p");
      return { top: answer.previousElementSibling.getBoundingClientRect().top - top, bottom: root.querySelector("dl").getBoundingClientRect().bottom - top + 10 };
    } },
  { file: "lp-screen-figure.webp", scene: PLK1, step: "figure", viewport: SCREEN, scale: 1.5, screen: true,
    region: "グラフの画面" },
  { file: "lp-focus-figure-layout.webp", scene: PLK1, step: "figure", viewport: [1600, 1000], scale: 3,
    region: "グラフの設定：図の幅とレイアウト",
    element: 'section[aria-label="図の作成・保存"] nav[aria-label="図の設定対象"]', parent: true,
    crop: root => {
      const top = root.getBoundingClientRect().top, labels = root.querySelectorAll(":scope > label");
      return { top: root.querySelector("nav").getBoundingClientRect().top - top - 10, bottom: labels[1].getBoundingClientRect().bottom - top + 12 };
    } },
  { file: "lp-focus-figure-size.webp", scene: PLK1, step: "figure", viewport: [1600, 1000], scale: 3,
    region: "グラフの設定：幅・高さ（mm）と文字（pt）",
    element: 'section[aria-label="図の作成・保存"] nav[aria-label="図の設定対象"]', parent: true,
    crop: root => {
      const top = root.getBoundingClientRect().top, numbers = [...root.querySelectorAll('input:not([type="checkbox"])')];
      return { top: numbers[0].closest("label").getBoundingClientRect().top - top - 8, bottom: numbers.at(-1).closest("label").getBoundingClientRect().bottom - top + 12 };
    } },
];

async function askAssistant(page) {
  await page.getByPlaceholder(/AIに指示/).click();
  await page.getByRole("button", { name: "核の数と面積の分布", exact: true }).click();
  await page.locator('aside[aria-label="AI"] dl').waitFor();
}

const json = async url => { const response = await fetch(url); if (!response.ok) throw new Error(`${url}: ${response.status}`); return response.json(); };
const scenes = (await json(`${base}/showcase/snapshot/scenes.json`)).scenes;
const manifest = await json(`${base}/showcase/manifest.json`);
const sceneOf = id => { const scene = scenes.find(item => item.id === id); if (!scene) throw new Error(`The demo has no scene ${id}`); return scene; };

const browser = await chromium.launch(process.env.CYTELLECT_CHROMIUM_EXECUTABLE ? { executablePath: process.env.CYTELLECT_CHROMIUM_EXECUTABLE } : {});
const records = [];
try {
  for (const shot of SHOTS) {
    const scene = sceneOf(shot.scene);
    const [width, height] = shot.viewport;
    const context = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: shot.scale, locale: "ja-JP" });
    const page = await context.newPage();
    await page.goto(`${base}/demo?id=${scene.workspaceId}&step=${shot.step}`, { waitUntil: "networkidle" });
    // The demo opens with a note about its scene, which the product does not have.
    const note = page.getByRole("button", { name: "場面の概要を閉じる" });
    if (await note.count()) await note.click();
    await shot.prepare?.(page);
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(1500);
    let png, box;
    if (shot.screen) {
      png = await page.screenshot({ type: "png" });
      box = { top: 0, bottom: height };
    } else {
      let target = page.locator(shot.element).first();
      if (shot.parent) target = target.locator("xpath=..");
      await target.waitFor();
      box = await target.evaluate((root, crop) => {
        const size = root.getBoundingClientRect();
        // The crop function is sent as source text; it only reads the layout.
        const cut = crop ? new Function(`return (${crop})`)()(root) : {};
        return { top: Math.max(0, cut.top ?? 0), bottom: Math.min(size.height, cut.bottom ?? size.height) };
      }, shot.crop?.toString());
      png = await target.screenshot({ type: "png" });
    }
    // Chromium encodes the WebP, so the script needs no image library. A blank page does it: the site's
    // own page may not read data: URLs.
    const encoder = await context.newPage();
    const encoded = await encoder.evaluate(async ({ data, top, bottom, scale }) => {
      const bitmap = await createImageBitmap(await (await fetch(`data:image/png;base64,${data}`)).blob());
      const y = Math.round(top * scale), h = Math.min(bitmap.height - y, Math.round((bottom - top) * scale));
      const canvas = new OffscreenCanvas(bitmap.width, h);
      canvas.getContext("2d").drawImage(bitmap, 0, y, bitmap.width, h, 0, 0, bitmap.width, h);
      const bytes = new Uint8Array(await (await canvas.convertToBlob({ type: "image/webp", quality: 0.92 })).arrayBuffer());
      let text = ""; for (let i = 0; i < bytes.length; i += 0x8000) text += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
      return { data: btoa(text), width: bitmap.width, height: h };
    }, { data: png.toString("base64"), top: box.top, bottom: box.bottom, scale: shot.scale });
    const bytes = Buffer.from(encoded.data, "base64");
    fs.writeFileSync(path.join(out, shot.file), bytes);
    records.push({
      file: shot.file, sha256: createHash("sha256").update(bytes).digest("hex"), bytes: bytes.length,
      width: encoded.width, height: encoded.height, css_width: Math.round(encoded.width / shot.scale), css_height: Math.round(encoded.height / shot.scale),
      scene: scene.id, step: shot.step, region: shot.region, viewport: shot.viewport, device_scale_factor: shot.scale,
      source: scene.sourceUrl, license: scene.licence, attribution: scene.attribution,
    });
    console.log(`${shot.file} ${encoded.width}x${encoded.height} ${bytes.length} bytes`);
    await context.close();
  }
} finally {
  await browser.close();
}

fs.writeFileSync(path.join(out, "lp-evidence.json"), JSON.stringify({
  schema_version: "1.0.0",
  kind: "landing-page-product-evidence",
  captured_by: "apps/web/scripts/capture-lp-evidence.mjs",
  note: "Browser captures of the public demo. Each asset is one rectangle of one screen; no interface element or value is edited.",
  demo: { origin: base, generated_from_commit: manifest.generated_from_commit, runtime_generated_from_commit: manifest.runtime_generated_from_commit },
  assets: records,
}, null, 2) + "\n");

const registry = path.join(repo, "fixtures/public/allowlist.json");
const allowed = JSON.parse(fs.readFileSync(registry, "utf8"));
for (const record of records) {
  allowed[`apps/web/public/marketing/${record.file}`] = { sha256: record.sha256, source: record.source, license: `${record.license} (public images/derived outputs); Apache-2.0 (Cytellect UI)` };
}
fs.writeFileSync(registry, JSON.stringify(allowed, null, 2) + "\n");
