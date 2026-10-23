import Link from "next/link";
import { LandingAnalytics } from "./LandingAnalytics";
import { PUBLISHED_RELEASE, WINDOWS_RELEASE_URL } from "@/lib/release";
import { ProductMenu } from "./ProductMenu";
import { HeroFilm } from "./HeroFilm";
import { LandingFeatures } from "./LandingFeatures";
import { LandingStory } from "./LandingStory";
import { LandingHomeLink } from "./LandingHomeLink";
import styles from "./product.module.css";
import lp from "./optical-landing.module.css";

const docs = "https://github.com/genellect/cytellect/blob/main/docs/";
const Arrow = () => <span aria-hidden="true">↗</span>;
const Forward = () => <span aria-hidden="true">→</span>;
/** No titles: a section opens with its own first sentence, set large. */
function Display({ id, text }: { id: string; text: string }) {
  return <h2 id={id} className={lp.display}>{text}</h2>;
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
        <div className={lp.heroCopy}><h1 id="hero-title" lang="en" aria-label="Get your microscopy publication-ready."><span>Get your</span>{" "}<span>microscopy</span>{" "}<span>publication-<br className={lp.mobileBreak} />ready.</span></h1><div className={lp.heroActions}><a data-lp-event="download_section" href="#download" className={lp.primary}>ダウンロード <span aria-hidden="true">↓</span></a><Link data-lp-event="example" href="/demo" className={lp.heroSecondary}>解析例を見る <Forward /></Link></div></div>
      </section>

      <section className={lp.mission} aria-labelledby="mission-title">
        <div className={lp.column}>
          <h2 id="mission-title" className={lp.manifesto}>画像解析を、一部の専門家の技術から、すべての生命科学研究者が使える研究基盤に。</h2>
          <p className={lp.missionLead}>Cytellectは、蛍光顕微鏡の画像をアップロードするだけで、画像解析から統計解析、論文に使えるグラフの作成までを一貫して行えるソフトウェアです。</p>
        </div>
      </section>
      <LandingStory />

      <figure className={lp.band}><img src="/marketing/lp-pipetting.webp" alt="白い実験台でマルチチャンネルピペットを使う手元" width={2400} height={1600} loading="lazy" /></figure>

      <section id="workflow" className={lp.section} aria-labelledby="workflow-title">
        <div className={lp.column}>
          <Display id="workflow-title" text="手作業で数週間かかっていた解析を、一つの画面で数分に。" />
        </div>
        <LandingFeatures />
      </section>

      <figure className={[lp.band, lp.bandLow].join(" ")}><img src="/marketing/lp-dish.webp" alt="淡いミント色の面に置いたシャーレとガラス管" width={2400} height={1597} loading="lazy" /></figure>

      <section className={lp.section} aria-labelledby="impact-title">
        <div className={lp.column}>
          <Display id="impact-title" text="核の形、核と細胞質の輝度の比、核小体の数と大きさは、がんやALS、認知症、老化の研究で使われている指標です。" />
          <div className={lp.prose}><p>研究室をまたいで同じ基準で測れれば、病気の仕組みの解明や新薬の候補選びにつながります。Cytellectは現在、核と核小体の自動検出に対応しており、細胞質の検出は追加学習を進めています。</p></div>
        </div>
      </section>

      <section id="download" className={[lp.section, lp.download].join(" ")} aria-labelledby="download-title">
        <div className={lp.wide}>
          <Display id="download-title" text="画像の解析はすべて手元のPCの中で行い、研究画像を外部に送りません。" />
          <div className={lp.prose}><p>CytellectのWindows（x64）版は無料です。PCの中で動く解析画面をブラウザで操作し、画像はPCの外に出ません。解析中のデータはPC内の専用フォルダーに置き、最後の操作から24時間で削除するので、必要な結果はCSV・SVG・PDFで書き出してください。解析のコードはApache-2.0で公開しており、測定と統計の計算方法を誰でも確かめられます。</p></div>
          <div className={lp.actions}>{WINDOWS_RELEASE_URL?<><a className={lp.primary} data-lp-event="download" href={WINDOWS_RELEASE_URL} rel="noreferrer">Windows版をダウンロード <span aria-hidden="true">↓</span></a>{PUBLISHED_RELEASE?.url===WINDOWS_RELEASE_URL&&<a className={lp.release} href={`https://github.com/genellect/cytellect/releases/tag/v${PUBLISHED_RELEASE.version}`}>v{PUBLISHED_RELEASE.version} · リリース情報 <Arrow /></a>}</>:null}<Link data-lp-event="example" href="/demo" className={lp.button}>解析例を見る <Forward /></Link><a href="https://github.com/genellect/cytellect" className={lp.button}>GitHub <Arrow /></a></div>
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
