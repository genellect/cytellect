"use client";
import {useEffect,useId,useState} from "react";
import {fetchBlob} from "@/lib/api";
import styles from "./connected-results.module.css";

export type FigurePart="figure"|"x"|"y"|"series";
/** Matplotlib's axis/collection IDs identify presentation elements, not invented data points. */
export function EditableFigure({path,onSelect}:{path:string;onSelect:(part:FigurePart)=>void}){
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
  return svg?<div className={styles.editableFigure} role="button" tabIndex={0} aria-label="グラフを選択。軸や点をクリックして表示設定を編集"
    onKeyDown={event=>{if(event.key==="Enter"||event.key===" "){event.preventDefault();onSelect("figure");}}}
    onClick={event=>{const element=event.target as Element;const axis=element.closest('[data-figure-id^="matplotlib.axis_"]')?.getAttribute("data-figure-id");onSelect(axis?.endsWith("_1")?"x":axis?.endsWith("_2")?"y":element.closest('[data-figure-id^="PathCollection"],[data-figure-id^="PolyCollection"]')?"series":"figure");}}
    dangerouslySetInnerHTML={{__html:svg}}/>:<p role="status">図を読み込み中…</p>;
}
