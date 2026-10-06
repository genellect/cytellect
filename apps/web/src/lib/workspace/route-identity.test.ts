import {describe, expect, it} from "vitest";
import {navigateIdentity, promoteIdentity, resolveIdentity, routeIdentity} from "./route-identity";
describe("workspace route isolation", () => {
  it("preserves an in-flight local upload when its new URL is assigned", () => {
    const initial = routeIdentity("");
    const created = promoteIdentity(initial, "new-workspace");
    expect(created).toEqual({route: "new-workspace", initial: "", generation: 0, pendingUrl: true});
    expect(navigateIdentity(created, "new-workspace")).toBe(created);
  });
  it("remounts for a different workspace and for browser-back to empty root", () => {
    const first = promoteIdentity(routeIdentity(""), "a");
    const second = navigateIdentity(first, "b");
    expect(second).toEqual({route: "b", initial: "b", generation: 1});
    expect(navigateIdentity(second, "")).toEqual({route: "", initial: "", generation: 2});
  });
});

describe("resolveIdentity", () => {
  it("keeps the session while the URL catches up with a promotion, then settles", () => {
    const promoted = promoteIdentity(routeIdentity(""), "w1");
    expect(resolveIdentity(promoted, "")).toBe(promoted);
    expect(resolveIdentity(promoted, "w1")).toEqual({...promoted, pendingUrl: false});
  });
  it("remounts for navigation to another workspace", () => {
    const settled = {...promoteIdentity(routeIdentity(""), "w1"), pendingUrl: false};
    expect(resolveIdentity(settled, "w2").generation).toBe(settled.generation + 1);
  });
});
