/** How the landing page's sections talk to its 3D stage (SceneWorld): the stage says whether it is drawing, and
 *  the product tour asks for the screen of the chosen tab. */
export type WorldState = "off" | "loading" | "live";
export const WORLD_STATE = "lp-world-state", WORLD_SCREEN = "lp-world-screen";

const root = () => document.querySelector<HTMLElement>("[data-cytellect-public-page]");
/** "live" once the stage is drawing; "loading" while it mounts; "off" where the page keeps its still pictures. */
export const worldState = (): WorldState => (root()?.dataset.worldState as WorldState | undefined) ?? "off";
export const announceWorld = (state: WorldState) => {
  const page = root();
  if (page) page.dataset.worldState = state;
  dispatchEvent(new CustomEvent(WORLD_STATE));
};
/** Turn the product wall to the screen of a tab (its index in the tour). */
export const showScreen = (index: number) => dispatchEvent(new CustomEvent<number>(WORLD_SCREEN, { detail: index }));
