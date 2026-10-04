import { spawnSync } from "node:child_process";
import { createRequire } from "node:module";
import { finalizeLocalExport } from "./finalize-local-export.mjs";
const require = createRequire(import.meta.url);
const result = spawnSync(process.execPath, [require.resolve("next/dist/bin/next"), "build"], {
  stdio: "inherit",
  env: { ...process.env, CYTELLECT_WEB_MODE: "local", NEXT_PUBLIC_API_ORIGIN: "" },
});
if (result.error) throw result.error;
if (result.status !== 0) process.exit(result.status ?? 1);
console.log(JSON.stringify({ localFlightExport: finalizeLocalExport(process.cwd()) }));
