"use client";

import { useEffect, useRef } from "react";
import type { SceneWorld as World } from "./scene-world-engine";
import lp from "./optical-landing.module.css";

/** The landing page's 3D world (scene-world-engine), fixed behind every section. It also tells the hero how far
 *  it has been scrolled (`--leave`, 0 to 1), so the film frame can draw back into the space as the page
 *  starts. With reduced motion the world is one still frame; without WebGL the page stays on black. */
export function SceneWorld() {
  const host = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const element = host.current;
    if (!element) return;
    const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
    const compact = matchMedia("(max-width: 760px), (pointer: coarse)").matches;
    const hero = document.getElementById("top");
    let world: World | null = null, disposed = false, frame = 0;
    const sync = () => {
      frame = 0;
      const max = document.documentElement.scrollHeight - innerHeight;
      world?.progress(max > 0 ? scrollY / max : 0);
      if (hero) hero.style.setProperty("--leave", still ? "0" : Math.min(1, Math.max(0, scrollY / (hero.offsetHeight * 0.9))).toFixed(4));
    };
    const schedule = () => { if (!frame) frame = requestAnimationFrame(sync); };
    const move = (event: PointerEvent) => { if (event.pointerType === "mouse") world?.pointer(event.clientX / innerWidth, 1 - event.clientY / innerHeight, true); };
    const leave = () => world?.pointer(0.5, 0.5, false);
    const visibility = () => world?.running(!document.hidden);
    void import("./scene-world-engine").then(({ mountSceneWorld }) => {
      if (disposed) return;
      world = mountSceneWorld(element, { still, compact });
      if (world) element.dataset.state = "ready";
      sync();
    });
    sync();
    addEventListener("scroll", schedule, { passive: true });
    addEventListener("resize", schedule);
    addEventListener("pointermove", move, { passive: true });
    document.documentElement.addEventListener("pointerleave", leave);
    document.addEventListener("visibilitychange", visibility);
    return () => {
      disposed = true;
      cancelAnimationFrame(frame);
      removeEventListener("scroll", schedule);
      removeEventListener("resize", schedule);
      removeEventListener("pointermove", move);
      document.documentElement.removeEventListener("pointerleave", leave);
      document.removeEventListener("visibilitychange", visibility);
      world?.dispose();
    };
  }, []);
  return <div ref={host} className={lp.world} aria-hidden="true" />;
}
