import Link from "next/link";
import { LandingAnalytics } from "./LandingAnalytics";
import { PUBLISHED_RELEASE, WINDOWS_RELEASE_URL } from "@/lib/release";
import { ProductMenu } from "./ProductMenu";
import { HeroFilm } from "./HeroFilm";
import { LandingStory } from "./LandingStory";
import { LandingHomeLink } from "./LandingHomeLink";
import styles from "./product.module.css";
import lp from "./optical-landing.module.css";

const docs = "https://github.com/genellect/cytellect/blob/main/docs/";
const Arrow = () => <span aria-hidden="true">↗</span>;
const Forward = () => <span aria-hidden="true">→</span>;
/** Lines break only between the phrases separated by "|". */
function Phrases({ text }: { text: string }) {
  return <>{text.split("|").map((phrase, index) => <span key={index}>{index > 0 && <wbr />}{phrase}</span>)}</>;
}
/** No titles: each beat opens with one sentence, set large. */
function Statement({ id, text, large }: { id: string; text: string; large?: boolean }) {
  return <h2 id={id} className={large ? lp.manifesto : lp.statement}><Phrases text={text} /></h2>;
}
function NavigationLinks(){return <><a href="#workflow">プロダクト</a><a data-lp-event="guide" href="#guide">ガイド</a><a href="https://yuto-matsui.com/">About the Developer</a><a data-lp-event="download_section" href="#download" className={lp.navDownload}>ダウンロード <span aria-hidden="true">↓</span></a></>;}

export default function PublicLanding() {
  return <div className={lp.page} data-cytellect-public-page="/">
    <LandingAnalytics page="/" />
    <a className={styles.skipLink} href="#main">本文へ</a>
    <header className={lp.header}><LandingHomeLink className={lp.wordmark} /><nav className={lp.navigation} aria-label="メインナビゲーション"><NavigationLinks /></nav><ProductMenu><NavigationLinks /></ProductMenu></header>
    <main id="main">
      <section id="top" className={lp.hero} aria-labelledby="hero-title">
        <HeroFilm />
        <div className={lp.heroShade} />
        <div className={lp.heroCopy}>
          <h1 id="hero-title" lang="en" aria-label="Get your microscopy publication-ready."><span>Get your</span>{" "}<span>microscopy</span>{" "}<span>publication-<br className={lp.mobileBreak} />ready.</span></h1>
          <p className={lp.heroLead}>画像をアップロードするだけで、<br className={lp.mobileBreak} />論文の図まで。</p>
          <div className={lp.heroActions}><Link data-lp-event="example" href="/demo" className={lp.primary}>デモを触る <Forward /></Link><a data-lp-event="download_section" href="#download" className={lp.heroSecondary}>ダウンロード <span aria-hidden="true">↓</span></a></div>
        </div>
      </section>

      <section className={lp.mission} aria-labelledby="mission-title">
        <div className={lp.wide}><Statement id="mission-title" large text="画像解析を、|一部の専門家の|技術から、|すべての|生命科学研究者の|ものへ。" /></div>
      </section>
      <LandingStory />

      <section className={lp.beat} aria-labelledby="practice-title">
        <figure className={lp.bleed}><img src="/marketing/lp-pipetting.webp" alt="白い実験台でマルチチャンネルピペットを使う手元" width={2400} height={1600} loading="lazy" /></figure>
        <div className={lp.column}><Statement id="practice-title" text="一つずつ|輪郭を描き、|数字を|表に写し、|ソフトを|渡り歩く。|その時間を、|研究に返す。" /></div>
      </section>

      <section id="workflow" className={[lp.beat, lp.dark].join(" ")} aria-labelledby="detection-title">
        <div className={lp.column}>
          <Statement id="detection-title" text="核も、|核小体も。|輪郭は、|もう手で|描かない。" />
          <div className={lp.prose}><p>機械学習モデルが蛍光画像から核と核小体を見つけ、一つずつ面積と輝度を測ります。</p></div>
        </div>
        <figure className={lp.specimen}>
          <picture><source media="(max-width: 760px)" srcSet="/marketing/lp-field-mobile.webp" width={1080} height={1080} /><img src="/marketing/lp-field.webp" alt="公開デモの蛍光画像。青い核と桃色の核小体を、Cytellectが検出した輪郭が囲んでいる" width={1536} height={864} loading="lazy" /></picture>
          <figcaption>公開デモの視野と、Cytellectの検出結果。画像：Schmidt, Rohatgi, Brandman (2022), Zenodo, CC BY 4.0</figcaption>
        </figure>
        <div className={[lp.wide, lp.numbers].join(" ")}>
          <p><strong>0%<span aria-hidden="true"> → </span><span className={lp.visuallyHidden}>から</span>90%</strong><span>核小体の検出率。研究室の画像で追加学習した前と後。</span></p>
          <p><strong>92%</strong><span>核の検出精度。</span></p>
        </div>
        <div className={lp.column}><Link data-lp-event="demo_image" href="/demo?step=image" className={lp.button}>公開デモで検出結果を確かめる <Forward /></Link></div>
      </section>

      <section className={lp.beat} aria-labelledby="workspace-title">
        <div className={lp.column}>
          <Statement id="workspace-title" text="直した輪郭は、|そのまま|数値に、|統計に、|図に。" />
          <div className={lp.prose}><p>検出がずれた核は、画像の上で直すだけ。測定値から統計、論文の図までが一つのワークスペースでつながり、気になる値からはいつでも元の画像に戻れます。</p></div>
        </div>
        <figure className={[lp.wide, lp.screen].join(" ")}><picture><source media="(max-width: 760px)" srcSet="/marketing/lp-workspace-mobile.webp" width={1080} height={871} /><img src="/marketing/lp-workspace.webp" alt="Cytellectの公開デモ。視野の一覧、核の輪郭を重ねた蛍光画像、核ごとの測定値、解析の設定が一つの画面に並ぶ" width={2880} height={1800} loading="lazy" /></picture></figure>
        <div className={lp.column}><Link data-lp-event="example" href="/demo" className={lp.button}>デモで輪郭を直してみる <Forward /></Link></div>
      </section>

      <section className={[lp.beat, lp.paperBeat].join(" ")} aria-labelledby="statistics-title">
        <div className={lp.column}>
          <Statement id="statistics-title" text="n は、|細胞の数ではなく、|実験の回数。" />
          <div className={lp.prose}><p>何百個の細胞を測っても、比べるのは独立した実験どうし。Cytellectは実験の組み方に合った比較を選び、そのまま論文の図に仕上げます。編集できるSVG・PDFと、元の測定値も一緒に。</p></div>
        </div>
        <figure className={[lp.wide, lp.paper].join(" ")}>
          <a href="/marketing/lp-figure.svg" aria-label="図を拡大"><img src="/marketing/lp-figure.svg" alt="公開デモから書き出した箱ひげ図。未処理とアクチノマイシンD処理で、核のNPM1平均輝度を独立した実験3回ずつ比べている" width={518.74} height={283.46} loading="lazy" /></a>
          <figcaption>公開デモの書き出し。核のNPM1平均輝度、未処理とアクチノマイシンD、独立した実験 n = 3。</figcaption>
        </figure>
        <div className={[lp.column, lp.links].join(" ")}><Link data-lp-event="demo_figure" href="/demo?step=figure" className={lp.button}>デモで統計と図を見る <Forward /></Link><Link data-lp-event="planning" href="/plan" className={lp.button}>解析設定を見る <Forward /></Link></div>
      </section>

      <section className={lp.trust} aria-labelledby="trust-title">
        <img src="/marketing/lp-dish.webp" alt="" width={2400} height={1597} loading="lazy" />
        <div className={lp.trustCopy}>
          <Statement id="trust-title" text="研究画像は、|あなたのPCから|出ない。" />
          <div className={lp.prose}><p>解析はすべてPCの中で。コードはApache-2.0で公開しているので、測定と統計の計算方法を誰でも確かめられます。</p></div>
          <div className={lp.links}><a href="https://github.com/genellect/cytellect" className={lp.button}>GitHub <Arrow /></a><a data-lp-event="methods" href={docs+"methods.md"} className={lp.button}>解析方法 <Arrow /></a></div>
        </div>
      </section>

      <section id="download" className={[lp.beat, lp.download].join(" ")} aria-labelledby="download-title">
        <div className={lp.wide}>
          <Statement id="download-title" large text="次の論文の図を、|今日の画像から。" />
          <div className={lp.actions}>{WINDOWS_RELEASE_URL?<><a className={lp.primary} data-lp-event="download" href={WINDOWS_RELEASE_URL} rel="noreferrer">Windows版をダウンロード <span aria-hidden="true">↓</span></a><Link data-lp-event="example" href="/demo" className={lp.button}>デモを触る <Forward /></Link>{PUBLISHED_RELEASE?.url===WINDOWS_RELEASE_URL&&<a className={lp.release} href={`https://github.com/genellect/cytellect/releases/tag/v${PUBLISHED_RELEASE.version}`}>v{PUBLISHED_RELEASE.version} · リリース情報 <Arrow /></a>}</>:<Link data-lp-event="example" href="/demo" className={lp.primary}>デモを触る <Forward /></Link>}</div>
          <p className={lp.note}>Windows PCで動作します。初回のセットアップ後は、ブラウザから画像を登録して解析できます。</p>
        </div>
        <div id="guide" className={[lp.wide, lp.guide].join(" ")}>
          <h2 className={lp.label}>使い方と解析方法</h2>
          <nav aria-label="使い方と解析方法"><a data-lp-event="quickstart" href={docs+"quickstart.ja.md"}>はじめての解析 <Arrow /></a><a data-lp-event="methods" href={docs+"methods.md"}>測定値と統計の定義 <Arrow /></a><a data-lp-event="setup" href={docs+"local.md"}>動作環境と導入手順 <Arrow /></a><a data-lp-event="figures" href={docs+"figures.md"}>出力できる図と形式 <Arrow /></a></nav>
        </div>
        <div className={[lp.wide, lp.details].join(" ")}>
          <div id="launch" className={lp.prose}><h3>インストール済みの方</h3><p>デスクトップの「Cytellect」を開くと、解析画面がブラウザに表示されます。起動済みの場合は、Cytellectの起動画面で「ブラウザで開く」を選択してください。</p><p>再ダウンロード・再インストールは不要です。</p><Link data-lp-event="workspace" href="/workspace" className={lp.button}>解析画面を開く <Forward /></Link></div>
          <div id="scope" className={lp.prose}>
            <details><summary>対応する画像と解析</summary><p>核と核小体は、機械学習モデルで自動検出します。GFPなどのシグナルは、検出した核での測定や、しきい値・手動の輪郭・整数ラベルで領域にして測れます。</p><p>読み込めるのは、8／16-bitグレースケールのチャンネル別2D TIFFと、対応範囲の単一シリーズOME-TIFF（Z=1、T=1）です。大きな画像は検出用に縮小した複製で検出し、測定は元の画素で行います。3D、時系列、細胞全体の境界の自動検出には、まだ対応していません。</p></details>
            <details><summary>インストールと動作環境</summary><p>Windows x64用のZIPを展開し、Cytellect Setup.cmdを開いてください。初回はインターネットに接続して解析環境を取得します。その後はショートカットから起動できます。</p><p>解析はPC内で実行します。アップロードした研究画像が、この公開サイトに送られることはありません。</p><a data-lp-event="setup" href={docs+"local.md"}>詳しいセットアップ手順 <Arrow /></a></details>
            <details><summary>保存先と削除について</summary><p>画像と解析結果はPC内のCytellect専用フォルダーに保存します。公開サイトや外部AIには送信しません。</p><p>保存期限は最後の明示的な操作から24時間です。終了中に期限を迎えたデータは次回起動時に削除します。</p><p>必要な結果は保存機能から書き出してください。作業の削除はワークスペース内から実行できます。</p></details>
          </div>
        </div>
      </section>
    </main>
    <footer className={lp.footer}><div className={lp.sectionShell}><a href="#top" className={lp.footerBrand}>cytellect</a><nav aria-label="製品情報"><a href="https://github.com/genellect/cytellect">GitHub <Arrow /></a><a href="https://github.com/genellect/cytellect/blob/main/SECURITY.md">セキュリティ <Arrow /></a><a href="/marketing/provenance.json">画像・映像の出典 <Arrow /></a></nav><p className={lp.copyright}>&copy; 2026 Genellect Inc. All rights reserved.</p></div></footer>
  </div>;
}
