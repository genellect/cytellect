/**
 * One shared workspace state (workspace redesign U01–U05).
 *
 * Automatic grouping, the adopted proposal and human corrections are separate
 * records. Adoption is not a record that every region was inspected. Field runs
 * are committed independently so a failure never discards other results.
 */
import { chooseNuclearChannel, nameChannel, type Grouping } from "./grouping";
import { buildProposal, type DesignInfo, type Proposal } from "./proposal";

export type FieldStatus = "waiting" | "running" | "done" | "failed";

export interface Region { region_id: number; [metric: string]: number }
export interface Outline { id: string; points: [number, number][] }

export interface FieldResult {
  measurements: Region[];
  outlines: Outline[] | null;
}

export interface Correction {
  kind: "exclude" | "delete";
  field: string;
  region: number;
  /** Who made the record: automatic records never use this type. */
  origin: "user";
}

export interface FigureSettings {
  metric: string;
  widthMm: number;
  heightMm: number;
  yLabel: string;
  order: string[];
}

export type Selection =
  | { view: "image"; field: string; region?: number }
  | { view: "figure"; figure: string; field?: string; region?: number };

export interface WorkspaceState {
  name: string;
  goal: string;
  grouping: Grouping | null;
  /** User statements about channels, kept with the automatic evidence they override. */
  channelHistory: { token: string; change: "nuclear" | "name"; value: string }[];
  design: DesignInfo;
  proposal: Proposal | null;
  adopted: { proposal: Proposal; inputFields: string[] } | null;
  runs: Record<string, { status: FieldStatus; error?: string }>;
  results: Record<string, FieldResult>;
  corrections: Correction[];
  redo: Correction[];
  figure: FigureSettings;
  selection: Selection | null;
  stopped: boolean;
}

export type Action =
  | { type: "imported"; name: string; grouping: Grouping }
  | { type: "goal"; goal: string }
  | { type: "choose-nuclear"; token: string }
  | { type: "name-channel"; token: string; stain: string }
  | { type: "design"; design: DesignInfo }
  | { type: "adopt" }
  | { type: "field-started"; field: string }
  | { type: "field-done"; field: string; result: FieldResult }
  | { type: "field-failed"; field: string; error: string }
  | { type: "retry"; field: string }
  | { type: "stop" }
  | { type: "correct"; correction: Omit<Correction, "origin"> }
  | { type: "undo" }
  | { type: "redo" }
  | { type: "select"; selection: Selection | null }
  | { type: "figure"; settings: Partial<FigureSettings> };

export function initialState(): WorkspaceState {
  return {
    name: "", goal: "", grouping: null, channelHistory: [], design: { conditions: {}, units: {} },
    proposal: null, adopted: null, runs: {}, results: {}, corrections: [], redo: [],
    figure: { metric: "area_px", widthMm: 89, heightMm: 60, yLabel: "", order: [] },
    selection: null, stopped: false,
  };
}

export type Phase = "empty" | "proposal" | "running" | "results";

export function phase(state: WorkspaceState): Phase {
  if (!state.grouping) return "empty";
  if (!state.adopted) return "proposal";
  const statuses = Object.values(state.runs).map((run) => run.status);
  return !state.stopped && statuses.some((status) => status === "waiting" || status === "running") ? "running" : "results";
}

export function reducer(state: WorkspaceState, action: Action): WorkspaceState {
  switch (action.type) {
    case "imported": {
      const grouping = action.grouping;
      return { ...initialState(), name: action.name, goal: state.goal, grouping, proposal: buildProposal(grouping),
        figure: { ...state.figure, order: grouping.fields.map((field) => field.key) } };
    }
    case "goal":
      return { ...state, goal: action.goal };
    case "choose-nuclear": {
      if (!state.grouping || state.adopted) return state;
      const grouping = chooseNuclearChannel(state.grouping, action.token);
      return { ...state, grouping, proposal: buildProposal(grouping, state.design),
        channelHistory: [...state.channelHistory, { token: action.token, change: "nuclear", value: action.token }] };
    }
    case "name-channel": {
      if (!state.grouping || state.adopted) return state;
      const grouping = nameChannel(state.grouping, action.token, action.stain);
      return { ...state, grouping, proposal: buildProposal(grouping, state.design),
        channelHistory: [...state.channelHistory, { token: action.token, change: "name", value: action.stain.trim() }] };
    }
    case "design":
      return { ...state, design: action.design, proposal: state.grouping ? buildProposal(state.grouping, action.design) : null };
    case "adopt": {
      if (!state.grouping || !state.proposal?.recipe || state.proposal.unresolved.length || state.adopted) return state;
      const fields = state.grouping.fields.map((field) => field.key);
      return { ...state, adopted: { proposal: state.proposal, inputFields: fields }, stopped: false,
        runs: Object.fromEntries(fields.map((field) => [field, { status: "waiting" as const }])),
        selection: { view: "image", field: fields[0] } };
    }
    case "field-started":
      return state.stopped ? state : { ...state, runs: { ...state.runs, [action.field]: { status: "running" } } };
    case "field-done":
      return { ...state, runs: { ...state.runs, [action.field]: { status: "done" } },
        results: { ...state.results, [action.field]: action.result } };
    case "field-failed":
      return { ...state, runs: { ...state.runs, [action.field]: { status: "failed", error: action.error } } };
    case "retry":
      return state.runs[action.field]?.status === "failed"
        ? { ...state, stopped: false, runs: { ...state.runs, [action.field]: { status: "waiting" } } } : state;
    case "stop":
      return { ...state, stopped: true };
    case "correct": {
      const correction: Correction = { ...action.correction, origin: "user" };
      if (!state.results[correction.field]?.measurements.some((row) => row.region_id === correction.region)) return state;
      if (state.corrections.some((item) => item.field === correction.field && item.region === correction.region && item.kind === correction.kind)) return state;
      return { ...state, corrections: [...state.corrections, correction], redo: [] };
    }
    case "undo": {
      const last = state.corrections.at(-1);
      return last ? { ...state, corrections: state.corrections.slice(0, -1), redo: [...state.redo, last] } : state;
    }
    case "redo": {
      const next = state.redo.at(-1);
      return next ? { ...state, corrections: [...state.corrections, next], redo: state.redo.slice(0, -1) } : state;
    }
    case "select":
      return { ...state, selection: action.selection };
    case "figure":
      // Styling only: never touches runs, results or corrections.
      return { ...state, figure: { ...state.figure, ...action.settings } };
  }
}

/** Region state after corrections; deleted regions disappear, excluded ones stay visible. */
export function regionState(state: WorkspaceState, field: string, region: number): "included" | "excluded" | "deleted" {
  const records = state.corrections.filter((item) => item.field === field && item.region === region);
  if (records.some((item) => item.kind === "delete")) return "deleted";
  if (records.some((item) => item.kind === "exclude")) return "excluded";
  return "included";
}

/** Fields whose derived results depend on a correction; others are untouched. */
export function affectedFields(state: WorkspaceState): Set<string> {
  return new Set(state.corrections.map((item) => item.field));
}

export function progress(state: WorkspaceState): { done: number; failed: number; total: number } {
  const runs = Object.values(state.runs);
  return { done: runs.filter((run) => run.status === "done").length, failed: runs.filter((run) => run.status === "failed").length, total: runs.length };
}
