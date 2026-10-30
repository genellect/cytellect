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
      <p className={lp.guideLead}>5〜10分で、解析を始められます。管理者権限もコマンド入力も要りません。</p>
      {WINDOWS_RELEASE_URL ? <>
        <DownloadStart url={WINDOWS_RELEASE_URL} installer={INSTALLER} guide={false} />
        <p className={lp.meta}>{INSTALLER ? "インストーラー" : "ZIP"}{size && `・${size}・v${PUBLISHED_RELEASE!.version}`}<br />Windows 10／11（64ビット）・メモリ 8 GB 以上・空き容量 6 GB 以上を推奨</p>
      </> : <p>ダウンロードできる版を準備中です。<Link href="/demo">デモ</Link>で操作を試せます。</p>}

      {INSTALLER ? <section aria-labelledby="flow-title">
        <h2 id="flow-title">インストールで起きること</h2>
        <ol className={lp.guideSteps}>
          <li><b>ダウンロードしたファイルを開く</b><span>「Cytellect-Setup{PUBLISHED_RELEASE ? `-${PUBLISHED_RELEASE.version}` : ""}.exe」{size && `（${size}）`}です。</span></li>
          <li><b>「PCが保護されました」と出たら、「詳細情報」→「実行」</b><span>開発版にはまだ署名がないため表示されます。この1回だけ実行を許可する操作で、PCの設定は変わりません。</span></li>
          <li><b>「インストール」を押す</b><span>PCが条件を満たしているかを確かめてから、解析に必要なものをすべて入れます。インストール中は、インターネットにつながりません。</span></li>
          <li><b>作業画面が開く</b><span>ブラウザで作業画面が開きます。次からは、デスクトップの「Cytellect」から開けます。</span></li>
        </ol>
      </section> : <section aria-labelledby="flow-title">
        <h2 id="flow-title">インストールで起きること</h2>
        <ol className={lp.guideSteps}>
          <li><b>ZIPを展開する</b><span>ダウンロードフォルダーなど、短い場所に展開します。</span></li>
          <li><b>「Cytellect Setup」を開く</b><span>初回は、解析に必要なものをインターネットから取得します。</span></li>
          <li><b>「セットアップ」を押し、終わったら「開く」</b><span>ブラウザで作業画面が開きます。</span></li>
        </ol>
      </section>}

      <section aria-labelledby="trouble-title">
        <h2 id="trouble-title">うまくいかないとき</h2>
        <dl className={lp.guideList}>
          <dt>「Smart App Control」と表示されて止まった</dt><dd>画面からは許可できません。設定は変えずに、<a data-lp-event="contact" href={CONTACT_URL} target="_blank" rel="noopener noreferrer">お問い合わせ <Out /></a>ください。</dd>
          <dt>空き容量が足りないと表示された</dt><dd>空きを作ってから、同じファイルをもう一度開きます。</dd>
          <dt>途中で閉じた・電源が切れた</dt><dd>同じファイルをもう一度開くと、続きから再開します。</dd>
        </dl>
      </section>

      <section aria-labelledby="remove-title">
        <h2 id="remove-title">やめるとき</h2>
        <p>Windowsの「設定」→「アプリ」で「Cytellect」を選び、「アンインストール」を押します。研究データは、残すか削除するかを選べます（既定は残す）。</p>
      </section>

      <section aria-labelledby="cloud-title">
        <h2 id="cloud-title">GPU推論とLLMも使うなら</h2>
        <p>Windows版だけで、核のセグメンテーションから統計、論文の図まで使えます。GPU推論による核小体や細胞の検出と、LLMによる解析の設定は、研究室のクラウドで加わります。料金は応相談、大学内での試験導入は基本無料です。</p>
        <a className={lp.secondary} data-lp-event="consult" href={CONTACT_URL} target="_blank" rel="noopener noreferrer">研究室で導入を相談 <Out /></a>
      </section>

      <p className={lp.guideMore}><a data-lp-event="setup" href={docs + "install-windows.ja.md"} target="_blank" rel="noopener noreferrer">詳しいインストールの手順 <Out /></a><Link href="/">Cytellect のトップへ</Link></p>
    </main>
  </div>;
}
