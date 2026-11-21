import { unstable_cache } from "next/cache";
import { PUBLISHED_RELEASE, WINDOWS_RELEASE_URL, verifiedRelease } from "./release";

const CHANNEL_URL = "https://raw.githubusercontent.com/genellect/cytellect/windows-exe-channel/windows-exe.json";

function versionNumber(version: string) {
  return Number(/^0\.1\.0-local\.([1-9]\d*)$/.exec(version)?.[1] ?? 0);
}

export function verifiedChannelRelease(value: unknown) {
  if (!value || typeof value !== "object") return null;
  const record = verifiedRelease(value);
  if (!record || record.asset !== "installer") return null;
  const number = versionNumber(record.version);
  return Number.isSafeInteger(number) && number > versionNumber(PUBLISHED_RELEASE?.version ?? "") ? record : null;
}

const readChannel = unstable_cache(async () => {
  const response = await fetch(CHANNEL_URL, { signal: AbortSignal.timeout(3000), redirect: "error" });
  if (!response.ok) throw new Error("Windows release channel is unavailable");
  const record = verifiedChannelRelease(await response.json());
  if (!record) throw new Error("Invalid Windows release channel metadata");
  return record;
}, ["windows-exe-channel-v1"], { revalidate: 60 });

export async function publicWindowsRelease() {
  const fallback = {
    url: WINDOWS_RELEASE_URL,
    release: PUBLISHED_RELEASE?.url === WINDOWS_RELEASE_URL ? PUBLISHED_RELEASE : null,
  };
  if (!WINDOWS_RELEASE_URL || process.env.NEXT_PUBLIC_WINDOWS_RELEASE_URL !== undefined ||
      process.env.VERCEL_ENV !== "production") return fallback;
  try {
    const release = await readChannel();
    return { url: release.url, release };
  } catch {
    return fallback;
  }
}
