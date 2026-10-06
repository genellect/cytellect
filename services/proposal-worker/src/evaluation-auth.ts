/** Evaluation-only authentication adapter. Production still requires a service key. */
export function evaluationAuth(env: Record<string, string | undefined>, transport: typeof fetch = fetch) {
  if (env.CYTELLECT_EVAL_PROXY_AUTH !== "true") {
    if (!env.OPENAI_API_KEY) throw new Error("evaluation_private_key_required");
    return { apiKey: env.OPENAI_API_KEY };
  }
  if (env.CLAUDE_CODE_REMOTE !== "true" || env.CYTELLECT_ALLOW_PAID_PUBLIC_EVAL !== "true"
    || (env.CI && env.CI !== "false") || env.OPENAI_API_KEY) {
    throw new Error("evaluation_proxy_auth_not_authorized");
  }
  // Remove the library's placeholder header. The environment proxy injects the
  // actual credential outside the VM. Do not depend on overwriting a dummy key.
  const fetcher: typeof fetch = async (input, init) => {
    if (input !== "https://api.openai.com/v1/responses" || init?.method !== "POST" || init.redirect !== "manual") {
      throw new Error("evaluation_proxy_destination_rejected");
    }
    const headers = new Headers(init.headers);
    headers.delete("authorization");
    // This evaluation-only proxy runs in Node, whose native error mode is valid.
    // The shared edge adapter uses manual; neither path follows a redirect.
    return transport(input, { ...init, headers, redirect: "error" });
  };
  return { apiKey: "", fetcher };
}
