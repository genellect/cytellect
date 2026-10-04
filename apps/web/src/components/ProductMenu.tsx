"use client";

import type { ReactNode } from "react";
import { useEffect, useRef, useState } from "react";
import styles from "./product.module.css";

// Adapted from COMPASS founder/MobileExternalMenu.tsx at
// 4805fb6df9e5a0bd267aef9cfa440174ccac5fb1.
// Copyright (c) 2026 Yuto Matsui. All rights reserved.
// Reuse and adaptation expressly authorized by the owner for Cytellect.
// Preserves outside-pointer, Escape and trigger-focus behavior; adapts navigation labels.
export function ProductMenu({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!open) return;
    const closeFromOutside = (event: PointerEvent) => {
      if (!(event.target instanceof Node) || rootRef.current?.contains(event.target)) return;
      setOpen(false);
    };
    const closeFromKeyboard = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setOpen(false);
      triggerRef.current?.focus();
    };
    document.addEventListener("pointerdown", closeFromOutside);
    document.addEventListener("keydown", closeFromKeyboard);
    return () => {
      document.removeEventListener("pointerdown", closeFromOutside);
      document.removeEventListener("keydown", closeFromKeyboard);
    };
  }, [open]);
  return <div ref={rootRef} className={styles.mobileMenu}>
    <button ref={triggerRef} type="button" aria-label={open ? "メニューを閉じる" : "メニューを開く"} aria-expanded={open} aria-controls="mobile-product-navigation" onClick={() => setOpen(current => !current)}>
      <svg viewBox="0 0 24 24" aria-hidden="true">{[5,12,19].flatMap(y=>[5,12,19].map(x=><circle key={`${x}-${y}`} cx={x} cy={y} r="1.6" />))}</svg>
    </button>
    {open ? <nav id="mobile-product-navigation" className={styles.mobilePopover} aria-label="モバイルナビゲーション" onClick={event => {if((event.target as Element).closest("a"))setOpen(false);}}>{children}</nav> : null}
  </div>;
}
