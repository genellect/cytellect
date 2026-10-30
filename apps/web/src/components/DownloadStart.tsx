"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";
import lp from "./optical-landing.module.css";

/** The download link itself, and right after it a small guide to what to do with the file.
 *  The file downloads as an ordinary link; the guide only appears once it is asked for. */
export function DownloadStart({ url, installer, guide = true }: { url: string; installer: boolean; guide?: boolean }) {
  const [open, setOpen] = useState(false);
  const title = useId();
  const heading = useRef<HTMLParagraphElement>(null);
  useEffect(() => {
    if (!open) return;
    heading.current?.focus();
    const close = (event: KeyboardEvent) => { if (event.key === "Escape") setOpen(false); };
    addEventListener("keydown", close);
    return () => removeEventListener("keydown", close);
  }, [open]);
  return <div className={lp.downloadStart}>
    <a className={lp.primary} data-lp-event="download" href={url} rel="noreferrer" onClick={() => { if (guide) setOpen(true); }}>Windows版をダウンロード <span aria-hidden="true">↓</span></a>
    {open && <div className={lp.nextSteps} role="dialog" aria-modal="false" aria-labelledby={title}>
      <p id={title} ref={heading} tabIndex={-1} className={lp.nextStepsTitle}>ダウンロードを始めました</p>
      {installer ? <ol>
        <li>ダウンロードしたファイルを開く</li>
        <li>「PCが保護されました」と出たら、「詳細情報」→「実行」</li>
        <li>「インストール」を押すと、5〜10分で使い始められます</li>
      </ol> : <ol>
        <li>ダウンロードしたZIPを展開する</li>
        <li>「Cytellect Setup」を開く</li>
        <li>「セットアップ」を押し、終わったら「開く」</li>
      </ol>}
      <div className={lp.nextStepsActions}>
        <Link data-lp-event="install_guide" href="/download">インストールの流れ</Link>
        <button type="button" onClick={() => setOpen(false)}>閉じる</button>
      </div>
    </div>}
  </div>;
}
