import type {ExperimentDesign} from "../../../lib/workspace/experiment-design";
import type {ResultOperation} from "./connected-results-model";

/** What a statistics request states, read from the work done before 統計 (genellect/cytellect#257 decision 11, owner,
 * 2026-11-21). With a declared design 統計 has no confirmation of its own: the regions and fields are those adopted in
 * 画像, the acquisition and pixel settings and the runs' independence are declared in 実験 (pairing follows the declared
 * layout), and nuclei without an established nucleolus stay as missing under `unresolved-as-missing/1.0.0`, counted in
 * the result's n. A workspace registered without a design has no place to declare them, so its typed groups and units
 * keep the confirmation in 統計 (owner decision on #273, 2026-11-21; Issue judgement 3). */
export interface Declarations {
  /** Every included field has an adopted measurement of the region (画像). */
  regions:boolean;
  /** 実験：各実験回は独立に行った. Without it a comparison is described, never tested (E-05). */
  independence:boolean;
  /** 実験：群の間で撮影・画素条件を比べられる. It backs the acquisition review of a comparison or an association (S10). */
  acquisition:boolean;
  /** The same statement covers the pixel size, so it also backs the spatial sampling of areas, integrals and counts. */
  sampling:boolean;
  /** Missing values follow the saved policies and are shown in the result's n breakdown (decision 11). */
  missingness:boolean;
}

export interface DeclarationSource {
  demo:boolean;experiment:ExperimentDesign|null|undefined;unmeasured:number;
  /** Without a declared design: the confirmation ticked in 統計 for the typed groups, units and acquisition. */
  typedConfirmed?:boolean;
}

export function declarations({demo,experiment,unmeasured,typedConfirmed=false}:DeclarationSource):Declarations {
  const independence=!!experiment?.independence_confirmed;
  // The public demo calculates with the confirmations its tour recorded (decision 2): its requests are replayed as
  // recorded, and nothing is declared for the public data on the visitor's behalf. A recorded scene without a design
  // was recorded with the tour's own confirmation of its units, as before.
  if(demo)return {regions:true,independence:experiment?independence:true,acquisition:true,sampling:true,missingness:true};
  // Typed groups and units: the one confirmation in 統計 states the units, the acquisition settings and their sampling.
  if(!experiment)return {regions:unmeasured===0,independence:typedConfirmed,acquisition:typedConfirmed,sampling:typedConfirmed,missingness:true};
  const acquisition=!!experiment.acquisition_confirmed;
  return {regions:unmeasured===0,independence,acquisition,sampling:acquisition,missingness:true};
}

/** The one piece of earlier work a result still waits for, named as 「画面：項目 値」 and opened with →. */
export interface RemainingWork {screen:"experiment"|"image";label:string}

/** The first remaining item, in the order of the screens (実験 → 画像); null when nothing earlier is missing. A design
 * declared without the acquisition statement waits for 実験; a workspace without a design is confirmed in 統計 itself,
 * so it waits for nothing earlier but its measurements. A description of the fields (分布) needs only the measurements.
 * The demo never asks. */
export function remainingWork({demo,experiment,unmeasured,operation}:DeclarationSource&{operation:ResultOperation}):RemainingWork|null {
  if(demo)return null;
  if(operation!=="distribution"&&experiment&&!experiment.acquisition_confirmed)return {screen:"experiment",label:"実験：撮影条件 未確認"};
  if(unmeasured>0)return {screen:"image",label:`画像：未測定 ${unmeasured} 視野`};
  return null;
}
