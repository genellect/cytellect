import type { Metadata } from "next";
import { InstallGuide } from "@/components/InstallGuide";

export const metadata: Metadata = {
  title: "Windows版のインストール | Cytellect",
  description: "Cytellect Windows 版のインストール、起動、更新、削除の手順。",
};

export default function DownloadPage() {
  return <InstallGuide />;
}
