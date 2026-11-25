"use client";

import { STORE_PRODUCT_URL } from "@/lib/release";
import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";
import defaults from "./optical-landing.module.css";

/** The download link itself, and right after it a small guide to what to do with the file.
 *  The file downloads as an ordinary link; the guide only appears once it is asked for. `classes` lets the
 *  landing page dress it in its own stylesheet. */
export function DownloadStart({ url, installer, guide = true, classes: lp = defaults }: { url: string; installer: boolean; guide?: boolean; classes?: Record<string, string> }) {
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
    <a className={lp.primary} data-lp-event="store" href={STORE_PRODUCT_URL}>Microsoft Store で入手（Windows 11 x64）</a>
    {url && <div className={lp.fileDownload}>
      <a className={lp.secondary} data-lp-event="download" href={url} rel="noreferrer" onClick={() => { if (guide) setOpen(true); }}>Windows版をダウンロード（{installer ? "EXE" : "ZIP"}） <span aria-hidden="true">↓</span></a>
      {open && <div className={lp.nextSteps} role="dialog" aria-modal="false" aria-labelledby={title}>
        <p id={title} ref={heading} tabIndex={-1} className={lp.nextStepsTitle}>ダウンロードを始めました</p>
        {installer ? <ol>
          <li>ダウンロードしたファイルを開きます。</li>
          <li>「PCが保護されました」と表示されたら、「詳細情報」→「実行」を押します。</li>
          <li>「インストール」を押します（約5〜10分）。</li>
        </ol> : <ol>
          <li>ダウンロードしたZIPを展開します。</li>
          <li>「Cytellect Setup」を開きます。</li>
          <li>「セットアップ」を押し、完了後に「開く」を押します。</li>
        </ol>}
        <div className={lp.nextStepsActions}>
          <Link data-lp-event="install_guide" href="/download">インストールの手順</Link>
          <button type="button" onClick={() => setOpen(false)}>閉じる</button>
        </div>
      </div>}
    </div>}
  </div>;
}
