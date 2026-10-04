"use client";

import { useEffect, useRef, useState } from "react";

import dynamic from "next/dynamic";
import styles from "./product.module.css";

export function MicroscopyMotion() {
  const video = useRef<HTMLVideoElement>(null);
  const userPaused = useRef(false);
  const [enabled, setEnabled] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    const preference = window.matchMedia("(prefers-reduced-motion: reduce)");
    const change = () => {
      setEnabled(!preference.matches);
      if (preference.matches) { video.current?.pause(); setPlaying(false); }
    };
    change(); preference.addEventListener("change", change);
    return () => preference.removeEventListener("change", change);
  }, []);
  useEffect(() => {
    if (!enabled || failed || !video.current) return;
    const current = video.current;
    const observer = new IntersectionObserver(entries => {
      if (entries[0]?.isIntersecting && !document.hidden && !userPaused.current) void current.play().catch(() => setPlaying(false));
      else current.pause();
    });
    observer.observe(current);
    const visibility = () => { if (document.hidden) current.pause(); };
    document.addEventListener("visibilitychange", visibility);
    return () => { observer.disconnect(); document.removeEventListener("visibilitychange", visibility); current.pause(); };
  }, [enabled, failed]);
  return <div className={styles.microscopy}>
    <img className={styles.heroPoster} src="/marketing/hero-microscopy-poster.webp" alt="公開蛍光顕微鏡画像" width={1920} height={1080} fetchPriority="high" />
    {enabled && !failed && <video ref={video} className={styles.heroVideo} muted playsInline loop preload="none" poster="/marketing/hero-microscopy-poster.webp" onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onError={() => { setFailed(true); setPlaying(false); }} aria-label="蛍光顕微鏡画像"><source src="/marketing/hero-microscopy.mp4" type="video/mp4" onError={() => { setFailed(true); setPlaying(false); }} /></video>}
    {enabled && !failed && <button className={styles.motionToggle} type="button" aria-label={playing ? "背景映像を停止" : "背景映像を再生"} onClick={() => { if (playing) { userPaused.current = true; video.current?.pause(); } else { userPaused.current = false; void video.current?.play().catch(() => setPlaying(false)); } }}>{playing ? "Ⅱ" : "▷"}</button>}
  </div>;
}


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
