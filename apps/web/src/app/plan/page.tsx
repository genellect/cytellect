import type { Metadata } from "next";
import { AnalysisPlanner } from "@/components/AnalysisPlanner";
import { LandingAnalytics } from "@/components/LandingAnalytics";

export const metadata: Metadata = {
  title: "解析設定 | Cytellect",
  description: "測定項目、画像形式、実験条件に対応する解析方法と必要な設定を確認できます。",
};

export default function PlanPage() {
  return <div data-cytellect-public-page="/plan" style={{ display: "contents" }}><LandingAnalytics page="/plan" /><AnalysisPlanner /></div>;
}
