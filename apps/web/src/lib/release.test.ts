import { describe, expect, it } from "vitest";
import { windowsReleaseUrl } from "./release";
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
