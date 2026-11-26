"use client";
import {useEffect,useId,useRef,useState} from "react";
import {fetchBlob} from "@/lib/api";
import {sanitizeFigureSvg} from "./figure-svg";
import styles from "./connected-results.module.css";

export type FigurePart="figure"|"x"|"y"|"series";
export type FigureSource={field_id?:string;region_id?:number;nucleus_id?:number;condition?:string;sample?:string;experimental_unit?:string};
/** Matplotlib's axis/collection IDs identify presentation elements, not invented data points. */
export function EditableFigure({path,onSelect,onSource}:{path:string;onSelect:(part:FigurePart)=>void;onSource?:(source:FigureSource)=>void}){
  const [svg,setSvg]=useState<Element|null>(null);
  const host=useRef<HTMLDivElement>(null);
  const prefix=useId().replace(/[^a-zA-Z0-9]/g,"")+"-";
  useEffect(()=>{let live=true;setSvg(null);void fetchBlob(path).then(blob=>blob.text()).then(text=>{
    if(live)setSvg(sanitizeFigureSvg(text,prefix));
  }).catch(()=>{if(live)setSvg(null);});return()=>{live=false;};},[path,prefix]);
  // The sanitized nodes are inserted as nodes; the figure is never re-parsed from a string.
  useEffect(()=>{const element=host.current;if(!element||!svg)return;element.replaceChildren(document.importNode(svg,true));return()=>{element.replaceChildren();};},[svg]);
  function openSource(element:Element){const source=element.closest('[data-cytellect-source]')?.getAttribute('data-cytellect-source');if(source&&onSource){try{const value=JSON.parse(source) as FigureSource;if(typeof value.field_id==='string'||typeof value.experimental_unit==='string'){onSource(value);return true;}}catch{/* invalid source annotations never navigate */}}return false;}
  return svg?<div ref={host} className={styles.editableFigure} role="button" tabIndex={0} aria-label="グラフを選択。軸で表示設定を編集、点から元データを表示"
    onKeyDown={event=>{if(event.key==="Enter"||event.key===" "){event.preventDefault();if(!openSource(event.target as Element))onSelect("figure");}}}
    onClick={event=>{const element=event.target as Element;if(openSource(element))return;const axis=element.closest('[data-figure-id^="matplotlib.axis_"]')?.getAttribute("data-figure-id");onSelect(axis?.endsWith("_1")?"x":axis?.endsWith("_2")?"y":element.closest('[data-figure-id^="PathCollection"],[data-figure-id^="PolyCollection"],[data-figure-id^="cytellect-source-points-"]')?"series":"figure");}}/>:<p role="status">図を読み込み中…</p>;
}
