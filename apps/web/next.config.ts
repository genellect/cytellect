import { readFileSync } from "node:fs";
import type { NextConfig } from "next";
const development = process.env.NODE_ENV === "development";
const local = process.env.CYTELLECT_WEB_MODE === "local";
const api = local ? "" : process.env.NEXT_PUBLIC_API_ORIGIN || (development ? "http://localhost:8000" : "");
/** The public build without an API hosts the serverless demo (docs/showcase.md). */
const showcase = !local && !api;
function originOf(value: string, protocols: string[]) {
  try { const url = new URL(value); return protocols.includes(url.protocol) ? url.origin : ""; } catch { return ""; }
}
// Pyodide and its bundled packages come from the version-pinned CDN recorded by the runtime build.
const runtimeCdn = showcase ? originOf((JSON.parse(readFileSync(new URL("./src/lib/showcase/runtime-config.json", import.meta.url), "utf8")) as { indexURL?: string }).indexURL || "", ["https:"]) : "";
// Development-only loopback forwarder (scripts/dev_showcase_backend.py); never set for a published build.
const devShowcase = showcase ? originOf(process.env.NEXT_PUBLIC_SHOWCASE_DEV_BACKEND || "", ["http:"]) : "";
const scriptSources = ["'self'", "'unsafe-inline'", ...(development ? ["'unsafe-eval'"] : []), ...(showcase ? ["'wasm-unsafe-eval'"] : []), ...(runtimeCdn ? [runtimeCdn] : [])].join(" ");
const connectSources = ["'self'", ...(api ? [api] : []), ...(runtimeCdn ? [runtimeCdn] : []), ...(devShowcase ? [devShowcase] : []), ...(development ? ["ws://localhost:*", "ws://127.0.0.1:*"] : [])].join(" ");
const config: NextConfig = {
  ...(process.env.CYTELLECT_NEXT_DIST_DIR ? {distDir: process.env.CYTELLECT_NEXT_DIST_DIR} : {}),
  output: local ? "export" : "standalone",
  trailingSlash: local,
  env: { NEXT_PUBLIC_CYTELLECT_WEB_MODE: local ? "local" : "web" },
  agentRules: false,
  poweredByHeader: false,
  ...(!local ? {
    // One canonical landing page; earlier /product links keep working.
    // Without an analysis API the analysis screen is the public demo.
    async redirects() { return [{ source: "/product", destination: "/", permanent: true }, ...(showcase ? [{ source: "/workspace", destination: "/demo", permanent: false }] : [])]; },
    async headers() {
      return [{ source: "/:path*", headers: [
        { key: "Cache-Control", value: "no-store, max-age=0" },
        { key: "Referrer-Policy", value: "no-referrer" },
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "X-Frame-Options", value: "DENY" },
        { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        { key: "Content-Security-Policy", value: `default-src 'self'; script-src ${scriptSources}; style-src 'self' 'unsafe-inline'; connect-src ${connectSources}; img-src 'self' blob: data:; font-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'${showcase ? "; worker-src 'self' blob:" : ""}` },
      ] }, ...(showcase ? [
        // Public demo files only. Runtime files are content-addressed by runtime-config.json (SHA-256);
        // the seed and recordings are revalidated so a new demo build is picked up at once.
        { source: "/showcase/runtime/:path*", headers: [{ key: "Cache-Control", value: "public, max-age=31536000, immutable" }] },
        { source: "/showcase/:file(seed\\.zip|manifest\\.json)", headers: [{ key: "Cache-Control", value: "public, max-age=0, must-revalidate" }] },
        { source: "/showcase/snapshot/:path*", headers: [{ key: "Cache-Control", value: "public, max-age=0, must-revalidate" }] },
      ] : []), {
        source: "/lp-metrics.html", headers: [
          { key: "X-Frame-Options", value: "SAMEORIGIN" },
          { key: "Content-Security-Policy", value: "default-src 'none'; script-src 'self' https://www.googletagmanager.com; style-src 'self'; connect-src https://*.google-analytics.com https://www.googletagmanager.com; img-src https://*.google-analytics.com; frame-ancestors 'self'; base-uri 'none'; form-action 'none'" },
        ],
      }];
    },
  } : {}),
};
export default config;
