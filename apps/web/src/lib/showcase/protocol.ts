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
