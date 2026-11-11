import type {MeasurementRow} from "@/lib/workspace/api-adapter";
import type {ColorBy,NextComparison} from "@/lib/workspace/color-by";
import type {Point} from "@/lib/types";
import type {RegionClassification} from "./ReviewImageCanvas";
import type {NucleusTableGate} from "./nucleus-table-model";
import styles from "./connected-workspace.module.css";

/** The one next step beside a table (MV-09): the comparison of groups the colour mode leads to. */
export type NextAction=NextComparison&{disabled:boolean;onClick:()=>void};

/** How a stage colours and lists one field (MV-01–MV-09): computed by the workspace, read by the single and pair stages. */
export interface ColorView {
  colorBy:ColorBy;
  states:(fieldId:string)=>Record<number,RegionClassification>|undefined;
  legend:(fieldId:string)=>Array<{key:string;label:string;count?:number}>|undefined;
  fills:(fieldId:string)=>Array<{id:number;points:Point[]}>|undefined;
  gateTable:(fieldId:string)=>NucleusTableGate|undefined;
  heading:(nucleusTable:boolean,rows:MeasurementRow[])=>string;
  next:NextAction|null;
}

/** A table's heading, naming per what, which stain and which values (MV-06), with the next step on its right (MV-09). */
export function TableHeading({heading,next}:{heading:string;next?:NextAction|null}){
  return <div className={styles.tableHeading}><h3>{heading}</h3>{next&&<span className={styles.nextStep}><button type="button" disabled={next.disabled} title={next.disabled?"陽性・陰性を判定すると比べられます":next.note} onClick={next.onClick}>{next.label} →</button>{next.note&&!next.disabled&&<small>{next.note}</small>}</span>}</div>;
}
