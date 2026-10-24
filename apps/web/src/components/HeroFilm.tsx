"use client";

import { useEffect, useRef, useState } from "react";
import styles from "./optical-landing.module.css";

const FILMS = [["/marketing/hero-film.webm", "video/webm"], ["/marketing/hero-film.mp4", "video/mp4"]] as const;
const POSTER = "/marketing/hero-film-poster.webp";

/** Hero film edited from licensed live-action footage (scripts/lp_film, marketing/hero-film-provenance.json).
 *  The poster frame renders first; the film mounts only when motion is allowed, plays only while the hero is
 *  visible and the tab is shown, and falls back to the poster when it cannot load. A deferred copy (the closing
 *  scene) loads its poster lazily and mounts the film only when the scene comes near the viewport. */
export function HeroFilm({ testId = "hero-film", deferred = false }: { testId?: string; deferred?: boolean }) {
  const host = useRef<HTMLDivElement>(null);
  const video = useRef<HTMLVideoElement>(null);
  const [near, setNear] = useState(!deferred);
  const [motion, setMotion] = useState(false);
  const [paused, setPaused] = useState(false);
  const [inView, setInView] = useState(true);
  const [state, setState] = useState<"poster" | "playing" | "error">("poster");

  useEffect(() => {
    const preference = matchMedia("(prefers-reduced-motion: no-preference)");
    const sync = () => setMotion(preference.matches);
    sync();
    preference.addEventListener("change", sync);
    return () => preference.removeEventListener("change", sync);
  }, []);

  useEffect(() => {
    if (near || !host.current) return;
    const observer = new IntersectionObserver(([entry]) => { if (entry.isIntersecting) setNear(true); }, { rootMargin: "50% 0px" });
    observer.observe(host.current);
    return () => observer.disconnect();
  }, [near]);

  useEffect(() => {
    const element = video.current;
    if (!motion || state === "error" || !element || !host.current) return;
    let visible = false;
    const sync = () => {
      if (visible && !paused && !document.hidden) void element.play().then(() => setState("playing"), () => undefined);
      else element.pause();
    };
    const observer = new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; setInView(visible); sync(); });
    observer.observe(host.current);
    document.addEventListener("visibilitychange", sync);
    return () => { observer.disconnect(); document.removeEventListener("visibilitychange", sync); element.pause(); };
  }, [motion, near, paused, state]);

  const playing = motion && near && state !== "error";
  return <>
    <div ref={host} className={styles.film} data-testid={testId} data-state={playing ? state : state === "error" ? "error" : "poster"} data-paused={paused} aria-hidden="true">
      <img className={styles.filmPoster} src={POSTER} alt="" width={1920} height={1080} {...deferred ? { loading: "lazy" as const } : { fetchPriority: "high" as const }} />
      {playing && <video ref={video} className={styles.filmVideo} data-visible={state === "playing"} muted loop playsInline preload="auto" poster={POSTER}>
        {/* VP9 first for browsers without H.264; the error of the last source means neither could load. */}
        {FILMS.map(([src, type], index) => <source key={src} src={src} type={type} onError={index === FILMS.length - 1 ? () => setState("error") : undefined} />)}
      </video>}
    </div>
    {/* Only the film on screen offers its control, so the hero and closing copies never show two at once. */}
    {playing && state === "playing" && inView && <button className={styles.motionToggle} type="button" aria-label={paused ? "背景映像を再生" : "背景映像を停止"} onClick={() => setPaused(value => !value)}>{paused ? "▷" : "Ⅱ"}</button>}
  </>;
}
