import type { Metadata } from "next";
import PublicLanding from "@/components/PublicLanding";
import WorkspacePrototype from "@/components/workspace/WorkspacePrototype";
import { LOCAL_MODE, LOOPBACK_API } from "@/lib/api";

// Installations on the user's own computer open their workspace at the root.
const OWN_COMPUTER = LOCAL_MODE || LOOPBACK_API;

export const metadata: Metadata = OWN_COMPUTER
  ? { title: "画像解析 | Cytellect", robots: { index: false, follow: false } }
  : {
      metadataBase: new URL("https://cytellect.vercel.app"),
      title: "Cytellect — Get your microscopy publication-ready.",
      description: "画像をアップロードするだけで、論文の図まで。核と核小体の検出、測定、統計、作図をひとつのワークスペースで。解析は研究室のPCの中で行うオープンソースソフトウェアです。",
      openGraph: { title: "Cytellect — Get your microscopy publication-ready.", description: "画像をアップロードするだけで、論文の図まで。顕微鏡画像の解析から統計、論文用の図まで。", type: "website", locale: "ja_JP", images: [{ url: "/marketing/workspace-public.png", width: 1520, height: 744, alt: "Cytellectの解析画面" }] },
      robots: { index: true, follow: true },
    };

/** The public site opens on the landing page and the analysis screen lives at /workspace.
 *  The Windows launcher and the Docker Desktop script open the root, so those installations
 *  (local mode or an analysis API on this computer) show their workspace directly. */
export default function Page() {
  return OWN_COMPUTER ? <WorkspacePrototype /> : <PublicLanding />;
}
