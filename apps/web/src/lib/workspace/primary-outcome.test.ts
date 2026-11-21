import {describe, expect, it} from "vitest";
import {outcomeRole, primaryOutcome, samePrimary} from "./primary-outcome";

const declared = {...primaryOutcome("solidity", "nucleoli", "c1"), declared_at: 2000};

describe("primary outcome", () => {
  it("declares the region set the values come from and a stain only where the metric reads one", () => {
    expect(primaryOutcome("solidity", "nucleoli", "c1")).toEqual({version: "1.0.0", metric: "solidity", region_set_id: "nuclei", channel_id: null});
    expect(primaryOutcome("mean", "nucleoli", "c1")).toEqual({version: "1.0.0", metric: "mean", region_set_id: "nucleoli", channel_id: "c1"});
    expect(primaryOutcome("nucleolar_count", "nucleoli", "c1").region_set_id).toBe("nucleoplasm");
  });
  it("marks nothing without a declaration", () => {
    expect(outcomeRole(null, {metric: "solidity", regionSet: "nuclei", channel: null}, 3000)).toBeNull();
    expect(outcomeRole(undefined, {metric: "solidity", regionSet: "nuclei", channel: null})).toBeNull();
  });
  it("is primary only for the declared measure calculated after the declaration", () => {
    const same = {metric: "solidity", regionSet: "nuclei", channel: null};
    expect(samePrimary(declared, same)).toBe(true);
    expect(outcomeRole(declared, same)).toBe("primary");
    expect(outcomeRole(declared, same, 2500)).toBe("primary");
    // 解析 -> 宣言 -> 図の描き直し: the re-drawn figure carries its statistics' time (1500), not the re-render's.
    expect(outcomeRole(declared, same, 1500)).toBe("exploratory");
    expect(outcomeRole(declared, same, 2000)).toBe("exploratory");
    // A result without a recorded calculation time is never primary.
    expect(outcomeRole(declared, same, null)).toBe("exploratory");
    expect(outcomeRole({...declared, declared_at: null}, same, 2500)).toBe("exploratory");
    expect(outcomeRole(declared, {metric: "eccentricity", regionSet: "nuclei", channel: null}, 2500)).toBe("exploratory");
    expect(outcomeRole(declared, {metric: "solidity", regionSet: "nuclei", channel: "c1"}, 2500)).toBe("exploratory");
  });
});
