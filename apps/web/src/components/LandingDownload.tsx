import Link from "next/link";
import { PUBLIC_SHOWCASE } from "@/lib/api";
import { releaseSize, windowsReleaseAsset } from "@/lib/release";
import { publicWindowsRelease } from "@/lib/public-windows-release";
import { CONTACT_URL } from "@/lib/site";
import { DownloadStart } from "./DownloadStart";
import lp from "./landing-world.module.css";

const Out = () => <span aria-hidden="true">↗</span>;

/** The LP's last step, drawn as one line like the patient path above it: start free on your own PC,
 *  then bring the lab cloud in. Questions stay folded; how to install lives on /download. */
export async function LandingDownload() {
  const { url, release } = await publicWindowsRelease();
  const installer = windowsReleaseAsset(url) === "installer";
  return <section id="download" className={lp.download} aria-labelledby="download-title">
    <div className={lp.shell}>
      <h2 id="download-title" className={lp.statement}>まず、あなたのPCで。そして、研究室へ。</h2>
      <ol className={lp.journey}>
        <li className={lp.stop}>
          <h3>Windows版は無料。</h3>
          <p>検出と測定から、統計、結論と考察、論文の図まで。画像はPCの外に出ません。</p>
          {PUBLIC_SHOWCASE ? <DownloadStart url={url} installer={installer} classes={lp} />
            : <Link data-lp-event="example" href="/demo" className={lp.primary}>デモを体験する <span aria-hidden="true">→</span></Link>}
          {PUBLIC_SHOWCASE && <p className={lp.meta}>{url && <>{installer ? "インストーラー" : "ZIP"}{release ? ` ${releaseSize(release.size_bytes)}（v${release.version}）` : ""}<br />Windows 10／11（64ビット）<br /></>}<Link data-lp-event="install_guide" href="/download">インストールの流れ</Link></p>}
        </li>
        <li className={lp.stop}>
          <h3>研究室のクラウドは応相談。</h3>
          <p>GPU推論とLLMで、高精度の検出も、解析の設定も、結果の考察も。大学内での試験導入は、基本無料です。</p>
          <a className={lp.secondary} data-lp-event="consult" href={CONTACT_URL} target="_blank" rel="noopener noreferrer">研究室で導入を相談 <Out /></a>
        </li>
      </ol>
    </div>
    <div id="guide" className={[lp.shell, lp.faq].join(" ")}>
      <h2 className={lp.faqTitle}>よくある質問</h2>
      <div className={lp.faqList}>
        <details><summary>料金は？</summary><p>Windows版は無料です。GPU推論とLLMを使う研究室のクラウドは応相談で、大学内での試験導入は基本無料です。</p></details>
        <details><summary>画像はPCの外に出ますか？</summary><p>Windows版では出ません。画像も結果も、あなたのPCの中だけに保存します。クラウドのGPUで検出するときは、検出に使う画像だけを送り、クラウドには残しません。LLMに解析を相談するときは、書いた目的、チャンネル名や視野の記録、代表的な視野の縮小画像を、あなたが同意した範囲で送ります。縮小画像は設定で止められます。</p></details>
        <details><summary>どのPCで使えますか？</summary><p>Windows 10または11（64ビット）、メモリ8 GB以上、空き容量6 GB以上。管理者権限もコマンド入力も要りません。</p></details>
        <details><summary>GPU推論とLLMを使うには？</summary><p>導入のご相談のあと、研究室のメールアドレスを登録します。あとは作業画面で、メールに届くコードを入れるだけです。</p><a data-lp-event="consult" href={CONTACT_URL} target="_blank" rel="noopener noreferrer">研究室で導入を相談 <Out /></a></details>
        <details id="launch"><summary>インストール済みの場合は？</summary><p>デスクトップの「Cytellect」から開けます。作業画面が開かないときは、起動画面の「作業画面を開く」を押してください。</p></details>
      </div>
      <p className={lp.faqContact}>ほかのご質問は、<a data-lp-event="contact" href={CONTACT_URL} target="_blank" rel="noopener noreferrer">お問い合わせ <Out /></a>から。</p>
    </div>
  </section>;
}
