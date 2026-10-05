"use client";
import { useMemo } from "react";
import { createPrototypeAdapter } from "@/lib/workspace/adapter";
import AnalysisWorkspace from "./AnalysisWorkspace";

/** Operable prototype: recorded public outputs through a simulated adapter (redesign step 1). */
export default function WorkspacePrototype() {
  const adapter = useMemo(() => createPrototypeAdapter(), []);
  return <AnalysisWorkspace adapter={adapter} />;
}
