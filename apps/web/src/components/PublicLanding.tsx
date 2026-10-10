import Link from "next/link";
import { LandingAnalytics } from "./LandingAnalytics";
import { PUBLISHED_RELEASE, WINDOWS_RELEASE_URL } from "@/lib/release";
import { ProductMenu } from "./ProductMenu";
import { CellHero } from "./CellHero";
import { LandingStory } from "./LandingStory";
import { EvidenceExample, ProductWalkthrough } from "./MarketingMotion";
import styles from "./product.module.css";
import lp from "./lp-sections.module.css";

const docs = "https://github.com/genellect/cytellect/blob/main/docs/";
const Arrow = () => <span aria-hidden="true">↗</span>;
/** No titles: a section opens with its own first sentence, set large. */
function Display({ id, text }: { id: string; text: string }) {
  return <h2 id={id} className={lp.display}>{text}</h2>;
}
function NavigationLinks(){return <><a href="#workflow">プロダクト</a><Link data-lp-event="example" href="/demo">解析例</Link><Link data-lp-event="workspace" href="/workspace">解析画面</Link><a data-lp-event="guide" href="#guide">ガイド</a><a data-lp-event="download_section" href="#download" className={styles.navDownload}>ダウンロード <Arrow /></a><a data-lp-event="launch" href="#launch">インストール済みの方</a></>;}

export default function PublicLanding() {
  return <div className={[styles.page, lp.page].join(" ")} data-cytellect-public-page="/">
    <LandingAnalytics page="/" />
    <a className={styles.skipLink} href="#main">本文へ</a>
    <header className={styles.header}><a href="#top" aria-label="Cytellect ホーム" className={styles.wordmark}>cytellect</a><nav className={styles.navigation} aria-label="メインナビゲーション"><NavigationLinks /></nav><ProductMenu><NavigationLinks /></ProductMenu></header>
    <main id="main">
      <section className={styles.hero} aria-labelledby="hero-title">
        <CellHero /><div className={styles.heroShade} />
        <div className={styles.heroCopy}><h1 id="hero-title" lang="en"><span>Get your</span>{" "}<span>microscopy</span>{" "}<span>publication-ready.</span></h1><div className={styles.heroActions}><a data-lp-event="download_section" href="#download" className={styles.primary}>ダウンロード <Arrow /></a><Link data-lp-event="example" href="/demo" className={styles.heroSecondary}>解析例を見る <Arrow /></Link></div></div>
      </section>

      <LandingStory />

      <figure className={lp.band}><img src="/marketing/photo-lab-automation.webp" alt="実験室の分注装置" width={1920} height={1280} loading="lazy" /></figure>

      <section id="workflow" className={lp.section} aria-labelledby="workflow-title">
        <div className={lp.column}>
          <Display id="workflow-title" text="Cytellectは、顕微鏡画像の解析から統計、論文用グラフの作成までをつなぐ、研究者のためのソフトウェアです。" />
          <div className={lp.prose}><p>一枚ずつの測定や、ソフトを移るたびのデータ整理。Cytellectは、画像の定量から集計までを一つのワークスペースでつなぎます。代表画像で確認した条件をまとめて適用し、気になる値は元の画像に戻って確認できます。</p></div>
        </div>
        <div className={[lp.wide, lp.media].join(" ")}>
          <figure className={lp.panel}><ProductWalkthrough /></figure>
          <EvidenceExample />
        </div>
      </section>

      <section className={lp.section} aria-labelledby="comparison-title">
        <div className={lp.column}>
          <Display id="comparison-title" text="画像解析や統計が専門でなくても、必要な設定を画面で確認しながら進められます。" />
          <div className={lp.prose}><p>測定方法から、実験の組み方に合った比較まで。解析の根拠を理解しながら、自分の研究に取り組めます。</p></div>
          <Link data-lp-event="planning" href="/plan" className={lp.button}>解析設定を見る <Arrow /></Link>
        </div>
        <div className={[lp.wide, lp.media, lp.pair].join(" ")}>
          <figure className={[lp.panel, lp.photo].join(" ")}><img src="/marketing/photo-pipetting.webp" alt="手袋を着けてピペットで試料を扱う手元" width={1920} height={2658} loading="lazy" /></figure>
          <figure className={lp.panel}><a href="/marketing/planning-public.png" aria-label="統計画面を拡大"><img src="/marketing/planning-public.png" alt="公開画像3視野の核の平均輝度を、視野ごとの分布と集計表で示した統計画面" width={1440} height={950} loading="lazy" /></a></figure>
        </div>
      </section>

      <section className={lp.section} aria-labelledby="figures-title">
        <div className={lp.column}>
          <Display id="figures-title" text="積み重ねた実験の成果を、論文で伝わるグラフへ。" />
          <div className={lp.prose}><p>測定結果から図を作り、誌面に合わせたサイズで出力できます。編集可能なSVG・PDFと元データを書き出し、論文の仕上げへ進めます。</p></div>
          <a data-lp-event="figures" href={docs+"figures.md"} className={lp.button}>出力できる図と形式 <Arrow /></a>
        </div>
        <div className={[lp.wide, lp.media].join(" ")}>
          <div className={[lp.light, lp.figureStage].join(" ")}>
            <figure className={styles.paperFigure}><a className={styles.paper} href="/marketing/figure-public.svg" aria-label="グラフを拡大"><picture><source media="(max-width: 760px)" srcSet="/marketing/figure-public-mobile.svg" /><img src="/marketing/figure-public.svg" alt="公開画像の817領域の面積分布を示すCytellectの出力図" width={518.74} height={216} loading="lazy" /></picture></a></figure>
          </div>
          <div className={lp.caption}><span>公開画像の測定値から出力した図</span><nav aria-label="図の元データ"><a href="/marketing/figure-public.svg">図を拡大</a><a href="/marketing/figure-public.csv">測定値 CSV</a><a href="/marketing/figure-source.json">作図条件</a><a href="/marketing/provenance.json">出典</a></nav></div>
        </div>
      </section>

      <section id="guide" className={lp.section} aria-labelledby="guide-title">
        <div className={lp.wide}>
          <h2 id="guide-title" className={lp.label}>使い方と解析方法</h2>
          <div className={lp.cards}>
            <a className={lp.card} data-lp-event="quickstart" href={docs+"quickstart.ja.md"}><span><b>はじめての解析</b><small>公開画像を使って操作する</small></span><Arrow /></a>
            <a className={lp.card} data-lp-event="methods" href={docs+"methods.md"}><span><b>解析方法</b><small>測定値と統計の定義を読む</small></span><Arrow /></a>
            <a className={lp.card} data-lp-event="setup" href={docs+"local.md"}><span><b>セットアップ</b><small>動作環境と導入手順を確認する</small></span><Arrow /></a>
          </div>
        </div>
      </section>

      <section id="download" className={lp.section} aria-labelledby="download-title">
        <div className={lp.wide}>
          <div className={[lp.light, lp.cta].join(" ")}>
            <Display id="download-title" text="Cytellectは、Windows PCで動作します。" />
            <div className={lp.prose}><p>初回セットアップ後は、ブラウザから画像を登録して解析できます。</p></div>
            <div className={lp.actions}>{WINDOWS_RELEASE_URL?<><a className={styles.primary} data-lp-event="download" href={WINDOWS_RELEASE_URL} rel="noreferrer">Windows版をダウンロード <span aria-hidden="true">↓</span></a>{PUBLISHED_RELEASE?.url===WINDOWS_RELEASE_URL&&<a className={lp.release} href={`https://github.com/genellect/cytellect/releases/tag/v${PUBLISHED_RELEASE.version}`}>v{PUBLISHED_RELEASE.version} · リリース情報 <Arrow /></a>}</>:<Link data-lp-event="example" href="/demo" className={styles.primary}>公開画像を見る <Arrow /></Link>}</div>
          </div>
        </div>
        <div className={[lp.column, lp.details].join(" ")}>
          <div id="launch" className={lp.prose}><h3>インストール済みの方</h3><p>デスクトップの「Cytellect」を開くと、解析画面がブラウザに表示されます。起動済みの場合は、Cytellectの起動画面で「ブラウザで開く」を選択してください。</p><p>再ダウンロード・再インストールは不要です。</p></div>
          <div id="scope" className={lp.prose}>
            <details><summary>対応する画像と解析</summary><p>汎用の領域解析は8／16-bitグレースケールのチャンネル別2D TIFFを扱います。核・核小体・GFPの専用レシピでは、対応範囲の単一シリーズOME-TIFF（Z=1、T=1）も読み込めます。手動・整数ラベル・確認した核染色からの検出領域で、面積・輝度を測定できます。</p><p>3D、時系列、自動細胞境界検出、任意の構造の自動検出は対象外です。大きな画像では、検出用に縮小した複製で核を検出し、測定は元の画素で行います。</p></details>
            <details><summary>インストールと動作環境</summary><p>Windows x64用のZIPを展開し、Cytellect Setup.cmdを開いてください。初回はインターネットに接続して解析環境を取得します。その後はショートカットから起動できます。</p><p>解析はPC内で実行します。アップロードした研究画像が、この公開サイトに送られることはありません。</p><a data-lp-event="setup" href={docs+"local.md"}>詳しいセットアップ手順 <Arrow /></a></details>
            <details><summary>保存先と削除について</summary><p>画像と解析結果はPC内のCytellect専用フォルダーに保存します。公開サイトや外部AIには送信しません。</p><p>保存期限は最後の明示的な操作から24時間です。終了中に期限を迎えたデータは次回起動時に削除します。</p><p>必要な結果は保存機能から書き出してください。作業の削除はワークスペース内から実行できます。</p></details>
          </div>
        </div>
      </section>
    </main>
    <footer className={styles.footer}><div className={styles.sectionShell}><a href="#top" className={styles.footerBrand}>cytellect</a><nav aria-label="製品情報"><a href="https://github.com/genellect/cytellect">GitHub <Arrow /></a><a href="https://github.com/genellect/cytellect/blob/main/SECURITY.md">セキュリティ <Arrow /></a><a href="/marketing/provenance.json">画像・映像の出典 <Arrow /></a></nav><p className={styles.copyright}>&copy; 2026 Yuto Matsui. All rights reserved.</p></div></footer>
  </div>;
}
