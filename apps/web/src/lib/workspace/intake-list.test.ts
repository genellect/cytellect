import {describe, expect, it, vi} from "vitest";
import {additions, breakdown, createIntakeList, listedFields, matchingFields, type Inspection} from "./intake-list";

/** Synthetic bytes: the names decide the grouping and the mocked judgement decides the role (W4 is tested on its own). */
const file = (name: string, byte: number) => new File([new Uint8Array([byte, byte + 1])], name);
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
