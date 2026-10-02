import { afterEach,describe,expect,it,vi } from "vitest";
import { ApiError,post,request } from "./api";
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
