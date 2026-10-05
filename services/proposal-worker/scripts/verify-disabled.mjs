import { pathToFileURL } from "node:url";

/** Empty context is deliberately invalid even if an operator enabled the service.
 * This probe cannot reach the model or consume a usage reservation. */
export async function verifyDisabled(target, deviceToken, fetcher = fetch) {
  const url = new URL(target);
  if (url.protocol !== "https:" || url.username || url.password || url.search || url.hash || url.pathname !== "/") {
    throw new Error("Use an HTTPS origin without credentials, query or path.");
  }
  const options = { method: "POST", redirect: "error", signal: AbortSignal.timeout(10_000),
    headers: { "content-type": "application/json" }, body: "{}" };
  const denied = await fetcher(new URL("/v1/proposals", url), options);
  if (denied.status !== 401 || denied.headers.get("cache-control") !== "no-store") throw new Error("Unauthenticated access check failed.");
  await denied.body?.cancel();
  if (!/^[A-Za-z0-9_-]{20,200}$/.test(deviceToken ?? "")) throw new Error("A valid device token is required to verify disabled status.");
  const response = await fetcher(new URL("/v1/proposals", url), { ...options, signal: AbortSignal.timeout(10_000),
    headers: { ...options.headers, authorization: `Bearer ${deviceToken}` } });
  const status = response.status;
  const noStore = response.headers.get("cache-control") === "no-store";
  await response.body?.cancel();
  if (status !== 503 || !noStore) throw new Error(`Disabled status check failed (HTTP ${status}). No valid analysis request was sent.`);
  return { unauthenticated: 401, authenticated: 503, cache: "no-store", provider_calls: 0 };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    console.info(JSON.stringify(await verifyDisabled(process.argv[2], process.env.CYTELLECT_PROPOSAL_TOKEN)));
  } catch {
    // Network/provider errors may contain private headers. Keep CLI failure fixed.
    console.error("Disabled deployment verification failed; check URL, device authorization and configuration. No analysis context was submitted.");
    process.exitCode = 1;
  }
}
