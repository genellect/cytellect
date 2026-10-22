"use client";

import { useEffect, useRef, useState } from "react";
import styles from "./optical-landing.module.css";

/** Hero film edited from licensed live-action footage; sources are listed in marketing/provenance.json.
 *  It plays only while visible and never when the reader prefers reduced motion; the poster is a frame of the film. */
export function HeroFilm() {
  const video = useRef<HTMLVideoElement>(null);
  const [paused, setPaused] = useState(false);
  const [state, setState] = useState<"poster" | "playing" | "error">("poster");

  useEffect(() => {
    const element = video.current;
    if (!element) return;
    const motion = matchMedia("(prefers-reduced-motion: no-preference)");
    let visible = false;
    const sync = () => {
      if (visible && motion.matches && !paused) void element.play().then(() => setState("playing"), () => setState("poster"));
      else element.pause();
    };
    const observer = new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; sync(); });
    observer.observe(element);
    motion.addEventListener("change", sync);
    document.addEventListener("visibilitychange", sync);
    return () => { observer.disconnect(); motion.removeEventListener("change", sync); document.removeEventListener("visibilitychange", sync); element.pause(); };
  }, [paused]);

  return <><div className={styles.film} data-testid="hero-film" data-state={state} data-paused={paused} aria-hidden="true">
    <video ref={video} className={styles.filmVideo} muted loop playsInline preload="metadata" poster="/marketing/hero-film-poster.webp"
      onError={() => setState("error")}>
      <source src="/marketing/hero-film.mp4" type="video/mp4" onError={() => setState("error")} />
    </video>
  </div>
  {state === "playing" && <button className={styles.motionToggle} type="button" aria-label={paused ? "背景映像を再生" : "背景映像を停止"} onClick={() => setPaused(value => !value)}>{paused ? "▷" : "Ⅱ"}</button>}
  </>;
}
