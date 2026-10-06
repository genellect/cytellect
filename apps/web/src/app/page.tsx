import type { Metadata } from "next";
import PublicLanding from "@/components/PublicLanding";
import WorkspacePrototype from "@/components/workspace/WorkspacePrototype";
import { LOCAL_MODE } from "@/lib/api";

export const metadata: Metadata = LOCAL_MODE
  ? { title: "画像解析 | Cytellect", robots: { index: false, follow: false } }
  : { title: "Cytellect — Get your microscopy publication-ready.", description: "顕微鏡画像の解析から統計、論文用グラフの作成まで。", robots: { index: true, follow: true } };

/** The public site opens on the landing page and the analysis screen lives at /workspace.
 *  The local package's launcher opens the root, so it shows its workspace directly. */
export default function Page() {
  return LOCAL_MODE ? <WorkspacePrototype /> : <PublicLanding />;
}
