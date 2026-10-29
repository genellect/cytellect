import { describe, expect, it } from "vitest";
import { indexedPaths, sharePreview, siteUrl, siteVerification } from "./site";

describe("public site origin",()=>{
 it("uses the Vercel production domain unless an origin is named",()=>{
  expect(siteUrl(undefined,"cytellect.vercel.app",false)).toBe("https://cytellect.vercel.app");
  expect(siteUrl("https://cytellect.example/","cytellect.vercel.app",false)).toBe("https://cytellect.example");
 });
 it("is empty on the user's own computer and for anything but a bare https origin",()=>{
  expect(siteUrl(undefined,"cytellect.vercel.app",true)).toBe("");
  expect(siteUrl(undefined,undefined,false)).toBe("");
  for(const value of ["http://cytellect.example","https://cytellect.example/lp","https://a:b@cytellect.example","https://cytellect.example/?x=1","not a url"])
   expect(siteUrl(value,undefined,false)).toBe("");
 });
 it("offers the demo only on the public demo build",()=>{
  expect(indexedPaths(true)).toEqual(["/","/demo"]);
  expect(indexedPaths(false)).toEqual(["/"]);
 });
});

describe("search engine ownership tokens",()=>{
 it("emits the Google and Bing tags that are set",()=>{
  expect(siteVerification("google_site_token","bing-site-token",false)).toEqual({google:"google_site_token",other:{"msvalidate.01":"bing-site-token"}});
  expect(siteVerification(undefined,"bing-site-token",false)).toEqual({other:{"msvalidate.01":"bing-site-token"}});
 });
 it("emits nothing locally, when unset, or for malformed values",()=>{
  expect(siteVerification("google_site_token",undefined,true)).toBeUndefined();
  expect(siteVerification(undefined,undefined,false)).toBeUndefined();
  expect(siteVerification('x" onload="y',"short",false)).toBeUndefined();
 });
});

describe("share preview",()=>{
 it("points shared links at the public origin and the registered hero poster",()=>{
  const preview=sharePreview("https://cytellect.app","/demo","T","D");
  expect(preview.openGraph).toMatchObject({url:"https://cytellect.app/demo",siteName:"Cytellect",locale:"ja_JP",title:"T",description:"D"});
  expect(preview.twitter).toMatchObject({card:"summary_large_image",images:["https://cytellect.app/marketing/hero-film-poster.webp"]});
 });
 it("is absent on the user's own computer",()=>{
  expect(sharePreview("","/","T","D")).toEqual({});
 });
});
