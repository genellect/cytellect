"use client";

import type { CSSProperties } from "react";
import { useEffect, useRef, useState } from "react";
import styles from "./landing-sections.module.css";

type Props = {
  video: string;
  poster: string;
  /** Still for narrow screens; phones then keep the still and never download the video. */
  mobilePoster?: string;
  mobileWidth?: number;
  mobileHeight?: number;
  width: number;
  height: number;
  alt: string;
  /** Loads the poster first (the hero); other videos load lazily. */
  priority?: boolean;
  /** Where the play/pause control sits: over the picture, or below it when the picture is itself a UI. */
  controls?: "inside" | "below";
  className?: string;
};

/**
 * A muted, looping product clip. It plays only while on screen and never
 * starts by itself under prefers-reduced-motion; a still image is always
 * underneath, so a failed video leaves the same picture in place.
 */
export function ProductVideo({ video, poster, mobilePoster, mobileWidth, mobileHeight, width, height, alt, priority = false, controls = "inside", className }: Props) {
  const ref = useRef<HTMLVideoElement>(null);
  // The researcher's last explicit choice: null until they press the control.
  const choice = useRef<"play" | "pause" | null>(null);
  const [state, setState] = useState<"still" | "playing" | "paused" | "failed">("still");
  const [available, setAvailable] = useState(false);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    const narrow = matchMedia("(max-width: 760px)");
    const reduced = matchMedia("(prefers-reduced-motion: reduce)");
    let visible = false;
    const usable = () => !(mobilePoster && narrow.matches);
    const sync = () => {
      setAvailable(usable());
      if (!usable()) { element.pause(); setState("still"); return; }
      const wanted = choice.current ?? (reduced.matches ? "pause" : "play");
      if (visible && wanted === "play") {
        element.play().catch(() => setState(current => current === "failed" ? current : "paused"));
      } else if (!element.paused) element.pause();
    };
    const observer = new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; sync(); }, { threshold: 0.2 });
    observer.observe(element);
    narrow.addEventListener("change", sync);
    reduced.addEventListener("change", sync);
    sync();
    return () => { observer.disconnect(); narrow.removeEventListener("change", sync); reduced.removeEventListener("change", sync); element.pause(); };
  }, [mobilePoster]);

  const toggle = () => {
    const element = ref.current;
    if (!element) return;
    if (element.paused) {
      choice.current = "play";
      element.play().catch(() => setState("failed"));
    } else {
      choice.current = "pause";
      element.pause();
    }
  };

  const playing = state === "playing";
  const button = available && state !== "failed"
    ? <button type="button" className={controls === "below" ? styles.videoToggleBelow : styles.videoToggle} onClick={toggle}
        aria-label={playing ? "動画を停止" : "動画を再生"}>
        <span aria-hidden="true">{playing ? "Ⅱ" : "▷"}</span>{controls === "below" && <span aria-hidden="true">{playing ? "動画を停止" : "動画を再生"}</span>}
      </button>
    : null;
  const ratio = { "--ratio": `${width} / ${height}`, ...(mobilePoster && mobileWidth && mobileHeight ? { "--mobile-ratio": `${mobileWidth} / ${mobileHeight}` } : {}) } as CSSProperties;

  return <div className={styles.videoBlock}>
    <div className={[styles.video, className].filter(Boolean).join(" ")} data-state={state} data-mobile-still={mobilePoster ? "" : undefined} style={ratio}>
      <picture>
        {mobilePoster && <source media="(max-width: 760px)" srcSet={mobilePoster} width={mobileWidth} height={mobileHeight} />}
        <img src={poster} alt={alt} width={width} height={height} loading={priority ? "eager" : "lazy"} fetchPriority={priority ? "high" : "auto"} decoding="async" />
      </picture>
      {state !== "failed" && <video ref={ref} muted loop playsInline preload="none" aria-hidden="true" tabIndex={-1}
        onPlaying={() => setState("playing")} onPause={() => setState(current => current === "failed" ? current : "paused")}
        onError={() => setState("failed")}>
        <source src={video} type="video/mp4" onError={() => setState("failed")} />
      </video>}
      {controls === "inside" && button}
    </div>
    {controls === "below" && button}
  </div>;
}
