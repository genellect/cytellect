"use client";

import { useEffect } from "react";

/** The glass and metal of the landing page answer the mouse in 3D: an element marked `data-tilt` (its value is
 *  the most it turns, in degrees) leans towards the pointer as it comes near, and a light on its surface follows
 *  the pointer. This only keeps the custom properties the stylesheet draws from (--rx, --ry, --lx, --ly, --lit).
 *  With reduced motion, or without a mouse, nothing leans. */
export function LandingTilt() {
  useEffect(() => {
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const nodes = [...document.querySelectorAll<HTMLElement>("[data-tilt]")];
    if (!nodes.length) return;
    let frame = 0, x = 0, y = 0, inside = false;
    const clamp = (value: number, limit: number) => Math.min(limit, Math.max(-limit, value));
    const apply = () => {
      frame = 0;
      for (const node of nodes) {
        const box = node.getBoundingClientRect();
        if (box.bottom < -200 || box.top > innerHeight + 200) continue;
        // The pointer on the element's own scale (−1 to 1 across it), and how near it is (1 on it, 0 from 280 px away).
        const cx = (x - (box.left + box.width / 2)) / (box.width / 2), cy = (y - (box.top + box.height / 2)) / (box.height / 2);
        const gap = Math.hypot(Math.max(0, Math.abs(cx) - 1) * box.width / 2, Math.max(0, Math.abs(cy) - 1) * box.height / 2);
        const near = inside ? Math.max(0, 1 - gap / 280) : 0, most = Number(node.dataset.tilt) || 5;
        node.style.setProperty("--ry", `${(clamp(cx, 1.3) * most * near).toFixed(2)}deg`);
        node.style.setProperty("--rx", `${(-clamp(cy, 1.3) * most * 0.7 * near).toFixed(2)}deg`);
        node.style.setProperty("--lx", `${((cx * 0.5 + 0.5) * 100).toFixed(1)}%`);
        node.style.setProperty("--ly", `${((cy * 0.5 + 0.5) * 100).toFixed(1)}%`);
        node.style.setProperty("--lit", near.toFixed(3));
      }
    };
    const schedule = () => { if (!frame) frame = requestAnimationFrame(apply); };
    const move = (event: PointerEvent) => { if (event.pointerType !== "mouse") return; x = event.clientX; y = event.clientY; inside = true; schedule(); };
    const leave = () => { inside = false; schedule(); };
    addEventListener("pointermove", move, { passive: true });
    addEventListener("scroll", schedule, { passive: true });
    document.documentElement.addEventListener("pointerleave", leave);
    return () => {
      cancelAnimationFrame(frame);
      removeEventListener("pointermove", move);
      removeEventListener("scroll", schedule);
      document.documentElement.removeEventListener("pointerleave", leave);
      for (const node of nodes) for (const name of ["--rx", "--ry", "--lx", "--ly", "--lit"]) node.style.removeProperty(name);
    };
  }, []);
  return null;
}
