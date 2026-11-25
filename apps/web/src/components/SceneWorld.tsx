"use client";

import { useEffect, useRef } from "react";
import type { SceneWorld as World, Station, WorldPanel } from "./scene-world-engine";
import { announceWorld, WORLD_SHOT, type WorldShot } from "./world-bus";
import lp from "./landing-world.module.css";

const shot = (file: string) => `/marketing/${file}`;
/** Every plate is a capture of the public demo (scripts/capture-lp-evidence.mjs, public/marketing/lp-evidence.json). */
const PANELS: WorldPanel[] = [
  { id: "stats", src: shot("lp-screen-statistics.webp") },
  { id: "ai", src: shot("lp-screen-ai.webp") },
  { id: "figure", src: shot("lp-screen-figure.webp") },
  { id: "ask", src: shot("lp-focus-ai.webp") },
  { id: "table", src: shot("lp-focus-table.webp") },
  { id: "conclusion", src: shot("lp-focus-conclusion.webp") },
  { id: "discussion", src: shot("lp-focus-discussion.webp") },
  { id: "layout", src: shot("lp-focus-figure-layout.webp") },
  { id: "size", src: shot("lp-focus-figure-size.webp") },
];

/** The landing page's 3D world (scene-world-engine), fixed behind every section. It reads where each section
 *  sits on the page and walks the camera from one to the next as the page scrolls. The world mounts on a wide
 *  screen with a mouse, when motion is allowed and WebGL 2 is there; otherwise the page shows the same pictures
 *  as still frames. */
export function SceneWorld() {
  const host = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const element = host.current;
    if (!element) return;
    const motion = matchMedia("(prefers-reduced-motion: no-preference)"), wide = matchMedia("(min-width: 1024px)"), coarse = matchMedia("(pointer: coarse)");
    let world: World | null = null, abort: AbortController | null = null, frame = 0, watch = 0;

    const stations = (): Station[] => {
      const vh = innerHeight;
      const top = (node: Element) => node.getBoundingClientRect().top + scrollY;
      const centre = (node: HTMLElement) => top(node) + node.offsetHeight / 2 - vh / 2;
      const at = (id: Station["id"], selector: string, place: (node: HTMLElement) => [number, number]): Station | null => {
        const node = document.querySelector<HTMLElement>(selector);
        if (!node) return null;
        const [from, to] = place(node);
        return { id, from, to: Math.max(from, to) };
      };
      // Each station holds while its copy is on screen; the camera travels in the gaps between.
      const list = [
        { id: "hero", from: 0, to: 0 } as Station,
        at("mission", "[data-station='mission']", node => [centre(node) - vh * 0.2, centre(node) + vh * 0.2]),
        at("product", "#workflow", node => [top(node) - vh * 0.5, top(node) - vh * 0.15]),
        at("tour", "[data-station='tour']", node => [top(node) - vh * 0.06, top(node) + node.offsetHeight - vh * 0.94]),
        at("reasons", "[data-station='reasons']", node => [top(node) - vh * 0.38, centre(node) + vh * 0.2]),
        at("impact", "#impact", node => [centre(node) - vh * 0.35, centre(node) + vh * 0.3]),
        at("invite", "#start", node => [centre(node) - vh * 0.1, top(node) + node.offsetHeight]),
      ].filter((station): station is Station => station !== null);
      // Stations keep their page order even where two sections sit closer than a screen apart.
      for (let i = 1; i < list.length; i++) { list[i].from = Math.max(list[i].from, list[i - 1].to + 1); list[i].to = Math.max(list[i].to, list[i].from); }
      return list;
    };
    const sync = () => { frame = 0; world?.scroll(scrollY); };
    const schedule = () => { if (!frame) frame = requestAnimationFrame(sync); };
    const layout = () => { world?.stations(stations()); schedule(); };
    const move = (event: PointerEvent) => { if (event.pointerType === "mouse") world?.pointer(event.clientX / innerWidth, 1 - event.clientY / innerHeight, true); };
    const leave = () => world?.pointer(0.5, 0.5, false);
    const visibility = () => world?.running(!document.hidden);
    const onShot = (event: Event) => { const { shot: index, then } = (event as CustomEvent<WorldShot>).detail; world?.shot(index, then); };
    // The film sheet shows whichever of the page's two film elements is playing: the hero's, or the closing one.
    const film = () => {
      const playing = [...document.querySelectorAll<HTMLVideoElement>("#start video, #top video")].find(video => !video.paused && video.readyState >= 2)
        ?? [...document.querySelectorAll<HTMLVideoElement>("#top video")].find(video => video.readyState >= 2);
      world?.film(playing ?? null);
    };

    const stop = () => {
      abort?.abort(); abort = null;
      world?.dispose(); world = null;
      announceWorld("off");
    };
    const start = async () => {
      stop();
      if (!motion.matches || !wide.matches || coarse.matches || !document.createElement("canvas").getContext("webgl2")) return;
      const controller = abort = new AbortController();
      announceWorld("loading");
      try {
        const { mountSceneWorld } = await import("./scene-world-engine");
        if (controller.signal.aborted) return;
        const mounted = await mountSceneWorld(element, { poster: shot("hero-film-poster.webp"), bench: shot("lp-pipetting.webp"), panels: PANELS }, controller.signal);
        if (controller.signal.aborted) { mounted?.dispose(); return; }
        if (!mounted) { announceWorld("off"); return; }
        world = mounted;
        layout(); sync(); film();
        announceWorld("tour");
      } catch {
        if (!controller.signal.aborted) stop();
      }
    };
    void start();

    const resized = new ResizeObserver(layout);
    resized.observe(document.body);
    watch = window.setInterval(film, 400);
    addEventListener("scroll", schedule, { passive: true });
    addEventListener("resize", layout);
    addEventListener("pointermove", move, { passive: true });
    addEventListener(WORLD_SHOT, onShot);
    document.documentElement.addEventListener("pointerleave", leave);
    document.addEventListener("visibilitychange", visibility);
    for (const query of [motion, wide, coarse]) query.addEventListener("change", start);
    return () => {
      cancelAnimationFrame(frame);
      clearInterval(watch);
      resized.disconnect();
      removeEventListener("scroll", schedule);
      removeEventListener("resize", layout);
      removeEventListener("pointermove", move);
      removeEventListener(WORLD_SHOT, onShot);
      document.documentElement.removeEventListener("pointerleave", leave);
      document.removeEventListener("visibilitychange", visibility);
      for (const query of [motion, wide, coarse]) query.removeEventListener("change", start);
      stop();
    };
  }, []);
  return <div ref={host} className={lp.world} data-lp-world aria-hidden="true" />;
}
