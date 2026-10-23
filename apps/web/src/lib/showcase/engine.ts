/** Main-thread side of the in-browser API: one dedicated Web Worker, one request at a time. */
import type {RuntimeConfig, ShowcaseRequest, ShowcaseResponse, WorkerInbound, WorkerOutbound} from "./protocol";
import type {ShowcaseEngine} from "./transport";

type Waiting = {resolve: (value: WorkerOutbound) => void; reject: (error: Error) => void};

export function createWorkerEngine(config: RuntimeConfig, devBackend: string | null): ShowcaseEngine | null {
  // Local (Windows) builds use the real API; this inlined constant drops the worker from their export.
  if (process.env.NEXT_PUBLIC_CYTELLECT_WEB_MODE === "local") return null;
  if (!devBackend && !config.indexURL) return null;
  let worker: Worker | null = null, sequence = 0;
  const waiting = new Map<number, Waiting>();
  function fail(error: Error) {for (const entry of waiting.values()) entry.reject(error); waiting.clear();}
  function call(message: WorkerInbound, transfer: Transferable[] = []) {
    if (!worker) return Promise.reject(new Error("showcase_engine_unavailable"));
    return new Promise<WorkerOutbound>((resolve, reject) => {
      waiting.set(message.id, {resolve, reject});
      worker!.postMessage(message, transfer);
    });
  }
  return {
    async start() {
      worker = new Worker(new URL("./python-worker.ts", import.meta.url), {type: "module", name: "cytellect-showcase"});
      worker.onmessage = (event: MessageEvent<WorkerOutbound>) => {
        const entry = waiting.get(event.data.id);
        if (!entry) return;
        waiting.delete(event.data.id);
        if (event.data.type === "failed") entry.reject(new Error(event.data.code)); else entry.resolve(event.data);
      };
      worker.onerror = event => {event.preventDefault(); fail(new Error("showcase_engine_unavailable"));};
      try {await call({type: "boot", id: ++sequence, origin: location.origin, config, devBackend});}
      catch (error) {worker.terminate(); worker = null; throw error;}
    },
    async handle(request: ShowcaseRequest): Promise<ShowcaseResponse> {
      const reply = await call({type: "handle", id: ++sequence, request}, request.body ? [request.body] : []);
      if (reply.type !== "response") throw new Error("showcase_engine_unavailable");
      return reply.response;
    },
  };
}
