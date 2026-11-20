import {describe, expect, it} from "vitest";
import {outcomeRole, outcomeRoleText, primaryName, primaryOutcome} from "./primary-outcome";

describe("primary measure (#257 RP-04)", () => {
  it("declares the region set the values come from and the stain only where the metric reads one", () => {
    expect(primaryOutcome("nucleolar_area_px", "nucleoli", "npm1")).toEqual({version: "1.0.0", metric: "nucleolar_area_px", region_set_id: "nucleoplasm", channel_id: null});
    expect(primaryOutcome("cv", "nuclei", "npm1")).toMatchObject({region_set_id: "nuclei", channel_id: "npm1"});
    expect(primaryOutcome("solidity", "nucleoli", "npm1")).toMatchObject({region_set_id: "nucleoli", channel_id: null});
  });
  it("marks the declared measure primary and every other measure exploratory", () => {
    const primary = {...primaryOutcome("cv", "nuclei", "npm1"), declared_at: 100};
    expect(outcomeRole(primary, {metric: "cv", regionSet: "nuclei", channel: "npm1"}, 150)).toBe("primary");
    expect(outcomeRole(primary, {metric: "cv", regionSet: "nuclei", channel: "npm1"})).toBe("primary");
    // A result of the declared measure calculated before the declaration says so.
    expect(outcomeRole(primary, {metric: "cv", regionSet: "nuclei", channel: "npm1"}, 50)).toBe("primary-after");
    expect(outcomeRole(primary, {metric: "cv", regionSet: "nuclei", channel: "eu5"}, 150)).toBe("exploratory");
    expect(outcomeRole(primary, {metric: "mean", regionSet: "nuclei", channel: "npm1"}, 150)).toBe("exploratory");
    expect(outcomeRole(null, {metric: "cv", regionSet: "nuclei", channel: "npm1"})).toBe("exploratory");
  });
  it("names the role and the primary measure in the label used everywhere", () => {
    const primary = primaryOutcome("cv", "nuclei", "npm1");
    const name = primaryName(primary, id => (id === "npm1" ? "NPM1" : id));
    expect(name).toBe("核の画素の変動係数（CV、NPM1）");
    expect(outcomeRoleText("exploratory", name)).toBe("探索的な指標（主要指標：核の画素の変動係数（CV、NPM1））");
    expect(outcomeRoleText("exploratory", null)).toBe("探索的な指標（主要指標は未宣言）");
    expect(outcomeRoleText("primary", name)).toBe("主要指標");
  });
});
