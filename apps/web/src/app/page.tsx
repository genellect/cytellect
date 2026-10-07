import type { Metadata } from "next";
import PublicLanding from "@/components/PublicLanding";
import WorkspacePrototype from "@/components/workspace/WorkspacePrototype";
import { LOCAL_MODE, LOOPBACK_API } from "@/lib/api";

// Installations on the user's own computer open their workspace at the root.
const OWN_COMPUTER = LOCAL_MODE || LOOPBACK_API;

export const metadata: Metadata = OWN_COMPUTER
  ? { title: "画像解析 | Cytellect", robots: { index: false, follow: false } }
  : { title: "Cytellect — Get your microscopy publication-ready.", description: "顕微鏡画像の解析から統計、論文用グラフの作成まで。", robots: { index: true, follow: true } };

/** The public site opens on the landing page and the analysis screen lives at /workspace.
 *  The Windows launcher and the Docker Desktop script open the root, so those installations
 *  (local mode or an analysis API on this computer) show their workspace directly. */
export default function Page() {
  return OWN_COMPUTER ? <WorkspacePrototype /> : <PublicLanding />;
}
