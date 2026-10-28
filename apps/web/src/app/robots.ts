import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/site";

// Pages kept out of search carry their own noindex, which crawlers must be allowed to read,
// so the public site disallows nothing. Builds without a public origin disallow everything.
export default function robots(): MetadataRoute.Robots {
  return SITE_URL
    ? { rules: { userAgent: "*", allow: "/" }, sitemap: `${SITE_URL}/sitemap.xml` }
    : { rules: { userAgent: "*", disallow: "/" } };
}
