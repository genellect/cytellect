import type { Metadata } from "next";
import { AnalysisPlanner } from "@/components/AnalysisPlanner";

export const metadata: Metadata = {
  title: "解析設定 | Cytellect",
  description: "測定項目、画像形式、実験条件に対応する解析方法と必要な設定を確認できます。",
};

export default function PlanPage() {
  return <AnalysisPlanner />;
}
