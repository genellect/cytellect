/** Evaluation-only authentication adapter. Production still requires a service key. */
import { ANTHROPIC_URL } from "./anthropic";
import type { Provider } from "./openai";

const DESTINATIONS: Record<Provider, { url: string; keyVariable: string; header: string }> = {
  openai: { url: "https://api.openai.com/v1/responses", keyVariable: "OPENAI_API_KEY", header: "authorization" },
  anthropic: { url: ANTHROPIC_URL, keyVariable: "ANTHROPIC_API_KEY", header: "x-api-key" },
};

/** `CYTELLECT_EVAL_PROVIDER` selects the provider ("openai" by default, or "anthropic"). */
export function evaluationAuth(env: Record<string, string | undefined>, transport: typeof fetch = fetch) {
  const provider = (env.CYTELLECT_EVAL_PROVIDER ?? "openai") as Provider;
  if (!Object.hasOwn(DESTINATIONS, provider)) throw new Error("evaluation_provider_unknown");
  const destination = DESTINATIONS[provider];
  const key = env[destination.keyVariable];
  if (env.CYTELLECT_EVAL_PROXY_AUTH !== "true") {
    if (!key) throw new Error("evaluation_private_key_required");
    return { apiKey: key, provider };
  }
  if (env.CLAUDE_CODE_REMOTE !== "true" || env.CYTELLECT_ALLOW_PAID_PUBLIC_EVAL !== "true"
    || (env.CI && env.CI !== "false") || key) {
    throw new Error("evaluation_proxy_auth_not_authorized");
  }
  // Remove the library's placeholder header. The environment proxy injects the
  // actual credential outside the VM. Do not depend on overwriting a dummy key.
  const fetcher: typeof fetch = async (input, init) => {
    if (input !== destination.url || init?.method !== "POST" || init.redirect !== "manual") {
      throw new Error("evaluation_proxy_destination_rejected");
    }
    const headers = new Headers(init.headers);
    headers.delete(destination.header);
    // This evaluation-only proxy runs in Node, whose native error mode is valid.
    // The shared edge adapter uses manual; neither path follows a redirect.
    return transport(input, { ...init, headers, redirect: "error" });
  };
  return { apiKey: "", provider, fetcher };
}
