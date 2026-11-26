/** The list of chosen files before they are added (#284 W5). It lives outside the runtime's one-at-a-time lock, so
 * files can be chosen and judged while images register or an analysis runs. Each file is judged by the API's own
 * readers (W4, nothing stored); the list shows role and state per file, and its breakdown adds up to what was
 * received. Names of files not yet added are kept for this tab (sessionStorage) and shown again after a reload as
 * 「再選択」: the browser cannot keep the files themselves. */
import type {IntakeTarget} from "./api-adapter";
import {intakePath} from "./dropped-files";
import {groupFiles, isSupportedImage, type AddedFile} from "./grouping";
import {tiffHasOmeMetadata, tiffInputMode} from "./tiff-intake";

/** The registration route of a file, and what the API's judgement returns (W4, `POST /v1/intake/inspect`). */
export type IntakeKind = "native" | "display-rgb" | "ome";
export interface Inspection {role: "image" | "label" | "unreadable"; code?: string | null; shape?: number[] | null; channel_names?: Array<string | null> | null; thumbnail_png?: string | null}
export type ItemState = "読み込み中" | "追加待ち" | "マスクの候補" | "対象外" | "読み取れない" | "同一内容" | "再選択";
export interface IntakeItem {
  id: string; name: string; file: File | null; size: number; state: ItemState;
  /** Registration's reason code when the file is unreadable or a label image. */
  code: string | null;
  shape: number[] | null; thumbnail: string | null; channelNames: string[]; sha256: string | null;
  /** The name of the file or field with the same bytes (同一内容). */
  sameAs: string | null;
  /** 「別の撮影として追加」 recorded for a copy. */
  separate: boolean;
  /** The selection the file came with (1, 2, …), for 「直前の選択を取り消し」. */
  selection: number;
  /** The run and group of the cell it was added from, or null. */
  target: IntakeTarget | null;
}
export interface IntakeListState {items: IntakeItem[]; selections: number}
export interface ListedField {
  key: string; name: string; channels: string[]; items: IntakeItem[]; loading: boolean; thumbnail: string | null;
  /** A field whose names are already in the list from an earlier selection (or a copy kept as a separate
   * acquisition): it is added as its own field, never merged into the earlier one. */
  repeated: boolean;
  /** Two files of different content for the same channel of this field: the researcher keeps one before it is added. */
  conflicts: Array<{channel: string; items: IntakeItem[]}>;
}
/** The images one call of registration receives together. */
export interface Addition {items: IntakeItem[]; separate: boolean; repeated: boolean}
export interface IntakeDependencies {
  inspect: (file: File, kind: IntakeKind) => Promise<Inspection>;
  /** Hashes of the inputs of registered fields, with the field's name (copies are found against them too). */
  known: () => Map<string, string>;
  storage?: Pick<Storage, "getItem" | "setItem" | "removeItem"> | null;
  /** Development builds report counts only (Issue input 6, step 2); never names or paths. */
  diagnose?: (counts: Record<string, number>) => void;
}

// One judgement at a time: judging and registering share the upload guard's two concurrent slots.
const LIMIT = 256 * 1024 * 1024, CONCURRENT = 1;
const storageKey = (workspace: string | null) => `cytellect.intake.v1.${workspace ?? "new"}`;
const hex = (digest: ArrayBuffer) => Array.from(new Uint8Array(digest), value => value.toString(16).padStart(2, "0")).join("");

export function createIntakeList(dependencies: IntakeDependencies) {
  let state: IntakeListState = {items: [], selections: 0}, workspace: string | null = null;
  const listeners = new Set<() => void>(), queue: IntakeItem[] = [];
  let running = 0;
  const publish = (items: IntakeItem[], selections = state.selections) => {
    state = {items, selections};
    try {
      const names = items.filter(item => item.state === "追加待ち" || item.state === "読み込み中" || item.state === "再選択").map(item => item.name);
      if (names.length) dependencies.storage?.setItem(storageKey(workspace), JSON.stringify(names)); else dependencies.storage?.removeItem(storageKey(workspace));
    } catch {/* storage is a convenience only */}
    for (const listener of listeners) listener();
  };
  const update = (id: string, patch: Partial<IntakeItem>) => publish(state.items.map(item => item.id === id ? {...item, ...patch} : item));
  async function judge(item: IntakeItem) {
    const file = item.file!;
    try {
      const kind: IntakeKind = await tiffHasOmeMetadata(file) ? "ome" : await tiffInputMode(file);
      const digest = hex(await crypto.subtle.digest("SHA-256", await file.arrayBuffer()));
      const same = dependencies.known().get(digest) ?? state.items.find(other => other.id !== item.id && other.sha256 === digest && other.state !== "同一内容" && other.selection <= item.selection)?.name;
      if (same && !item.separate) {update(item.id, {sha256: digest, state: "同一内容", sameAs: same}); return;}
      const found = await dependencies.inspect(file, kind);
      update(item.id, {sha256: digest, code: found.code ?? null, shape: found.shape ?? null, channelNames: (found.channel_names ?? []).map((name, index) => name?.trim() || `c${index + 1}`),
        thumbnail: found.thumbnail_png ? `data:image/png;base64,${found.thumbnail_png}` : null,
        state: found.role === "image" ? "追加待ち" : found.role === "label" ? "マスクの候補" : "読み取れない"});
    } catch (error) {
      // A refusal of this file names its reason; an unanswered judgement leaves the file to registration's own check.
      const code = typeof error === "object" && error && "code" in error && typeof (error as {code: unknown}).code === "string" ? (error as {code: string}).code : null;
      const status = typeof error === "object" && error && "status" in error ? (error as {status: number}).status : 0;
      update(item.id, [403, 413, 415, 422].includes(status) && code ? {state: "読み取れない", code} : {state: "追加待ち"});
    }
  }
  function pump() {
    while (running < CONCURRENT && queue.length) {
      const item = queue.shift()!;running++;
      void judge(item).finally(() => {running--;pump();});
    }
  }
  return {
    subscribe(listener: () => void) {listeners.add(listener);return () => {listeners.delete(listener);};},
    getSnapshot: () => state,
    /** Opens the list of a workspace: names chosen there and not added before a reload come back as 「再選択」. */
    open(id: string | null) {
      workspace = id;let names: string[] = [];
      try {names = JSON.parse(dependencies.storage?.getItem(storageKey(id)) ?? "[]");} catch {names = [];}
      publish(Array.isArray(names) ? names.filter(name => typeof name === "string").map((name, index) => ({...blank(`restored-${index}`, name, 0), state: "再選択" as const})) : [], 0);
    },
    /** Moves the names kept for a new workspace to the workspace it became. */
    rename(id: string) {const items = state.items;workspace = id;try {dependencies.storage?.removeItem(storageKey(null));} catch {/* convenience */}publish(items);},
    /** Adds one selection (a file choice, a folder or a drop). An empty choice is reported, never silent. */
    add(list: File[], target: IntakeTarget | null = null): {received: number; images: number} {
      const selection = state.selections + 1;
      const fresh = list.map(file => {
        const name = intakePath(file);
        const item = {...blank(crypto.randomUUID(), name, selection), file, size: file.size, target};
        if (!isSupportedImage(name)) return {...item, state: "対象外" as const};
        if (file.size > LIMIT) return {...item, state: "読み取れない" as const, code: "field_upload_limit"};
        return item;
      });
      dependencies.diagnose?.({received: list.length, relative_paths: list.filter(file => (file.webkitRelativePath || intakePath(file)).includes("/")).length,
        images: fresh.filter(item => item.state === "読み込み中").length, listed: state.items.length + fresh.length});
      // A file chosen again under a restored name takes the place of its 「再選択」 row.
      const restored = new Set(fresh.map(item => item.name));
      publish([...state.items.filter(item => !(item.state === "再選択" && restored.has(item.name))), ...fresh], list.length ? selection : state.selections);
      for (const item of fresh) if (item.state === "読み込み中") queue.push(item);
      pump();
      return {received: list.length, images: fresh.filter(item => item.state === "読み込み中").length};
    },
    remove(id: string) {publish(state.items.filter(item => item.id !== id));},
    /** Takes back the latest selection only (Issue input 3: 「その時点で選んだ操作だけを戻せる」). */
    undoLast() {const last = Math.max(0, ...state.items.map(item => item.selection));if (last) publish(state.items.filter(item => item.selection !== last));},
    /** Chooses a file again for one row (a file that could not be read, or a 「再選択」 row). */
    replace(id: string, file: File) {
      const old = state.items.find(item => item.id === id);if (!old) return;
      const name = intakePath(file), item = {...blank(id, name, old.selection), file, size: file.size, target: old.target};
      const next = !isSupportedImage(name) ? {...item, state: "対象外" as const} : file.size > LIMIT ? {...item, state: "読み取れない" as const, code: "field_upload_limit"} : item;
      publish(state.items.map(value => value.id === id ? next : value));
      if (next.state === "読み込み中") {queue.push(next);pump();}
    },
    /** Records that a copy is a separate acquisition; it is then judged and added like any image. */
    keepSeparately(id: string) {const item = state.items.find(value => value.id === id);if (!item?.file) return;const next = {...item, separate: true, state: "読み込み中" as const, sameAs: null};update(id, next);queue.push(next);pump();},
    /** Removes the given rows (after they were added or recorded). */
    clear(ids?: Iterable<string>) {const gone = ids ? new Set(ids) : null;publish(gone ? state.items.filter(item => !gone.has(item.id)) : []);},
  };
}

function blank(id: string, name: string, selection: number): IntakeItem {
  return {id, name, file: null, size: 0, state: "読み込み中", code: null, shape: null, thumbnail: null, channelNames: [], sha256: null, sameAs: null, separate: false, selection, target: null};
}

const added = (item: IntakeItem): AddedFile => ({path: item.name, size: item.size, ...(item.sha256 ? {sha256: item.sha256} : {}), ...(item.channelNames.length ? {omeChannels: item.channelNames} : {})});

/**
 * The images of the list in the additions registration receives (W5 change 4; the list and registration use this one
 * split, so the list shows the fields that will be made). Every selection is added together, so another stain of the
 * same field chosen later joins it. Files whose names are already in the list from an earlier selection (the same file
 * names in another condition's folder, chosen one folder at a time) are not that field again: with the rest of their
 * field in that selection they form an addition of their own. A copy kept as a separate acquisition is added alone.
 */
export function additions(items: readonly IntakeItem[]): Addition[] {
  const images = items.filter(item => (item.state === "追加待ち" || item.state === "読み込み中") && item.file), plain = images.filter(item => !item.separate);
  const grouping = groupFiles([...new Map(plain.map(item => [item.name, added(item)])).values()]), keys = new Map<string, string>();
  for (const field of grouping.fields) for (const file of Object.values(field.files)) keys.set(file.path, field.key);
  for (const issue of grouping.issues) if (issue.kind === "duplicate_channel") for (const path of issue.paths) keys.set(path, issue.field);
  const keyOf = (item: IntakeItem) => keys.get(item.name) ?? item.name;
  const first: IntakeItem[] = [], later = new Map<number, IntakeItem[]>(), seen = new Set<string>();
  for (const selection of [...new Set(plain.map(item => item.selection))].sort((a, b) => a - b)) {
    const mine = plain.filter(item => item.selection === selection), again = new Set(mine.filter(item => seen.has(item.name)).map(keyOf));
    for (const item of mine) {
      if (again.has(keyOf(item))) later.set(selection, [...(later.get(selection) ?? []), item]);
      else first.push(item);
    }
    for (const item of mine) seen.add(item.name);
  }
  return [{items: first, separate: false, repeated: false}, ...[...later.values()].map(value => ({items: value, separate: false, repeated: true})),
    ...images.filter(item => item.separate).map(item => ({items: [item], separate: true, repeated: true}))].filter(value => value.items.length);
}

/** The images of the list as the fields they will make, addition by addition. The grouping is the one registration uses. */
export function listedFields(items: readonly IntakeItem[]): ListedField[] {
  return additions(items).flatMap((addition, index) => {
    const pathToItem = new Map(addition.items.map(item => [item.name, item])), grouping = groupFiles(addition.items.map(added));
    return grouping.fields.map(field => {
      const conflicts = grouping.issues.flatMap(issue => issue.kind === "duplicate_channel" && issue.field === field.key
        ? [{channel: issue.token, items: issue.paths.map(path => pathToItem.get(path)!).filter(Boolean)}] : []);
      const members = [...new Set([...Object.values(field.files).map(file => pathToItem.get(file.path)!), ...conflicts.flatMap(value => value.items)].filter(Boolean))];
      return {key: `${index}:${field.key}`, name: field.key.split("/").at(-1) || field.key, channels: Object.keys(field.files), items: members,
        loading: members.some(item => item.state === "読み込み中"), thumbnail: members.find(item => item.thumbnail)?.thumbnail ?? null,
        repeated: addition.repeated, conflicts};
    });
  });
}

/** One status line whose parts add up to what was received (Issue input 5). */
export function breakdown(items: readonly IntakeItem[]): string {
  const received = items.filter(item => item.state !== "再選択").length;
  if (!received && !items.length) return "";
  const count = (state: ItemState) => items.filter(item => item.state === state).length;
  const images = count("追加待ち") + count("読み込み中"), fields = listedFields(items).length;
  const parts = [`受け取り：${received}`, `画像：${images}（${fields} 視野）`];
  for (const state of ["マスクの候補", "同一内容", "読み取れない", "対象外", "再選択"] as const) if (count(state)) parts.push(`${state}：${count(state)}`);
  return parts.join(" · ");
}

/** The fields (registered or listed) whose size matches a mask candidate (W5 change 9); its use is not inferred. */
export function matchingFields(mask: IntakeItem, items: readonly IntakeItem[], registered: ReadonlyArray<{name: string; shape: readonly number[]}>): string[] {
  if (!mask.shape) return [];
  const same = (shape: readonly number[] | null) => !!shape && shape.length >= 2 && shape.at(-2) === mask.shape!.at(-2) && shape.at(-1) === mask.shape!.at(-1);
  const listed = listedFields(items).filter(field => field.items.some(item => same(item.shape))).map(field => field.name);
  return [...new Set([...listed, ...registered.filter(field => same(field.shape)).map(field => field.name)])];
}
