/**
 * Files dropped on the workspace, for the same intake as the 画像 and フォルダ buttons. A dropped folder
 * is read recursively, and each of its files keeps its path inside the dropped folder, as the folder
 * button's `webkitRelativePath` does, so grouping reads the same folder names (grouping.ts).
 */

/** The part of a drop that is read: the items (folders included) where the browser offers them, else the files. */
export interface DropSource {
  items?: ArrayLike<Pick<DataTransferItem, "kind" | "getAsFile"> & {webkitGetAsEntry?: () => FileSystemEntry | null}>;
  files: ArrayLike<File>;
}

const relativePaths = new WeakMap<File, string>();
/** The path of a file to add: inside a dropped or chosen folder, else its name. */
export const intakePath = (file: File) => relativePaths.get(file) ?? (file.webkitRelativePath || file.name);

/** The dropped files; the items are taken at once, because a drop's items are readable only while its event runs. */
export function droppedFiles(transfer: DropSource): Promise<File[]> {
  const items = transfer.items ? Array.from(transfer.items).filter(item => item.kind === "file") : [];
  if (!items.length) return Promise.resolve(Array.from(transfer.files));
  const taken = items.map(item => ({entry: item.webkitGetAsEntry?.() ?? null, file: item.getAsFile()}));
  return Promise.all(taken.map(({entry, file}) => entry?.isDirectory ? folderFiles(entry as FileSystemDirectoryEntry) : Promise.resolve(file ? [file] : []))).then(lists => lists.flat());
}

async function folderFiles(folder: FileSystemDirectoryEntry): Promise<File[]> {
  const reader = folder.createReader(), entries: FileSystemEntry[] = [];
  // A folder's entries arrive in batches until an empty one.
  for (;;) {
    const batch = await new Promise<FileSystemEntry[]>((resolve, reject) => reader.readEntries(resolve, reject));
    if (!batch.length) break;
    entries.push(...batch);
  }
  const lists = await Promise.all(entries.map(entry => entry.isDirectory ? folderFiles(entry as FileSystemDirectoryEntry)
    : entry.isFile ? new Promise<File[]>((resolve, reject) => (entry as FileSystemFileEntry).file(file => {relativePaths.set(file, entry.fullPath.replace(/^\/+/, "")); resolve([file]);}, reject))
    : Promise.resolve([])));
  return lists.flat();
}
