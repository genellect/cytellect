/** Web Worker that hosts the in-browser API. Requests are handled strictly one at a time. */
import type {WorkerInbound, WorkerOutbound} from "./protocol";
import {bootDevelopmentRuntime, bootPyodideRuntime, type PyodideLike, type RuntimeHandle} from "./worker-runtime";

const scope = self as unknown as {postMessage(message: WorkerOutbound, transfer?: Transferable[]): void; onmessage: ((event: MessageEvent<WorkerInbound>) => void) | null; location: Location};
let runtime: RuntimeHandle | null = null;
let queue: Promise<unknown> = Promise.resolve();

async function loadPyodide(indexURL: string): Promise<PyodideLike> {
  // The interpreter comes from the pinned CDN in runtime-config.json; the bundler must not resolve it.
  const pyodideModule = await import(/* webpackIgnore: true */ /* turbopackIgnore: true */ `${indexURL}pyodide.mjs`) as {loadPyodide(options: {indexURL: string}): Promise<PyodideLike>};
  return pyodideModule.loadPyodide({indexURL});
}

async function receive(message: WorkerInbound) {
  if (message.type === "boot") {
    try {
      runtime = message.devBackend
        ? await bootDevelopmentRuntime(message.devBackend, message.origin)
        : await bootPyodideRuntime(message.config, message.origin, {fetcher: fetch.bind(self), loadPyodide, base: `${scope.location.origin}/showcase/`});
      scope.postMessage({type: "booted", id: message.id});
    } catch (error) {
      scope.postMessage({type: "failed", id: message.id, code: error instanceof Error && /^showcase_[a-z_]+$/.test(error.message) ? error.message : "showcase_engine_unavailable"});
    }
    return;
  }
  if (!runtime) {scope.postMessage({type: "failed", id: message.id, code: "showcase_engine_unavailable"}); return;}
  try {
    const response = await runtime.handle(message.request);
    scope.postMessage({type: "response", id: message.id, response}, [response.body]);
  } catch {
    scope.postMessage({type: "failed", id: message.id, code: "showcase_engine_unavailable"});
  }
}

scope.onmessage = event => {queue = queue.then(() => receive(event.data), () => receive(event.data));};
