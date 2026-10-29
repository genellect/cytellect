import type {Metadata} from "next";
import {notFound} from "next/navigation";
import ConnectedWorkspace from "@/components/workspace/review/ConnectedWorkspace";
import {LandingAnalytics} from "@/components/LandingAnalytics";
import {PUBLIC_SHOWCASE} from "@/lib/api";
import {SITE_URL, sharePreview} from "@/lib/site";

const TITLE = "公開デモ | Cytellect", DESCRIPTION = "公開顕微鏡画像の検出・測定・統計・グラフ作成を、本番と同じ解析画面で試せます。";

export const metadata: Metadata = {
  title: TITLE,
  description: DESCRIPTION,
  robots: {index: true, follow: true},
  ...(SITE_URL ? {alternates: {canonical: `${SITE_URL}/demo`}} : {}),
  ...sharePreview(SITE_URL, "/demo", TITLE, DESCRIPTION),
};

/** The public site's demo: the production workspace on the serverless transport (docs/showcase.md).
 *  Builds with an analysis API, the local package and Docker installations have no public demo. */
export default function DemoPage() {
  if (!PUBLIC_SHOWCASE) notFound();
  return <div data-cytellect-public-page="/demo" style={{display: "contents"}}><LandingAnalytics page="/demo"/><ConnectedWorkspace showcase/></div>;
}
