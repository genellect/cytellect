"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import lp from "./optical-landing.module.css";

/** On phones the header has no demo button, so once the hero has scrolled away a bar keeps the demo one tap away.
 *  It steps aside while the closing scene, which carries the same action, is on screen. */
export function LandingDemoBar() {
  const [shown, setShown] = useState(false);
  useEffect(() => {
    const hero = document.getElementById("top");
    const finale = document.getElementById("start");
    if (!hero || !finale) return;
    const visible = new Map<Element, boolean>();
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => visible.set(entry.target, entry.isIntersecting));
      setShown(!visible.get(hero) && !visible.get(finale));
    });
    observer.observe(hero);
    observer.observe(finale);
    return () => observer.disconnect();
  }, []);
  return <div className={lp.demoBar} data-testid="demo-bar" data-shown={shown} inert={!shown}>
    <Link data-lp-event="example_sticky" href="/demo">デモを体験する <span aria-hidden="true">→</span></Link>
  </div>;
}
