import type {Metadata} from "next";
import PublicLanding from "@/components/PublicLanding";

export const metadata: Metadata = {title: "Cytellect — Get your microscopy publication-ready.", description: "顕微鏡画像の解析から統計、論文用グラフの作成まで。", robots: {index: true, follow: true}};
export default function ProductPage() {return <PublicLanding />;}
