"use client";

import { useEffect } from "react";

/** A soft light follows the mouse over the dark sections of the landing page: this keeps `--mx` and `--my`
 *  (the pointer in the window, in px) on the page's root, and the stylesheet draws the light from them. Nothing
 *  moves unless the visitor moves the mouse; with reduced motion, or on touch, there is no light. */
export function LandingSpotlight() {
  useEffect(() => {
    const page = document.querySelector<HTMLElement>("[data-cytellect-public-page]");
    if (!page || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let frame = 0, x = 0, y = 0;
    const apply = () => { frame = 0; page.style.setProperty("--mx", `${x}px`); page.style.setProperty("--my", `${y}px`); };
    const move = (event: PointerEvent) => {
      if (event.pointerType !== "mouse") return;
      x = event.clientX; y = event.clientY;
      if (!frame) frame = requestAnimationFrame(apply);
    };
    addEventListener("pointermove", move, { passive: true });
    return () => { cancelAnimationFrame(frame); removeEventListener("pointermove", move); page.style.removeProperty("--mx"); page.style.removeProperty("--my"); };
  }, []);
  return null;
}
