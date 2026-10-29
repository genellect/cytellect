import type { Metadata } from "next";
import PublicLanding from "@/components/PublicLanding";
import WorkspaceScreen from "@/components/workspace/WorkspaceScreen";
import { OWN_COMPUTER, SITE_URL, SITE_VERIFICATION, sharePreview } from "@/lib/site";

// Search result and share text: the product subtitle and the landing page's own mission lines.
const TITLE = "Cytellect — 顕微鏡画像から論文の図までを一つにつなぐ、生命科学研究の解析基盤", DESCRIPTION = "画像解析を、一部の専門家の技術から、すべての生命科学研究者が使える研究基盤に。蛍光顕微鏡の画像をアップロードするだけで、画像解析・統計・論文用のグラフまで。";

export const metadata: Metadata = OWN_COMPUTER
  ? { title: "画像解析 | Cytellect", robots: { index: false, follow: false } }
  : { title: TITLE, description: DESCRIPTION, robots: { index: true, follow: true }, ...sharePreview(SITE_URL, "/", TITLE, DESCRIPTION),
      ...(SITE_URL ? { alternates: { canonical: `${SITE_URL}/` } } : {}), ...(SITE_VERIFICATION ? { verification: SITE_VERIFICATION } : {}) };

/** The public site opens on the landing page and the analysis screen lives at /workspace.
 *  The Windows launcher and the Docker Desktop script open the root, so those installations
 *  (local mode or an analysis API on this computer) show their workspace directly. */
export default function Page() {
  return OWN_COMPUTER ? <WorkspaceScreen /> : <PublicLanding />;
}
