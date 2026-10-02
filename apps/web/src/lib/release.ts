import { API_CONFIGURED, LOCAL_MODE } from "./api";

// Set only after checking that the tagged release asset is public and downloadable.
// No default URL, redirects through /latest, background probes, or local-service discovery.
export function windowsReleaseUrl(value: string | undefined, local: boolean, apiConfigured: boolean): string {
 if(local || apiConfigured || !value) return "";
 try {
  const url=new URL(value);
  return url.protocol==="https:" && url.hostname==="github.com" && !url.username && !url.password && !url.port && !url.search && !url.hash &&
   /^\/genellect\/cytellect\/releases\/download\/[^/]+\/Cytellect-[^/]+-windows-x64\.zip$/.test(url.pathname) ? url.href : "";
 } catch { return ""; }
}
export const WINDOWS_RELEASE_URL=windowsReleaseUrl(process.env.NEXT_PUBLIC_WINDOWS_RELEASE_URL,LOCAL_MODE,API_CONFIGURED);
