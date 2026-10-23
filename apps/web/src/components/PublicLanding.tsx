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
          <div className={lp.prose}><p>これまでは、画像解析ソフトで細胞の輪郭を手で描き、表計算ソフトに写し、統計ソフトで検定と作図をしていました。Cytellectは、核の検出・修正・測定から統計、論文用の図までを一つの画面で行います。検出の設定、手で直した輪郭、除外の記録が残るので、後から同じ結果を再現できます。</p></div>
        </div>
        <figure className={[lp.wide, lp.media, lp.screen].join(" ")}><picture><source media="(max-width: 760px)" srcSet="/marketing/lp-workspace-mobile.webp" width={1080} height={871} /><img src="/marketing/lp-workspace.webp" alt="Cytellectの解析例。視野の一覧、核の輪郭を重ねた蛍光画像、核ごとの測定値、解析の設定が一つの画面に並ぶ" width={2880} height={1800} loading="lazy" /></picture></figure>
        <div className={lp.column}><Link data-lp-event="example" href="/demo" className={lp.button}>解析例を操作する <Forward /></Link></div>
      </section>

      <section className={lp.section} aria-labelledby="detection-title">
        <div className={lp.column}>
          <Display id="detection-title" text="汎用のモデルでは見つからない核小体を、追加学習で検出できるようにしました。" />
          <div className={lp.prose}><p>研究室の抗NCL抗体で染色した画像では、汎用の深層学習モデルが検出できた核小体は15個中0個でした。研究者が修正した輪郭で追加学習したモデルは、20個中18個を検出します。核は、正解の輪郭が付いた公開画像で、人が描いた輪郭とのF1が0.92です。</p></div>
          <div className={lp.numbers}>
            <p><strong>0% → 90%</strong><span>核小体の検出成功率（研究室の画像、追加学習の前と後）</span></p>
            <p><strong>0.92</strong><span>核の検出のF1（正解付きの公開画像）</span></p>
          </div>
        </div>
        <div className={[lp.wide, lp.media].join(" ")}>
          <figure className={lp.specimen}>
            <picture><source media="(max-width: 760px)" srcSet="/marketing/lp-field-mobile.webp" width={1080} height={1080} /><img src="/marketing/lp-field.webp" alt="解析例の蛍光画像。青い核と桃色の核小体を、Cytellectが検出した輪郭が囲んでいる" width={1536} height={864} loading="lazy" /></picture>
            <figcaption>解析例の公開画像に、Cytellectの検出結果を重ねたもの。核（青）と核小体（桃）の輪郭。上の数値はこの画像で測ったものではありません。画像：Schmidt, Rohatgi, Brandman (2022), Zenodo, CC BY 4.0</figcaption>
          </figure>
        </div>
        <div className={lp.column}><Link data-lp-event="demo_image" href="/demo?step=image" className={lp.button}>この画像を解析例で見る <Forward /></Link></div>
      </section>

      <section className={lp.section} aria-labelledby="ai-title">
        <div className={lp.column}>
          <Display id="ai-title" text="やりたい解析を一文で書くと、解析の設定に分解して提案します。" />
          <div className={lp.prose}><p>たとえば「NPM1の核内平均輝度を未処理とActD処理で比較したい」と書くと、測る対象と指標、統計の方法を組み立て、その理由と一緒に示します。採用するかは研究者が決め、計算はAIではなくCytellectの解析処理が行い、その測定値はImageJによる独立計算と一致することを確かめています。AIに送るのは入力した文だけで、画像・測定値・ファイル名は送りません。</p></div>
        </div>
        <figure className={[lp.wide, lp.media, lp.screen].join(" ")}><picture><source media="(max-width: 760px)" srcSet="/marketing/lp-ai-mobile.webp" width={580} height={1050} /><img src="/marketing/lp-ai.webp" alt="解析例でAIに指示した画面。指示の文と、反復を対応とした対応ありt検定で比べるという提案が表示されている" width={2880} height={1800} loading="lazy" /></picture></figure>
      </section>

      <section className={lp.section} aria-labelledby="statistics-title">
        <div className={lp.column}>
          <Display id="statistics-title" text="nは細胞の数ではなく、独立した実験の数として検定します。" />
          <div className={lp.prose}><p>細胞の数をnにすると、差のないデータからも誤った有意差が生まれます。Cytellectは視野と試料を独立した実験に対応づけ、その単位で検定します。輪郭を直せば測定値・統計・図が更新され、図の点からはその値のもとになった画像を開けます。図は編集できるSVG・PDFで、測定値はCSVで書き出せます。</p></div>
        </div>
        <div className={[lp.wide, lp.media, lp.pair].join(" ")}>
          <figure className={lp.screen}><img src="/marketing/lp-statistics.webp" alt="解析例の統計の画面。視野ごとに群・試料・独立実験単位を対応づけた表と、反復ごとの平均値" width={2880} height={1800} loading="lazy" /></figure>
          <figure className={lp.paper}>
            <a href="/marketing/lp-figure.svg" aria-label="図を拡大"><img src="/marketing/lp-figure.svg" alt="解析例から書き出した図。反復ごとに、未処理とアクチノマイシンD処理の核のNPM1平均輝度を線で結んでいる" width={518.74} height={283.46} loading="lazy" /></a>
            <figcaption>解析例から書き出した図。核のNPM1平均輝度を、反復（Rep）ごとに未処理とActD処理で結んだもの（n = 3）。この公開データは同じ日の撮影で、反復の独立性は出典に記載がありません。</figcaption>
          </figure>
        </div>
        <div className={[lp.column, lp.links].join(" ")}><Link data-lp-event="demo_figure" href="/demo?step=figure" className={lp.button}>統計とグラフを解析例で見る <Forward /></Link><Link data-lp-event="planning" href="/plan" className={lp.button}>解析の計画を立てる <Forward /></Link></div>
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
