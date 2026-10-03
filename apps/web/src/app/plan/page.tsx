import type { Metadata } from "next";
import { AnalysisPlanner } from "@/components/AnalysisPlanner";

export const metadata: Metadata = {
  title: "解析計画 | Cytellect",
  description: "測定の目的、画像の条件、独立反復を整理する、出典付きの解析計画。",
};

export default function PlanPage() {
  return <AnalysisPlanner />;
}
