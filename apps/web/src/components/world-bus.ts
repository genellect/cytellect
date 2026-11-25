/** How the landing page's sections talk to its 3D world (SceneWorld): the world says what it can draw, and the
 *  product tour asks for the shot of the chosen tab. */
export type WorldState = "off" | "loading" | "tour";
export const WORLD_STATE = "lp-world-state", WORLD_SHOT = "lp-world-shot";
export type WorldShot = { shot: number; then?: number };

const root = () => document.querySelector<HTMLElement>("[data-cytellect-public-page]");
/** "tour" once the world is drawing; "loading" while it mounts; "off" where the page keeps its still frames. */
export const worldState = (): WorldState => (root()?.dataset.worldState as WorldState | undefined) ?? "off";
export const announceWorld = (state: WorldState) => {
  const page = root();
  if (page) page.dataset.worldState = state;
  dispatchEvent(new CustomEvent(WORLD_STATE));
};
export const showShot = (shot: number, then?: number) => dispatchEvent(new CustomEvent<WorldShot>(WORLD_SHOT, { detail: { shot, then } }));
