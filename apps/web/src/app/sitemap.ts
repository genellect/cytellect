import type { MetadataRoute } from "next";
import { INDEXED_PATHS, SITE_URL } from "@/lib/site";

export const dynamic = "force-static";

export default function sitemap(): MetadataRoute.Sitemap {
  return INDEXED_PATHS.map((path) => ({ url: `${SITE_URL}${path}` }));
}
