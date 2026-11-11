"use client";
import {useEffect,useRef,useState,type ReactNode} from "react";
import type {NucleusTableData} from "@/lib/workspace/api-adapter";
import {nucleusTableKey,nucleusTableView,type NucleusTableChannel,type NucleusTableGate} from "./nucleus-table-model";
import styles from "./nucleus-table.module.css";

/** Every nucleus of one field in one row: area, each stain's signal and the nucleus's confirmed nucleoli.
 * The values come from the API; a row selects the nucleus on the image, and a nucleus chosen on the
 * image brings its row into view. Missing values show their reason, never a zero. */
export function NucleusTable({table,channels,gate,selected,onSelect,onSave,aside}:{table:NucleusTableData;channels:NucleusTableChannel[];gate?:NucleusTableGate;selected?:number;onSelect:(n:number)=>void;onSave?:()=>Promise<void>;
  /** A control that shares the summary line (the next step), so the rows keep their room. */aside?:ReactNode}){
  const body=useRef<HTMLTableSectionElement>(null);
  const [saving,setSaving]=useState(""),[saveError,setSaveError]=useState("");
  async function save(){if(!onSave||saving)return;setSaving("保存中…");setSaveError("");try{await onSave();}catch(error){setSaveError(error instanceof Error?error.message:String(error));}finally{setSaving("");}}
  useEffect(()=>{if(selected!==undefined)body.current?.querySelector("tr[aria-selected=true]")?.scrollIntoView({block:"nearest"});},[selected]);
  const view=nucleusTableView(table,channels,gate);
  return <>
    {/* The ledger accounts for every nucleus; it is one line that opens to its full text, beside the ZIP of the saved
        table (CSV with each column's unit and definition, and the JSON it was copied from), so the rows keep their room. */}
    <div className={styles.ledgerRow}><details className={styles.ledger}><summary aria-live="polite" title={view.ledger}>{view.ledger}</summary><p>{view.ledger}</p></details>
      {onSave&&<button type="button" className={styles.save} disabled={!!saving} onClick={()=>void save()} title="核ごとの表（CSV）、列の単位と定義（CSV）、元の値（JSON）を ZIP で保存">{saving||"CSV を保存"}</button>}{aside}</div>
    {saveError&&<p role="alert">保存できませんでした（{saveError}）。</p>}
    <table aria-label="核ごとの表"><thead><tr>{view.columns.map(column=><th key={column.key} title={column.title}>{column.label}</th>)}</tr></thead>
      <tbody ref={body}>{view.rows.map(row=><tr key={row.id} aria-selected={row.id===selected} data-excluded={row.excluded||undefined} data-gate={row.status}>
        <td><button onClick={()=>onSelect(row.id)}>{row.id}</button></td>
        {row.cells.map((cell,i)=><td key={view.columns[i+1].key} title={cell.title}>{cell.text}</td>)}
      </tr>)}</tbody>
    </table>
  </>;
}

/** Loads the nucleus table of the adopted nuclei (and nucleoli, when adopted) of one field. */
export function ConnectedNucleusTable({load,save,field,nuclearRevision,nucleolarRevision,exclusion,channels,gate,selected,onSelect,aside}:{
  load:(revision:string,field:string,nucleolarRevision?:string)=>Promise<NucleusTableData>;save?:(revision:string,field:string,nucleolarRevision?:string)=>Promise<void>;
  field:string;nuclearRevision?:string;nucleolarRevision?:string;
  /** The field's exclusion on the workspace's selection screen (its reason, or none). The table repeats
   * it, and excluding or restoring a field changes no revision, so it is part of what the table shows. */
  exclusion?:string|null;
  channels:NucleusTableChannel[];gate?:NucleusTableGate;selected?:number;onSelect:(n:number)=>void;aside?:ReactNode}){
  const [state,setState]=useState<{key:string;table?:NucleusTableData;error?:string}>({key:""});
  const key=nucleusTableKey(field,nuclearRevision,nucleolarRevision,exclusion);
  // The loader may be a new function on every render; only what the table depends on decides a new request.
  const loader=useRef(load);
  useEffect(()=>{loader.current=load;},[load]);
  useEffect(()=>{
    if(!nuclearRevision)return;
    let current=true;
    loader.current(nuclearRevision,field,nucleolarRevision).then(table=>{if(current)setState({key,table});},
      error=>{if(current)setState({key,error:error instanceof Error?error.message:String(error)});});
    return()=>{current=false;};
  },[key,field,nuclearRevision,nucleolarRevision]);
  if(!nuclearRevision)return <p>核を検出して採用すると、核ごとの表が表示されます。</p>;
  if(state.key!==key)return <p>核ごとの表を読み込み中…</p>;
  if(state.error)return <p role="alert">核ごとの表を読み込めませんでした（{state.error}）。</p>;
  return <NucleusTable table={state.table!} channels={channels} gate={gate} aside={aside} selected={selected} onSelect={onSelect}
    onSave={save?()=>save(nuclearRevision,field,nucleolarRevision):undefined}/>;
}

/** What the workspace passes to show a field's nucleus table beside the image. */
export interface NucleusTableSource {
  shown:boolean;onShow:(shown:boolean)=>void;load:(revision:string,field:string,nucleolarRevision?:string)=>Promise<NucleusTableData>;
  save:(revision:string,field:string,nucleolarRevision?:string)=>Promise<void>;
  field:string;caption:string;nuclearRevision:string;nucleolarRevision?:string;exclusion?:string|null;channels:NucleusTableChannel[];
}
