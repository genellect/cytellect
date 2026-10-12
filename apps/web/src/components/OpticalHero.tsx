"use client";

import { useEffect, useRef, useState } from "react";
import type { OpticalSceneController } from "./optical-scene-engine";
import styles from "./optical-landing.module.css";

/* Adapted from COMPASS ProductSculpture.tsx, 4805fb6df9e5a0bd267aef9cfa440174ccac5fb1.
 * Copyright (c) 2026 Yuto Matsui. Owner-authorized Cytellect adaptation.
 * Visibility-triggered engine loading, generation guards, and cleanup are retained.
 */
export function OpticalHero() {
  const host = useRef<HTMLDivElement>(null);
  const controller = useRef<OpticalSceneController | null>(null);
  const pausedRef = useRef(false);
  const [paused, setPaused] = useState(false);
  const [state, setState] = useState<"static" | "loading" | "ready" | "error">("static");

  useEffect(() => {
    const element = host.current;
    if (!element) return;
    const preference = matchMedia("(prefers-reduced-motion: no-preference)");
    let disposed = false;
    let generation = 0;
    let abort: AbortController | undefined;
    const observer = new IntersectionObserver(async ([entry]) => {
      if (!entry.isIntersecting || !preference.matches) return;
      observer.disconnect();
      const current = generation;
      abort = new AbortController();
      setState("loading");
      try {
        const { mountOpticalScene } = await import("./optical-scene-engine");
        if (disposed || current !== generation) return;
        const scene = await mountOpticalScene(element, () => pausedRef.current, abort.signal, () => { if (!disposed && current === generation) setState("error"); });
        if (disposed || current !== generation) { scene.dispose(); return; }
        controller.current = scene;
        setState("ready");
      } catch {
        if (!disposed && current === generation) setState("error");
      }
    }, { rootMargin: "120px" });
    const sync = () => {
      generation++;
      abort?.abort();
      observer.disconnect();
      controller.current?.dispose();
      controller.current = null;
      setState("static");
      if (preference.matches) observer.observe(element);
    };
    sync();
    preference.addEventListener("change", sync);
    return () => { disposed = true; generation++; abort?.abort(); observer.disconnect(); preference.removeEventListener("change", sync); controller.current?.dispose(); controller.current = null; };
  }, []);

  return <><div className={styles.optical} data-testid="hero-scene" data-state={state} data-paused={paused}>
    <picture className={styles.poster}><source media="(max-width: 760px)" srcSet="/marketing/optical-mobile-poster.webp" /><img src="/marketing/optical-poster.webp" alt="光と透明な構造が広がる3D空間" width={1600} height={1000} fetchPriority="high" /></picture>
    <div ref={host} className={styles.canvas} aria-hidden="true" />
    </div>
    {state === "ready" && <button className={styles.motionToggle} type="button" aria-label={paused ? "背景映像を再生" : "背景映像を停止"} onClick={() => { const next = !pausedRef.current; pausedRef.current = next; setPaused(next); controller.current?.syncMotion(); }}>{paused ? "▷" : "Ⅱ"}</button>}
  </>;
}
