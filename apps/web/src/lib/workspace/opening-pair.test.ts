import {describe, expect, it} from "vitest";
import {openingPair} from "./experiment-design";

describe("opening pair", () => {
  it("names the first run's first field of each group, control first", () => {
    const design = {version: "1.0.0", layout: "pair", control_group_id: "c", independence_confirmed: false,
      groups: [{id: "t", label: "KO"}, {id: "c", label: "NT"}],
      runs: [{id: "r0", label: "Run0"}, {id: "r1", label: "Run1"}, {id: "r2", label: "Run2"}],
      fields: {a: {group_id: "t", run_id: "r1"}, b: {group_id: "c", run_id: "r1"}, d: {group_id: "c", run_id: "r1"}, e: {group_id: "c", run_id: "r2"}}} as never;
    expect(openingPair(design)).toEqual(["b", "a"]);
    expect(openingPair(null)).toEqual([]);
    expect(openingPair({...(design as object), layout: "single"} as never)).toEqual([]);
  });
});
