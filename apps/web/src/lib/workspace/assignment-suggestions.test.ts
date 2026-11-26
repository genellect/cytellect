import {describe, expect, it} from "vitest";
import {addRun, emptyDesign, fieldsIn} from "./experiment-design";
import {applySuggestions, suggestAssignments, suggestedGroups} from "./assignment-suggestions";

/** DS6a's layout (Issue input 4): one run folder, two group folders, one field each (names only; no pixels). */
const ds6a = [
  {id: "f-untreated", label: "視野01", paths: ["Rep1/未処理/視野01-Hoechst.tif", "Rep1/未処理/視野01-C02.tif", "Rep1/未処理/視野01-C03.tif"]},
  {id: "f-actd", label: "視野01", paths: ["Rep1/ActD 1 µM/視野01-Hoechst.tif", "Rep1/ActD 1 µM/視野01-C02.tif", "Rep1/ActD 1 µM/視野01-C03.tif"]},
];

describe("run and group suggestions for unassigned fields (#284 W6)", () => {
  it("proposes the same run and two groups from DS6a's folders, and applying gives one run with one field per group", () => {
    const suggestions = suggestAssignments(null, ds6a);
    expect(suggestions).toEqual([{fieldId: "f-untreated", runLabel: "Rep1", groupLabel: "未処理"}, {fieldId: "f-actd", runLabel: "Rep1", groupLabel: "ActD 1 µM"}]);
    expect(suggestedGroups(suggestions)).toEqual(["未処理", "ActD 1 µM"]);
    const {design, left} = applySuggestions(emptyDesign("pair"), suggestions);
    expect(left).toEqual([]);
    expect(design.runs?.map(run => run.label)).toEqual(["Rep1"]);
    expect(design.groups.map(group => group.label)).toEqual(["未処理", "ActD 1 µM"]);
    // The control stays the researcher's choice (the first group by default, as before).
    expect(design.control_group_id).toBe("group-1");
    const run = design.runs![0].id;
    expect(fieldsIn(design, "group-1", run).map(([id]) => id)).toEqual(["f-untreated"]);
    expect(fieldsIn(design, "group-2", run).map(([id]) => id)).toEqual(["f-actd"]);
  });
  it("uses the only run and group of a one-screen design, and gives no suggestion from file names alone otherwise", () => {
    const single = addRun(emptyDesign("single"), {label: "2026-11-26"});
    const plain = [{id: "a9", label: "BBBC007-a9", paths: ["BBBC007-a9-C01.tif", "BBBC007-a9-C02.tif"]}];
    expect(suggestAssignments(single, plain)).toEqual([{fieldId: "a9", runLabel: "2026-11-26", groupLabel: "群 1"}]);
    expect(suggestAssignments(addRun(emptyDesign("pair"), {label: "Rep1"}), plain)).toEqual([]);
    // A group folder alone uses the design's only run.
    expect(suggestAssignments(addRun(emptyDesign("pair"), {label: "Rep1"}), [{id: "x", label: "x", paths: ["処理/x-C01.tif"]}])).toEqual([{fieldId: "x", runLabel: "Rep1", groupLabel: "処理"}]);
    // A folder name the design cannot hold as a label is not shortened into a suggestion.
    expect(suggestAssignments(null, [{id: "y", label: "y", paths: ["Rep1/" + "長".repeat(30) + "/y.tif"]}])).toEqual([]);
  });
  it("names the design's only, still empty run after the folders instead of adding another", () => {
    const {design} = applySuggestions(addRun(emptyDesign("pair"), {label: "2026-11-26"}), suggestAssignments(null, ds6a));
    expect(design.runs?.map(run => run.label)).toEqual(["Rep1"]);
    expect(Object.keys(design.fields ?? {})).toEqual(["f-untreated", "f-actd"]);
  });
  it("leaves fields whose group the design cannot place unassigned", () => {
    const design = addRun(emptyDesign("pair"), {label: "Rep1"});
    const {left} = applySuggestions({...design, groups: [{id: "group-1", label: "対照"}, {id: "group-2", label: "処理"}]},
      [{fieldId: "a", runLabel: "Rep1", groupLabel: "対照"}, {fieldId: "b", runLabel: "Rep1", groupLabel: "別の群"}]);
    expect(left).toEqual(["b"]);
  });
});
