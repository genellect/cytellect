/**
 * Runtime boot used inside the showcase Web Worker. Kept free of worker globals so
 * the verification order can be tested: every self-hosted file is checked against
 * runtime-config.json before it is written into the Python file system.
 */
import {fetchVerified} from "./digest";
import type {HeaderList, RuntimeConfig, ShowcaseRequest, ShowcaseResponse} from "./protocol";

export interface PyodideLike {
  loadPackage(names: string[]): Promise<unknown>;
  unpackArchive(buffer: Uint8Array, format: string, options?: {extractDir?: string}): void;
  runPython(code: string): unknown;
  runPythonAsync(code: string): Promise<unknown>;
  globals: {get(name: string): unknown};
  FS: {mkdirTree(path: string): void; writeFile(path: string, data: Uint8Array): void};
}
export interface RuntimeHandle {handle(request: ShowcaseRequest): Promise<ShowcaseResponse>}
export interface BootDependencies {
  fetcher: typeof fetch;
  loadPyodide: (indexURL: string) => Promise<PyodideLike>;
  /** Base for self-hosted files, e.g. "https://example.org/showcase/". */
  base: string;
}

/** cytellect_showcase.runtime.DEFAULT_FONT_DIR; the Node harness installs fonts in the same place. */
export const FONT_DIR = "/showcase/fonts";
const GLUE = `
import js
from pyodide.ffi import to_js
import cytellect_showcase.runtime as _cytellect_runtime
async def _cytellect_boot(seed, origin):
    await _cytellect_runtime.boot(seed.to_bytes(), str(origin), font_dir=${JSON.stringify(FONT_DIR)})
async def _cytellect_handle(method, url, headers, body):
    result = await _cytellect_runtime.handle(str(method), str(url), [[str(k), str(v)] for k, v in headers.to_py()],
                                             None if body is None else body.to_bytes())
    return to_js({"status": int(result["status"]), "headers": [[str(k), str(v)] for k, v in result["headers"]],
                  "body": bytes(result["body"])}, dict_converter=js.Object.fromEntries)
`;
const safeName = (name: string) => /^[A-Za-z0-9][A-Za-z0-9._+-]*$/.test(name) && !name.includes("..");

/** Download, verify and install the runtime, then boot the API from the seed. */
export async function bootPyodideRuntime(config: RuntimeConfig, origin: string, dependencies: BootDependencies): Promise<RuntimeHandle> {
  const {fetcher, base} = dependencies;
  if (!config.indexURL || !/^https:\/\//.test(config.indexURL)) throw new Error("showcase_runtime_missing");
  const files = [...config.wheels, ...config.fonts];
  if (files.some(file => !safeName(file.file))) throw new Error("showcase_runtime_invalid");
  // The seed is checked first so an unpublished demo never downloads the interpreter.
  // Runtime URLs carry their digest, so the immutable browser cache never serves another build's file.
  const seedResponse = await fetcher(`${base}seed.zip`);
  if (!seedResponse.ok) throw new Error("showcase_seed_missing");
  const seed = new Uint8Array(await seedResponse.arrayBuffer());
  const verified = await Promise.all(files.map(async file => ({file, bytes: await fetchVerified(`${base}runtime/${file.file}?sha256=${file.sha256}`, file.sha256, fetcher)})));
  const pyodide = await dependencies.loadPyodide(config.indexURL);
  if (config.packages.length) await pyodide.loadPackage(config.packages);
  const sitePackages = String(pyodide.runPython("import site; site.getsitepackages()[0]"));
  const wheels = new Set(config.wheels.map(file => file.file));
  pyodide.FS.mkdirTree(FONT_DIR);
  for (const {file, bytes} of verified) {
    if (wheels.has(file.file)) pyodide.unpackArchive(bytes, "wheel", {extractDir: sitePackages});
    else pyodide.FS.writeFile(`${FONT_DIR}/${file.file}`, bytes);
  }
  await pyodide.runPythonAsync(GLUE);
  const boot = pyodide.globals.get("_cytellect_boot") as (seed: Uint8Array, origin: string) => Promise<void>;
  const handle = pyodide.globals.get("_cytellect_handle") as (method: string, url: string, headers: HeaderList, body: Uint8Array | null) => Promise<{status: number; headers: HeaderList; body: Uint8Array}>;
  await boot(seed, origin);
  return {
    async handle(request) {
      const result = await handle(request.method, request.url, request.headers, request.body ? new Uint8Array(request.body) : null);
      const body = result.body.slice().buffer as ArrayBuffer;
      return {status: result.status, headers: result.headers.map(([name, value]) => [name, value]), body};
    },
  };
}

const toBase64 = (buffer: ArrayBuffer) => {let text = ""; for (const value of new Uint8Array(buffer)) text += String.fromCharCode(value); return btoa(text);};
const fromBase64 = (text: string) => Uint8Array.from(atob(text), character => character.charCodeAt(0)).buffer as ArrayBuffer;

/**
 * Development only: forward to `scripts/dev_showcase_backend.py`, which serves the
 * same boot/handle contract from a local CPython API. Never configured in a public build.
 */
export async function bootDevelopmentRuntime(devBackend: string, origin: string, fetcher: typeof fetch = fetch): Promise<RuntimeHandle> {
  const booted = await fetcher(`${devBackend}/boot`, {method: "POST", body: JSON.stringify({origin})});
  if (!booted.ok) throw new Error("showcase_engine_unavailable");
  return {
    async handle(request) {
      const response = await fetcher(`${devBackend}/handle`, {method: "POST", body: JSON.stringify({
        method: request.method, url: request.url, headers: request.headers, body: request.body ? toBase64(request.body) : null,
      })});
      if (!response.ok) throw new Error("showcase_engine_unavailable");
      const value = await response.json() as {status: number; headers: HeaderList; body: string};
      return {status: value.status, headers: value.headers, body: fromBase64(value.body)};
    },
  };
}
