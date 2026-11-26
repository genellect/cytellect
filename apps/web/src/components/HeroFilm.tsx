"use client";

import { useEffect, useRef, useState } from "react";
import styles from "./optical-landing.module.css";

const FILMS = [["/marketing/hero-film.webm", "video/webm"], ["/marketing/hero-film.mp4", "video/mp4"]] as const;
const POSTER = "/marketing/hero-film-poster.webp";

/** Hero film edited from licensed live-action footage (scripts/lp_film, marketing/hero-film-provenance.json).
 *  The poster frame renders first; the film mounts only when motion is allowed, plays only while the hero is
 *  visible and the tab is shown, and falls back to the poster when it cannot load. */
export function HeroFilm() {
  const host = useRef<HTMLDivElement>(null);
  const video = useRef<HTMLVideoElement>(null);
  const [motion, setMotion] = useState(false);
  const [paused, setPaused] = useState(false);
  const [state, setState] = useState<"poster" | "playing" | "error">("poster");

  useEffect(() => {
    const preference = matchMedia("(prefers-reduced-motion: no-preference)");
    const sync = () => setMotion(preference.matches);
    sync();
    preference.addEventListener("change", sync);
    return () => preference.removeEventListener("change", sync);
  }, []);

  useEffect(() => {
    const element = video.current;
    if (!motion || state === "error" || !element || !host.current) return;
    let visible = false;
    const sync = () => {
      if (visible && !paused && !document.hidden) void element.play().then(() => setState("playing"), () => undefined);
      else element.pause();
    };
    const observer = new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; sync(); });
    observer.observe(host.current);
    document.addEventListener("visibilitychange", sync);
    return () => { observer.disconnect(); document.removeEventListener("visibilitychange", sync); element.pause(); };
  }, [motion, paused, state]);

  const playing = motion && state !== "error";
  return <>
    <div ref={host} className={styles.film} data-testid="hero-film" data-state={playing ? state : state === "error" ? "error" : "poster"} data-paused={paused} aria-hidden="true">
      <img className={styles.filmPoster} src={POSTER} alt="" width={1920} height={1080} fetchPriority="high" />
      {playing && <video ref={video} className={styles.filmVideo} data-visible={state === "playing"} muted loop playsInline preload="auto" poster={POSTER}>
        {/* VP9 first for browsers without H.264; the error of the last source means neither could load. */}
        {FILMS.map(([src, type], index) => <source key={src} src={src} type={type} onError={index === FILMS.length - 1 ? () => setState("error") : undefined} />)}
      </video>}
    </div>
    {playing && state === "playing" && <button className={styles.motionToggle} type="button" aria-label={paused ? "背景映像を再生" : "背景映像を停止"} onClick={() => setPaused(value => !value)}>{paused ? "▷" : "Ⅱ"}</button>}
  </>;
}
