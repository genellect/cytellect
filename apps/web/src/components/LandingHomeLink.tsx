"use client";

import { useEffect, useRef } from "react";

export function LandingHomeLink({ className }: { className: string }) {
  const frame = useRef(0);
  useEffect(() => () => cancelAnimationFrame(frame.current), []);

  return <a href="#top" aria-label="Cytellect ホーム" className={className} onClick={event => {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    cancelAnimationFrame(frame.current);
    const startY = window.scrollY;
    if (matchMedia("(prefers-reduced-motion: reduce)").matches || startY === 0) {
      window.scrollTo({ top: 0, behavior: "instant" });
      return;
    }
    const start = performance.now();
    const step = (now: number) => {
      const progress = Math.min(1, (now - start) / 250);
      window.scrollTo({ top: startY * (1 - progress) ** 3, behavior: "instant" });
      if (progress < 1) frame.current = requestAnimationFrame(step);
    };
    frame.current = requestAnimationFrame(step);
  }}>cytellect</a>;
}
