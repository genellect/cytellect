// Rasterize the existing application icon; do not introduce a second identity.
import { createRequire } from "node:module";
import { mkdir } from "node:fs/promises";
import { resolve } from "node:path";

const require = createRequire(import.meta.url);
const nextRequire = createRequire(require.resolve("next/package.json"));
const sharp = nextRequire("sharp");
const output = process.argv[2];
if (!output) throw new Error("MSIX asset destination required");
await mkdir(output, { recursive: true });
for (const [name, size] of [["StoreLogo", 50], ["Square44x44Logo", 44], ["Square150x150Logo", 150]]) {
  await sharp(resolve(import.meta.dirname, "../src/app/icon.svg"))
    .resize(size, size).png().toFile(resolve(output, `${name}.png`));
}
