import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = { title: "Cytellect — 蛍光画像から、論文の図まで。", description: "2D蛍光画像の領域確認・定量から、統計解析と編集可能な図の出力まで。研究画像をPC内で扱うCytellectのWindows版と公開画像サンプル。", robots: { index: false, follow: false } };
export default function RootLayout({ children }: { children: React.ReactNode }) {
 return <html lang="ja"><body>{children}</body></html>;
}
