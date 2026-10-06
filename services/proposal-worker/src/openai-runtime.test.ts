/** Real workerd fetch semantics, with every outbound request handled locally. */
import {expect, it} from "vitest";

const moduleName = "node:module", urlName = "node:url", fsName = "node:fs";

it.each([200, 302, 307])("workerd handles provider HTTP %i without following redirects", async status => {
  const {createRequire} = await import(moduleName);
  const {pathToFileURL} = await import(urlName);
  const {readFileSync} = await import(fsName);
  const require = createRequire(import.meta.url);
  const paths = [require.resolve("wrangler")];
  // Reuse the pinned Wrangler dependencies; no additional downloads/dependencies.
  const {Miniflare, convertV4MiniflareOptions} = await import(pathToFileURL(require.resolve("miniflare", {paths})).href);
  const {transform} = await import(pathToFileURL(require.resolve("esbuild", {paths})).href);
  // Compile the actual closed adapter dependencies in memory; no filesystem
  // bundler discovery or credential/config loading is needed by the runtime test.
  const adapter = readFileSync(new URL("./openai.ts", import.meta.url), "utf8")
    .replace('import contract from "./contract.json";', "")
    .replace('import { boundedJson, matchesSchema } from "./schema";', "");
  const schema = readFileSync(new URL("./schema.ts", import.meta.url), "utf8");
  const contract = readFileSync(new URL("./contract.json", import.meta.url), "utf8");
  const dependencyCode = `${schema}\n${adapter}`.replace(/^export /gm, "");
  const bundled = await transform(`const contract=${contract};\n${dependencyCode}\n
      export default {async fetch(){try{const result=await draftProposal({apiKey:"test-only",model:MODEL,maxOutputTokens:8000},{},[]);return Response.json({ok:true,calls:result.calls})}
      catch(error){return Response.json({ok:false,code:error.code,status:error.providerHttpStatus})}}};`, {loader: "ts", format: "esm", target: "es2023"});
  const seen: Array<{url: string; authorized: boolean}> = [];
  const draft = {recipe: "nuclear-intensity", channels: [{token: "dapi", stain: "DAPI", role: "nuclear", reason: "Nuclear stain"}],
    metrics: [{metric: "area", channel: null, region: "nucleus"}],
    statistics: {kind: "descriptive", test: null, omnibus: null, association: null, x: null, y: null}, additional_analyses: [],
    figures: [{kind: "field-distribution", metric: "area", channel: null, region: "nucleus", analysis_index: 0}],
    missing_information: [], reference_ids: ["senft-2023"], rationale: "Measure nuclear area."};
  const options = {modules: true,
    // The pinned local workerd supports this date; production date is unchanged.
    compatibilityDate: "2026-09-25", script: bundled.code,
    outboundService: async (request: Request) => {
      seen.push({url: request.url, authorized: request.headers.get("authorization") === "Bearer test-only"});
      if (status !== 200) return new Response(null, {status, headers: {location: "https://redirect.invalid/credential-sink"}});
      return Response.json({status: "completed", usage: {input_tokens: 1000, output_tokens: 200},
        output: [{type: "message", content: [{type: "output_text", text: JSON.stringify(draft)}]}]});
    },
  };
  const runtime = new Miniflare(convertV4MiniflareOptions(options));
  try {
    const response = await runtime.dispatchFetch("http://localhost/");
    expect(await response.json()).toEqual(status === 200 ? {ok: true, calls: 1} : {ok: false, code: "model_unavailable", status});
    expect(seen).toEqual([{url: "https://api.openai.com/v1/responses", authorized: true}]);
  } finally {await runtime.dispose();}
}, 30_000);
