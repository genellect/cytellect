"use client";

import { useEffect, useRef } from "react";
import type { SceneWorld as World } from "./scene-world-engine";
import { announceWorld, WORLD_SCREEN } from "./world-bus";
import lp from "./landing-world.module.css";

const shot = (file: string) => `/marketing/${file}`;
/** The screen each tab's wall shows, in tab order: captures of the public demo
 *  (scripts/capture-lp-evidence.mjs, public/marketing/lp-evidence.json). */
export const TOUR_SCREENS = ["lp-focus-table.webp", "lp-screen-statistics.webp", "lp-screen-ai.webp", "lp-screen-figure.webp"];

/** The landing page's 3D stage (scene-world-engine), fixed behind every section: the light of the page, and a
 *  wall of glass prisms standing in the frame of every picture (elements marked `data-wall`). It runs wherever
 *  motion is allowed and WebGL 2 is there, phones included; otherwise the page shows the same pictures, in the
 *  same frames, as still images. */
export function SceneWorld() {
  const host = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const element = host.current;
    if (!element) return;
    const motion = matchMedia("(prefers-reduced-motion: no-preference)"), compact = matchMedia("(max-width: 760px), (pointer: coarse)");
    let world: World | null = null, abort: AbortController | null = null, watch = 0;

    const frame = (name: string) => () => document.querySelector<HTMLElement>(`[data-wall="${name}"]`);
    const move = (event: PointerEvent) => { if (event.pointerType === "mouse") world?.pointer(event.clientX / innerWidth, 1 - event.clientY / innerHeight, true); };
    const leave = () => world?.pointer(0.5, 0.5, false);
    const visibility = () => world?.running(!document.hidden);
    const onScreen = (event: Event) => world?.show("screen", (event as CustomEvent<number>).detail);
    // The film walls show whichever of the page's two film elements is playing: the hero's, or the closing one.
    const film = () => {
      const videos = [...document.querySelectorAll<HTMLVideoElement>("#start video, #top video")].filter(video => video.readyState >= 2);
      world?.film(videos.find(video => !video.paused) ?? videos.at(-1) ?? null);
    };

    const stop = () => {
      abort?.abort(); abort = null;
      world?.dispose(); world = null;
      announceWorld("off");
    };
    const start = async () => {
      stop();
      if (!motion.matches || !document.createElement("canvas").getContext("webgl2")) return;
      const controller = abort = new AbortController();
      announceWorld("loading");
      try {
        const { mountSceneWorld } = await import("./scene-world-engine");
        if (controller.signal.aborted) return;
        const mounted = await mountSceneWorld(element, { compact: compact.matches, walls: [
          { id: "film", element: frame("film"), sources: [shot("hero-film-poster.webp")], film: true, opens: true },
          // The visible tab's frame; the table is wider than the frame and glides.
          { id: "screen", element: () => document.querySelector<HTMLElement>('#workflow [role="tabpanel"]:not([hidden]) [data-wall="screen"]'), sources: TOUR_SCREENS.map(shot), glide: [0] },
          { id: "bench", element: frame("bench"), sources: [shot("lp-pipetting.webp")] },
          { id: "closing", element: frame("closing"), sources: [shot("hero-film-poster.webp")], film: true },
        ] }, controller.signal);
        if (controller.signal.aborted) { mounted?.dispose(); return; }
        if (!mounted) { announceWorld("off"); return; }
        world = mounted;
        film();
        announceWorld("live");
      } catch {
        if (!controller.signal.aborted) stop();
      }
    };
    void start();

    watch = window.setInterval(film, 400);
    addEventListener("pointermove", move, { passive: true });
    addEventListener(WORLD_SCREEN, onScreen);
    document.documentElement.addEventListener("pointerleave", leave);
    document.addEventListener("visibilitychange", visibility);
    for (const query of [motion, compact]) query.addEventListener("change", start);
    return () => {
      clearInterval(watch);
      removeEventListener("pointermove", move);
      removeEventListener(WORLD_SCREEN, onScreen);
      document.documentElement.removeEventListener("pointerleave", leave);
      document.removeEventListener("visibilitychange", visibility);
      for (const query of [motion, compact]) query.removeEventListener("change", start);
      stop();
    };
  }, []);
  return <div ref={host} className={lp.world} data-lp-world aria-hidden="true" />;
}
