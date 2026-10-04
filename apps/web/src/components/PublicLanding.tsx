import Link from "next/link";
import { PUBLISHED_RELEASE, WINDOWS_RELEASE_URL } from "@/lib/release";
import { EditorialHeading } from "./EditorialHeading";
import { PublicationStage } from "./PublicationStage";
import { ProductMenu } from "./ProductMenu";
import { MicroscopyMotion, EvidenceExample, ProductWalkthrough } from "./MarketingMotion";
import styles from "./product.module.css";

const docs = "https://github.com/genellect/cytellect/blob/main/docs/";
const Arrow = () => <span aria-hidden="true">↗</span>;
function NavigationLinks(){return <><a href="#workflow">プロダクト</a><Link href="/demo">解析例</Link><a href="#guide">ガイド</a><a href="#download" className={styles.navDownload}>ダウンロード <Arrow /></a></>;}

export default function PublicLanding() {
  return <div className={styles.page}>
    <a className={styles.skipLink} href="#main">本文へ</a>
    <header className={styles.header}><Link href="/" aria-label="Cytellect ホーム" className={styles.wordmark}>cytellect</Link><nav className={styles.navigation} aria-label="メインナビゲーション"><NavigationLinks /></nav><ProductMenu><NavigationLinks /></ProductMenu></header>
    <main id="main">
      <section className={styles.hero} aria-labelledby="hero-title">
        <MicroscopyMotion /><div className={styles.heroShade} />
        <div className={styles.heroCopy}><h1 id="hero-title" lang="en"><span>Get your</span>{" "}<span>microscopy</span>{" "}<span>publication-ready.</span></h1><div className={styles.heroActions}><a href="#download" className={styles.primary}>ダウンロード <Arrow /></a><Link href="/demo" className={styles.heroSecondary}>解析例を見る <Arrow /></Link></div></div>
      </section>

      <section id="workflow" className={styles.overview} aria-labelledby="workflow-title">
        <div className={styles.sectionShell}>
          <p className={styles.introduction}>Cytellectは、顕微鏡画像の解析から統計、論文用グラフの作成までをつなぐ、研究者のためのソフトウェアです。</p>
          <div className={styles.editorialGrid}><EditorialHeading id="workflow-title" title={<><span className={styles.headingPhrase}>研究に使える</span><span className={styles.headingPhrase}>時間を、もっと。</span></>} /><div className={styles.story}><p>一枚ずつの測定や、ソフトを移るたびのデータ整理。Cytellectは、画像の定量から集計までを一つのワークスペースでつなぎます。代表画像で確認した条件をまとめて適用し、気になる値は元の画像に戻って確認できます。</p></div></div>
        </div>
        <figure className={styles.labPanorama}><img src="/marketing/photo-lab-automation.webp" alt="実験室の分注装置" width={1920} height={1280} loading="lazy" /></figure>
        <div className={styles.sectionShell}><figure className={styles.productVisual}><ProductWalkthrough /></figure><EvidenceExample /></div>
      </section>

      <section className={styles.comparison} aria-labelledby="comparison-title"><div className={styles.sectionShell}>
        <div className={styles.regionComposition}>
          <figure className={styles.researchPortrait}><img src="/marketing/photo-pipetting.webp" alt="手袋を着けてピペットで試料を扱う手元" width={1920} height={2658} loading="lazy" /></figure>
          <div><EditorialHeading id="comparison-title" title={<><span className={styles.headingPhrase}>コードを書かずに、</span><span className={styles.headingPhrase}>統計まで。</span></>} /><div className={styles.story}><p>画像解析や統計が専門でなくても、必要な設定を画面で確認しながら進められます。測定方法から、実験の組み方に合った比較まで。解析の根拠を理解しながら、自分の研究に取り組めます。</p><Link href="/plan" className={styles.textLink}>解析設定を見る <Arrow /></Link></div></div>
        </div>
        <figure className={styles.planningFigure}><picture><source media="(max-width: 760px)" srcSet="/marketing/planning-public-mobile.png" width={326} height={470} /><img src="/marketing/planning-public.png" alt="測定の目的に対応する解析方法と必要な入力を確認する画面" width={1256} height={910} loading="lazy" /></picture></figure>
      </div></section>

      <section className={styles.figures} aria-labelledby="figures-title"><div className={styles.sectionShell}><div className={styles.figureGrid}>
        <div><EditorialHeading id="figures-title" title={<><span className={styles.headingPhrase}>その研究を、</span><span className={styles.headingPhrase}>伝わる一枚に。</span></>} /><div className={styles.story}><p>積み重ねた実験の成果を、論文で伝わるグラフへ。測定結果から図を作り、誌面に合わせたサイズで出力できます。編集可能なSVG・PDFと元データを書き出し、論文の仕上げへ進めます。</p><a href={docs+"figures.md"} className={styles.textLink}>出力できる図と形式 <Arrow /></a></div></div>
        <PublicationStage><figure className={styles.paperFigure}><a className={styles.paper} href="/marketing/figure-public.svg" aria-label="グラフを拡大"><picture><source media="(max-width: 760px)" srcSet="/marketing/figure-public-mobile.svg" /><img src="/marketing/figure-public.svg" alt="公開画像の817領域の面積分布を示すCytellectの出力図" width={518.74} height={216} loading="lazy" /></picture></a><figcaption><span>公開画像の測定値から出力した図</span><a href="/marketing/figure-public.svg">図を拡大 <Arrow /></a></figcaption><div className={styles.figureSources}><a href="/marketing/figure-public.csv">測定値 CSV</a><a href="/marketing/figure-source.json">作図条件</a><a href="/marketing/provenance.json">出典</a></div></figure></PublicationStage>
      </div></div></section>

      <section id="guide" className={styles.guides} aria-labelledby="guide-title"><div className={styles.sectionShell}><EditorialHeading id="guide-title" title="使い方と解析方法" /><div className={styles.guideLinks}><a href={docs+"quickstart.ja.md"}><span><b>はじめての解析</b><small>公開画像を使って操作する</small></span><Arrow /></a><a href={docs+"methods.md"}><span><b>解析方法</b><small>測定値と統計の定義を読む</small></span><Arrow /></a><a href={docs+"local.md"}><span><b>セットアップ</b><small>動作環境と導入手順を確認する</small></span><Arrow /></a></div></div></section>

      <figure className={styles.instrumentPhoto}><img src="/marketing/photo-microscope.webp" alt="白い実験台に置かれた顕微鏡" width={1108} height={1477} loading="lazy" /></figure><section id="download" className={styles.download} aria-labelledby="download-title"><div className={styles.sectionShell}><div className={styles.downloadIntro}><EditorialHeading id="download-title" title={<><span className={styles.headingPhrase}>次の論文に、</span><span className={styles.headingPhrase}>Cytellectを。</span></>} /><div><p>Windows PCで動作します。初回セットアップ後は、ブラウザから画像を登録して解析できます。</p>{WINDOWS_RELEASE_URL?<><a className={styles.primary} href={WINDOWS_RELEASE_URL} rel="noreferrer">Windows版をダウンロード <span aria-hidden="true">↓</span></a>{PUBLISHED_RELEASE?.url===WINDOWS_RELEASE_URL&&<a className={styles.release} href={`https://github.com/genellect/cytellect/releases/tag/v${PUBLISHED_RELEASE.version}`}>v{PUBLISHED_RELEASE.version} · リリース情報 <Arrow /></a>}</>:<Link href="/demo" className={styles.primary}>公開画像を見る <Arrow /></Link>}</div></div>
        <div id="scope" className={styles.conditions}><details><summary>対応する画像と解析</summary><p>汎用の領域解析は8／16-bitグレースケールのチャンネル別2D TIFFを扱います。核・核小体・GFPの専用レシピでは、対応範囲の単一シリーズOME-TIFF（Z=1、T=1）も読み込めます。手動・整数ラベル・確認した核染色からの検出領域で、面積・輝度を測定できます。</p><p>3D、時系列、自動細胞境界検出、任意の構造の自動検出は対象外です。通常の核自動検出は1辺2,048 px・270万画素以内です。</p></details><details><summary>インストールと動作環境</summary><p>Windows x64用のZIPを展開し、Cytellect Setup.cmdを開いてください。初回はインターネットに接続して解析環境を取得します。その後はショートカットから起動できます。</p><p>解析はPC内で実行します。この公開サイトへ研究画像をアップロードする機能はありません。</p><a href={docs+"local.md"}>詳しいセットアップ手順 <Arrow /></a></details><details><summary>保存先と削除について</summary><p>画像と解析結果はPC内のCytellect専用フォルダーに保存します。公開サイトや外部AIには送信しません。</p><p>保存期限は最後の明示的な操作から24時間です。終了中に期限を迎えたデータは次回起動時に削除します。</p><p>必要な結果は保存機能から書き出してください。作業の削除はワークスペース内から実行できます。</p></details></div>
      </div></section>
    </main>
    <footer className={styles.footer}><div className={styles.sectionShell}><Link href="/" className={styles.footerBrand}>cytellect</Link><nav aria-label="製品情報"><a href="https://github.com/genellect/cytellect">GitHub <Arrow /></a><a href="https://github.com/genellect/cytellect/blob/main/SECURITY.md">セキュリティ <Arrow /></a><a href="/marketing/provenance.json">画像・映像の出典 <Arrow /></a></nav></div></footer>
  </div>;
}
