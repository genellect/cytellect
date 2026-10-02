import { afterEach, describe, expect, it, vi } from "vitest";
afterEach(()=>{vi.unstubAllGlobals();vi.unstubAllEnvs();vi.resetModules();});
describe("packaged local API boundary",()=>{
 it("uses same-origin paths and a protected POST on loopback",async()=>{
  vi.stubEnv("NEXT_PUBLIC_CYTELLECT_WEB_MODE","local");
  vi.stubGlobal("window",{location:{hostname:"127.0.0.1"}});
  const fetch=vi.fn().mockResolvedValue(new Response(JSON.stringify({authenticated:true}),{status:200}));vi.stubGlobal("fetch",fetch);
  const api=await import("./api");
  expect(api.API_CONFIGURED).toBe(true);expect(api.API).toBe("");
  await api.post("/v1/local/session");
  expect(fetch.mock.calls[0][0]).toBe("/v1/local/session");
  expect(fetch.mock.calls[0][1].credentials).toBe("include");
  expect(fetch.mock.calls[0][1].headers.get("X-Cytellect-Request")).toBe("1");
 });
 it("never sends local-build requests from an external host",async()=>{
  vi.stubEnv("NEXT_PUBLIC_CYTELLECT_WEB_MODE","local");
  vi.stubGlobal("window",{location:{hostname:"example.com"}});
  const fetch=vi.fn();vi.stubGlobal("fetch",fetch);
  const api=await import("./api");
  await expect(api.request("/v1/local/setup")).rejects.toMatchObject({code:"local_host_required"});
  await expect(api.fetchBlob("/v1/fields/test/preview")).rejects.toMatchObject({code:"local_host_required"});
  expect(fetch).not.toHaveBeenCalled();
 });
 it("leaves an unconfigured public production build disconnected",async()=>{
  vi.stubEnv("NEXT_PUBLIC_CYTELLECT_WEB_MODE","web");vi.stubEnv("NODE_ENV","production");vi.stubEnv("NEXT_PUBLIC_API_ORIGIN","");
  const fetch=vi.fn();vi.stubGlobal("fetch",fetch);
  const api=await import("./api");
  expect(api.API_CONFIGURED).toBe(false);
  await expect(api.request("/v1/local/setup")).rejects.toMatchObject({code:"server_not_configured"});
  expect(fetch).not.toHaveBeenCalled();
 });
});

