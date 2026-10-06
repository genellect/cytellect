import {describe, expect, it} from "vitest";
import {navigateIdentity, promoteIdentity, routeIdentity} from "./route-identity";
describe("workspace route isolation", () => {
  it("preserves an in-flight local upload when its new URL is assigned", () => {
    const initial = routeIdentity("");
    const created = promoteIdentity(initial, "new-workspace");
    expect(created).toEqual({route: "new-workspace", initial: "", generation: 0});
    expect(navigateIdentity(created, "new-workspace")).toBe(created);
  });
  it("remounts for a different workspace and for browser-back to empty root", () => {
    const first = promoteIdentity(routeIdentity(""), "a");
    const second = navigateIdentity(first, "b");
    expect(second).toEqual({route: "b", initial: "b", generation: 1});
    expect(navigateIdentity(second, "")).toEqual({route: "", initial: "", generation: 2});
  });
});
