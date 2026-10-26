import type { Metadata } from "next";
import { LandingStory } from "@/components/LandingStory";

export const metadata: Metadata = {
  title: "Cytellectが生まれた理由 | Cytellect",
  description: "顕微鏡画像の解析が抱えてきた課題と、Cytellectを開発した理由。",
};

export default function StoryPage() {
  return <LandingStory />;
}
