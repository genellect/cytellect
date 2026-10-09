import {describe, expect, it} from "vitest";
import {initialPanelState, panelReducer} from "./panel-state";

describe("AI and analysis panel navigation", () => {
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
