import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = { title: "Cytellect — IF image analysis", description: "招待制の免疫蛍光画像解析ワークスペース。核・核小体から定量と図表まで。", robots: { index: false, follow: false } };
export default function RootLayout({ children }: { children: React.ReactNode }) {
 return <html lang="ja"><body>{children}</body></html>;
}
