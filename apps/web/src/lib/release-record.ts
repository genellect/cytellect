export type WindowsAsset="installer"|"zip";
const ASSET_PATH:Record<WindowsAsset,RegExp>={
 // The installer is accepted only from the tag of its own version: v<version>/Cytellect-Setup-<version>.exe.
 installer:/^\/genellect\/cytellect\/releases\/download\/v([0-9A-Za-z][0-9A-Za-z.-]*)\/Cytellect-Setup-\1\.exe$/,
 zip:/^\/genellect\/cytellect\/releases\/download\/[^/]+\/Cytellect-[^/]+-windows-x64\.zip$/,
};
/** Which Windows asset an accepted download URL points at; null for anything else. */
export function windowsReleaseAsset(value:string|undefined):WindowsAsset|null {
 if(!value) return null;
 try {
  const url=new URL(value);
  if(url.protocol!=="https:" || url.hostname!=="github.com" || url.username || url.password || url.port || url.search || url.hash) return null;
  return ASSET_PATH.installer.test(url.pathname)?"installer":ASSET_PATH.zip.test(url.pathname)?"zip":null;
 } catch { return null; }
}
export function windowsReleaseUrl(value: string | undefined, local: boolean, apiConfigured: boolean): string {
 if(local || apiConfigured || !value || !windowsReleaseAsset(value)) return "";
 return new URL(value).href;
}
export function windowsAssetUrl(version:string,asset:WindowsAsset):string {
 const file=asset==="installer"?`Cytellect-Setup-${version}.exe`:`Cytellect-${version}-windows-x64.zip`;
 return `https://github.com/genellect/cytellect/releases/download/v${version}/${file}`;
}
export type PublishedRelease={version:string;asset:WindowsAsset;url:string;sha256:string;source_commit:string;size_bytes:number};
/** A record is used only when it names its asset and its URL is exactly that asset of its version. */
export function verifiedRelease(record:Partial<Record<keyof PublishedRelease,unknown>>):PublishedRelease|null {
 const {version,asset,url,sha256,source_commit,size_bytes}=record;
 if(typeof version!=="string" || !/^[0-9A-Za-z][0-9A-Za-z.-]*$/.test(version) || (asset!=="installer" && asset!=="zip") || typeof url!=="string") return null;
 return windowsReleaseUrl(url,false,false)===windowsAssetUrl(version,asset) &&
  typeof sha256==="string" && /^[a-f0-9]{64}$/.test(sha256) && typeof source_commit==="string" && /^[a-f0-9]{40}$/.test(source_commit) &&
  typeof size_bytes==="number" && Number.isSafeInteger(size_bytes) && size_bytes>0 ? {version,asset,url,sha256,source_commit,size_bytes} : null;
}
