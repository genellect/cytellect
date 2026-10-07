import type {Metadata} from "next";
import {notFound} from "next/navigation";
import {LOCAL_MODE, LOOPBACK_API} from "@/lib/api";
import WorkspaceEntry from "@/components/WorkspaceEntry";

export const metadata: Metadata = {title: "詳細解析 | Cytellect", robots: {index: false, follow: false}};
export default function LegacyPage() {
  if (!LOCAL_MODE && !LOOPBACK_API) notFound();
  return <WorkspaceEntry />;
}
