import {describe, expect, it} from "vitest";
import {droppedFiles, intakePath, type DropSource} from "./dropped-files";

// Stand-ins for the browser's file system entries: names and bytes only, no image content.
const tif = (name: string) => new File([new Uint8Array([1, 2, 3])], name, {type: "image/tiff"});
const fileEntry = (fullPath: string, file: File) => ({isFile: true, isDirectory: false, fullPath, name: file.name, file: (done: (value: File) => void) => done(file)});
/** A folder whose reader hands out one entry per call, then an empty batch. */
const folderEntry = (fullPath: string, children: unknown[]) => ({isFile: false, isDirectory: true, fullPath, name: fullPath.split("/").at(-1),
  createReader: () => {let next = 0; return {readEntries: (done: (value: unknown[]) => void) => done(children.slice(next, ++next))};}});
const item = (entry: unknown, file: File | null) => ({kind: "file" as const, getAsFile: () => file, webkitGetAsEntry: () => entry as FileSystemEntry});

describe("dropped files", () => {
  it("reads a dropped folder recursively and keeps each file's path inside it, as the folder button does", async () => {
    const top = tif("A01_DAPI.tif"), nested = tif("A01_NCL.tif");
    const folder = folderEntry("/plate", [fileEntry("/plate/A01_DAPI.tif", top), folderEntry("/plate/run2", [fileEntry("/plate/run2/A01_NCL.tif", nested)])]);
    // A folder item also offers an empty File; it is not added.
    const files = await droppedFiles({items: [item(folder, new File([], "plate"))], files: []});
    expect(files.map(intakePath).sort()).toEqual(["plate/A01_DAPI.tif", "plate/run2/A01_NCL.tif"]);
  });

  it("adds dropped files by name and ignores dropped text", async () => {
    const first = tif("B02_c1.tif"), second = tif("B02_c2.tif");
    const text = {kind: "string" as const, getAsFile: () => null, webkitGetAsEntry: () => null};
    const files = await droppedFiles({items: [item(fileEntry("/B02_c1.tif", first), first), text, item(null, second)], files: [first, second]} as DropSource);
    expect(files).toEqual([first, second]);
    expect(files.map(intakePath)).toEqual(["B02_c1.tif", "B02_c2.tif"]);
  });

  it("uses the dropped file list where the browser offers no items", async () => {
    const only = tif("C03.tif");
    expect(await droppedFiles({files: [only]})).toEqual([only]);
  });
});
