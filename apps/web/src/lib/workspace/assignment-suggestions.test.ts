import {describe, expect, it} from "vitest";
import {addRun, emptyDesign, fieldsIn} from "./experiment-design";
import {applySuggestions, mergeSuggestions, planSuggestions, suggestAssignments, suggestedGroups} from "./assignment-suggestions";

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
    // Neither group has a name the folders use: which one is the control is the researcher's choice, never the
    // order of the folder names. Until it is made, applying places nothing and renames nothing.
    const fresh = emptyDesign("pair");
    expect(planSuggestions(fresh, suggestions)).toEqual({renames: [], controlChoice: ["未処理", "ActD 1 µM"], unplaced: ["未処理", "ActD 1 µM"]});
    expect(applySuggestions(fresh, suggestions)).toEqual({design: fresh, left: ["f-untreated", "f-actd"]});
    const {design, left} = applySuggestions(fresh, suggestions, "未処理");
    expect(left).toEqual([]);
    expect(design.runs?.map(run => run.label)).toEqual(["Rep1"]);
    expect(design.groups.map(group => group.label)).toEqual(["未処理", "ActD 1 µM"]);
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
    const {design} = applySuggestions(addRun(emptyDesign("pair"), {label: "2026-11-26"}), suggestAssignments(null, ds6a), "未処理");
    expect(design.runs?.map(run => run.label)).toEqual(["Rep1"]);
    expect(Object.keys(design.fields ?? {})).toEqual(["f-untreated", "f-actd"]);
  });
  it("leaves fields whose group the design cannot place unassigned", () => {
    // 処理 already holds a field, so it keeps its name; 別の群 has no group to go to.
    let design = addRun(emptyDesign("pair"), {label: "Rep1"});
    design = {...design, fields: {p: {group_id: "group-2", run_id: design.runs![0].id, sample: null, acquired_on: null}}};
    const {left, design: applied} = applySuggestions(design,
      [{fieldId: "a", runLabel: "Rep1", groupLabel: "対照"}, {fieldId: "b", runLabel: "Rep1", groupLabel: "別の群"}]);
    expect(left).toEqual(["b"]);
    expect(applied.groups.map(group => group.label)).toEqual(["対照", "処理"]);
  });
});

describe("applying never changes what the researcher set (#284 W6, independent review)", () => {
  const actdFirst = [{fieldId: "x", runLabel: "Rep1", groupLabel: "ActD"}, {fieldId: "y", runLabel: "Rep1", groupLabel: "untreated"}];
  it("the control is the group the researcher names, whatever the order of the folder names", () => {
    // ActD sorts before untreated; the control group still takes the name the researcher chose.
    const {design} = applySuggestions(addRun(emptyDesign("pair"), {label: "2026-11-26"}), actdFirst, "untreated");
    const control = design.groups.find(group => group.id === design.control_group_id)!;
    expect(control.label).toBe("untreated");
    expect(fieldsIn(design, control.id, design.runs![0].id).map(([id]) => id)).toEqual(["y"]);
    expect(design.runs?.map(run => run.label)).toEqual(["Rep1"]);
  });
  it("a group that has fields keeps its name and its fields; suggestions it cannot hold stay unassigned", () => {
    let design = addRun({...emptyDesign("pair"), groups: [{id: "group-1", label: "WT"}, {id: "group-2", label: "KO"}]}, {label: "2026-11-01"});
    design = {...design, fields: {a01: {group_id: "group-1", run_id: design.runs![0].id, sample: null, acquired_on: null}}};
    expect(planSuggestions(design, actdFirst)).toEqual({renames: [], controlChoice: null, unplaced: ["ActD", "untreated"]});
    const applied = applySuggestions(design, actdFirst, "untreated");
    expect(applied.left).toEqual(["x", "y"]);
    expect(applied.design).toEqual(design);
  });
  it("one empty group takes the one name the design lacks, and the control stays where it was", () => {
    const design = addRun({...emptyDesign("pair"), groups: [{id: "group-1", label: "対照"}, {id: "group-2", label: "処理"}]}, {label: "Rep1"});
    const suggestions = [{fieldId: "a", runLabel: "Rep1", groupLabel: "対照"}, {fieldId: "b", runLabel: "Rep1", groupLabel: "ActD"}];
    expect(planSuggestions(design, suggestions)).toEqual({renames: [{groupId: "group-2", from: "処理", to: "ActD"}], controlChoice: null, unplaced: []});
    const applied = applySuggestions(design, suggestions);
    expect(applied.left).toEqual([]);
    expect(applied.design.groups.map(group => group.label)).toEqual(["対照", "ActD"]);
    expect(applied.design.control_group_id).toBe("group-1");
  });
  it("adds no run for a suggestion it cannot place, and leaves no unused dated run when the folders name several", () => {
    const design = addRun(emptyDesign("pair"), {label: "2026-11-26"});
    const two = [{fieldId: "a", runLabel: "Rep1", groupLabel: "対照"}, {fieldId: "b", runLabel: "Rep2", groupLabel: "処理"}, {fieldId: "c", runLabel: "Rep3", groupLabel: "別の群"}];
    const applied = applySuggestions(design, two);
    expect(applied.design.runs?.map(run => run.label)).toEqual(["Rep1", "Rep2"]);
    expect(applied.left).toEqual(["c"]);
  });
});

describe("suggestions from an AI answer (#284 W7)", () => {
  it("files picked one by one: the AI's suggestions split them, marked as the AI's, and applying places one field per group", () => {
    // Names only (no folders): the rules suggest nothing for a two-screen design, the answer to 「未処理と ActD に分けて」 does.
    const picked = [{id: "a", label: "視野01-未処理", paths: ["視野01-未処理-Hoechst.tif"]}, {id: "b", label: "視野01-ActD", paths: ["視野01-ActD-Hoechst.tif"]}];
    const design = addRun(emptyDesign("pair"), {label: "2026-11-26"});
    const rules = suggestAssignments(design, picked);
    expect(rules).toEqual([]);
    const ai = [{fieldId: "a", runLabel: "Rep1", groupLabel: "未処理", source: "ai" as const}, {fieldId: "b", runLabel: "Rep1", groupLabel: "ActD", source: "ai" as const}];
    const merged = mergeSuggestions(rules, ai, picked.map(field => field.id));
    expect(merged.map(value => value.source)).toEqual(["ai", "ai"]);
    const {design: applied, left} = applySuggestions(design, merged, "未処理");
    expect(left).toEqual([]);
    expect(applied.groups.map(group => group.label)).toEqual(["未処理", "ActD"]);
    expect(applied.runs?.map(run => run.label)).toEqual(["Rep1"]);
    expect(applied.groups.map(group => fieldsIn(applied, group.id, applied.runs![0].id).map(([id]) => id))).toEqual([["a"], ["b"]]);
  });
  it("replaces the rule's suggestion for the same field, and never suggests for a field the table does not list", () => {
    const rules = suggestAssignments(null, ds6a);
    const ai = [{fieldId: "f-actd", runLabel: "Rep2", groupLabel: "ActD", source: "ai" as const},
      {fieldId: "assigned", runLabel: "Rep1", groupLabel: "未処理", source: "ai" as const},
      {fieldId: "f-untreated", runLabel: "Rep · 1", groupLabel: "未処理", source: "ai" as const}];
    expect(mergeSuggestions(rules, ai, ds6a.map(field => field.id))).toEqual([
      {fieldId: "f-untreated", runLabel: "Rep1", groupLabel: "未処理", source: "rules"},
      {fieldId: "f-actd", runLabel: "Rep2", groupLabel: "ActD", source: "ai"}]);
  });
});
