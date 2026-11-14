"use client";

import { useEffect, useRef, useState } from "react";
import lp from "./optical-landing.module.css";

/** The invitation closes on the same footage the page opens with. The poster stays when motion is reduced,
 *  and the film plays only while it is on screen. */
export function LandingClosingFilm() {
  const ref = useRef<HTMLDivElement>(null);
  const [play, setPlay] = useState(false);
  useEffect(() => {
    const node = ref.current;
    const still = matchMedia("(prefers-reduced-motion: reduce)");
    if (!node) return;
    const observer = new IntersectionObserver(([entry]) => setPlay(entry.isIntersecting && !still.matches), { rootMargin: "120px" });
    observer.observe(node);
    return () => observer.disconnect();
  }, []);
  return <div ref={ref} className={lp.closingFilm} aria-hidden="true">
    <img src="/marketing/hero-film-poster.webp" alt="" width={1920} height={1080} loading="lazy" decoding="async" />
    {play && <video autoPlay muted loop playsInline preload="none" poster="/marketing/hero-film-poster.webp">
      <source src="/marketing/hero-film.webm" type="video/webm" /><source src="/marketing/hero-film.mp4" type="video/mp4" />
    </video>}
  </div>;
}
