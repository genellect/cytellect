import type {Metadata} from "next";
import {notFound} from "next/navigation";
import {API, LOCAL_MODE} from "@/lib/api";
import WorkspaceEntry from "@/components/WorkspaceEntry";

export const metadata: Metadata = {title: "詳細解析 | Cytellect", robots: {index: false, follow: false}};
export default function LegacyPage() {
  let localApi = false;
  try {localApi = ["localhost", "127.0.0.1", "[::1]"].includes(new URL(API).hostname);} catch {}
  if (!LOCAL_MODE && !localApi) notFound();
  return <WorkspaceEntry />;
}
