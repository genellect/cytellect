import type { Metadata } from "next";
import "./globals.css";
import "./fonts.css";
import {PlanMemory} from "@/components/PlanMemory";
export const metadata: Metadata = { title: "Cytellect — Get your microscopy publication-ready.", description: "顕微鏡画像の解析から統計、論文用グラフの作成まで。", robots: { index: false, follow: false } };
export default function RootLayout({ children }: { children: React.ReactNode }) {
 return <html lang="ja"><body><PlanMemory>{children}</PlanMemory></body></html>;
}
