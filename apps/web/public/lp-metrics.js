/* Only the public LP may create this document. No application state is read. */
(() => {
  "use strict";
  const origin = "https://cytellect.vercel.app";
  const measurement = "G-EHKJ8B8N0Y";
  if (location.origin !== origin || location.search || location.hash || window.parent === window
    || navigator.doNotTrack === "1" || navigator.globalPrivacyControl) return;
  try {
    if (parent.location.origin !== origin || parent.location.pathname !== "/"
      || !parent.document.querySelector("[data-cytellect-public-landing]")) return;
  } catch { return; }
  const names = {
    download: "download_click", download_section: "download_section_click",
    launch: "launch_help_click", launch: "launch_help_click", example: "example_click", planning: "planning_click", guide: "guide_click",
    quickstart: "guide_click", methods: "guide_click", setup: "guide_click", figures: "guide_click",
  };
  window.dataLayer = [];
  function gtag() { window.dataLayer.push(arguments); }
  gtag("consent", "default", { ad_storage: "denied", ad_user_data: "denied", ad_personalization: "denied", analytics_storage: "granted" });
  gtag("js", new Date());
  let initialized = false;
  window.addEventListener("message", (event) => {
    if (event.origin !== origin || event.source !== parent) return;
    const data = event.data;
    if (data?.type === "cytellect-lp-init" && !initialized) {
      initialized = true;
      let referrer = "";
      try { const url = new URL(data.referrer); if (url.protocol === "https:") referrer = url.origin; } catch {}
      gtag("config", measurement, {
        send_page_view: false, page_location: origin + "/", page_title: "Cytellect",
        page_referrer: referrer, allow_google_signals: false, allow_ad_personalization_signals: false,
        cookie_prefix: "cytellect_lp", cookie_flags: "SameSite=Lax;Secure",
      });
      gtag("event", "page_view", { send_to: measurement });
    }
    if (initialized && data?.type === "cytellect-lp-event" && Object.hasOwn(names, data.id)
      && Number.isSafeInteger(data.sequence) && data.sequence > 0) {
      gtag("event", names[data.id], {
        send_to: measurement, content_id: data.id, transport_type: "beacon", event_timeout: 250,
        event_callback: () => parent.postMessage({ type: "cytellect-lp-sent", sequence: data.sequence }, origin),
      });
    }
  });
  const script = document.createElement("script");
  script.async = true;
  script.src = "https://www.googletagmanager.com/gtag/js?id=" + measurement;
  script.onload = () => parent.postMessage({ type: "cytellect-lp-ready" }, origin);
  document.head.appendChild(script);
})();
