import type { Metadata } from "next";
import { InstallGuide } from "@/components/InstallGuide";

export const metadata: Metadata = {
  title: "Windows版のインストール | Cytellect",
  description: "Cytellect の Windows 版をダウンロードしてから、作業画面が開くまでの流れ。",
};

export default function DownloadPage() {
  return <InstallGuide />;
}
