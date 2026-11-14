import Link from "next/link";
import { PUBLISHED_RELEASE, WINDOWS_RELEASE_URL, releaseSize, windowsReleaseAsset } from "@/lib/release";
import { CONTACT_URL } from "@/lib/site";
import { DownloadStart } from "./DownloadStart";
import { LandingAnalytics } from "./LandingAnalytics";
import lp from "./optical-landing.module.css";

const INSTALLER = windowsReleaseAsset(WINDOWS_RELEASE_URL) === "installer";
const docs = "https://github.com/genellect/cytellect/blob/main/docs/";
const Out = () => <span aria-hidden="true">↗</span>;

/** What installing the Windows version looks like, before and after the download. Kept off the LP. */
export function InstallGuide() {
  const size = PUBLISHED_RELEASE?.url === WINDOWS_RELEASE_URL ? releaseSize(PUBLISHED_RELEASE.size_bytes) : "";
  return <div className={[lp.page, lp.guidePage].join(" ")} data-cytellect-public-page="/download">
    <LandingAnalytics page="/download" />
    <header className={lp.guideHeader}><Link href="/" className={lp.wordmark} aria-label="Cytellect ホーム">cytellect</Link><a data-lp-event="contact" href={CONTACT_URL} target="_blank" rel="noopener noreferrer">お問い合わせ <Out /></a></header>
    <main className={lp.guideMain}>
      <h1>Windows版のインストール</h1>
      <p className={lp.guideLead}>所要時間は5〜10分です。管理者権限とコマンド入力は不要です。</p>
      {WINDOWS_RELEASE_URL ? <>
        <DownloadStart url={WINDOWS_RELEASE_URL} installer={INSTALLER} guide={false} />
        <p className={lp.meta}>{INSTALLER ? "インストーラー" : "ZIP"}{size && `・${size}・v${PUBLISHED_RELEASE!.version}`}<br />推奨：Windows 10／11（64ビット）・メモリ 8 GB 以上・空き容量 6 GB 以上</p>
      </> : <p>配布版は準備中です。操作は<Link href="/demo">デモ</Link>で確認できます。</p>}

      {INSTALLER ? <section aria-labelledby="flow-title">
        <h2 id="flow-title">インストールの手順</h2>
        <ol className={lp.guideSteps}>
          <li><b>ダウンロードしたファイルを開きます。</b><span>「Cytellect-Setup{PUBLISHED_RELEASE ? `-${PUBLISHED_RELEASE.version}` : ""}.exe」{size && `（${size}）`}</span></li>
          <li><b>「PCが保護されました」と表示されたら、「詳細情報」→「実行」を押します。</b><span>開発版は未署名のため表示されます。この操作で許可するのは今回の実行だけで、PCの設定は変わりません。</span></li>
          <li><b>「インストール」を押します。</b><span>PCの要件を確認してから、解析に必要なものをすべてインストールします。インストール中はインターネットに接続しません。</span></li>
          <li><b>ブラウザに開いた作業画面を確認します。</b><span>次回からはデスクトップの「Cytellect」から開きます。</span></li>
        </ol>
      </section> : <section aria-labelledby="flow-title">
        <h2 id="flow-title">インストールの手順</h2>
        <ol className={lp.guideSteps}>
          <li><b>ZIPを展開します。</b><span>展開先は、ダウンロードフォルダーなど短いパスの場所にします。</span></li>
          <li><b>「Cytellect Setup」を開きます。</b><span>初回は、解析に必要なものをインターネットから取得します。</span></li>
          <li><b>「セットアップ」を押し、完了後に「開く」を押します。</b><span>ブラウザで作業画面が開きます。</span></li>
        </ol>
      </section>}

      <section aria-labelledby="trouble-title">
        <h2 id="trouble-title">トラブルシューティング</h2>
        <dl className={lp.guideList}>
          <dt>「Smart App Control」で停止した</dt><dd>画面からは許可できません。設定を変更せずに、<a data-lp-event="contact" href={CONTACT_URL} target="_blank" rel="noopener noreferrer">お問い合わせ <Out /></a>ください。</dd>
          <dt>空き容量の不足が表示された</dt><dd>空き容量を確保し、同じファイルを開き直します。</dd>
          <dt>途中で閉じた・電源が切れた</dt><dd>同じファイルを開き直します。未完了の部分を削除して準備をやり直すため、再ダウンロードは不要です。</dd>
        </dl>
      </section>

      <section aria-labelledby="remove-title">
        <h2 id="remove-title">アンインストール</h2>
        <p>Windowsの「設定」→「アプリ」で「Cytellect」を選び、「アンインストール」を押します。研究データは、保持か削除かを選択します（既定：保持）。</p>
      </section>

      <section aria-labelledby="cloud-title">
        <h2 id="cloud-title">GPU推論とLLMの利用</h2>
        <p>Windows版は、核のセグメンテーションから統計、論文の図までに対応します。GPU推論による核小体・細胞の検出と、LLMによる解析の設定は、研究室のクラウドで提供します。料金は応相談で、大学内での試験導入は基本無料です。</p>
        <a className={lp.secondary} data-lp-event="consult" href={CONTACT_URL} target="_blank" rel="noopener noreferrer">研究室で導入を相談 <Out /></a>
      </section>

      <p className={lp.guideMore}><a data-lp-event="setup" href={docs + "install-windows.ja.md"} target="_blank" rel="noopener noreferrer">インストールの詳細手順 <Out /></a><Link href="/">Cytellect のトップへ</Link></p>
    </main>
  </div>;
}
