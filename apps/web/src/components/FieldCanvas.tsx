"use client";
import { useEffect, useRef, useState } from "react";
import { Stage, Layer as CanvasLayer, Image as CanvasImage, Line, Circle, Text } from "react-konva";
import type Konva from "konva";
import type { Point, Contour, Layer, Operation } from "@/lib/types";
import { usePrivateImage } from "@/lib/usePrivateImage";
import styles from "./workspace.module.css";
const colors={nuclei:"#7bbbea",nucleoli:"#f2bb67",manual:"#b6a1f0",regions:"#8bcbe3"};
type DisplayLayer=Layer|"regions";
type Props={fieldId:string;shape:[number,number];masks?:Partial<Record<DisplayLayer,Contour[]>>;layer:DisplayLayer;operation:Operation;selected:number[];onSelect:(ids:number[])=>void;polygon:Point[];onPolygon:(points:Point[])=>void;background?:Point[];channel:string;gain:number;showMasks:boolean;previewPath?:string;regionLabel?:string};
export default function FieldCanvas(p:Props){
 const box=useRef<HTMLDivElement>(null);const stage=useRef<Konva.Stage>(null);
 const [width,setWidth]=useState(640);const [zoom,setZoom]=useState(1);const [offset,setOffset]=useState({x:0,y:0});
 const [image,setImage]=useState<HTMLImageElement|null>(null);
 const url=usePrivateImage(p.previewPath??`/v1/fields/${p.fieldId}/preview?channel=${p.channel}&gain=${p.gain}`);
 useEffect(()=>{const obs=new ResizeObserver(([entry])=>setWidth(Math.max(220,entry.contentRect.width)));if(box.current)obs.observe(box.current);return()=>obs.disconnect();},[]);
 useEffect(()=>{setImage(null);if(!url)return;const img=new window.Image();img.onload=()=>setImage(img);img.src=url;return()=>{img.onload=null;};},[url]);
 useEffect(()=>{setZoom(1);setOffset({x:0,y:0});},[p.fieldId]);
 const height=Math.min(600,Math.max(350,width*.68));const base=Math.min((width-48)/p.shape[1],(height-48)/p.shape[0]);const scale=base*zoom;
 const x=(width-p.shape[1]*base)/2+offset.x,y=(height-p.shape[0]*base)/2+offset.y;
 const drawing=["background","add","replace","split"].includes(p.operation);
 const layers:DisplayLayer[]=p.layer==="regions"?["regions"]:["nuclei","nucleoli","manual"];
 function draw(){if(!drawing)return;const pos=stage.current?.getPointerPosition();if(!pos)return;const point:Point=[Math.round((pos.x-x)/scale*10)/10,Math.round((pos.y-y)/scale*10)/10];if(point[0]>=0&&point[1]>=0&&point[0]<=p.shape[1]&&point[1]<=p.shape[0])p.onPolygon([...p.polygon,point]);}
 return <div ref={box} className={styles.canvasBox} data-testid="image-canvas">
  <div className={styles.canvasLabel}><span>{p.shape[1]} × {p.shape[0]} px</span><span>表示調整は測定値を変更しません</span></div>
  <Stage ref={stage} width={width} height={height} onClick={draw} onTap={draw} onWheel={e=>{e.evt.preventDefault();setZoom(z=>Math.max(.5,Math.min(8,z*(e.evt.deltaY>0?.9:1.1))));}} style={{cursor:drawing?"crosshair":"default"}}>
   <CanvasLayer x={x} y={y} scaleX={scale} scaleY={scale} draggable={!drawing} onDragEnd={e=>setOffset({x:e.target.x()-(width-p.shape[1]*base)/2,y:e.target.y()-(height-p.shape[0]*base)/2})}>
    {image&&<CanvasImage image={image} width={p.shape[1]} height={p.shape[0]}/>}
    {p.showMasks&&p.masks&&layers.flatMap(layer=>(p.masks![layer]??[]).map((contour,index)=><Line key={layer+"-"+index} points={contour.points.flat()} closed stroke={p.selected.includes(contour.id)&&layer===p.layer?"#fff":colors[layer]} fill={layer===p.layer?"rgba(0,0,0,0.01)":undefined} strokeWidth={(p.selected.includes(contour.id)&&layer===p.layer?2:1)/scale} hitStrokeWidth={8/scale} listening={!drawing&&layer===p.layer} onClick={e=>{e.cancelBubble=true;p.onSelect(p.selected.includes(contour.id)?p.selected.filter(id=>id!==contour.id):[...p.selected,contour.id]);}} onTap={e=>{e.cancelBubble=true;p.onSelect(layer==="regions"?(p.selected.includes(contour.id)?p.selected.filter(id=>id!==contour.id):[...p.selected,contour.id]):[contour.id]);}}/>))}
    {p.background&&<Line points={p.background.flat()} closed stroke="#72e0b9" strokeWidth={1/scale} dash={[4/scale,3/scale]} listening={false}/>}
    {p.polygon.length>0&&<Line points={p.polygon.flat()} closed={p.polygon.length>=3} stroke="#fff" fill="rgba(255,255,255,.07)" strokeWidth={1.5/scale} listening={false}/>}
    {p.polygon.map((point,i)=><Circle key={i} x={point[0]} y={point[1]} radius={2.5/scale} fill="#fff" listening={false}/>)}
    {!image&&<Text text="画像を読み込み中…" fill="#bbc5c8" x={5} y={10} fontSize={13/scale}/>}
   </CanvasLayer>
  </Stage>
  <div className={styles.canvasBottom}><div className={styles.legend}>{p.layer==="regions"?<span style={{color:colors.regions}}>● {p.regionLabel||"領域"}</span>:<><span style={{color:colors.nuclei}}>● 核</span><span style={{color:colors.nucleoli}}>● 核小体</span><span style={{color:colors.manual}}>● 手動ROI</span></>}<span style={{color:"#72e0b9"}}>▱ 背景</span></div>{p.layer==="regions"&&<div className={styles.canvasZoom}><button aria-label="縮小" onClick={()=>setZoom(z=>Math.max(.5,z/1.25))}>−</button><button aria-label="拡大" onClick={()=>setZoom(z=>Math.min(8,z*1.25))}>＋</button></div>}<button onClick={()=>{setZoom(1);setOffset({x:0,y:0});}}>全体を表示 · {Math.round(zoom*100)}%</button></div>
 </div>;
}
