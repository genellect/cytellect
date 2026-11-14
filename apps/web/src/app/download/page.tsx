import type { Metadata } from "next";
import { InstallGuide } from "@/components/InstallGuide";

export const metadata: Metadata = {
  title: "Windows版のインストール | Cytellect",
  description: "Cytellect Windows 版のダウンロードから作業画面の起動までの手順。",
};

export default function DownloadPage() {
  return <InstallGuide />;
}
