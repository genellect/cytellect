import type { Metadata } from "next";
import { LOCAL_MODE, LOOPBACK_API, PUBLIC_SHOWCASE } from "./api";

/** Installations on the user's own computer: never offered to search engines. */
export const OWN_COMPUTER = LOCAL_MODE || LOOPBACK_API;

// The public origin for robots.txt, the sitemap and canonical links. CYTELLECT_SITE_URL overrides;
// Vercel builds use the project's production domain. Only a bare https origin is accepted.
export function siteUrl(explicit: string | undefined, vercelProduction: string | undefined, ownComputer: boolean): string {
 if(ownComputer) return "";
 const value=explicit || (vercelProduction ? `https://${vercelProduction}` : "");
 try {
  const url=new URL(value);
  return url.protocol==="https:" && !url.username && !url.password && url.pathname==="/" && !url.search && !url.hash ? url.origin : "";
 } catch { return ""; }
}
export const SITE_URL=siteUrl(process.env.CYTELLECT_SITE_URL,process.env.VERCEL_PROJECT_PRODUCTION_URL,OWN_COMPUTER);

/** Pages offered to search engines; every other page is noindex (app/layout.tsx). */
export function indexedPaths(showcase: boolean): string[] {
 return ["/", ...(showcase ? ["/demo"] : [])];
}
export const INDEXED_PATHS=SITE_URL ? indexedPaths(PUBLIC_SHOWCASE) : [];

// Search Console and Bing Webmaster Tools ownership tokens. They are public by design (served in
// the page), set on the hosting project rather than in the repository so they follow its owner.
const TOKEN=/^[A-Za-z0-9_-]{8,128}$/;
export function siteVerification(google: string | undefined, bing: string | undefined, ownComputer: boolean): Metadata["verification"] {
 if(ownComputer) return undefined;
 const g=google && TOKEN.test(google) ? google : "", b=bing && TOKEN.test(bing) ? bing : "";
 if(!g && !b) return undefined;
 return {...(g ? {google:g} : {}), ...(b ? {other:{"msvalidate.01":b}} : {})};
}
export const SITE_VERIFICATION=siteVerification(process.env.CYTELLECT_GOOGLE_SITE_VERIFICATION,process.env.CYTELLECT_BING_SITE_VERIFICATION,OWN_COMPUTER);
