"use client";

import { useEffect, useRef } from "react";
import type { HeroSpace as Space } from "./hero-space-engine";
import lp from "./optical-landing.module.css";

/** The hero's 3D space (hero-space-engine): the film as a room the visitor can look around and spin. It mounts
 *  where motion is allowed and WebGL 2 is there, and runs only while the hero is on screen; otherwise the hero
 *  keeps the film as HeroFilm shows it. */
export function HeroSpace() {
  const host = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const element = host.current, hero = element?.closest<HTMLElement>("section");
    if (!element || !hero) return;
    const motion = matchMedia("(prefers-reduced-motion: no-preference)");
    let space: Space | null = null, abort: AbortController | null = null, watch = 0, seen = true;
    const film = () => {
      const video = hero.querySelector<HTMLVideoElement>("video");
      space?.film(video && video.readyState >= 2 ? video : null);
    };
    const sync = () => space?.running(seen && !document.hidden);
    const stop = () => { abort?.abort(); abort = null; space?.dispose(); space = null; delete hero.dataset.space; };
    const start = async () => {
      stop();
      if (!motion.matches || !document.createElement("canvas").getContext("webgl2")) return;
      const controller = abort = new AbortController();
      try {
        const { mountHeroSpace } = await import("./hero-space-engine");
        if (controller.signal.aborted) return;
        const mounted = await mountHeroSpace(element, hero, "/marketing/hero-film-poster.webp", controller.signal);
        if (controller.signal.aborted) { mounted?.dispose(); return; }
        if (!mounted) return;
        space = mounted;
        hero.dataset.space = "ready";
        film(); sync();
      } catch {
        if (!controller.signal.aborted) stop();
      }
    };
    void start();
    const sight = new IntersectionObserver(([entry]) => { seen = entry.isIntersecting; sync(); });
    sight.observe(hero);
    watch = window.setInterval(film, 400);
    document.addEventListener("visibilitychange", sync);
    motion.addEventListener("change", start);
    return () => {
      clearInterval(watch);
      sight.disconnect();
      document.removeEventListener("visibilitychange", sync);
      motion.removeEventListener("change", start);
      stop();
    };
  }, []);
  return <div ref={host} className={lp.heroSpace} aria-hidden="true" />;
}
