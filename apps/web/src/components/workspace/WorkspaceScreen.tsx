"use client";
import ConnectedWorkspace from "./review/ConnectedWorkspace";
import WorkspaceAccess from "./WorkspaceAccess";

/** The analysis workspace of an installation with an analysis API; the public demo lives at /demo. */
export default function WorkspaceScreen() {
  return <WorkspaceAccess><ConnectedWorkspace/></WorkspaceAccess>;
}
