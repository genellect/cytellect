"use client";

import {useEffect, useEffectEvent, useMemo, useRef, useState, type CSSProperties, type PointerEvent} from "react";
import type {Point} from "@/lib/types";
import type {MaskOperation} from "@/lib/workspace/api-adapter";
import {compoundOutlines} from "../../../lib/workspace/compound-outlines";
import {regionAnnotations} from "../../../lib/workspace/image-viewport";
import styles from "./review-image.module.css";

export interface ReviewImageCanvasProps {
  src: string;
  width: number;
  height: number;
  contours: Array<{id: number; points: Point[]}>;
  selected?: number;
  classification?: Record<number,boolean|null>;
  onSelect: (id: number) => void;
  label: string;
  showMasks?: boolean;
  onOpen?: () => void;
  className?: string;
  style?: CSSProperties;
  /** Canonical field/target/mask revision identity. Changes never retarget an unfinished edit. */
  editingKey?: string;
  loading?: boolean;
  editDisabled?: boolean;
  onEdit?: (operation: MaskOperation, polygon: Point[], region?: number, merged?: number[]) => Promise<void>;
  onDelete?: (region: number) => Promise<void>;
  onUndo?: () => Promise<void> | void;
  onRedo?: () => Promise<void> | void;
  canUndo?: boolean;
  canRedo?: boolean;
  onEditingChange?: (active: boolean) => void;
  viewport?: ReviewImageViewport | null;
  onViewportChange?: (value: ReviewImageViewport | null) => void;
  backgroundPolygon?: Point[];
  backgroundEdit?: {requestId:string;onSave:(polygon:Point[])=>Promise<void>;onCancel:()=>void};
}

type Camera = {scale: number; x: number; y: number};
type Size = {width: number; height: number};
export type ReviewImageViewport = {scale: number; centerX: number; centerY: number};
type EditDraft = {identity: string; operation: MaskOperation | "background"; polygon: Point[]; region?: number; merged: number[]};

/** Screen geometry only. Source pixels and saved contour coordinates are never altered. */
export function reviewImageFit(image: Size, viewport: Size): Camera {
  if (Math.min(image.width, image.height, viewport.width, viewport.height) <= 0) return {scale: 1, x: 0, y: 0};
  const scale = Math.min(viewport.width / image.width, viewport.height / image.height);
  return {scale, x: (viewport.width - image.width * scale) / 2, y: (viewport.height - image.height * scale) / 2};
}

export function reviewImageZoom(camera: Camera, scale: number, anchor: {x: number; y: number}): Camera {
  const factor = scale / camera.scale;
  return {scale, x: anchor.x - (anchor.x - camera.x) * factor, y: anchor.y - (anchor.y - camera.y) * factor};
}

function boundedCamera(camera: Camera, image: Size, viewport: Size): Camera {
  const bound = (position: number, length: number, available: number) => length <= available ? (available - length) / 2 : Math.max(available - length, Math.min(0, position));
  return {...camera, x: bound(camera.x, image.width * camera.scale, viewport.width), y: bound(camera.y, image.height * camera.scale, viewport.height)};
}

export function reviewImagePoint(camera: Camera, point: {x: number; y: number}): Point {
  return [(point.x - camera.x) / camera.scale, (point.y - camera.y) / camera.scale];
}

export function reviewViewportCamera(viewport: ReviewImageViewport, available: Size): Camera {
  return {scale: viewport.scale, x: available.width / 2 - viewport.centerX * viewport.scale, y: available.height / 2 - viewport.centerY * viewport.scale};
}

/** Reveal a selected source object without changing magnification or moving visible objects. */
export function reviewImageReveal(camera: Camera, anchor: {x:number;y:number}, image: Size, available: Size): Camera {
  const x=anchor.x*camera.scale+camera.x,y=anchor.y*camera.scale+camera.y;
  if(x>=0&&x<=available.width&&y>=0&&y<=available.height)return camera;
  return boundedCamera({...camera,x:available.width/2-anchor.x*camera.scale,y:available.height/2-anchor.y*camera.scale},image,available);
}

export function reviewImageSelection(ids: readonly number[], selected: number | undefined, direction: -1 | 1): number | undefined {
  const unique = [...new Set(ids)].sort((a, b) => a - b);
  if (!unique.length) return undefined;
  const index = selected === undefined ? -1 : unique.indexOf(selected);
  return unique[index === -1 ? (direction === 1 ? 0 : unique.length - 1) : (index + direction + unique.length) % unique.length];
}

const iconPaths = {fit: "M4 9V4h5M15 4h5v5M20 15v5h-5M9 20H4v-5", layers: "m3 8 9-5 9 5-9 5-9-5Zm0 5 9 5 9-5M3 18l9 5 9-5", open: "M14 3h7v7M21 3l-9 9M10 5H4v15h15v-6", add: "M3 15 14 4l6 6L9 21H3v-6Zm9-9 6 6M17 2v5M14.5 4.5h5", replace: "m4 16 11-11 4 4L8 20H4v-4Zm9-9 4 4M16 4l2-2 4 4-2 2", split: "M9 9 20 20M9 15 20 4M4 4a3 3 0 1 0 4 4 3 3 0 0 0-4-4Zm0 12a3 3 0 1 0 4 4 3 3 0 0 0-4-4Z", merge: "M3 3h6v6H3zM15 15h6v6h-6zM9 6h7v5M16 11l-3-3m3 3 3-3M6 9v7h5M11 16l-3-3m3 3-3 3", delete: "M4 6h16M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7M14 10v7", undo: "M9 5 4 10l5 5M4 10h10a6 6 0 0 1 0 12", redo: "m15 5 5 5-5 5M20 10H10a6 6 0 0 0 0 12", save: "m4 12 5 5L20 6", cancel: "m6 6 12 12M6 18 18 6"};
function Icon({kind}: {kind: keyof typeof iconPaths}) {
  return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={iconPaths[kind]}/></svg>;
}

export function ReviewImageCanvas({src, width, height, contours, selected, classification, onSelect, label, showMasks = true, onOpen, className, style, editingKey, loading = false, editDisabled = false, onEdit, onDelete, onUndo, onRedo, canUndo = false, canRedo = false, onEditingChange, viewport: sharedViewport, onViewportChange, backgroundPolygon, backgroundEdit}: ReviewImageCanvasProps) {
  const viewportRef = useRef<HTMLDivElement>(null);
  const [available, setAvailable] = useState<Size>({width: 0, height: 0});
  const [manual, setManual] = useState<{source: string; camera: Camera} | null>(null);
  const [masksEnabled, setMasksEnabled] = useState(true);
  const [failedSource, setFailedSource] = useState<string | null>(null);
  const [loadedSource, setLoadedSource] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [draft, setDraft] = useState<EditDraft | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const pending = useRef(false);
  const focusedSelection = useRef("");
  const drawingPointer = useRef<number | null>(null);
  const drag = useRef<{pointer: number; x: number; y: number; camera: Camera; moved: boolean} | null>(null);
  const suppressClick = useRef(false);
  const source = `${src}:${width}:${height}`;
  const identity = `${editingKey ?? ""}:${source}`;
  const imageSize = {width, height};
  const fit = reviewImageFit(imageSize, available);
  const camera = sharedViewport !== undefined ? sharedViewport === null ? fit : boundedCamera(reviewViewportCamera(sharedViewport, available), imageSize, available) : manual?.source === source ? boundedCamera(manual.camera, imageSize, available) : fit;
  const visible = showMasks && (masksEnabled || !!draft);
  const interactionBlocked = loading || loadedSource !== src || failedSource === src || saving;
  const blocked = interactionBlocked || (editDisabled && draft?.operation !== "background");
  const stale = !!draft && draft.identity !== identity;
  const selectedExists = selected !== undefined && contours.some(contour => contour.id === selected);
  const canSave = !!draft && !stale && !blocked && (draft.operation === "merge" ? draft.merged.length >= 2 : new Set(draft.polygon.map(point => point.join(","))).size >= 3);
  const outlines = useMemo(() => contours.map(contour => ({outline: {id: String(contour.id), points: contour.points}, state: "included" as const})), [contours]);
  const regions = useMemo(() => compoundOutlines(outlines), [outlines]);
  const selectedAnchor = useMemo(() => selected === undefined ? undefined : regionAnnotations(outlines.filter(value => Number(value.outline.id) === selected))[0], [outlines, selected]);
  const syncBackground = useEffectEvent(()=>{
    if(backgroundEdit){setDraft({identity,operation:"background",polygon:[],merged:[]});setError("");onEditingChange?.(true);}
    else if(draft?.operation==="background"){setDraft(null);onEditingChange?.(false);}
  });
  useEffect(()=>{syncBackground();},[backgroundEdit?.requestId]);

  useEffect(() => {
    const element = viewportRef.current;
    if (!element) return;
    const resize = () => setAvailable({width: element.clientWidth, height: element.clientHeight});
    const observer = new ResizeObserver(resize);
    observer.observe(element); resize();
    return () => observer.disconnect();
  }, []);

  const publishCamera = (next: Camera | null) => {
    if (onViewportChange) onViewportChange(next ? {scale: next.scale, centerX: (available.width / 2 - next.x) / next.scale, centerY: (available.height / 2 - next.y) / next.scale} : null);
    if (sharedViewport === undefined) setManual(next ? {source, camera: next} : null);
  };

  const revealSelection=useEffectEvent(()=>{
    if(selected===undefined){focusedSelection.current="";return;}
    if(!selectedAnchor||loadedSource!==src||available.width<=0||available.height<=0||draft)return;
    const key=`${identity}:${selected}`;
    if(focusedSelection.current===key)return;
    focusedSelection.current=key;
    const revealed=reviewImageReveal(camera,selectedAnchor,imageSize,available);
    if(revealed!==camera)publishCamera(revealed);
  });
  useEffect(()=>{revealSelection();},[selected,selectedAnchor?.x,selectedAnchor?.y,identity,loadedSource,available.width,available.height]);

  const changeZoom = (factor: number, anchor = {x: available.width / 2, y: available.height / 2}) => {
    const scale = Math.max(fit.scale, Math.min(Math.max(8, fit.scale * 8), camera.scale * factor));
    publishCamera(boundedCamera(reviewImageZoom(camera, scale, anchor), imageSize, available));
  };
  const wheel = useEffectEvent((event: WheelEvent) => {
    event.preventDefault();
    const bounds = viewportRef.current!.getBoundingClientRect();
    changeZoom(Math.exp(-Math.max(-100, Math.min(100, event.deltaY)) * 0.003), {x: event.clientX - bounds.left, y: event.clientY - bounds.top});
  });
  useEffect(() => {
    const element = viewportRef.current;
    if (!element) return;
    const listener = (event: WheelEvent) => wheel(event);
    element.addEventListener("wheel", listener, {passive: false});
    return () => element.removeEventListener("wheel", listener);
  }, []);

  const cancelEdit = () => {if (pending.current) return; if(draft?.operation==="background")backgroundEdit?.onCancel();setDraft(null); setError(""); drawingPointer.current = null; onEditingChange?.(false);};
  const startEdit = (operation: MaskOperation) => {
    if (blocked || !onEdit || (operation !== "add" && !selectedExists)) return;
    setDraft({identity, operation, polygon: [], region: selected, merged: operation === "merge" && selected !== undefined ? [selected] : []});
    setError(""); onEditingChange?.(true);
  };
  const commitEdit = async () => {
    if (!canSave || !draft || (draft.operation==="background"?!backgroundEdit:!onEdit) || pending.current) return;
    pending.current = true; setSaving(true); setError("");
    try {
      const polygon=draft.polygon.map(point=>[...point] as Point);
      if(draft.operation==="background")await backgroundEdit!.onSave(polygon);
      else await onEdit!(draft.operation,polygon,draft.region,[...draft.merged]);
      setDraft(null); onEditingChange?.(false);
    }
    catch {setError("保存できませんでした。描画は保持しています。");}
    finally {pending.current = false; setSaving(false);}
  };
  const runAction = async (action: (() => Promise<void> | void) | undefined) => {
    if (!action || blocked || draft || pending.current) return;
    pending.current = true; setSaving(true); setError("");
    try {await action();} catch {setError("操作を完了できませんでした。");}
    finally {pending.current = false; setSaving(false);}
  };
  const chooseRegion = (id: number) => {
    if (suppressClick.current || interactionBlocked || stale) return;
    if (draft?.operation === "merge") setDraft({...draft, merged: draft.merged.includes(id) ? draft.merged.filter(value => value !== id) : [...draft.merged, id]});
    else if (!draft) onSelect(id);
  };
  const sourcePoint = (event: PointerEvent<HTMLDivElement>) => {
    const bounds = event.currentTarget.getBoundingClientRect();
    const point = reviewImagePoint(camera, {x: event.clientX - bounds.left, y: event.clientY - bounds.top});
    return point[0] >= 0 && point[1] >= 0 && point[0] < width && point[1] < height ? point : null;
  };
  const endDrag = (event: PointerEvent<HTMLDivElement>) => {
    if (drawingPointer.current === event.pointerId) {drawingPointer.current = null; if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId); return;}
    if (drag.current?.pointer !== event.pointerId) return;
    suppressClick.current = drag.current.moved;
    drag.current = null; setDragging(false);
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
  };
  return <div className={[styles.frame, className].filter(Boolean).join(" ")} style={{aspectRatio: `${width} / ${height}`, ...style}} aria-busy={loading || saving} onKeyDown={event => {
    if (event.key === "Escape" && draft) {event.preventDefault(); cancelEdit(); return;}
    if (interactionBlocked || stale) return;
    if (draft) {
      if (event.key === "Enter") {event.preventDefault(); void commitEdit();}
      if (event.key === "Backspace" && draft.operation !== "merge") {event.preventDefault(); setDraft({...draft, polygon: draft.polygon.slice(0, -1)});}
      return;
    }
    if (["ArrowLeft", "ArrowUp", "ArrowRight", "ArrowDown"].includes(event.key)) {event.preventDefault(); const next = reviewImageSelection(contours.map(value => value.id), selected, event.key === "ArrowLeft" || event.key === "ArrowUp" ? -1 : 1); if (next !== undefined) onSelect(next);}
    if (event.key === "Delete" && selectedExists && onDelete) {event.preventDefault(); void runAction(() => onDelete(selected!));}
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z") {event.preventDefault(); if (event.shiftKey ? canRedo : canUndo) void runAction(event.shiftKey ? onRedo : onUndo);}
  }}>
    <div className={styles.viewport} ref={viewportRef} data-dragging={dragging} data-drawing={!!draft && draft.operation !== "merge"} tabIndex={0} aria-label={`${label}の画像操作`}
      onPointerDown={event => {
        if (event.button !== 0) return;
        if (draft) {
          if (!blocked && !stale && draft.operation !== "merge") {const point = sourcePoint(event); if (point) {event.preventDefault(); event.currentTarget.focus(); drawingPointer.current = event.pointerId; event.currentTarget.setPointerCapture(event.pointerId); setDraft({...draft, polygon: [...draft.polygon, point]});}}
          return;
        }
        suppressClick.current = false;
        drag.current = {pointer: event.pointerId, x: event.clientX, y: event.clientY, camera, moved: false};
      }}
      onPointerMove={event => {
        if (drawingPointer.current === event.pointerId && draft && !blocked && !stale) {const point = sourcePoint(event); const last = draft.polygon.at(-1); if (point && (!last || Math.hypot(point[0] - last[0], point[1] - last[1]) * camera.scale >= 3)) setDraft({...draft, polygon: [...draft.polygon, point]}); return;}
        const current = drag.current;
        if (!current || current.pointer !== event.pointerId) return;
        const dx = event.clientX - current.x, dy = event.clientY - current.y;
        if (!current.moved && Math.hypot(dx, dy) < 4) return;
        current.moved = true; suppressClick.current = true; setDragging(true);
        if (!event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.setPointerCapture(event.pointerId);
        publishCamera(boundedCamera({...current.camera, x: current.camera.x + dx, y: current.camera.y + dy}, imageSize, available));
      }}
      onPointerUp={endDrag} onPointerCancel={endDrag}
      onPointerLeave={event => {if (drag.current && !drag.current.moved) endDrag(event);}}
      onDoubleClick={event => {if (!draft && !suppressClick.current && onOpen) {event.preventDefault(); onOpen();}}}>
      <svg className={styles.image} role="img" aria-label={label} width="100%" height="100%">
        <g transform={`translate(${camera.x} ${camera.y}) scale(${camera.scale})`}>
          <image href={src} width={width} height={height} preserveAspectRatio="xMidYMid meet" onLoad={() => {setLoadedSource(src);setFailedSource(null);}} onError={() => setFailedSource(src)}/>
          {visible && regions.map(region => <path key={region.id} d={region.path} fillRule="evenodd" data-region={region.id} data-classification={classification&&Number(region.id) in classification?(classification[Number(region.id)]===null?"unknown":classification[Number(region.id)]?"positive":"negative"):undefined}
            className={(draft?.operation === "merge" ? draft.merged.includes(Number(region.id)) : Number(region.id) === selected) ? styles.selected : styles.outline} vectorEffect="non-scaling-stroke"
            role="button" tabIndex={0} aria-label={`領域 ${region.id}`} aria-pressed={Number(region.id) === selected}
            onClick={event => {event.stopPropagation(); chooseRegion(Number(region.id));}}
            onKeyDown={event => {if ((!draft && event.key === "Enter") || (event.key === " " && (!draft || draft.operation === "merge"))) {event.preventDefault(); event.stopPropagation(); chooseRegion(Number(region.id));}}}/>) }
          {visible && selectedAnchor && <text x={selectedAnchor.x} y={selectedAnchor.y} className={styles.number} fontSize={13 / camera.scale} strokeWidth={3 / camera.scale} textAnchor="middle" dominantBaseline="central">{selected}</text>}
          {backgroundPolygon && !backgroundEdit && <polygon points={backgroundPolygon.map(point=>point.join(",")).join(" ")} fill="rgba(255,204,64,0.12)" stroke="#ffcc40" strokeWidth="1.5" strokeDasharray="4 3" vectorEffect="non-scaling-stroke" pointerEvents="none"/>}
          {draft && !stale && draft.operation !== "merge" && <polygon points={draft.polygon.map(point => point.join(",")).join(" ")} className={styles.draft} vectorEffect="non-scaling-stroke"/>}
        </g>
      </svg>
      {failedSource === src && <p className={styles.error} role="alert">画像を読み込めませんでした</p>}
      {(error || stale) && <p className={styles.error} role="alert">{stale ? "画像または領域が更新されました。描画を取り消してから再編集してください。" : error}</p>}
    </div>
    <div className={styles.toolbar} role="toolbar" aria-label={`${label}の表示操作`}>
      <button type="button" title="縮小" aria-label="縮小" disabled={camera.scale <= fit.scale} onClick={() => changeZoom(1 / 1.5)}>−</button>
      <span className={styles.zoom}>{Math.round(camera.scale * 100)}%</span>
      <button type="button" title="拡大" aria-label="拡大" onClick={() => changeZoom(1.5)}>＋</button>
      <button type="button" title="画像全体を表示" aria-label="画像全体を表示" onClick={() => publishCamera(null)}><Icon kind="fit"/></button>
      <button type="button" title="輪郭の表示" aria-label="輪郭の表示" aria-pressed={visible} disabled={!showMasks || regions.length === 0} onClick={() => setMasksEnabled(value => !value)}><Icon kind="layers"/></button>
      {onOpen && <button type="button" title="この画像を大きく表示" aria-label="この画像を大きく表示" disabled={!!draft} onClick={onOpen}><Icon kind="open"/></button>}
    </div>
    {(onEdit || onDelete || onUndo || onRedo || backgroundEdit) && <div className={[styles.toolbar, styles.editToolbar].join(" ")} role="toolbar" aria-label={`${label}の領域編集`}>
      {draft ? <>
        <span className={styles.mode}>{stale ? "描画を取り消す" : draft.operation === "background" ? "背景を囲む" : draft.operation === "merge" ? `結合 · ${draft.merged.length} 領域` : draft.operation === "split" ? "切り離す部分を囲む" : draft.operation === "replace" ? "輪郭を描き直す" : "領域を描く"}</span>
        {draft.operation !== "merge" && <button type="button" title="1点戻す" aria-label="1点戻す" disabled={blocked || !draft.polygon.length} onClick={() => setDraft({...draft, polygon: draft.polygon.slice(0, -1)})}><Icon kind="undo"/></button>}
        <button type="button" title="描画を保存" aria-label="描画を保存" disabled={!canSave} onClick={() => void commitEdit()}><Icon kind="save"/></button>
        <button type="button" title="描画を取り消す" aria-label="描画を取り消す" disabled={saving} onClick={cancelEdit}><Icon kind="cancel"/></button>
      </> : <>
        {onEdit && <button type="button" title="領域を描く" aria-label="領域を描く" disabled={blocked} onClick={() => startEdit("add")}><Icon kind="add"/></button>}
        {onEdit && selectedExists && ([{operation: "replace", title: "輪郭を描き直す"}, {operation: "split", title: "領域を分割"}, {operation: "merge", title: "領域を結合"}] as const).map(({operation, title}) => <button key={operation} type="button" title={title} aria-label={title} disabled={blocked} onClick={() => startEdit(operation)}><Icon kind={operation}/></button>)}
        {onDelete && selectedExists && <button type="button" title="選択領域を削除" aria-label="選択領域を削除" disabled={blocked} onClick={() => void runAction(() => onDelete(selected!))}><Icon kind="delete"/></button>}
        {onUndo && <button type="button" title="元に戻す" aria-label="元に戻す" disabled={blocked || !canUndo} onClick={() => void runAction(onUndo)}><Icon kind="undo"/></button>}
        {onRedo && <button type="button" title="やり直す" aria-label="やり直す" disabled={blocked || !canRedo} onClick={() => void runAction(onRedo)}><Icon kind="redo"/></button>}
      </>}
    </div>}
  </div>;
}
