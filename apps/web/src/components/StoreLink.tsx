"use client";

import type { ReactNode } from "react";

/** Only Windows handles the Store app link; every other device opens the Store's web listing. */
export function storeDestination(userAgent: string, links: { app: string; web: string }) {
  return /Windows NT/.test(userAgent) ? links.app : links.web;
}

/** "Microsoft Store で入手". The link opens the Store app. A device without that app would do nothing
 *  on a click, so there the click opens the web listing instead. */
export function StoreLink({ app, web, className, children }: { app: string; web: string; className?: string; children: ReactNode }) {
  return <a className={className} data-lp-event="download" href={app} onClick={event => {
    if (event.defaultPrevented || storeDestination(navigator.userAgent, { app, web }) === app) return;
    event.preventDefault();
    location.assign(web);
  }}>{children}</a>;
}
