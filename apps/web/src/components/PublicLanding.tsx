import Link from "next/link";
import type { ReactNode } from "react";
import { LandingAnalytics } from "./LandingAnalytics";
import { PUBLISHED_RELEASE, WINDOWS_RELEASE_URL, releaseSize, windowsReleaseAsset } from "@/lib/release";
import { ProductMenu } from "./ProductMenu";
import { HeroFilm } from "./HeroFilm";
import { LandingFeatures } from "./LandingFeatures";
import { LandingHomeLink } from "./LandingHomeLink";
import { LandingImpact } from "./LandingImpact";
import { LandingInvite } from "./LandingInvite";
import { LandingDemoBar } from "./LandingDemoBar";
import styles from "./product.module.css";
import lp from "./optical-landing.module.css";

const docs = "https://github.com/genellect/cytellect/blob/main/docs/";
// The installer flow is shown only when the effective download is the installer; versions without one keep the ZIP flow.
const INSTALLER = windowsReleaseAsset(WINDOWS_RELEASE_URL) === "installer";
const Arrow = () => <span aria-hidden="true">↗</span>;
const Forward = () => <span aria-hidden="true">→</span>;
/** No titles: a section opens with its own first sentence, set large. */
function Display({ id, text }: { id: string; text: string }) {
  return <h2 id={id} className={lp.display}>{text}</h2>;
}
/** Image credits, in page order. Records: public/marketing/{hero-film,photo}-provenance.json and provenance.json (lp_demo_evidence). */
const CREDITS: { label: string; sources: [string, string][]; note?: ReactNode }[] = [
  { label: "ヒーロー映像", sources: [["CDC / Pexels", "https://www.pexels.com/photo/person-doing-an-experiment-3992927/"], ["Thirdman / Pexels", "https://www.pexels.com/video/close-up-of-a-machine-putting-liquid-on-vials-8940765/"], ["Pressmaster / Pexels", "https://www.pexels.com/video/drops-of-liquid-on-a-tray-to-be-use-as-samples-3195394/"], ["Tima Miroshnichenko / Pexels", "https://www.pexels.com/video/man-and-a-woman-using-microscope-9573740/"]] },
  { label: "ピペット", sources: [["Thirdman / Pexels", "https://www.pexels.com/photo/scientist-holding-a-pipette-8940473/"]] },
  { label: "核と核小体の蛍光画像", sources: [["Schmidt HB, Rohatgi R, Brandman O (2022) / Zenodo", "https://doi.org/10.5281/zenodo.6643470"]],
    note: <>（<a href="https://creativecommons.org/licenses/by/4.0/deed.ja" target="_blank" rel="noopener noreferrer">CC BY 4.0</a>。表示用にコントラストを調整し、Cytellectが検出した輪郭を重ねています）</> },
];
function NavigationLinks(){return <><a href="#workflow">プロダクト</a><a data-lp-event="guide" href="#guide">ガイド</a><a href="https://yuto-matsui.com/">About the Developer</a><a data-lp-event="download_section" href="#download">ダウンロード</a><Link data-lp-event="example" href="/demo" className={lp.navDownload}>デモを体験 <span aria-hidden="true">→</span></Link></>;}

export default function PublicLanding() {
  return <div className={lp.page} data-cytellect-public-page="/">
    <LandingAnalytics page="/" />
    <a className={styles.skipLink} href="#main">本文へ</a>
    <header className={lp.header}><LandingHomeLink className={lp.wordmark} /><nav className={lp.navigation} aria-label="メインナビゲーション"><NavigationLinks /></nav><ProductMenu><NavigationLinks /></ProductMenu></header>
    <main id="main">
      <section id="top" className={lp.hero} aria-labelledby="hero-title">
        <HeroFilm />
        <div className={lp.heroShade} />
        <div className={lp.heroCopy}><h1 id="hero-title" lang="en" aria-label="Get your microscopy publication-ready."><span>Get your</span>{" "}<span>microscopy</span>{" "}<span>publication-<br className={lp.mobileBreak} />ready.</span></h1><div className={lp.heroActions}><Link data-lp-event="example" href="/demo" className={lp.primary}>デモを体験する <Forward /></Link><a data-lp-event="download_section" href="#download" className={lp.heroSecondary}>ダウンロード <span aria-hidden="true">↓</span></a></div></div>
      </section>

      <section className={lp.mission} aria-labelledby="mission-title">
        <div className={lp.column}>
          <h2 id="mission-title" className={lp.manifesto} aria-label="画像解析を、一部の専門家の技術から、すべての生命科学研究者が使える研究基盤に。"><span><span>画像解析を、</span><span>一部の専門家の技術から、</span></span><span><span>すべての生命科学研究者が</span><span>使える研究基盤に。</span></span></h2>
          <p className={lp.missionLead}>蛍光顕微鏡の画像をアップロードするだけで、画像解析・統計・論文用のグラフまで。</p>
        </div>
      </section>

      <figure className={lp.band}><img src="/marketing/lp-pipetting.webp" alt="白い実験台でマルチチャンネルピペットを使う手元" width={2400} height={1600} loading="lazy" /></figure>

      <section id="workflow" className={lp.section} aria-labelledby="workflow-title">
        <div className={lp.column}>
          <Display id="workflow-title" text="手作業で数週間かかっていた解析を、一つの画面で数分に。" />
        </div>
        <LandingFeatures />
      </section>

      <section className={[lp.section, lp.loopSection].join(" ")} aria-labelledby="loop-title">
        <div className={lp.wide}>
          <Display id="loop-title" text="どんな研究の画像も、入れるだけで、自動で。" />
          <p className={lp.loopLead}>汎用のAIでは見つからない構造まで、輪郭を一つも描かずに測れます。</p>
          <ul className={lp.loop} aria-label="自動で測れる理由">
            <li><b>研究ごとに、専用のAI</b><span>測りたいものは、研究ごとに違う。それぞれの研究に合わせたAIが、細胞を一つずつ切り分けます。</span></li>
            <li><b>どのPCでも、GPUの速さで</b><span>検出はクラウドの高性能なGPUで。研究室のノートPCのままで、GPUを買う必要はありません。</span></li>
            <li><b>何度やっても、同じ結果</b><span>同じ画像からは、いつも同じ輪郭と数値。使ったAIの版まで記録します。</span></li>
            <li><b>すべての数値が、元の画像に戻れる</b><span>測定は元の画素値から。グラフの点から、その細胞の輪郭へ戻れます。</span></li>
          </ul>
        </div>
      </section>

      <LandingImpact />

      <LandingInvite />

      <section id="download" className={[lp.section, lp.download, lp.reference].join(" ")} aria-labelledby="download-title">
        <div className={lp.wide}>
          <div className={lp.setup}>
            <div>
              <Display id="download-title" text="Windows版は無料。測定も保存も、あなたのPCで。" />
              <p className={lp.setupLead}>画面の案内どおりに進めるだけ。コマンド入力も管理者権限も要りません。</p>
              {WINDOWS_RELEASE_URL?<a className={lp.primary} data-lp-event="download" href={WINDOWS_RELEASE_URL} rel="noreferrer">Windows版をダウンロード <span aria-hidden="true">↓</span></a>:<Link data-lp-event="example" href="/demo" className={lp.primary}>デモを体験する <Forward /></Link>}
              {WINDOWS_RELEASE_URL&&<p className={lp.meta}>{INSTALLER?"インストーラー":"ZIP"}{PUBLISHED_RELEASE?.url===WINDOWS_RELEASE_URL?`・${releaseSize(PUBLISHED_RELEASE.size_bytes)}・v${PUBLISHED_RELEASE.version}`:""}<br />Windows 10／11（64ビット）・空き容量 6 GB 以上を推奨</p>}
            </div>
            {INSTALLER?<ol className={lp.setupSteps} aria-label="はじめかた">
              <li><b>ダウンロードして、開く</b></li>
              <li><b>「インストール」を押す</b><span>約5〜10分で、解析画面がブラウザで開きます</span></li>
              <li><b>メールのコードでログイン</b><span>GPUでの検出も使えるようになります</span></li>
            </ol>:<ol className={lp.setupSteps} aria-label="はじめかた">
              <li><b>ダウンロードして、展開する</b></li>
              <li><b>「Cytellect Setup」を開く</b></li>
              <li><b>「セットアップ」を押し、終わったら「開く」</b><span>解析画面がブラウザで開きます</span></li>
            </ol>}
          </div>
        </div>
        <div id="guide" className={[lp.wide, lp.more].join(" ")}>
          <nav aria-label="使い方と解析方法"><span>使い方と解析方法</span><a data-lp-event="quickstart" href={docs+"quickstart.ja.md"}>はじめての解析 <Arrow /></a><a data-lp-event="methods" href={docs+"methods.md"}>測定値と統計の定義 <Arrow /></a><a data-lp-event="figures" href={docs+"figures.md"}>出力できる図と形式 <Arrow /></a></nav>
          <div id="scope" className={lp.moreDetails}>
            <details id="launch"><summary>インストール済みの方</summary><p>デスクトップの「Cytellect」を開くと、解析画面がブラウザに表示されます。起動済みの場合は、Cytellectの起動画面で「ブラウザで開く」を選択してください。</p><p>再ダウンロード・再インストールは不要です。</p><Link data-lp-event="workspace" href="/workspace" className={lp.button}>解析画面を開く <Forward /></Link></details>
            <details><summary>対応する画像と解析</summary><p>核と核小体は、機械学習モデルで自動検出します。GFPなどのシグナルは、検出した核での測定や、しきい値・手動の輪郭・整数ラベルで領域にして測れます。</p><p>読み込めるのは、8／16-bitグレースケールのチャンネル別2D TIFFと、対応範囲の単一シリーズOME-TIFF（Z=1、T=1）です。大きな画像は検出用に縮小した複製で検出し、測定は元の画素で行います。3D、時系列、細胞全体の境界の自動検出には、まだ対応していません。</p></details>
            <details><summary>インストールと動作環境</summary>{INSTALLER?<p>ダウンロードしたインストーラーを開き、「インストール」を押してください。解析に必要なPythonとFijiも入っているため、インストール中は通信しません。管理者権限も要りません。その後はデスクトップのショートカットから起動できます。</p>:<p>Windows x64用のZIPを展開し、Cytellect Setup.cmdを開いてください。初回はインターネットに接続して解析環境を取得します。その後はショートカットから起動できます。</p>}<p>解析はPC内で実行します。Cellposeの検出だけは、管理者が設定したクラウドGPUで実行できます。アップロードした研究画像が、この公開サイトに送られることはありません。</p><a data-lp-event="setup" href={docs+"local.md"}>詳しいセットアップ手順 <Arrow /></a></details>
            <details><summary>保存先と削除について</summary><p>画像と解析結果はPC内のCytellect専用フォルダーに保存し、公開サイトには送信しません。PCの外へ画像を送るのは、管理者がCellpose用のクラウドGPUを設定した場合（検出に使う画像をそのGPUへ送り、クラウド側には保存しません）だけです。</p><p>作業は、既定ではワークスペースで削除するまで保持します。セットアップで選択を外した場合は、最後の明示的な操作から24時間で削除します。</p><p>必要な結果は保存機能から書き出し、別の媒体にもバックアップしてください。作業の削除はワークスペース内から実行できます。</p></details>
          </div>
        </div>
      </section>

    </main>
    <LandingDemoBar />
    <footer className={lp.footer}><div className={lp.sectionShell}>
      <div className={lp.footerPrimary}><div><a href="#top" className={lp.footerBrand}>cytellect</a><span>顕微鏡画像の解析から統計、論文用グラフの作成まで</span></div><nav aria-label="製品情報"><a href="https://github.com/genellect/cytellect" target="_blank" rel="noopener noreferrer">GitHub <Arrow /></a><a href="#top">ページの先頭へ <span aria-hidden="true">↑</span></a></nav></div>
      <details className={lp.credits}><summary>画像・映像の出典</summary><p>{CREDITS.map(({ label, sources, note }, index) => <span key={label}>{index > 0 && " · "}{label}：{sources.map(([name, href], i) => <span key={href}>{i > 0 && "、"}<a href={href} target="_blank" rel="noopener noreferrer">{name}</a></span>)}{note}</span>)}</p></details>
      <p className={lp.copyright}>&copy; 2026 Genellect Inc. All rights reserved.</p>
    </div></footer>
  </div>;
}
