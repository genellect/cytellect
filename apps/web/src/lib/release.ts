import { API_CONFIGURED, LOCAL_MODE } from "./api";
import published from "./published-release.json";

// Published metadata is updated only after checking the actual public asset and checksum.
// No /latest redirects, background probes, or local-service discovery.
export function windowsReleaseUrl(value: string | undefined, local: boolean, apiConfigured: boolean): string {
 if(local || apiConfigured || !value) return "";
 try {
  const url=new URL(value);
  return url.protocol==="https:" && url.hostname==="github.com" && !url.username && !url.password && !url.port && !url.search && !url.hash &&
   /^\/genellect\/cytellect\/releases\/download\/[^/]+\/Cytellect-[^/]+-windows-x64\.zip$/.test(url.pathname) ? url.href : "";
 } catch { return ""; }
}
const expectedAsset=`https://github.com/genellect/cytellect/releases/download/v${published.version}/Cytellect-${published.version}-windows-x64.zip`;
export const PUBLISHED_RELEASE=windowsReleaseUrl(published.url,false,false)===expectedAsset &&
 /^[a-f0-9]{64}$/.test(published.sha256) && /^[a-f0-9]{40}$/.test(published.source_commit) &&
 Number.isSafeInteger(published.size_bytes) && published.size_bytes>0 ? published : null;
export function resolveWindowsReleaseUrl(override:string|undefined,local:boolean,apiConfigured:boolean):string {
 // An explicit empty override disables downloads; invalid overrides never fall back.
 return windowsReleaseUrl(override===undefined?PUBLISHED_RELEASE?.url:override,local,apiConfigured);
}
export const WINDOWS_RELEASE_URL=resolveWindowsReleaseUrl(process.env.NEXT_PUBLIC_WINDOWS_RELEASE_URL,LOCAL_MODE,API_CONFIGURED);
