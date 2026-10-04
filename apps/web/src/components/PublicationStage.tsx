"use client";

import { useEffect, useRef, type ReactNode } from "react";
import styles from "./product.module.css";

/* Adapted from COMPASS ProductSculpture.tsx at 4805fb6df9e5a0bd267aef9cfa440174ccac5fb1.
 * Copyright (c) 2026 Yuto Matsui. Owner-authorized Cytellect adaptation.
 * Retains visibility-triggered engine loading, generation guards and disposal.
 * Replaces the WebGL sculpture with the actual exported figure, animated only by scrolling.
 */
export function PublicationStage({ children }: { children: ReactNode }) {
  const host = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const element = host.current;
    if (!element) return;
    const motion = matchMedia("(min-width: 1000px) and (prefers-reduced-motion: no-preference)");
    let disposed = false;
    let generation = 0;
    let cleanup: (() => void) | undefined;
    const observer = new IntersectionObserver(async ([entry]) => {
      if (!entry.isIntersecting || !motion.matches) return;
      observer.disconnect();
      const current = generation;
      try {
        const { mountPublication } = await import("./publication-stage-engine");
        if (!disposed && current === generation && motion.matches) cleanup = mountPublication(element);
      } catch { /* The untransformed figure remains available. */ }
    }, { rootMargin: "240px" });
    const sync = () => {
      generation++;
      observer.disconnect();
      cleanup?.();
      cleanup = undefined;
      if (motion.matches) observer.observe(element);
    };
    sync();
    motion.addEventListener("change", sync);
    return () => { disposed = true; generation++; observer.disconnect(); motion.removeEventListener("change", sync); cleanup?.(); };
  }, []);
  return <div ref={host} className={styles.publicationStage}>{children}</div>;
}
