import { afterEach,describe,expect,it,vi } from "vitest";
import {readFileSync} from "node:fs";
import { ApiError,errorCodeMessage,post,request } from "./api";
afterEach(()=>vi.unstubAllGlobals());
describe("private API transport",()=>{
 it("uses credentials/no-store/CSRF without persisting data",async()=>{
  const fetch=vi.fn().mockResolvedValue(new Response(JSON.stringify({ok:true}),{status:200}));vi.stubGlobal("fetch",fetch);
  expect(await post("/v1/workspaces",{title:"synthetic"})).toEqual({ok:true});
  const [,options]=fetch.mock.calls[0];expect(options.credentials).toBe("include");expect(options.cache).toBe("no-store");expect(options.headers.get("X-Cytellect-Request")).toBe("1");
 });
 it("retains multipart boundaries and returns safe coded failures",async()=>{
  const fetch=vi.fn().mockResolvedValue(new Response(JSON.stringify({detail:"session_required"}),{status:401}));vi.stubGlobal("fetch",fetch);
  await expect(request("/v1/fields",{method:"POST",body:new FormData()})).rejects.toEqual(new ApiError("session_required",401));
  expect(fetch.mock.calls[0][1].headers.has("Content-Type")).toBe(false);
 });
});

it("has a readable message for every proposal/discussion service failure (LP-04)",()=>{
 const source=(path:string)=>readFileSync(new URL(`../../../../${path}`,import.meta.url),"utf8");
 const proposals=source("services/api/src/cytellect_api/proposals.py");
 const discussions=source("services/api/src/cytellect_api/discussions.py");
 const handler=proposals.slice(proposals.indexOf("def post_to_service("),proposals.indexOf("class ProposalDraftRequest"));
 const codes=new Set([...handler.matchAll(/["'](proposal_[a-z_]+)["']/g)].map(match=>match[1]).filter(code=>!code.endsWith("_")));
 for(const apiSource of [proposals,discussions])for(const match of apiSource.matchAll(/(?:HTTPException|ProposalServiceError)\(\s*[^,\n]+,\s*["']((?:proposal|discussion)_[a-z_]+)["']/g))codes.add(match[1]);
 for(const match of handler.matchAll(/["'](model_[a-z_]+)["']/g))codes.add(`proposal_${match[1]}`);
 const providers=proposals.match(/PROVIDER_ERROR_CODES = frozenset\(\{([\s\S]*?)\}\)/)?.[1]||"";
 for(const match of providers.matchAll(/["']([a-z_]+)["']/g))codes.add(`proposal_provider_${match[1]}`);
 expect(codes.size).toBeGreaterThan(20);
 expect([...codes].filter(code=>errorCodeMessage(code)===code)).toEqual([]);
 for(const code of codes)expect(errorCodeMessage(code),code).not.toMatch(/OpenAI|Anthropic/);
 expect(errorCodeMessage("proposal_provider_http_503")).not.toContain("OpenAI");
});
