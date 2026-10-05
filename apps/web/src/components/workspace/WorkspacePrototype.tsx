"use client";
import { useEffect, useMemo, useState } from "react";
import { createPrototypeAdapter } from "@/lib/workspace/adapter";
import AnalysisWorkspace from "./AnalysisWorkspace";

/** Operable prototype: recorded public outputs through a simulated adapter (redesign step 1). */
export default function WorkspacePrototype() {
  const adapter = useMemo(() => createPrototypeAdapter(), []);
  const [demo, setDemo] = useState<boolean | null>(null);
  // The registered public example opens only through ?demo=bbbc013 (owner review, tests and the site).
  useEffect(() => { setDemo(new URLSearchParams(window.location.search).get("demo") === "bbbc013"); }, []);
  if (demo === null) return null;
  return <AnalysisWorkspace adapter={adapter} demo={demo} />;
}
