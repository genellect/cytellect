"use client";

import { useEffect } from "react";

/** The floating header turns light over the bright sections and dark over the film and the deep green ones. */
export function LandingHeaderTone() {
  useEffect(() => {
    const header = document.querySelector<HTMLElement>("[data-lp-header]");
    if (!header) return;
    let frame = 0;
    const sync = () => {
      frame = 0;
      const line = header.getBoundingClientRect().bottom - 8;
      const dark = [...document.querySelectorAll<HTMLElement>('main [data-tone="dark"]')].some(node => { const box = node.getBoundingClientRect(); return box.top <= line && box.bottom >= line; });
      header.dataset.tone = dark ? "dark" : "light";
    };
    const schedule = () => { if (!frame) frame = requestAnimationFrame(sync); };
    sync();
    addEventListener("scroll", schedule, { passive: true });
    addEventListener("resize", schedule);
    return () => { cancelAnimationFrame(frame); removeEventListener("scroll", schedule); removeEventListener("resize", schedule); };
  }, []);
  return null;
}
