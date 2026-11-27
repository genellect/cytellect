import {describe, expect, it, vi} from "vitest";
import {intakePath} from "./dropped-files";
import {additions, breakdown, createIntakeList, listedFields, matchingFields, type Inspection} from "./intake-list";

/** Synthetic bytes: the names decide the grouping and the mocked judgement decides the role (W4 is tested on its own). */
/** The same name and byte stand for the same file: the same content, size and last-modified time. */
const file = (name: string, byte: number) => new File([new Uint8Array([byte, byte + 1])], name, {lastModified: 1_700_000_000_000 + byte});
const flush = () => new Promise(resolve => setTimeout(resolve, 0));
async function settled(list: ReturnType<typeof createIntakeList>) {for (let i = 0; i < 20 && list.getSnapshot().items.some(item => item.state === "読み込み中"); i++) await flush();}
function memoryStorage() {const values = new Map<string, string>();return {getItem: (key: string) => values.get(key) ?? null, setItem: (key: string, value: string) => void values.set(key, value), removeItem: (key: string) => void values.delete(key), values};}
const judge = (file: File): Inspection => file.name.includes("輪郭") ? {role: "label", code: "region_image_bit_depth_unsupported", shape: [400, 400]}
  : file.name.includes("truncated") ? {role: "unreadable", code: "unsupported_or_invalid_region_image"} : {role: "image", shape: [400, 400], thumbnail_png: "iVBOR"};

describe("intake list before adding (#284 W5)", () => {
  it("adds up what was received: images by field, a mask candidate, a copy, an unreadable file and a text file", async () => {
    const inspect = vi.fn(async (value: File) => judge(value));
    const list = createIntakeList({inspect, known: () => new Map(), storage: null});
    list.add([file("BBBC007-a9-C01.tif", 1), file("BBBC007-a9-C02.tif", 3), file("BBBC007-f9620-C01.tif", 5), file("BBBC007-f9620-C02.tif", 7),
      file("copy/BBBC007-a9-C01.tif", 1), file("BBBC007-a9-核の手動輪郭.tif", 9), file("test-truncated-DRAQ.tif", 11), file("読み方.txt", 13)]);
    expect(list.getSnapshot().items.find(item => item.name === "読み方.txt")?.state).toBe("対象外");
    await settled(list);
    const items = list.getSnapshot().items;
    expect(breakdown(items)).toBe("受け取り：8 · 画像：4（2 視野） · マスクの候補：1 · 同一内容：1 · 読み取れない：1 · 対象外：1");
    expect(listedFields(items).map(field => [field.name, field.channels])).toEqual([["BBBC007-a9", ["c01", "c02"]], ["BBBC007-f9620", ["c01", "c02"]]]);
    expect(items.find(item => item.state === "同一内容")?.sameAs).toBe("BBBC007-a9-C01.tif");
    // The mask candidate names the fields of its size; its use is not inferred.
    const mask = items.find(item => item.state === "マスクの候補")!;
    expect(matchingFields(mask, items, [{name: "A01", shape: [512, 512]}])).toEqual(["BBBC007-a9", "BBBC007-f9620"]);
    // A text file and a copy are never sent to be judged.
    expect(inspect).toHaveBeenCalledTimes(6);
  });
  it("keeps the first choice when another is added, takes back only the last one, and joins a later stain to its field", async () => {
    const list = createIntakeList({inspect: async value => judge(value), known: () => new Map(), storage: null});
    list.add([file("BBBC007-a9-C01.tif", 1), file("BBBC007-f9620-C01.tif", 5), file("BBBC007-f9620-C02.tif", 7), file("BBBC007-a9-C02.tif", 3)]);
    list.add([file("BBBC039-B02-Hoechst.tif", 21)]);
    await settled(list);
    expect(list.getSnapshot().items).toHaveLength(5);
    expect(listedFields(list.getSnapshot().items)).toHaveLength(3);
    list.undoLast();
    expect(list.getSnapshot().items.map(item => item.name)).not.toContain("BBBC039-B02-Hoechst.tif");
    expect(list.getSnapshot().items).toHaveLength(4);
    const split = createIntakeList({inspect: async value => judge(value), known: () => new Map(), storage: null});
    split.add([file("A01-DRAQ.tif", 31)]);split.add([file("A01-GFP.tif", 33)]);
    await settled(split);
    expect(listedFields(split.getSnapshot().items).map(field => field.channels)).toEqual([["draq", "gfp"]]);
  });
  it("the same file names chosen again with other content are their own field, pair kept, and are added on their own (independent review)", async () => {
    // Two condition folders hold the same file names; the researcher chooses the files of one folder, then the other's.
    const list = createIntakeList({inspect: async value => judge(value), known: () => new Map(), storage: null});
    list.add([file("field01-C01.tif", 1), file("field01-C02.tif", 3)]);
    list.add([file("field01-C01.tif", 5), file("field01-C02.tif", 7), file("field02-C01.tif", 9)]);
    await settled(list);
    const items = list.getSnapshot().items, fields = listedFields(items);
    // What the list counts is what registration makes: three fields, each with its own pair.
    expect(breakdown(items)).toBe("受け取り：5 · 画像：5（3 視野）");
    expect(fields.map(field => [field.name, field.channels, field.repeated, field.items.map(item => item.selection)])).toEqual([
      ["field01", ["c01", "c02"], false, [1, 1]], ["field02", ["c01"], false, [2]], ["field01", ["c01", "c02"], true, [2, 2]]]);
    expect(new Set(fields.map(field => field.key)).size).toBe(3);
    expect(additions(items).map(value => [value.repeated, value.items.map(item => `${item.selection}:${item.name}`)])).toEqual([
      [false, ["1:field01-C01.tif", "1:field01-C02.tif", "2:field02-C01.tif"]], [true, ["2:field01-C01.tif", "2:field01-C02.tif"]]]);
  });
  it("a field goes to one run and group: a stain chosen without a cell joins its field's cell, and two cells make two fields", async () => {
    const control = {run_id: "r1", group_id: "c", sample: null}, treated = {run_id: "r1", group_id: "t", sample: null};
    const list = createIntakeList({inspect: async value => judge(value), known: () => new Map(), storage: null});
    // C01 chosen in 対照's cell; C02 then chosen with 「画像を追加」 in the list (no cell).
    list.add([file("BBBC007-a9-C01.tif", 1)], control);
    list.add([file("BBBC007-a9-C02.tif", 3)]);
    // f9620's two stains chosen in two different cells.
    list.add([file("BBBC007-f9620-C01.tif", 5)], control);
    list.add([file("BBBC007-f9620-C02.tif", 7)], treated);
    await settled(list);
    const items = list.getSnapshot().items;
    expect(listedFields(items).map(field => [field.name, field.channels, field.target?.group_id ?? null])).toEqual([
      ["BBBC007-a9", ["c01", "c02"], "c"], ["BBBC007-f9620", ["c01"], "c"], ["BBBC007-f9620", ["c02"], "t"]]);
    expect(breakdown(items)).toBe("受け取り：4 · 画像：4（3 視野）");
    // Registration receives exactly these groups, each with its cell.
    expect(additions(items).map(value => [value.target?.group_id ?? null, value.items.map(item => item.name)])).toEqual([
      ["c", ["BBBC007-a9-C01.tif", "BBBC007-a9-C02.tif", "BBBC007-f9620-C01.tif"]], ["t", ["BBBC007-f9620-C02.tif"]]]);
  });
  it("an OME-TIFF is a field of its own beside single planes of the same name, and a copied field kept apart stays one field", async () => {
    const inspect = async (value: File): Promise<Inspection> => value.name.endsWith(".ome.tif") ? {role: "image", shape: [400, 400], channel_names: ["DRAQ", "GFP"]} : judge(value);
    const ome = Object.assign(file("A01.ome.tif", 1), {});
    // The OME header is read from the bytes: these synthetic bytes carry none, so the kind is given by the test.
    const list = createIntakeList({inspect, known: () => new Map(), storage: null});
    list.add([ome, file("A01-rfp.tif", 3)]);
    await settled(list);
    list.getSnapshot().items[0].ome = true;
    expect(listedFields(list.getSnapshot().items).map(field => [field.name, field.channels])).toEqual([["A01", ["rfp"]], ["A01", ["DRAQ", "GFP"]]]);
    // Two stains of a registered field, chosen again and kept as a separate acquisition: one field, stains together.
    const known = new Map([["x", "BBBC007-a9"]]);
    const copies = createIntakeList({inspect: async value => judge(value), known: () => known, storage: null});
    copies.add([file("copy/BBBC007-a9-C01.tif", 1), file("copy/BBBC007-a9-C02.tif", 3)]);
    await settled(copies);
    for (const item of copies.getSnapshot().items) copies.keepSeparately(item.id);
    await settled(copies);
    const kept = listedFields(copies.getSnapshot().items);
    expect(kept.map(field => [field.name, field.channels, field.separate])).toEqual([["BBBC007-a9", ["c01", "c02"], true]]);
    expect(additions(copies.getSnapshot().items)).toHaveLength(1);
  });
  it("shows two files of different content for one channel of a field as a conflict of that field only", async () => {
    const list = createIntakeList({inspect: async value => judge(value), known: () => new Map(), storage: null});
    list.add([file("BBBC007-a9-C01.tif", 1), file("BBBC007-a9-C02.tif", 3), file("BBBC007-a9_c01.tif", 5), file("BBBC007-f9620-C01.tif", 7)]);
    await settled(list);
    const fields = listedFields(list.getSnapshot().items), a9 = fields.find(field => field.name === "BBBC007-a9")!;
    expect(a9.conflicts.map(value => [value.channel, value.items.map(item => item.name)])).toEqual([["c01", ["BBBC007-a9-C01.tif", "BBBC007-a9_c01.tif"]]]);
    // Both candidates and the field's other stain are the field's files; the other field has no conflict.
    expect(a9.items.map(item => item.name).sort()).toEqual(["BBBC007-a9-C01.tif", "BBBC007-a9-C02.tif", "BBBC007-a9_c01.tif"]);
    expect(fields.find(field => field.name === "BBBC007-f9620")?.conflicts).toEqual([]);
    // Keeping one (removing the other from the list) resolves it.
    list.remove(a9.conflicts[0].items[1].id);
    expect(listedFields(list.getSnapshot().items).find(field => field.name === "BBBC007-a9")?.conflicts).toEqual([]);
  });
  it("the first opening of a page keeps files chosen while the workspace loaded, beside the names kept from before", async () => {
    const storage = memoryStorage();storage.setItem("cytellect.intake.v1.w", JSON.stringify(["old_c1.tif", "A01_c1.tif"]));
    const list = createIntakeList({inspect: async value => judge(value), known: () => new Map(), storage});
    list.add([file("A01_c1.tif", 1)]);
    await settled(list);
    list.open("w", true);
    expect(list.getSnapshot().items.map(item => [item.name, item.state])).toEqual([["old_c1.tif", "再選択"], ["A01_c1.tif", "追加待ち"]]);
    // Another workspace's list starts from its own names only.
    list.open("other");
    expect(list.getSnapshot().items).toEqual([]);
  });
  it("keeps the cell a file was chosen in over a reload, so choosing it again goes where it was going (independent review)", async () => {
    const storage = memoryStorage(), control = {run_id: "r1", group_id: "c", sample: null};
    const list = createIntakeList({inspect: async value => judge(value), known: () => new Map(), storage});
    list.open("w");
    list.add([file("BBBC007-a9-C01.tif", 1)], control);
    list.add([file("plain_c1.tif", 3)]);
    await settled(list);
    // A reload: another list reads the same storage. The names come back with their cells.
    const reloaded = createIntakeList({inspect: async value => judge(value), known: () => new Map(), storage});
    reloaded.open("w", true);
    expect(reloaded.getSnapshot().items.map(item => [item.name, item.state, item.target?.group_id ?? null])).toEqual([["BBBC007-a9-C01.tif", "再選択", "c"], ["plain_c1.tif", "再選択", null]]);
    reloaded.replace(reloaded.getSnapshot().items[0].id, file("BBBC007-a9-C01.tif", 1));
    await settled(reloaded);
    expect(listedFields(reloaded.getSnapshot().items).map(field => [field.name, field.target?.group_id ?? null])).toEqual([["BBBC007-a9", "c"]]);
    // Names kept by an earlier version (plain strings) are read as names without a cell; anything else is ignored.
    storage.setItem("cytellect.intake.v1.old", JSON.stringify(["old_c1.tif", {name: 3}, {name: "bad_c1.tif", target: {run_id: 1}}]));
    reloaded.open("old");
    expect(reloaded.getSnapshot().items.map(item => [item.name, item.target])).toEqual([["old_c1.tif", null], ["bad_c1.tif", null]]);
  });
  it("a file chosen again after a reload goes where it was going, however it is chosen (independent review, round 4)", async () => {
    const storage = memoryStorage(), control = {run_id: "r1", group_id: "c", sample: null}, treated = {run_id: "r1", group_id: "t", sample: null};
    const first = createIntakeList({inspect: async value => judge(value), known: () => new Map(), storage});
    first.open("w");
    // The same file names in two cells (two condition folders), one of them from a folder choice.
    first.add([file("field1-C01.tif", 1), file("field1-C02.tif", 3)], control);
    first.add([file("field1-C01.tif", 5), file("field1-C02.tif", 7)], treated);
    const inFolder = file("solo_c1.tif", 9);Object.defineProperty(inFolder, "webkitRelativePath", {value: "Rep1/treated/solo_c1.tif"});
    first.add([inFolder], treated);
    await settled(first);
    const reload = () => {const list = createIntakeList({inspect: async value => judge(value), known: () => new Map(), storage});list.open("w", true);return list;};
    // 「画像を追加」 (no cell): each file takes the place, the cell and the path of a kept name, one row per file.
    const general = reload();
    general.add([file("field1-C01.tif", 1), file("field1-C02.tif", 3), file("solo_c1.tif", 9)]);
    await settled(general);
    expect(general.getSnapshot().items.map(item => [item.name, item.state, item.target?.group_id ?? null])).toEqual([
      ["field1-C01.tif", "再選択", "t"], ["field1-C02.tif", "再選択", "t"],
      ["field1-C01.tif", "追加待ち", "c"], ["field1-C02.tif", "追加待ち", "c"], ["Rep1/treated/solo_c1.tif", "追加待ち", "t"]]);
    // The file from the folder is added under the path it was first chosen with (its pending row has that name).
    expect(additions(general.getSnapshot().items).flatMap(value => value.items.map(item => intakePath(item.file!)))).toContain("Rep1/treated/solo_c1.tif");
    // Chosen again in 処理's cell: only 処理's kept rows are taken; 対照's stay to be chosen.
    const cell = reload();
    cell.add([file("field1-C01.tif", 5), file("field1-C02.tif", 7)], treated);
    await settled(cell);
    expect(cell.getSnapshot().items.filter(item => item.state === "再選択").map(item => [item.name, item.target?.group_id ?? null])).toEqual([
      ["field1-C01.tif", "c"], ["field1-C02.tif", "c"], ["Rep1/treated/solo_c1.tif", "t"]]);
    // The row's own 「選択」 keeps the folder path too.
    const row = cell.getSnapshot().items.find(item => item.name === "Rep1/treated/solo_c1.tif")!;
    cell.replace(row.id, file("solo_c1.tif", 9));
    await settled(cell);
    expect(cell.getSnapshot().items.find(item => item.id === row.id)).toMatchObject({name: "Rep1/treated/solo_c1.tif", state: "追加待ち", target: treated});
  });
  it("a file chosen again is recognised by its size and time, not by its name alone (independent review, round 5)", async () => {
    const storage = memoryStorage(), control = {run_id: "r1", group_id: "c", sample: null}, treated = {run_id: "r1", group_id: "t", sample: null};
    const first = createIntakeList({inspect: async value => judge(value), known: () => new Map(), storage});
    first.open("w");
    // Two condition folders with the same file names; one more file from a folder choice.
    first.add([file("field1-C01.tif", 1), file("field1-C02.tif", 3)], control);
    first.add([file("field1-C01.tif", 5), file("field1-C02.tif", 7)], treated);
    const inFolder = file("solo_c1.tif", 9);Object.defineProperty(inFolder, "webkitRelativePath", {value: "Rep1/treated/solo_c1.tif"});
    first.add([inFolder], treated);
    await settled(first);
    // Only the name, the cell, the size and the time are kept: never the content.
    expect(JSON.parse(storage.values.get("cytellect.intake.v1.w")!)[0]).toEqual({name: "field1-C01.tif", target: control, size: 2, modified: 1_700_000_000_001});
    const reload = () => {const list = createIntakeList({inspect: async value => judge(value), known: () => new Map(), storage});list.open("w", true);return list;};
    // 処理's files chosen with 「画像を追加」 take 処理's rows, although 対照's rows of the same names come first.
    const general = reload();
    general.add([file("field1-C01.tif", 5), file("field1-C02.tif", 7)]);
    await settled(general);
    expect(general.getSnapshot().items.map(item => [item.name, item.state, item.target?.group_id ?? null])).toEqual([
      ["field1-C01.tif", "再選択", "c"], ["field1-C02.tif", "再選択", "c"], ["Rep1/treated/solo_c1.tif", "再選択", "t"],
      ["field1-C01.tif", "追加待ち", "t"], ["field1-C02.tif", "追加待ち", "t"]]);
    // Another file that only shares a name with a kept one takes neither its cell nor its folder path.
    const other = reload();
    other.add([file("solo_c1.tif", 11), file("field1-C01.tif", 13)]);
    await settled(other);
    expect(other.getSnapshot().items.filter(item => item.file).map(item => [item.name, item.target])).toEqual([["solo_c1.tif", null], ["field1-C01.tif", null]]);
    expect(other.getSnapshot().items.filter(item => item.state === "再選択")).toHaveLength(5);
    // The kept rows survive another reload with their size and time.
    expect(reload().getSnapshot().items.find(item => item.name === "Rep1/treated/solo_c1.tif")).toMatchObject({state: "再選択", size: 2, modified: 1_700_000_000_009});
  });
  it("kept names that the file cannot tell apart are left to their own 「選択」 (independent review, round 5)", async () => {
    const storage = memoryStorage(), control = {run_id: "r1", group_id: "c", sample: null}, treated = {run_id: "r1", group_id: "t", sample: null};
    const first = createIntakeList({inspect: async value => judge(value), known: () => new Map(), storage});
    first.open("w");
    // The same name, size and time in two cells, with different content (files exported together).
    const twin = () => new File([new Uint8Array([5, 6])], "field1-C01.tif", {lastModified: 1_700_000_000_001});
    first.add([file("field1-C01.tif", 1)], control);
    first.add([twin()], treated);
    await settled(first);
    // Each reload starts from the names kept by the first page.
    const keptNames = storage.values.get("cytellect.intake.v1.w")!;
    const reload = () => {storage.setItem("cytellect.intake.v1.w", keptNames);const list = createIntakeList({inspect: async value => judge(value), known: () => new Map(), storage});list.open("w", true);return list;};
    const general = reload();
    general.add([file("field1-C01.tif", 1)]);
    await settled(general);
    // No cell is guessed: both rows wait, and the file is listed without a cell.
    expect(general.getSnapshot().items.map(item => [item.state === "再選択", item.target?.group_id ?? null])).toEqual([[true, "c"], [true, "t"], [false, null]]);
    // Chosen in 処理's cell, or with the row's own 「選択」, it is the researcher's choice.
    const cell = reload();
    cell.add([twin()], treated);
    await settled(cell);
    expect(cell.getSnapshot().items.map(item => [item.state === "再選択", item.target?.group_id ?? null])).toEqual([[true, "c"], [false, "t"]]);
    // A name kept without a size and time (an earlier version) is taken by the same name only, never by a file name inside a folder path.
    storage.setItem("cytellect.intake.v1.old", JSON.stringify(["Rep1/treated/old_c1.tif", "plain_c1.tif"]));
    const old = createIntakeList({inspect: async value => judge(value), known: () => new Map(), storage});
    old.open("old");
    old.add([file("old_c1.tif", 3), file("plain_c1.tif", 5)]);
    await settled(old);
    expect(old.getSnapshot().items.map(item => [item.name, item.state])).toEqual([["Rep1/treated/old_c1.tif", "再選択"], ["old_c1.tif", "追加待ち"], ["plain_c1.tif", "追加待ち"]]);
  });
  it("a copy whose original is removed from the list is no longer a copy: it becomes the image", async () => {
    const list = createIntakeList({inspect: async value => judge(value), known: () => new Map(), storage: null});
    list.add([file("BBBC007-a9-C01.tif", 1), file("copy/BBBC007-a9-C01.tif", 1)]);
    await settled(list);
    const [original, copy] = list.getSnapshot().items;
    expect(copy).toMatchObject({state: "同一内容", sameAs: "BBBC007-a9-C01.tif"});
    list.remove(original.id);
    await settled(list);
    expect(list.getSnapshot().items).toEqual([expect.objectContaining({name: "copy/BBBC007-a9-C01.tif", state: "追加待ち", sameAs: null})]);
  });
  it("finds a copy of a registered field, replaces an unreadable file in its row, and records a separate acquisition", async () => {
    const digest = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", new Uint8Array([1, 2]))), value => value.toString(16).padStart(2, "0")).join("");
    const list = createIntakeList({inspect: async value => judge(value), known: () => new Map([[digest, "BBBC007-a9"]]), storage: null});
    list.add([file("BBBC007-a9-C01.tif", 1), file("test-truncated-DRAQ.tif", 11)]);
    await settled(list);
    const [copy, broken] = list.getSnapshot().items;
    expect(copy).toMatchObject({state: "同一内容", sameAs: "BBBC007-a9"});
    list.replace(broken.id, file("A01-DRAQ.tif", 31));
    await settled(list);
    expect(list.getSnapshot().items[1]).toMatchObject({id: broken.id, name: "A01-DRAQ.tif", state: "追加待ち"});
    list.keepSeparately(copy.id);
    await settled(list);
    expect(list.getSnapshot().items[0]).toMatchObject({state: "追加待ち", separate: true});
  });
  it("names the files not yet added after a reload, without keeping their contents, and reports an empty choice", async () => {
    const storage = memoryStorage(), diagnose = vi.fn();
    const list = createIntakeList({inspect: async value => judge(value), known: () => new Map(), storage, diagnose});
    list.open("w1");
    expect(list.add([])).toEqual({received: 0, images: 0});
    list.add([file("BBBC007-a9-C01.tif", 1), file("BBBC007-a9-C02.tif", 3)]);
    await settled(list);
    expect(diagnose).toHaveBeenLastCalledWith({received: 2, relative_paths: 0, images: 2, listed: 2});
    expect(JSON.stringify(diagnose.mock.calls)).not.toContain("BBBC007");
    const reopened = createIntakeList({inspect: async value => judge(value), known: () => new Map(), storage});
    reopened.open("w1");
    expect(reopened.getSnapshot().items.map(item => [item.name, item.state, item.file])).toEqual([["BBBC007-a9-C01.tif", "再選択", null], ["BBBC007-a9-C02.tif", "再選択", null]]);
    // Choosing the file again takes the place of its row.
    reopened.add([file("BBBC007-a9-C01.tif", 1)]);
    await settled(reopened);
    expect(reopened.getSnapshot().items.map(item => item.state)).toEqual(["再選択", "追加待ち"]);
    reopened.clear();
    expect(storage.values.size).toBe(0);
  });
});
