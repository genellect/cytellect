import type { Metadata } from "next";
import WorkspacePrototype from "@/components/workspace/WorkspacePrototype";

export const metadata: Metadata = { title: "画像解析 | Cytellect", description: "画像の追加、領域の確認、定量、統計、グラフの出力。", robots: {index: false, follow: false} };

export default function Page() {
  return <WorkspacePrototype />;
}
