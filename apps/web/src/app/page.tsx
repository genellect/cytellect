import type { Metadata } from "next";
import PublicLanding from "@/components/PublicLanding";
import WorkspaceEntry from "@/components/WorkspaceEntry";
import { API_CONFIGURED, LOCAL_MODE } from "@/lib/api";

export const metadata: Metadata = { title: "Cytellect — Get your microscopy publication-ready.", description: "2D蛍光画像の解析手法を整理し、領域の検出・修正、定量、統計、編集可能な論文用グラフまで。CytellectのWindows版は、研究画像をPC内で解析し、ブラウザから操作できます。" };

export default function Page() {
  if (API_CONFIGURED || LOCAL_MODE) {
    return <WorkspaceEntry />;
  }
  return <PublicLanding />;
}
