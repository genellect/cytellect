import type { Metadata } from "next";
import PublicLanding from "@/components/PublicLanding";
import WorkspaceScreen from "@/components/workspace/WorkspaceScreen";
import { OWN_COMPUTER, SITE_URL, SITE_VERIFICATION, sharePreview } from "@/lib/site";

const TITLE = "Cytellect — Get your microscopy publication-ready.", DESCRIPTION = "顕微鏡画像の解析から統計、論文用グラフの作成まで。";

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
