"use client";

import { useEffect, useRef } from "react";
import lp from "./optical-landing.module.css";

/** The far layer of the landing page's stage: one field of light, fixed behind every section. Each section
 *  gives the stage its own two lights (where they stand and what colour they are), and the field passes from
 *  one to the next as the page scrolls: blue beside the mission, blue behind the product's screens, the warm
 *  colour of culture medium where the path reaches the patient. A third, soft light follows the mouse. The
 *  lights are plain CSS gradients placed by custom properties, so the stage needs no WebGL and stands still
 *  unless the visitor scrolls or moves the mouse. */
type Light = { at: [number, number]; colour: [number, number, number] };
/** Positions are fractions of the window (x from the left, y from the top); colours are RGB. Sections without
 *  a key (the hero and the invitation, which the film covers) leave the stage dark. */
const KEYS: { selector: string; a: Light; b: Light }[] = [
  { selector: "[data-stage='mission']", a: { at: [0.84, 0.72], colour: [77, 124, 255] }, b: { at: [0.16, 0.04], colour: [139, 120, 240] } },
  { selector: "#workflow", a: { at: [0.82, 0.46], colour: [46, 86, 214] }, b: { at: [0.04, 0.94], colour: [96, 84, 200] } },
  { selector: "[data-stage='reasons']", a: { at: [0.1, 0.1], colour: [60, 104, 230] }, b: { at: [0.94, 0.94], colour: [40, 66, 150] } },
  { selector: "#impact", a: { at: [0.84, 0.74], colour: [231, 184, 164] }, b: { at: [0.1, 0.08], colour: [77, 124, 255] } },
  { selector: "#download", a: { at: [0.88, 0.12], colour: [66, 130, 255] }, b: { at: [0.06, 0.92], colour: [96, 84, 200] } },
];

export function LightField() {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const stage = ref.current;
    if (!stage) return;
    const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
    const sections = KEYS.map(key => ({ ...key, node: document.querySelector<HTMLElement>(key.selector) }));
    // x, y, r, g, b and strength of each light as shown now; they ease towards the section in view.
    const shown = { a: [0.8, 0.7, 77, 124, 255, 0], b: [0.2, 0.1, 139, 120, 240, 0] };
    let frame = 0, last = 0, placed = false;
    const draw = (now: number) => {
      frame = 0;
      // The first frame places the lights; after that they ease, also when the loop starts again after a rest.
      const ease = still || !placed ? 1 : 1 - Math.exp(-(last ? Math.min(0.05, (now - last) / 1000) : 1 / 60) * 3.2);
      last = now; placed = true;
      // Each section weighs in by how close it is to the middle of the window.
      const want = { a: [0, 0, 0, 0, 0], b: [0, 0, 0, 0, 0] };
      let total = 0;
      for (const section of sections) {
        if (!section.node) continue;
        const box = section.node.getBoundingClientRect();
        const reach = box.height / 2 + innerHeight / 2, away = Math.abs(box.top + box.height / 2 - innerHeight / 2);
        const weight = Math.max(0, 1 - away / reach) ** 2;
        if (weight <= 0) continue;
        total += weight;
        for (const [slot, light] of [[want.a, section.a], [want.b, section.b]] as const) {
          slot[0] += light.at[0] * weight; slot[1] += light.at[1] * weight;
          for (let i = 0; i < 3; i++) slot[2 + i] += light.colour[i] * weight;
        }
      }
      let moving = false;
      for (const [name, slot, target] of [["a", shown.a, want.a], ["b", shown.b, want.b]] as const) {
        // Where no section lights the stage, the light fades where it stands.
        const goal = total > 0 ? [...target.map(value => value / total), Math.min(1, total * 1.4)] : [...slot.slice(0, 5), 0];
        for (let i = 0; i < 6; i++) { const step = (goal[i] - slot[i]) * ease; slot[i] += step; if (Math.abs(goal[i] - slot[i]) > (i < 2 || i === 5 ? 0.002 : 0.5)) moving = true; }
        stage.style.setProperty(`--${name}x`, `${(slot[0] * 100).toFixed(2)}%`);
        stage.style.setProperty(`--${name}y`, `${(slot[1] * 100).toFixed(2)}%`);
        stage.style.setProperty(`--${name}c`, `${Math.round(slot[2])} ${Math.round(slot[3])} ${Math.round(slot[4])}`);
        stage.style.setProperty(`--${name}s`, slot[5].toFixed(3));
      }
      stage.dataset.state = "ready";
      if (moving) frame = requestAnimationFrame(draw); else last = 0;
    };
    const wake = () => { if (!frame) frame = requestAnimationFrame(draw); };
    const move = (event: PointerEvent) => {
      if (event.pointerType !== "mouse" || still) return;
      stage.style.setProperty("--mx", `${event.clientX}px`); stage.style.setProperty("--my", `${event.clientY}px`); stage.style.setProperty("--ms", "1");
    };
    const leave = () => stage.style.setProperty("--ms", "0");
    addEventListener("scroll", wake, { passive: true });
    addEventListener("resize", wake);
    addEventListener("pointermove", move, { passive: true });
    document.documentElement.addEventListener("pointerleave", leave);
    wake();
    return () => {
      cancelAnimationFrame(frame);
      removeEventListener("scroll", wake);
      removeEventListener("resize", wake);
      removeEventListener("pointermove", move);
      document.documentElement.removeEventListener("pointerleave", leave);
    };
  }, []);
  return <div ref={ref} className={lp.lightField} aria-hidden="true" />;
}
