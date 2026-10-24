"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import lp from "./optical-landing.module.css";

/** On phones the header has no demo button, so once the hero has scrolled away a bar keeps the demo one tap away.
 *  It leaves when the closing chapter begins, whose last screen carries the same action. */
export function LandingDemoBar() {
  const [shown, setShown] = useState(false);
  useEffect(() => {
    const hero = document.getElementById("top");
    const chapter = document.getElementById("future");
    if (!hero || !chapter) return;
    let frame = 0;
    const sync = () => {
      frame = 0;
      setShown(hero.getBoundingClientRect().bottom < 0 && chapter.getBoundingClientRect().top > innerHeight);
    };
    const schedule = () => { if (!frame) frame = requestAnimationFrame(sync); };
    sync();
    addEventListener("scroll", schedule, { passive: true });
    addEventListener("resize", schedule);
    return () => { cancelAnimationFrame(frame); removeEventListener("scroll", schedule); removeEventListener("resize", schedule); };
  }, []);
  return <div className={lp.demoBar} data-testid="demo-bar" data-shown={shown} inert={!shown}>
    <Link data-lp-event="example_sticky" href="/demo">デモを体験する <span aria-hidden="true">→</span></Link>
  </div>;
}
