"use client";

import dynamic from "next/dynamic";
import "./workspace.module.css";

// Keep the private analysis client out of the public landing page's initial chunks.
const WorkspaceApp = dynamic(() => import("./WorkspaceApp"), {
  ssr: false,
  loading: () => <main role="status" style={{padding:"3rem"}}>ワークスペースを開いています…</main>,
});

export default function WorkspaceEntry() { return <WorkspaceApp />; }
