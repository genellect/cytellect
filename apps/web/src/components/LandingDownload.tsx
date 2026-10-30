import Link from "next/link";
import { PUBLISHED_RELEASE, WINDOWS_RELEASE_URL, releaseSize, windowsReleaseAsset } from "@/lib/release";
import { CONTACT_URL } from "@/lib/site";
import { DownloadStart } from "./DownloadStart";
import lp from "./optical-landing.module.css";

const INSTALLER = windowsReleaseAsset(WINDOWS_RELEASE_URL) === "installer";
const Out = () => <span aria-hidden="true">↗</span>;

/** The LP's last step: start free on this PC, or bring the lab cloud in. Questions stay folded;
 *  how to install lives on /download. */
export function LandingDownload() {
  return <section id="download" className={[lp.section, lp.download].join(" ")} aria-labelledby="download-title">
    <div className={lp.wide}>
      <div className={lp.offer}>
        <div className={lp.offerBase}>
          <div>
            <h2 id="download-title" className={lp.display}>Windows版は無料。測定も保存も、あなたのPCで。</h2>
            <p className={lp.offerLead}>核のセグメンテーションから統計、論文の図まで。画像はPCの外に出ません。</p>
          </div>
          {WINDOWS_RELEASE_URL ? <div className={lp.offerAction}>
            <DownloadStart url={WINDOWS_RELEASE_URL} installer={INSTALLER} />
            <p className={lp.meta}>{INSTALLER ? "インストーラー" : "ZIP"}{PUBLISHED_RELEASE?.url === WINDOWS_RELEASE_URL ? `・${releaseSize(PUBLISHED_RELEASE.size_bytes)}・v${PUBLISHED_RELEASE.version}` : ""}・Windows 10／11（64ビット）<br /><Link data-lp-event="install_guide" href="/download">インストールの流れ</Link></p>
          </div> : <Link data-lp-event="example" href="/demo" className={lp.primary}>デモを体験する <span aria-hidden="true">→</span></Link>}
        </div>
        <div className={lp.offerCloud}>
          <div>
            <h3>研究室のクラウドなら、GPU推論とLLMも。</h3>
            <p>核小体や細胞の検出はクラウドのGPUで。やりたい解析を書けば、LLMが設定を組み立てます。料金は応相談、大学内での試験導入は基本無料です。</p>
          </div>
          <a className={lp.secondary} data-lp-event="consult" href={CONTACT_URL} target="_blank" rel="noopener noreferrer">研究室で導入を相談 <Out /></a>
        </div>
      </div>
    </div>
    <div id="guide" className={[lp.wide, lp.faq].join(" ")}>
      <h2 className={lp.faqTitle}>よくある質問</h2>
      <div className={lp.faqList}>
        <details><summary>料金は？</summary><p>Windows版は無料です。GPU推論とLLMを使う研究室のクラウドは応相談で、大学内での試験導入は基本無料です。</p></details>
        <details><summary>画像はPCの外に出ますか？</summary><p>Windows版では出ません。画像も結果も、あなたのPCの中だけに保存します。クラウドのGPUを使うときも、送るのは検出に使う画像だけで、クラウドには残りません。LLMに渡るのは、入力した文だけです。</p></details>
        <details><summary>どのPCで使えますか？</summary><p>Windows 10または11（64ビット）、メモリ8 GB以上、空き容量6 GB以上。管理者権限もコマンド入力も要りません。</p></details>
        <details><summary>GPU推論とLLMを使うには？</summary><p>導入のご相談のあと、研究室のメールアドレスを登録します。あとは作業画面で、メールに届くコードを入れるだけです。</p><a data-lp-event="consult" href={CONTACT_URL} target="_blank" rel="noopener noreferrer">研究室で導入を相談 <Out /></a></details>
        <details id="launch"><summary>インストール済みの場合は？</summary><p>デスクトップの「Cytellect」から開けます。作業画面が開かないときは、起動画面の「作業画面を開く」を押してください。</p></details>
      </div>
      <p className={lp.faqContact}>ほかのご質問は、<a data-lp-event="contact" href={CONTACT_URL} target="_blank" rel="noopener noreferrer">お問い合わせ <Out /></a>から。</p>
    </div>
  </section>;
}
