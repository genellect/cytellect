import type { Metadata } from "next";
import WorkspacePrototype from "@/components/workspace/WorkspacePrototype";

export const metadata: Metadata = {
  title: "ワークスペース | Cytellect",
  description: "画像の追加から解析案の確認、結果の修正、グラフの書き出しまでを1つの画面で行います。",
  robots: { index: false, follow: false },
};

export default function WorkspacePage() {
  return <WorkspacePrototype />;
}
