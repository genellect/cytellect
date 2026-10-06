"use client";

import { useEffect } from "react";
import { API_CONFIGURED, LOCAL_MODE } from "@/lib/api";

const origin = "https://cytellect.vercel.app";
const events = new Set(["download", "download_section", "example", "planning", "guide", "quickstart", "methods", "setup", "figures", "launch"]);

/** The Google tag lives in a disposable document, never the application shell. */
export function LandingAnalytics() {
  useEffect(() => {
    if (LOCAL_MODE || API_CONFIGURED || location.origin !== origin || location.pathname !== "/product"
      || navigator.doNotTrack === "1" || (navigator as Navigator & { globalPrivacyControl?: boolean }).globalPrivacyControl) return;

    const frame = document.createElement("iframe");
    frame.src = "/lp-metrics.html";
    frame.tabIndex = -1;
    frame.style.cssText = "position:fixed;left:-10000px;top:0;width:1px;height:1px;border:0;pointer-events:none";
    frame.title = "LP analytics";
    frame.referrerPolicy = "no-referrer";
    frame.setAttribute("aria-hidden", "true");
    frame.setAttribute("sandbox", "allow-scripts allow-same-origin");
    let ready = false;
    let sequence = 0;
    const queued: string[] = [];
    const pending = new Map<number, () => void>();
    const timers = new Set<ReturnType<typeof setTimeout>>();
    const receive = (event: MessageEvent) => {
      if (event.origin !== origin || event.source !== frame.contentWindow) return;
      if (event.data?.type === "cytellect-lp-ready") {
        ready = true;
        let referrer = "";
        try { const url = new URL(document.referrer); if (url.protocol === "https:") referrer = url.origin; } catch {}
        frame.contentWindow?.postMessage({ type: "cytellect-lp-init", referrer }, origin);
        queued.splice(0).forEach(id => frame.contentWindow?.postMessage({ type: "cytellect-lp-event", id, sequence: ++sequence }, origin));
      }
      if (event.data?.type === "cytellect-lp-sent") pending.get(event.data.sequence)?.();
    };
    const click = (event: MouseEvent) => {
      const anchor = event.target instanceof Element ? event.target.closest<HTMLAnchorElement>("a[data-lp-event]") : null;
      const id = anchor?.dataset.lpEvent;
      if (!anchor || !id || !events.has(id)) return;
      if (!ready) { if (queued.length < 20) queued.push(id); return; }
      const serial = ++sequence;
      const url = new URL(anchor.href);
      // Preserve normal modified-click, hash navigation and new-tab behavior.
      const navigating = !event.defaultPrevented && event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey
        && (!anchor.target || anchor.target === "_self") && !anchor.hasAttribute("download")
        && (url.origin !== location.origin || url.pathname !== location.pathname);
      if (navigating) {
        event.preventDefault();
        event.stopPropagation();
        const finish = () => {
          if (!pending.delete(serial)) return;
          location.assign(anchor.href);
        };
        pending.set(serial, finish);
        timers.add(setTimeout(finish, 350));
      }
      frame.contentWindow?.postMessage({ type: "cytellect-lp-event", id, sequence: serial }, origin);
    };
    window.addEventListener("message", receive);
    document.addEventListener("click", click, true);
    document.body.appendChild(frame);
    return () => {
      window.removeEventListener("message", receive);
      document.removeEventListener("click", click, true);
      timers.forEach(clearTimeout);
      pending.clear();
      if (frame.contentWindow) (frame.contentWindow as Window & Record<string, unknown>)["ga-disable-G-EHKJ8B8N0Y"] = true;
      frame.remove();
    };
  }, []);
  return null;
}
