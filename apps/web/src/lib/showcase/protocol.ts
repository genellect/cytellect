/** Shared shapes of the public showcase transport (docs/showcase.md). */

export type HeaderList = Array<[string, string]>;
/** One API request as `cytellect_showcase.runtime.handle` receives it. */
export interface ShowcaseRequest {method: string; url: string; headers: HeaderList; body: ArrayBuffer | null}
/** The runtime's response: `{"status": int, "headers": [[name, value], ...], "body": bytes}`. */
export interface ShowcaseResponse {status: number; headers: HeaderList; body: ArrayBuffer}

/** `apps/web/src/lib/showcase/runtime-config.json`, written by the runtime build. */
export interface RuntimeConfig {
  pyodideVersion: string; indexURL: string; packages: string[];
  wheels: Array<{file: string; sha256: string}>; fonts: Array<{file: string; sha256: string}>;
}

/** `snapshot/journal.json`: the demo tour recorded in order through the in-browser API, scene by scene.
 *  `body` is the request body (JSON text) with client-generated identifiers written as "*"; null matches any body.
 *  `PUT .../analysis-spec` entries record the settings later runs of the scene were measured under. */
export interface JournalEntry {scene?: string; method: string; path: string; pattern?: string; body: string | null; status: number; headers: HeaderList; file: string | null}
export interface Journal {version: 1; entries: JournalEntry[]}
/** `snapshot/journal.json` of a tour split into parts (one per scene, each a {@link Journal}), because the whole tour
 *  is larger than a file may be on GitHub. Read in order, the parts are the tour (services/showcase journal_files.py). */
export interface JournalIndex {
  version: 2; parts: string[];
  /** For each part, its number of entries and the workspaces its paths name (written only when no workspace is named
   *  by the parts of two scenes): the scene of the open workspace is read first and answers its own changes. */
  counts?: number[]; workspaces?: string[][];
}

/** `snapshot/figures.json`: the figures of the tour's results, drawn by the production renderer from the
 *  recorded results (services/showcase figure_catalog.py). A figure request is answered by the result it
 *  draws and its settings, not by its text, so the figure controls can change without recording the tour again.
 *  A group holds the figures of results with the same values; `figures[0]` is the opening figure as a request. */
export interface CatalogFigure {plot: unknown; figure: unknown; files: Record<string, string>}
export interface FigureCatalog {
  version: 1;
  groups: Record<string, {observations: string; opening: CatalogFigure; figures: CatalogFigure[]}>;
  /** Statistics jobs (recorded in the tour, or saved in the seed) and the group that draws them. */
  sources: Record<string, {group: string; workspace: string; revision: string; seed?: boolean}>;
  /** Figures the seed saved (「保存した図」), drawn anew with the settings each was saved with. */
  saved?: Record<string, {source: string; figure: unknown; plot: unknown; files: Record<string, string>}>;
  /** Publication packages of a figure of the group of `source`, with the recorded analysis export. */
  packages: Array<{source: string; figure: number; analysis: string; files: Record<string, string>}>;
}

/** `snapshot/index.json`: recorded initial GET responses. */
export interface SnapshotIndex {version: 1; entries: Record<string, {status: number; headers: HeaderList; file: string}>}

export interface BootMessage {type: "boot"; id: number; origin: string; config: RuntimeConfig; devBackend: string | null}
export interface HandleMessage {type: "handle"; id: number; request: ShowcaseRequest}
export type WorkerInbound = BootMessage | HandleMessage;
export type WorkerOutbound =
  | {type: "booted"; id: number}
  | {type: "response"; id: number; response: ShowcaseResponse}
  | {type: "failed"; id: number; code: string};

/** Codes the UI shows as information, never as an error. */
export const SHOWCASE_NOTICE_CODES = [
  "showcase_detection_not_recorded", "showcase_proposal_not_recorded", "showcase_upload_disabled",
  "showcase_engine_unavailable", "showcase_unavailable", "showcase_action_not_recorded",
] as const;
export type ShowcaseNoticeCode = typeof SHOWCASE_NOTICE_CODES[number];
