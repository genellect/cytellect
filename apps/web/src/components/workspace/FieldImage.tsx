"use client";
import {useEffect, useMemo, useRef, useState} from "react";
import type { Outline } from "@/lib/workspace/model";
import type {Point} from "@/lib/types";
import type {MaskOperation} from "@/lib/workspace/api-adapter";
import {compoundOutlines} from "../../lib/workspace/compound-outlines";
import {imageFit, regionAnnotations, scrollToRegion, visibleRegionAnnotations} from "../../lib/workspace/image-viewport";
import styles from "./analysis-workspace.module.css";
import viewer from "./field-image.module.css";

const iconPaths = {fit:"M4 9V4h5M15 4h5v5M20 15v5h-5M9 20H4v-5",layers:"M3 8l9-5 9 5-9 5-9-5Zm0 5 9 5 9-5M3 18l9 5 9-5",draw:"M4 5h4v4H4zM16 3h4v4h-4zM15 16h4v4h-4zM3 16h4v4H3zM8 7l8-2M18 7l-1 9M15 18H7M5 16V9",edit:"m4 16 11-11 4 4L8 20H4v-4Zm9-9 4 4M16 4l2-2 4 4-2 2",split:"M9 9 20 20M9 15 20 4M4 4a3 3 0 1 0 4 4 3 3 0 0 0-4-4Zm0 12a3 3 0 1 0 4 4 3 3 0 0 0-4-4Z",merge:"M3 3h6v6H3zM15 15h6v6h-6zM9 6h7v5M16 11l-3-3m3 3 3-3M6 9v7h5M11 16l-3-3m3 3-3 3",close:"m6 6 12 12M6 18 18 6"};
function ToolIcon({name}:{name:keyof typeof iconPaths}) {return <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={iconPaths[name]}/></svg>;}

export interface OutlineView { outline: Outline; state: "included" | "excluded" | "deleted" }

/** Holes and disconnected contours retain their parent region ID. */
export function uniqueRegionCount(contours: ReadonlyArray<{id: number | string}>): number {
  return new Set(contours.map(contour => String(contour.id))).size;
}

/** Display-only image with region outlines; preview pixels are never measured. */
export function FieldImage({ src, size, outlines, analyzed, selected, onSelect, onClearSelection, label, controlledZoom, onZoomChange, onDrawSave, onDrawingChange, editDisabled }: {
  src: string | null;
  size: { width: number; height: number } | null;
  outlines: OutlineView[];
  analyzed: boolean;
  selected?: number;
  onSelect: (region: number) => void;
  onClearSelection?: () => void;
  label: string;
  controlledZoom?: number | null;
  onZoomChange?: (value: number | null) => void;
  onDrawSave?: (operation: MaskOperation, polygon: Point[], region?: number, merged?: number[]) => Promise<void>;
  onDrawingChange?: (drawing: boolean) => void;
  editDisabled?: boolean;
}) {
  const viewport = useRef<HTMLDivElement>(null);
  const [localView, setLocalView] = useState<{src:string | null;zoom:number | null}>({src:null,zoom:null});
  const manualZoom = controlledZoom === undefined ? (localView.src === src ? localView.zoom : null) : controlledZoom;
  const setZoom = (value: number | null | ((previous: number | null) => number | null)) => {
    const next = typeof value === "function" ? value(manualZoom) : value;
    if (onZoomChange) onZoomChange(next); else setLocalView({src,zoom:next});
  };
  const [fitZoom, setFitZoom] = useState(1);
  const zoom = manualZoom ?? fitZoom;
  const imageWidth = size?.width;
  const imageHeight = size?.height;
  useEffect(() => {
    const element = viewport.current;
    if (!element || !imageWidth || !imageHeight || !src) return;
    // Use the container, not a nested image-shaped box or scrollbar-reduced content area.
    const resize = () => setFitZoom(imageFit(imageWidth, imageHeight, element.offsetWidth, element.offsetHeight));
    const observer = new ResizeObserver(resize); observer.observe(element); resize();
    element.scrollLeft = 0; element.scrollTop = 0;
    return () => observer.disconnect();
  }, [imageWidth, imageHeight, src]);
  const [showNumbers, setShowNumbers] = useState(false);
  const annotations = useMemo(() => regionAnnotations(showNumbers ? outlines : outlines.filter(value => Number(value.outline.id) === selected)), [outlines, selected, showNumbers]);
  const labels = useMemo(() => showNumbers ? visibleRegionAnnotations(annotations, zoom, selected) : annotations.filter(annotation => annotation.id === selected), [annotations, zoom, selected, showNumbers]);
  const lastSelection = useRef("");
  useEffect(() => {
    if (selected === undefined) {lastSelection.current = ""; return;}
    const selectionKey = `${src}:${selected}`;
    if (lastSelection.current === selectionKey) return;
    const element = viewport.current;
    const anchor = annotations.find(annotation => annotation.id === selected);
    if (!element || !anchor || !imageWidth || !imageHeight) return;
    lastSelection.current = selectionKey;
    const position = scrollToRegion(anchor, zoom, {width:element.clientWidth,height:element.clientHeight,left:element.scrollLeft,top:element.scrollTop}, {width:imageWidth,height:imageHeight});
    element.scrollLeft = position.left; element.scrollTop = position.top;
  }, [src, selected, annotations, imageWidth, imageHeight, zoom]);
  const [showOutlines, setShowOutlines] = useState(true);
  const [drawMode, setDrawMode] = useState<MaskOperation | null>(null);
  const [merged, setMerged] = useState<number[]>([]);
  const [drawRegion, setDrawRegion] = useState<number>();
  const [polygon, setPolygon] = useState<Point[]>([]);
  const [saving, setSaving] = useState(false);
  const [drawError, setDrawError] = useState("");
  const endDrawing = () => {setDrawMode(null); setPolygon([]); setMerged([]); setDrawError(""); onDrawingChange?.(false);};
  const startDrawing = (mode: MaskOperation) => {setDrawMode(mode); setDrawRegion(selected); setPolygon([]); setMerged(mode === "merge" && selected ? [selected] : []); setShowOutlines(true); setDrawError(""); onDrawingChange?.(true);};
  const ready = drawMode === "merge" ? merged.length >= 2 : polygon.length >= 3;
  const saveDrawing = async () => {
    if (!onDrawSave || !drawMode || !ready || saving || editDisabled) return;
    setSaving(true); setDrawError("");
    try {await onDrawSave(drawMode, polygon, drawRegion, merged); endDrawing();}
    catch {setDrawError("輪郭を保存できませんでした。描画は保持しています。");}
    finally {setSaving(false);}
  };
  const drag = useRef<{x:number;y:number;left:number;top:number;moved:boolean} | null>(null);
  const suppressClick = useRef(false);
  useEffect(() => {
    const element = viewport.current;
    if (!element || !src) return;
    const wheel = (event: WheelEvent) => {
      event.preventDefault();
      const next = Math.max(0.001, Math.min(8, zoom * Math.exp(-event.deltaY * 0.002)));
      const bounds = element.getBoundingClientRect();
      const x = event.clientX - bounds.left, y = event.clientY - bounds.top;
      const imageOffset = Math.max(0, (element.clientWidth - (imageWidth ?? 0) * zoom) / 2);
      const nextOffset = Math.max(0, (element.clientWidth - (imageWidth ?? 0) * next) / 2);
      const left = (element.scrollLeft + x - imageOffset) * next / zoom + nextOffset - x;
      const top = (element.scrollTop + y) * next / zoom - y;
      if (onZoomChange) onZoomChange(next); else setLocalView({src,zoom:next});
      requestAnimationFrame(() => {element.scrollLeft = left; element.scrollTop = top;});
    };
    element.addEventListener("wheel", wheel, {passive:false});
    return () => element.removeEventListener("wheel", wheel);
  }, [src, zoom, onZoomChange, imageWidth]);
  if (!src || !size) {
    return <div className={styles.imageEmpty}><p>プレビューなし</p></div>;
  }
  return (
    <div className={styles.imageFrame}>
      <div className={[styles.zoomToolbar,viewer.toolbar].join(" ")} role="toolbar" aria-label="画像操作">
        <button type="button" onClick={() => setZoom(value => Math.max(0.001, (value ?? fitZoom) / 1.5))} aria-label="縮小">−</button>
        <button type="button" onClick={() => setZoom(1)} aria-label="原寸で表示">{Math.round(zoom * 100)}%</button>
        <button type="button" onClick={() => setZoom(value => Math.min(8, (value ?? fitZoom) * 1.5))} aria-label="拡大">＋</button>
        <button type="button" title="画像全体を表示" aria-label="画像全体を表示" onClick={() => {setZoom(null); if(viewport.current){viewport.current.scrollLeft=0;viewport.current.scrollTop=0;}}}><ToolIcon name="fit"/></button>
        {analyzed && <><button type="button" title="輪郭の表示・非表示" aria-label="輪郭の表示・非表示" aria-pressed={showOutlines} onClick={() => setShowOutlines(value => !value)}><ToolIcon name="layers"/></button><details className={viewer.displayMenu}><summary title="表示オプション" aria-label="表示オプション">⋯</summary><div><span>{uniqueRegionCount(outlines.filter(value => value.state !== "deleted").map(value => value.outline))} 領域</span><label><input type="checkbox" checked={showNumbers} onChange={event=>setShowNumbers(event.target.checked)}/>領域番号を表示</label></div></details></>}
        {onDrawSave && !drawMode && <button type="button" title="画像上に領域を描く" aria-label="画像上に領域を描く" disabled={editDisabled} onClick={() => startDrawing("add")}><ToolIcon name="draw"/></button>}
        {drawMode === "merge" && <><span>つなげる領域をクリック（{merged.length} 個選択）</span><button type="button" disabled={saving || editDisabled || !ready} onClick={() => void saveDrawing()}>{saving ? "保存中…" : "つなげて保存"}</button></>}
        {drawMode && drawMode !== "merge" && <><span>{drawMode === "split" ? `領域 ${drawRegion} から切り離す部分を囲む` : "輪郭に沿ってクリック"}</span><button type="button" disabled={saving || !polygon.length} onClick={() => setPolygon(points => points.slice(0,-1))}>1点戻す</button><button type="button" disabled={saving || editDisabled || !ready} onClick={() => void saveDrawing()}>{saving ? "保存中…" : drawMode === "split" ? "分けて保存" : "輪郭を保存"}</button></>}
        {drawMode && <><button type="button" disabled={saving} onClick={endDrawing}>描画を取り消す</button></>}
      </div>
      <div className={[styles.imageSurface,viewer.surface].join(" ")}>
      <div ref={viewport} className={styles.imageViewport} style={{width:"100%",height:"100%",flex:"1 1 auto"}}
        onPointerDown={event => {if(event.button !== 0 || drawMode) return; suppressClick.current = false; drag.current = {x:event.clientX,y:event.clientY,left:event.currentTarget.scrollLeft,top:event.currentTarget.scrollTop,moved:false};}}
        onPointerMove={event => {const start = drag.current; if(!start) return; const dx = event.clientX-start.x, dy = event.clientY-start.y; if(!start.moved && Math.hypot(dx,dy)<4) return; start.moved=true; suppressClick.current=true; event.currentTarget.setPointerCapture(event.pointerId); event.currentTarget.scrollLeft=start.left-dx; event.currentTarget.scrollTop=start.top-dy;}}
        onPointerUp={event => {drag.current=null; if(event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);}}
        onPointerCancel={() => {drag.current=null;}}
        onClickCapture={event => {if(suppressClick.current){event.preventDefault();event.stopPropagation();suppressClick.current=false;}}}>
      <svg className={styles.imageSvg} style={{width: size.width * zoom, height: size.height * zoom, minWidth: size.width * zoom, cursor:drawMode ? "crosshair" : undefined}} viewBox={`0 0 ${size.width} ${size.height}`} role="img" aria-label={label}
        onClickCapture={event => {if(!drawMode || drawMode === "merge" || saving || editDisabled) return; event.stopPropagation(); event.preventDefault(); const bounds=event.currentTarget.getBoundingClientRect(); const x=(event.clientX-bounds.left)*size.width/bounds.width, y=(event.clientY-bounds.top)*size.height/bounds.height; if(x>=0&&y>=0&&x<size.width&&y<size.height) setPolygon(points => [...points,[x,y]]);}}>
        <image href={src} width={size.width} height={size.height} preserveAspectRatio="xMidYMid meet" />
        {showOutlines && compoundOutlines(outlines).map(({id: regionId, path, state}) => {
          const id = Number(regionId);
          const className = [styles.outline, state === "excluded" ? styles.outlineExcluded : "", (drawMode === "merge" ? merged.includes(id) : id === selected) ? styles.outlineSelected : ""].join(" ");
          const choose = () => drawMode === "merge" ? setMerged(current => current.includes(id) ? current.filter(value => value !== id) : [...current, id]) : onSelect(id);
          return (
            <path key={regionId} d={path} fillRule="evenodd" clipRule="evenodd" className={className} data-region={regionId}
              role="button" tabIndex={0} aria-label={`領域 ${id}`} onKeyDown={event => {if (event.key === "Enter" || event.key === " ") {event.preventDefault(); choose();}}} onClick={choose}>
              <title>{`領域 ${regionId}${state === "excluded" ? "（除外）" : ""}`}</title>
            </path>
          );
        })}
        {showOutlines && labels.map(({id,x,y}) => <text key={`number-${id}`} x={x} y={y} textAnchor="middle" dominantBaseline="central" fontSize={13/zoom} fontWeight={id === selected ? 800 : 600} fill={id === selected ? "#fff1a5" : "white"} stroke="#111b2c" strokeWidth={3/zoom} paintOrder="stroke" strokeLinejoin="round" pointerEvents="none" aria-hidden="true">{id}</text>)}
        {drawMode && <polygon points={polygon.map(point => point.join(",")).join(" ")} fill="#fbbf2426" stroke="#fbbf24" strokeWidth={2} vectorEffect="non-scaling-stroke" pointerEvents="none"/>}
        {drawMode && polygon.map(([x,y], index) => <circle key={index} cx={x} cy={y} r={3/zoom} fill="#fbbf24" pointerEvents="none"/>)}
      </svg>
      </div>
      {selected !== undefined && !drawMode && <div className={viewer.selectionTools} role="toolbar" aria-label={`領域 ${selected} の操作`}><span>{selected}</span>{onDrawSave && <><button type="button" title="選択した輪郭を描き直す" aria-label="選択した輪郭を描き直す" disabled={editDisabled} onClick={()=>startDrawing("replace")}><ToolIcon name="edit"/></button><button type="button" title="選択領域を分割" aria-label="選択領域を分割" disabled={editDisabled} onClick={()=>startDrawing("split")}><ToolIcon name="split"/></button><button type="button" title="別の領域と結合" aria-label="別の領域と結合" disabled={editDisabled} onClick={()=>startDrawing("merge")}><ToolIcon name="merge"/></button></>}{onClearSelection && <button type="button" title="選択を解除" aria-label="選択を解除" onClick={onClearSelection}><ToolIcon name="close"/></button>}</div>}
      </div>
      {analyzed && !outlines.length && <p className={styles.imageNote}>輪郭データなし（測定値は表・グラフで確認）</p>}
      {drawError && <p role="alert">{drawError}</p>}
    </div>
  );
}
