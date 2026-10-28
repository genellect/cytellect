import {describe, expect, it} from "vitest";
import {experimentSetupShown, initialPanelState, panelReducer} from "./panel-state";

describe("AI and analysis panel navigation", () => {
  it("starts closed so the images come first, in the demo and in production alike", () => {
    expect(initialPanelState).toEqual({view: "closed", returnView: "closed"});
    expect(panelReducer(initialPanelState, "settings").view).toBe("settings");
  });
  it("opens analysis settings from AI even when settings were previously open", () => {
    const ai = panelReducer(initialPanelState, "open-ai");
    expect(panelReducer(ai, "settings").view).toBe("settings");
  });
  it.each(["close", "toggle-ai", "work"] as const)("restores the prior panel on %s", action => {
    for (const view of ["settings", "closed"] as const) {
      const before = {view, returnView: view};
      expect(panelReducer(panelReducer(before, "open-ai"), action)).toEqual(before);
    }
  });
  it("keeps the return destination when a second instruction is sent", () => {
    const ai = panelReducer({view: "closed", returnView: "closed"}, "open-ai");
    expect(panelReducer(panelReducer(ai, "open-ai"), "close").view).toBe("closed");
  });
});

describe("experiment form placement", () => {
  it("stays in one place from a new workspace's first choice to the experiment view", () => {
    // The first save moves a new workspace from the image view to the experiment view.
    expect(experimentSetupShown("image", false, false)).toBe(true);
    expect(experimentSetupShown("experiment", false, false)).toBe(true);
    expect(experimentSetupShown("experiment", true, true)).toBe(true);
    expect(experimentSetupShown("image", true, false)).toBe(false);
    expect(experimentSetupShown("image", false, true)).toBe(false);
    expect(experimentSetupShown("statistics", false, false)).toBe(false);
  });
});
