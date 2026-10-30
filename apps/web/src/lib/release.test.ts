import { describe, expect, it } from "vitest";
import { windowsReleaseUrl, windowsReleaseAsset, resolveWindowsReleaseUrl, verifiedRelease, releaseSize, PUBLISHED_RELEASE } from "./release";
import published from "./published-release.json";
const asset="https://github.com/genellect/cytellect/releases/download/test-fixture/Cytellect-test-fixture-windows-x64.zip";
const installer="https://github.com/genellect/cytellect/releases/download/v0.1.0-local.99/Cytellect-Setup-0.1.0-local.99.exe";
/** Hosts, schemes, repositories, paths and decorations that only look like a release asset. */
function lookalikes(value:string):string[]{
 return [value.replace("https:","http:"),value.replace("github.com","example.com"),value.replace("github.com","github.com.evil.example"),
  value.replace("https://github.com","https://evil.example/https://github.com"),value.replace("https://","https://user:pass@"),value.replace("github.com","github.com:8443"),
  value.replace("genellect/cytellect","other/repo"),value.replace("genellect/cytellect","genellect/cytellect-fork"),value.replace("/releases/download/","/releases/latest/download/"),
  value.replace("/releases/download/","/blob/main/"),value.replace("/releases/download/","/releases/download/x/"),value+"?token=secret",value+"#download",value+"/"];
}
describe("explicit public Windows release configuration",()=>{
 it("keeps local and configured-API workspaces unchanged",()=>{
  expect(windowsReleaseUrl(asset,true,false)).toBe("");
  expect(windowsReleaseUrl(asset,false,true)).toBe("");
  expect(windowsReleaseUrl(installer,true,false)).toBe("");
  expect(windowsReleaseUrl(installer,false,true)).toBe("");
 });
 it("requires an explicitly configured versioned asset in this repository",()=>{
  expect(windowsReleaseUrl(undefined,false,false)).toBe("");
  expect(windowsReleaseUrl(asset,false,false)).toBe(asset);
  expect(windowsReleaseAsset(asset)).toBe("zip");
  for(const value of ["javascript:alert(1)",asset.replace("download/test-fixture/","latest/download/"),...lookalikes(asset)]){
   expect(windowsReleaseUrl(value,false,false)).toBe("");
   expect(windowsReleaseAsset(value)).toBeNull();
  }
 });
 it("accepts the per-user installer only from the tag of its own version",()=>{
  expect(windowsReleaseUrl(installer,false,false)).toBe(installer);
  expect(windowsReleaseAsset(installer)).toBe("installer");
  for(const value of [...lookalikes(installer),
   installer.replace("/v0.1.0-local.99/","/v0.1.0-local.98/"),installer.replace("/v0.1.0-local.99/","/0.1.0-local.99/"),
   installer.replace("Cytellect-Setup-0.1.0-local.99.exe","Cytellect-Setup.exe"),installer.replace(".exe",".exe.sha256"),installer.replace(".exe",".msi"),
   installer.replace("Cytellect-Setup-","cytellect-setup-"),installer.replace("Cytellect-Setup-0.1.0-local.99.exe","Cytellect-update-0.1.0-local.99.json"),
   "https://github.com/genellect/cytellect/releases/download/v..%2f/Cytellect-Setup-..%2f.exe"]){
   expect(windowsReleaseUrl(value,false,false)).toBe("");
   expect(windowsReleaseAsset(value)).toBeNull();
  }
 });
});

describe("published release metadata",()=>{
 const record={version:"0.1.0-local.99",asset:"installer",url:installer,sha256:"a".repeat(64),source_commit:"b".repeat(40),size_bytes:1_070_000_000};
 it("names its asset and is used only when the URL is exactly that asset of its version",()=>{
  expect(verifiedRelease(record)).toEqual(record);
  const zip={...record,asset:"zip",url:"https://github.com/genellect/cytellect/releases/download/v0.1.0-local.99/Cytellect-0.1.0-local.99-windows-x64.zip"};
  expect(verifiedRelease(zip)).toEqual(zip);
  for(const wrong of [{...record,asset:undefined},{...record,asset:"exe"},{...record,asset:"zip"},{...zip,asset:"installer"},
   {...record,version:"0.1.0-local.98"},{...record,url:asset},{...record,url:installer.replace("github.com","example.com")},
   {...record,sha256:"A".repeat(64)},{...record,sha256:"a".repeat(63)},{...record,source_commit:"b".repeat(39)},
   {...record,size_bytes:0},{...record,size_bytes:1.5},{...record,size_bytes:"1070000000"}]){
   expect(verifiedRelease(wrong)).toBeNull();
  }
 });
 it("records the asset the site currently offers",()=>{
  // local.20 has no installer; switch to "installer" only after the owner publishes one and it is checked.
  expect(PUBLISHED_RELEASE).toEqual(published);
  expect(windowsReleaseAsset(PUBLISHED_RELEASE?.url)).toBe(published.asset);
 });
 it("shows the download size in decimal units",()=>{
  expect(releaseSize(1_070_000_000)).toBe("1.07 GB");
  expect(releaseSize(10_204_099)).toBe("10 MB");
 });
});

describe("published release fallback",()=>{
 it("uses verified metadata only when the environment override is undefined",()=>{
  expect(PUBLISHED_RELEASE).not.toBeNull();
  expect(resolveWindowsReleaseUrl(undefined,false,false)).toBe(PUBLISHED_RELEASE?.url);
  expect(resolveWindowsReleaseUrl("",false,false)).toBe("");
  expect(resolveWindowsReleaseUrl("https://example.com/unpublished.zip",false,false)).toBe("");
  expect(resolveWindowsReleaseUrl("https://example.com/Cytellect-Setup-0.1.0-local.99.exe",false,false)).toBe("");
  expect(resolveWindowsReleaseUrl(asset,false,false)).toBe(asset);
  expect(resolveWindowsReleaseUrl(installer,false,false)).toBe(installer);
 });
 it("never enables downloads in local or API-configured mode",()=>{
  expect(resolveWindowsReleaseUrl(undefined,true,false)).toBe("");
  expect(resolveWindowsReleaseUrl(undefined,false,true)).toBe("");
 });
});
