import { describe, expect, it } from "vitest";
import { windowsReleaseUrl, resolveWindowsReleaseUrl, PUBLISHED_RELEASE } from "./release";
const asset="https://github.com/genellect/cytellect/releases/download/test-fixture/Cytellect-test-fixture-windows-x64.zip";
describe("explicit public Windows release configuration",()=>{
 it("keeps local and configured-API workspaces unchanged",()=>{
  expect(windowsReleaseUrl(asset,true,false)).toBe("");
  expect(windowsReleaseUrl(asset,false,true)).toBe("");
 });
 it("requires an explicitly configured versioned asset in this repository",()=>{
  expect(windowsReleaseUrl(undefined,false,false)).toBe("");
  expect(windowsReleaseUrl(asset,false,false)).toBe(asset);
  for(const value of ["javascript:alert(1)",asset.replace("https:","http:"),asset.replace("github.com","example.com"),asset.replace("genellect/cytellect","other/repo"),asset.replace("download/test-fixture/","latest/download/"),asset+"?token=secret",asset+"#download"]){
   expect(windowsReleaseUrl(value,false,false)).toBe("");
  }
 });
});

describe("published release fallback",()=>{
 it("uses verified metadata only when the environment override is undefined",()=>{
  expect(PUBLISHED_RELEASE).not.toBeNull();
  expect(resolveWindowsReleaseUrl(undefined,false,false)).toBe(PUBLISHED_RELEASE?.url);
  expect(resolveWindowsReleaseUrl("",false,false)).toBe("");
  expect(resolveWindowsReleaseUrl("https://example.com/unpublished.zip",false,false)).toBe("");
  expect(resolveWindowsReleaseUrl(asset,false,false)).toBe(asset);
 });
 it("never enables downloads in local or API-configured mode",()=>{
  expect(resolveWindowsReleaseUrl(undefined,true,false)).toBe("");
  expect(resolveWindowsReleaseUrl(undefined,false,true)).toBe("");
 });
});
