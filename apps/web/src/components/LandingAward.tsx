"use client";

import { useEffect, useRef } from "react";
import lp from "./optical-landing.module.css";

/** The award as its own scene: the claim on the left, a trophy of laboratory glass on the right. */
export function LandingAward() {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    let dispose: (() => void) | undefined, cancelled = false;
    const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
    import("./award-scene").then(({ mountAwardTrophy }) => {
      if (cancelled) return;
      try { dispose = mountAwardTrophy(canvas, still); canvas.dataset.state = "ready"; } catch { /* the words stand alone without WebGL */ }
    });
    return () => { cancelled = true; dispose?.(); };
  }, []);
  return <section className={lp.award} data-tone="dark" aria-labelledby="award-title">
    <div className={lp.awardInner}>
      <div className={lp.awardCopy}>
        <p className={lp.awardEvent}>東京AIハッカソン2026</p>
        <h2 id="award-title" className={lp.awardTitle}><span>最優秀賞</span></h2>
        <p className={lp.awardLead}>顕微鏡画像の解析から統計、論文の図までをつなぐ Cytellect が、最優秀賞を受賞しました。</p>
      </div>
      <canvas ref={ref} className={lp.awardTrophy} aria-hidden="true" />
    </div>
  </section>;
}
