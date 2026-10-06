"use client";
import {useEffect, useRef, useState} from "react";
import type { Outline } from "@/lib/workspace/model";
import type {Point} from "@/lib/types";
import type {MaskOperation} from "@/lib/workspace/api-adapter";
import {compoundOutlines} from "../../lib/workspace/compound-outlines";
import styles from "./analysis-workspace.module.css";

export interface OutlineView { outline: Outline; state: "included" | "excluded" | "deleted" }

/** Holes and disconnected contours retain their parent region ID. */
export function uniqueRegionCount(contours: ReadonlyArray<{id: number | string}>): number {
  return new Set(contours.map(contour => String(contour.id))).size;
}

/** Display-only image with region outlines; preview pixels are never measured. */
export function FieldImage({ src, size, outlines, analyzed, selected, onSelect, label, controlledZoom, onZoomChange, onDrawSave, onDrawingChange, editDisabled }: {
  src: string | null;
  size: { width: number; height: number } | null;
  outlines: OutlineView[];
  analyzed: boolean;
  selected?: number;
  onSelect: (region: number) => void;
  label: string;
  controlledZoom?: number | null;
  onZoomChange?: (value: number | null) => void;
  onDrawSave?: (operation: MaskOperation, polygon: Point[], region?: number, merged?: number[]) => Promise<void>;
  onDrawingChange?: (drawing: boolean) => void;
  editDisabled?: boolean;
}) {
  const viewport = useRef<HTMLDivElement>(null);
  const surface = useRef<HTMLDivElement>(null);
  const [surfaceSize, setSurfaceSize] = useState({width:0,height:0});
  const [localZoom, setLocalZoom] = useState<number | null>(null);
  const manualZoom = controlledZoom === undefined ? localZoom : controlledZoom;
  const setZoom = (value: number | null | ((previous: number | null) => number | null)) => {
    const next = typeof value === "function" ? value(manualZoom) : value;
    if (onZoomChange) onZoomChange(next); else setLocalZoom(next);
  };
  const [fitZoom, setFitZoom] = useState(1);
  const zoom = manualZoom ?? fitZoom;
  const imageWidth = size?.width;
  const imageHeight = size?.height;
  useEffect(() => {
    const element = surface.current;
    if (!element || !src) return;
    const resize = () => setSurfaceSize({width:element.clientWidth,height:element.clientHeight});
    const observer = new ResizeObserver(resize); observer.observe(element); resize();
    return () => observer.disconnect();
  }, [src]);
  useEffect(() => {
    const element = viewport.current;
    if (!element || !imageWidth || !imageHeight || !src) return;
    const resize = () => setFitZoom(Math.max(0.01, Math.min(element.clientWidth / imageWidth, element.clientHeight / imageHeight)));
    const observer = new ResizeObserver(resize); observer.observe(element); resize();
    return () => observer.disconnect();
  }, [imageWidth, imageHeight, src]);
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
      const next = Math.max(0.01, Math.min(8, zoom * Math.exp(-event.deltaY * 0.002)));
      const bounds = element.getBoundingClientRect();
      const x = event.clientX - bounds.left, y = event.clientY - bounds.top;
      const left = (element.scrollLeft + x) * next / zoom - x;
      const top = (element.scrollTop + y) * next / zoom - y;
      if (onZoomChange) onZoomChange(next); else setLocalZoom(next);
      requestAnimationFrame(() => {element.scrollLeft = left; element.scrollTop = top;});
    };
    element.addEventListener("wheel", wheel, {passive:false});
    return () => element.removeEventListener("wheel", wheel);
  }, [src, zoom, onZoomChange]);
  if (!src || !size) {
    return <div className={styles.imageEmpty}><p>プレビューなし</p></div>;
  }
  return (
    <div className={styles.imageFrame}>
      <div className={styles.zoomToolbar}>
        <button type="button" onClick={() => setZoom(value => Math.max(0.1, (value ?? fitZoom) / 1.5))} aria-label="縮小">−</button>
        <button type="button" onClick={() => setZoom(1)} aria-label="原寸で表示">{Math.round(zoom * 100)}%</button>
        <button type="button" onClick={() => setZoom(value => Math.min(8, (value ?? fitZoom) * 1.5))} aria-label="拡大">＋</button>
        <button type="button" onClick={() => {setZoom(null);}}>全体を表示</button>
        {analyzed && <button type="button" aria-pressed={showOutlines} onClick={() => setShowOutlines(value => !value)}>検出領域 {uniqueRegionCount(outlines.filter(value => value.state !== "deleted").map(value => value.outline))}</button>}
        {onDrawSave && !drawMode && <><button type="button" disabled={editDisabled} onClick={() => startDrawing("add")}>領域を描く</button><button type="button" disabled={editDisabled || !selected} onClick={() => startDrawing("replace")}>輪郭を描き直す</button><button type="button" disabled={editDisabled || !selected} onClick={() => startDrawing("split")}>分ける</button><button type="button" disabled={editDisabled} onClick={() => startDrawing("merge")}>つなげる</button></>}
        {drawMode === "merge" && <><span>つなげる領域をクリック（{merged.length} 個選択）</span><button type="button" disabled={saving || editDisabled || !ready} onClick={() => void saveDrawing()}>{saving ? "保存中…" : "つなげて保存"}</button></>}
        {drawMode && drawMode !== "merge" && <><span>{drawMode === "split" ? `領域 ${drawRegion} から切り離す部分を囲む` : "輪郭に沿ってクリック"}</span><button type="button" disabled={saving || !polygon.length} onClick={() => setPolygon(points => points.slice(0,-1))}>1点戻す</button><button type="button" disabled={saving || editDisabled || !ready} onClick={() => void saveDrawing()}>{saving ? "保存中…" : drawMode === "split" ? "分けて保存" : "輪郭を保存"}</button></>}
        {drawMode && <><button type="button" disabled={saving} onClick={endDrawing}>描画を取り消す</button></>}
      </div>
      <div ref={surface} className={styles.imageSurface}>
      <div ref={viewport} className={styles.imageViewport} style={surfaceSize.width && surfaceSize.height ? {width:Math.min(surfaceSize.width,surfaceSize.height*size.width/size.height),height:Math.min(surfaceSize.height,surfaceSize.width*size.height/size.width)} : undefined}
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
        {drawMode && <polygon points={polygon.map(point => point.join(",")).join(" ")} fill="#fbbf2426" stroke="#fbbf24" strokeWidth={2} vectorEffect="non-scaling-stroke" pointerEvents="none"/>}
        {drawMode && polygon.map(([x,y], index) => <circle key={index} cx={x} cy={y} r={3/zoom} fill="#fbbf24" pointerEvents="none"/>)}
      </svg>
      </div>
      </div>
      {analyzed && !outlines.length && <p className={styles.imageNote}>輪郭データなし（測定値は表・グラフで確認）</p>}
      {drawError && <p role="alert">{drawError}</p>}
    </div>
  );
}
