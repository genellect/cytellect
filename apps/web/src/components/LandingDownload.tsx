import Link from "next/link";
import { PUBLISHED_RELEASE, WINDOWS_RELEASE_URL, WINDOWS_STORE_LINKS, releaseSize, windowsReleaseAsset } from "@/lib/release";
import { CONTACT_URL } from "@/lib/site";
import { DownloadStart } from "./DownloadStart";
import { StoreLink } from "./StoreLink";
import lp from "./optical-landing.module.css";

const INSTALLER = windowsReleaseAsset(WINDOWS_RELEASE_URL) === "installer";
const Out = () => <span aria-hidden="true">↗</span>;

/** The LP's last step, drawn as one line like the patient path above it: start free on your own PC,
 *  then bring the lab cloud in. Questions stay folded; how to install lives on /download. */
export function LandingDownload() {
  return <section id="download" className={[lp.section, lp.download].join(" ")} aria-labelledby="download-title">
    <div className={lp.wide}>
      <h2 id="download-title" className={lp.statement}>まず、あなたのPCで。そして、研究室へ。</h2>
      <ol className={lp.journey}>
        <li className={lp.stop}>
          <h3>Windows 版</h3>
          <p>核の検出、測定、統計、作図は、この PC で無料で使えます。サインインは不要です。</p>
          {WINDOWS_STORE_LINKS ? <>
            <StoreLink {...WINDOWS_STORE_LINKS} className={lp.primary}>Microsoft Store で入手 <Out /></StoreLink>
            <p className={lp.meta}><span>Windows 11（x64）</span><br /><Link data-lp-event="install_guide" href="/download">インストールと最初の解析</Link> · <a href={WINDOWS_STORE_LINKS.web}>Store の掲載ページ</a></p>
          </> : WINDOWS_RELEASE_URL ? <>
            <DownloadStart url={WINDOWS_RELEASE_URL} installer={INSTALLER} />
            <p className={lp.meta}>{INSTALLER ? "インストーラー" : "ZIP"}{PUBLISHED_RELEASE?.url === WINDOWS_RELEASE_URL ? ` ${releaseSize(PUBLISHED_RELEASE.size_bytes)}（v${PUBLISHED_RELEASE.version}）` : ""}<br />Windows 10／11（64ビット）<br /><Link data-lp-event="install_guide" href="/download">インストールの流れ</Link></p>
          </> : <Link data-lp-event="example" href="/demo" className={lp.primary}>デモを体験する <span aria-hidden="true">→</span></Link>}
        </li>
        <li className={lp.stop}>
          <h3>研究室向けクラウド機能</h3>
          <p>クラウド GPU での検出や、AI による解析提案・考察を使えます。利用には承認とログインが必要です。</p>
          <a className={lp.secondary} data-lp-event="consult" href={CONTACT_URL} target="_blank" rel="noopener noreferrer">研究室で導入を相談 <Out /></a>
        </li>
      </ol>
    </div>
    <div id="guide" className={[lp.wide, lp.faq].join(" ")}>
      <h2 className={lp.faqTitle}>よくある質問</h2>
      <div className={lp.faqList}>
        <details><summary>料金は？</summary><p>Windows 版を入手して PC 上で解析するのは無料です。研究室向けクラウド機能の料金は、導入時にご案内します。</p></details>
        <details><summary>画像は PC の外に出ますか？</summary><p>PC 上で解析するときは、画像と結果を PC に保存します。クラウド GPU で検出するときは対象の画像を送ります。AI への解析相談では、指示や画像の記録に加えて縮小画像を送る場合があります。縮小画像は設定で送らないようにできます。<Link href="/privacy">機能ごとに送る情報を確認する</Link></p></details>
        <details><summary>どのPCで使えますか？</summary><p>{WINDOWS_STORE_LINKS ? "Windows 11（x64）" : "Windows 10または11（64ビット）"}、メモリ8 GB以上、空き容量6 GB以上を目安にしてください。管理者権限もコマンド入力も要りません。</p></details>
        <details><summary>クラウド機能を使うには？</summary><p>研究室のメールアドレスで利用を申請します。承認後に、作業画面でメールに届くコードを入力してください。</p><a data-lp-event="consult" href={CONTACT_URL} target="_blank" rel="noopener noreferrer">研究室で導入を相談 <Out /></a></details>
        <details id="launch"><summary>インストール済みの場合は？</summary><p>{WINDOWS_STORE_LINKS ? "スタートメニューで「Cytellect」を選びます。" : "デスクトップの「Cytellect」から開けます。"}作業画面が開かないときは、起動画面の「作業画面を開く」を押してください。</p></details>
      </div>
      <p className={lp.faqContact}>ほかのご質問は、<a data-lp-event="contact" href={CONTACT_URL} target="_blank" rel="noopener noreferrer">お問い合わせ <Out /></a>から。</p>
    </div>
  </section>;
}
