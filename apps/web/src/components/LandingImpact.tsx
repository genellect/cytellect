"use client";

import { useEffect, useRef, useState } from "react";
import lp from "./optical-landing.module.css";

/** The future research can lead to, ending with the patients it is for. */
const PATH = [
  ["病気のしくみを", "解き明かす"],
  ["新しい薬の可能性を", "見つける"],
  ["患者へ届ける"],
];

/** Once, when the path comes into view, its line runs from the research to the patient and the last step lights
 *  up. With reduced motion, and until then, the path stands complete. */
export function LandingImpact() {
  const path = useRef<HTMLOListElement>(null);
  const [state, setState] = useState<"still" | "waiting" | "arrived">("still");
  useEffect(() => {
    const node = path.current;
    if (!node || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const box = node.getBoundingClientRect();
    // A path already on screen (a reload further down the page) stays as it is.
    if (box.top < innerHeight && box.bottom > 0) return;
    setState("waiting");
    const seen = new IntersectionObserver(([entry]) => { if (entry.isIntersecting) { setState("arrived"); seen.disconnect(); } }, { threshold: 0.6 });
    seen.observe(node);
    return () => seen.disconnect();
  }, []);
  return <section id="impact" className={lp.impact} data-tone="dark" aria-labelledby="impact-title">
    <div className={lp.wide}>
      <div className={lp.impactPanel}>
        <h2 id="impact-title" className={lp.impactTitle} aria-label="研究の先に、待っている患者さんがいる。"><span>研究の先に、</span><span><span>待っている</span><span>患者さんがいる。</span></span></h2>
        <ol ref={path} className={lp.path} data-state={state} aria-label="研究から患者さんまで">
          {PATH.map(lines => <li key={lines[0]}><b>{lines.map(line => <span key={line}>{line}</span>)}</b></li>)}
        </ol>
      </div>
    </div>
  </section>;
}
