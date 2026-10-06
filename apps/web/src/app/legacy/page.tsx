import type {Metadata} from "next";
import {notFound} from "next/navigation";
import {API_CONFIGURED, LOCAL_MODE} from "@/lib/api";
import WorkspaceEntry from "@/components/WorkspaceEntry";

export const metadata: Metadata = {title: "詳細解析 | Cytellect", robots: {index: false, follow: false}};
export default function LegacyPage() {
  if (!API_CONFIGURED && !LOCAL_MODE) notFound();
  return <WorkspaceEntry />;
}
