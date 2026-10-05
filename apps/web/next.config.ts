import type { NextConfig } from "next";
const development = process.env.NODE_ENV === "development";
const local = process.env.CYTELLECT_WEB_MODE === "local";
const api = local ? "" : process.env.NEXT_PUBLIC_API_ORIGIN || (development ? "http://localhost:8000" : "");
const config: NextConfig = {
  output: local ? "export" : "standalone",
  trailingSlash: local,
  env: { NEXT_PUBLIC_CYTELLECT_WEB_MODE: local ? "local" : "web" },
  agentRules: false,
  poweredByHeader: false,
  ...(!local ? {
    async headers() {
      return [{ source: "/:path*", headers: [
        { key: "Cache-Control", value: "no-store, max-age=0" },
        { key: "Referrer-Policy", value: "no-referrer" },
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "X-Frame-Options", value: "DENY" },
        { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        { key: "Content-Security-Policy", value: `default-src 'self'; script-src 'self' 'unsafe-inline'${development ? " 'unsafe-eval'" : ""}; style-src 'self' 'unsafe-inline'; connect-src 'self' ${api}${development ? " ws://localhost:* ws://127.0.0.1:*" : ""}; img-src 'self' blob: data:; font-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'` },
      ] }, {
        source: "/lp-metrics.html", headers: [
          { key: "X-Frame-Options", value: "SAMEORIGIN" },
          { key: "Content-Security-Policy", value: "default-src 'none'; script-src 'self' https://www.googletagmanager.com; style-src 'self'; connect-src https://*.google-analytics.com https://www.googletagmanager.com; img-src https://*.google-analytics.com; frame-ancestors 'self'; base-uri 'none'; form-action 'none'" },
        ],
      }];
    },
  } : {}),
};
export default config;
