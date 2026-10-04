"use client";

import { useState } from "react";

import dynamic from "next/dynamic";
import styles from "./product.module.css";

const LinkedImageFigure = dynamic(() => import("./LinkedImageFigure"), {loading: () => <p>公開画像を読み込んでいます…</p>});
export function EvidenceExample() {
  const [open, setOpen] = useState(false);
  return <details className={styles.linkedExample} onToggle={event => setOpen(event.currentTarget.open)}><summary>画像と測定値を見比べる <span aria-hidden="true">＋</span></summary>{open && <div className={styles.linkedContent}><LinkedImageFigure /></div>}</details>;
}

export function ProductWalkthrough() {
  const [open, setOpen] = useState(false);
  const [failed, setFailed] = useState(false);
  return <div className={styles.screenFrame}>
    {open && !failed ? <video className={styles.walkthroughVideo} controls autoPlay muted playsInline preload="none" poster="/marketing/workspace-public.png" aria-label="解析の操作例" onError={() => { setFailed(true); setOpen(false); }}><source src="/marketing/workspace-public.mp4" type="video/mp4" onError={() => { setFailed(true); setOpen(false); }} /></video> : <picture><source media="(max-width: 760px)" srcSet="/marketing/workspace-public-mobile.png" width={340} height={600} /><img src="/marketing/workspace-public.png" alt="公開蛍光画像を読み込んだCytellectの解析画面。視野一覧と検出領域、測定条件を確認できる。" width={1520} height={744} loading="lazy" /></picture>}
    <div className={styles.walkthroughBar}>{failed ? <span role="status">映像を読み込めませんでした。画面例をご確認ください。</span> : <button type="button" onClick={() => setOpen(!open)}>{open ? "画面例に戻る" : "操作例を見る"} <span aria-hidden="true">{open ? "×" : "▷"}</span></button>}</div>
  </div>;
}
