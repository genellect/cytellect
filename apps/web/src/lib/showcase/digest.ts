/** SHA-256 verification of downloaded runtime files before they are installed. */
export async function sha256Hex(data: ArrayBuffer | Uint8Array): Promise<string> {
  const bytes = data instanceof Uint8Array ? data : new Uint8Array(data);
  const digest = await crypto.subtle.digest("SHA-256", bytes as Uint8Array<ArrayBuffer>);
  return Array.from(new Uint8Array(digest), value => value.toString(16).padStart(2, "0")).join("");
}

export class IntegrityError extends Error {
  constructor(public file: string) { super("showcase_integrity_failed"); }
}

/** Fetch a file and return its bytes only when they match the recorded digest. */
export async function fetchVerified(url: string, expected: string, fetcher: typeof fetch = fetch): Promise<Uint8Array> {
  if (!/^[a-f0-9]{64}$/.test(expected)) throw new IntegrityError(url);
  const response = await fetcher(url);
  if (!response.ok) throw new Error("showcase_runtime_missing");
  const bytes = new Uint8Array(await response.arrayBuffer());
  if (await sha256Hex(bytes) !== expected) throw new IntegrityError(url);
  return bytes;
}
