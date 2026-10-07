"use client";
import {useEffect,useId,useState} from "react";
import {fetchBlob} from "@/lib/api";
import styles from "./connected-results.module.css";

export type FigurePart="figure"|"x"|"y"|"series";
export type FigureSource={field_id?:string;region_id?:number;nucleus_id?:number;condition?:string;sample?:string;experimental_unit?:string};
/** Matplotlib's axis/collection IDs identify presentation elements, not invented data points. */
export function EditableFigure({path,onSelect,onSource}:{path:string;onSelect:(part:FigurePart)=>void;onSource?:(source:FigureSource)=>void}){
  const [svg,setSvg]=useState("");
  const prefix=useId().replace(/[^a-zA-Z0-9]/g,"")+"-";
  useEffect(()=>{let live=true;setSvg("");void fetchBlob(path).then(blob=>blob.text()).then(text=>{
    const document=new DOMParser().parseFromString(text,"image/svg+xml");
    if(document.querySelector("parsererror")||document.documentElement.tagName!=="svg")return;
    const allowed=new Set(["svg","g","defs","path","rect","clipPath","use","text","tspan","line","circle","polygon","polyline","title","desc","metadata"]);
    for(const element of [...document.querySelectorAll("*")]){
      if(!allowed.has(element.tagName)){element.remove();continue;}
      for(const attribute of [...element.attributes]){
        if(/^on/i.test(attribute.name)||((attribute.localName==="href")&&!attribute.value.startsWith("#"))||/url\((?!\s*#)/i.test(attribute.value))element.removeAttribute(attribute.name);
      }
      if(element.id){element.setAttribute("data-figure-id",element.id);element.id=prefix+element.id;}
      for(const attribute of [...element.attributes]){
        if(attribute.localName==="href"&&attribute.value.startsWith("#"))element.setAttributeNS(attribute.namespaceURI,attribute.name,"#"+prefix+attribute.value.slice(1));
        else if(attribute.value.includes("url(#"))element.setAttribute(attribute.name,attribute.value.replaceAll("url(#","url(#"+prefix));
      }
    }
    if(live)setSvg(new XMLSerializer().serializeToString(document.documentElement));
  }).catch(()=>{if(live)setSvg("");});return()=>{live=false;};},[path,prefix]);
  function openSource(element:Element){const source=element.closest('[data-cytellect-source]')?.getAttribute('data-cytellect-source');if(source&&onSource){try{const value=JSON.parse(source) as FigureSource;if(typeof value.field_id==='string'||typeof value.experimental_unit==='string'){onSource(value);return true;}}catch{/* invalid source annotations never navigate */}}return false;}
  return svg?<div className={styles.editableFigure} role="button" tabIndex={0} aria-label="グラフを選択。軸で表示設定を編集、点から元データを表示"
    onKeyDown={event=>{if(event.key==="Enter"||event.key===" "){event.preventDefault();if(!openSource(event.target as Element))onSelect("figure");}}}
    onClick={event=>{const element=event.target as Element;if(openSource(element))return;const axis=element.closest('[data-figure-id^="matplotlib.axis_"]')?.getAttribute("data-figure-id");onSelect(axis?.endsWith("_1")?"x":axis?.endsWith("_2")?"y":element.closest('[data-figure-id^="PathCollection"],[data-figure-id^="PolyCollection"],[data-figure-id^="cytellect-source-points-"]')?"series":"figure");}}
    dangerouslySetInnerHTML={{__html:svg}}/>:<p role="status">図を読み込み中…</p>;
}
