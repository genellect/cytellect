import { API_CONFIGURED, LOCAL_MODE } from "./api";
import published from "./published-release.json";
import { verifiedRelease, windowsReleaseUrl } from "./release-record";

export { verifiedRelease, windowsAssetUrl, windowsReleaseAsset, windowsReleaseUrl } from "./release-record";
export type { PublishedRelease, WindowsAsset } from "./release-record";

// Published metadata is updated only after checking the actual public asset and checksum.
// From 0.1.0-local.21 a release carries the per-user installer Cytellect-Setup-<version>.exe;
// the record then names it with "asset": "installer". "zip" stays only for versions without an
// installer. This checked-in record is the fallback for the public release channel.
export const STORE_PRODUCT_URL = "https://apps.microsoft.com/detail/9PGKTQGV7X5C";
export const PUBLISHED_RELEASE=verifiedRelease(published);
/** Download size next to the button, in decimal units (1 GB = 10^9 bytes). */
export function releaseSize(bytes:number):string {
 return bytes>=1e9?`${(bytes/1e9).toFixed(2)} GB`:`${Math.round(bytes/1e6)} MB`;
}
export function resolveWindowsReleaseUrl(override:string|undefined,local:boolean,apiConfigured:boolean):string {
 // An explicit empty override disables downloads; invalid overrides never fall back.
 return windowsReleaseUrl(override===undefined?PUBLISHED_RELEASE?.url:override,local,apiConfigured);
}
export const WINDOWS_RELEASE_URL=resolveWindowsReleaseUrl(process.env.NEXT_PUBLIC_WINDOWS_RELEASE_URL,LOCAL_MODE,API_CONFIGURED);
