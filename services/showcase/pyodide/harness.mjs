// Runs the showcase runtime in Pyodide under Node, loaded the same way as the browser
// worker: the pinned Pyodide packages from runtime-config.json, then every wheel from
// apps/web/public/showcase/runtime/ (SHA-256 verified, unpacked into site-packages), the
// fonts into /showcase/fonts, and finally cytellect_showcase.runtime.boot/handle.
//
// node harness.mjs --seed seed.zip --requests requests.json [--cache DIR] [--origin URL]
//
// requests.json is a list of steps:
//   {"method": "GET", "url": "/v1/...", "body": {...}, "headers": [[name, value]], "save": "name"}
//   {"settle": true}                       wait until queued jobs have run
//   {"poll": "/v1/jobs/{x.job_id}", "until": "state", "in": ["succeeded", "failed"]}
//   {"python": "code", "save": "name"}     run code in the runtime; a JSON string result is saved
//   {"copy_out": "{name.root}", "items": "{name.dirs}", "to": "DIR"}  copy those directories
//                                          from the runtime's file system to DIR (replacing them)
// Any step may carry "label". "{name.a.0.b}" inside a url or string body value is replaced
// from a saved JSON response; a string that is exactly "{name.a}" becomes that JSON value.
// One JSON line ({step, status, type, bytes, sha256, json}) is printed per response; the
// last line reports timing and memory. Network access is needed only for the Pyodide CDN
// (Node: NODE_USE_ENV_PROXY=1 behind a proxy); --cache keeps downloaded packages.
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "../../..");
const { values: args } = parseArgs({
  options: {
    seed: { type: "string" },
    requests: { type: "string" },
    cache: { type: "string" },
    origin: { type: "string", default: "https://showcase.test" },
    runtime: { type: "string", default: join(root, "apps/web/public/showcase/runtime") },
    config: { type: "string", default: join(root, "apps/web/src/lib/showcase/runtime-config.json") },
  },
});
if (!args.seed || !args.requests) throw new Error("--seed and --requests are required");

// Browser-like inputs: Pyodide converts Uint8Array, not Node Buffer.
const read = (path) => new Uint8Array(readFileSync(path));
const sha256 = (bytes) => createHash("sha256").update(bytes).digest("hex");
const config = JSON.parse(readFileSync(args.config, "utf8"));
const started = Date.now();
const timings = {};
const mark = (name) => { timings[name] = Date.now() - started; };

const { loadPyodide, version } = await import("pyodide");
if (version !== config.pyodideVersion) throw new Error(`pyodide ${version} != ${config.pyodideVersion}`);
// In Node the core comes from the pinned npm package; packages are fetched from the
// same versioned CDN as indexURL (cached in --cache when given).
const pyodide = await loadPyodide({ ...(args.cache ? { packageCacheDir: args.cache } : {}) });
mark("pyodide");
await pyodide.loadPackage(config.packages, { messageCallback: () => {}, errorCallback: (m) => process.stderr.write(m + "\n") });
mark("packages");
const sitePackages = pyodide.runPython("import site; site.getsitepackages()[0]");
let downloadBytes = 0;
for (const wheel of config.wheels) {
  const bytes = read(join(args.runtime, wheel.file));
  if (sha256(bytes) !== wheel.sha256) throw new Error(`hash mismatch: ${wheel.file}`);
  downloadBytes += bytes.length;
  pyodide.unpackArchive(bytes, "wheel", { extractDir: sitePackages });
}
pyodide.FS.mkdirTree("/showcase/fonts");
for (const font of config.fonts) {
  const bytes = read(join(args.runtime, font.file));
  if (sha256(bytes) !== font.sha256) throw new Error(`hash mismatch: ${font.file}`);
  downloadBytes += bytes.length;
  pyodide.FS.writeFile(`/showcase/fonts/${font.file}`, bytes);
}
pyodide.runPython("import importlib; importlib.invalidate_caches()");
mark("wheels");
const runtime = pyodide.pyimport("cytellect_showcase.runtime");
const seed = read(args.seed);
await runtime.boot(seed, args.origin);
mark("boot");

const saved = {};
const lookup = (expression) => expression.split(".").reduce((value, key) => {
  if (value === undefined || value === null) throw new Error(`unresolved {${expression}}`);
  return value[key];
}, saved);
const fill = (value) => {
  if (typeof value === "string" && /^\{[A-Za-z0-9_.-]+\}$/.test(value)) return lookup(value.slice(1, -1));
  if (typeof value === "string") return value.replace(/\{([A-Za-z0-9_.-]+)\}/g, (_, e) => String(lookup(e)));
  if (Array.isArray(value)) return value.map(fill);
  if (value && typeof value === "object") return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, fill(v)]));
  return value;
};

async function request(method, url, body, headers) {
  const sent = [...(headers ?? [])];
  let payload;
  if (body !== undefined) {
    payload = new TextEncoder().encode(JSON.stringify(fill(body)));
    sent.push(["content-type", "application/json"]);
  }
  if (!["GET", "HEAD"].includes(method)) sent.push(["x-cytellect-request", "1"]);
  const proxy = await runtime.handle(method, fill(url), sent, payload);
  const response = proxy.toJs({ dict_converter: Object.fromEntries });
  proxy.destroy();
  const bytes = response.body;
  const type = (response.headers.find(([name]) => name.toLowerCase() === "content-type") ?? [, ""])[1];
  let json;
  if (type.startsWith("application/json")) json = JSON.parse(new TextDecoder().decode(bytes));
  return { status: response.status, type, bytes: bytes.length, sha256: sha256(bytes), json };
}

function copyOut(from, to) {
  rmSync(to, { recursive: true, force: true });
  mkdirSync(to, { recursive: true });
  for (const name of pyodide.FS.readdir(from)) {
    if (name === "." || name === "..") continue;
    const source = `${from}/${name}`;
    if (pyodide.FS.isDir(pyodide.FS.stat(source).mode)) copyOut(source, join(to, name));
    else writeFileSync(join(to, name), pyodide.FS.readFile(source));
  }
}

for (const step of JSON.parse(readFileSync(args.requests, "utf8"))) {
  if (step.python !== undefined) {
    const value = await pyodide.runPythonAsync(step.python);
    const json = typeof value === "string" ? JSON.parse(value) : null;
    if (step.save) saved[step.save] = json;
    console.log(JSON.stringify({ step: step.label ?? "python", json }));
    continue;
  }
  if (step.copy_out !== undefined) {
    const from = fill(step.copy_out);
    for (const item of fill(step.items)) copyOut(`${from}/${item}`, join(resolve(step.to), item));
    continue;
  }
  if (step.settle) {
    await runtime.settle();
    continue;
  }
  let result;
  if (step.poll) {
    for (let attempt = 0; attempt < 600; attempt += 1) {
      result = await request("GET", step.poll);
      if (result.status !== 200 || step.in.includes(result.json?.[step.until])) break;
      await new Promise((done) => setTimeout(done, 50));
    }
  } else {
    result = await request(step.method ?? "GET", step.url, step.body, step.headers);
  }
  if (step.save) saved[step.save] = result.json;
  console.log(JSON.stringify({ step: step.label ?? step.url ?? step.poll, status: result.status, type: result.type,
    bytes: result.bytes, sha256: result.sha256, json: result.json ?? null }));
}
mark("requests");
console.log(JSON.stringify({
  summary: true, timings_ms: timings,
  runtime_download_bytes: downloadBytes,
  wasm_heap_bytes: pyodide._module.HEAPU8.length,
  node_rss_bytes: process.memoryUsage().rss,
}));
