"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import lp from "./optical-landing.module.css";

/** On phones, from the impact section on, the demo stays one tap away; it steps aside while the invitation is on screen. */
export function LandingDemoBar() {
  const [shown, setShown] = useState(false);
  useEffect(() => {
    const start = document.getElementById("impact");
    const invite = document.getElementById("start");
    if (!start || !invite) return;
    let frame = 0;
    const sync = () => {
      frame = 0;
      const box = invite.getBoundingClientRect();
      setShown(start.getBoundingClientRect().top < innerHeight * .6 && (box.bottom < 0 || box.top > innerHeight));
    };
    const schedule = () => { if (!frame) frame = requestAnimationFrame(sync); };
    sync();
    addEventListener("scroll", schedule, { passive: true });
    addEventListener("resize", schedule);
    return () => { cancelAnimationFrame(frame); removeEventListener("scroll", schedule); removeEventListener("resize", schedule); };
  }, []);
  return <div className={lp.demoBar} data-testid="demo-bar" data-shown={shown} inert={!shown}>
    <Link data-lp-event="example" href="/demo">デモを体験する <span aria-hidden="true">→</span></Link>
  </div>;
}
