import scenes from "../../../public/showcase/snapshot/scenes.json";

export type DemoStep = "image" | "statistics" | "figure";

/** A link from the landing page to one screen of one demo scene. The demo opens a scene by its
 *  workspace ID, which a rebuilt demo may change; the scene ID does not, so links are written with
 *  the scene ID and resolved here at build time. Import this from server components only: the scene
 *  list is large. */
export function demoSceneHref(sceneId: string, step: DemoStep): string {
  const scene = (scenes as { scenes: { id: string; workspaceId: string }[] }).scenes.find(item => item.id === sceneId);
  return scene ? `/demo?id=${scene.workspaceId}&step=${step}` : `/demo?step=${step}`;
}
