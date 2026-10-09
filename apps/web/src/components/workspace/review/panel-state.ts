export type PanelView = "settings" | "ai" | "closed";
export type PanelState = {view: PanelView; returnView: "settings" | "closed"};
export type PanelAction = "settings" | "open-ai" | "toggle-ai" | "close" | "work";

export const initialPanelState: PanelState = {view: "settings", returnView: "settings"};

/** Navigation changes only the visible panel, never analysis settings or requests. */
export function panelReducer(state: PanelState, action: PanelAction): PanelState {
  if (action === "open-ai" || action === "toggle-ai") {
    if (state.view === "ai") return action === "open-ai" ? state : {view: state.returnView, returnView: state.returnView};
    return {view: "ai", returnView: state.view};
  }
  if (action === "work") return state.view === "ai" ? {view: state.returnView, returnView: state.returnView} : state;
  if (action === "close") return state.view === "ai" ? {view: state.returnView, returnView: state.returnView} : {view: "closed", returnView: "closed"};
  const view = state.view === "settings" ? "closed" : "settings";
  return {view, returnView: view};
}
