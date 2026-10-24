"use client";

import { useEffect, useRef, useState } from "react";
import lp from "./optical-landing.module.css";

/** What can be measured, ending open; the highlight moves through them while the section is on screen. */
const TARGETS = ["核", "核小体", "細胞質", "蛍光シグナル", "陽性細胞", "見たいもの"];

/** From what a researcher measures to the people waiting for a treatment, laid out as one composition. */
export function LandingImpact() {
  const host = useRef<HTMLElement>(null);
  const [active, setActive] = useState(0);
  useEffect(() => {
    const element = host.current;
    if (!element || !matchMedia("(prefers-reduced-motion: no-preference)").matches) return;
    let timer: ReturnType<typeof setInterval> | undefined;
    const observer = new IntersectionObserver(([entry]) => {
      clearInterval(timer);
      if (entry.isIntersecting) timer = setInterval(() => setActive(value => (value + 1) % TARGETS.length), 1400);
    });
    observer.observe(element);
    return () => { observer.disconnect(); clearInterval(timer); };
  }, []);
  return <section ref={host} id="impact" className={lp.impact} aria-labelledby="impact-title">
    <div className={lp.wide}>
      <h2 id="impact-title" className={lp.impactTitle} aria-label="治せない病気を、過去のものに。"><span>治せない病気を、</span><span>過去のものに。</span></h2>
      <ol className={lp.journey}>
        <li className={lp.measureStep}>
          <span className={lp.stepIndex}>01</span>
          <ul aria-label="測れるもの">{TARGETS.map((target, index) => <li key={target} data-active={index === active}>{target}</li>)}</ul>
          <b>を、測る。</b>
        </li>
        <li><span className={lp.stepIndex}>02</span><span>病気のしくみを、</span><b>解き明かす。</b></li>
        <li><span className={lp.stepIndex}>03</span><span>新しい薬を、</span><b>見つける。</b></li>
        <li className={lp.deliverStep}><span className={lp.stepIndex}>04</span><span>待っている人へ、</span><b>届ける。</b></li>
      </ol>
    </div>
  </section>;
}
