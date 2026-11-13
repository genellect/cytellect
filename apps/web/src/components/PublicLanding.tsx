import Link from "next/link";
import type { ReactNode } from "react";
import { LandingAnalytics } from "./LandingAnalytics";
import { ProductMenu } from "./ProductMenu";
import { HeroFilm } from "./HeroFilm";
import { LandingExperience, type FeatureLinks } from "./LandingExperience";
import { LandingHeaderTone } from "./LandingHeaderTone";
import { LightField } from "./LightField";
import { LandingHomeLink } from "./LandingHomeLink";
import { LandingImpact } from "./LandingImpact";
import { LandingInvite } from "./LandingInvite";
import { LandingDownload } from "./LandingDownload";
import { LandingDemoBar } from "./LandingDemoBar";
import { demoSceneHref } from "@/lib/showcase/scene-links";
import styles from "./product.module.css";
import lp from "./optical-landing.module.css";

const Arrow = () => <span aria-hidden="true">↗</span>;
const Forward = () => <span aria-hidden="true">→</span>;
/** The demo screens the landing page shows (public/marketing/lp-evidence.json), each opened by its scene. */
const PLK1 = "cpg0016-jump-source13-plk1", OXALIPLATIN = "zenodo-6643470-oxaliplatin";
const FEATURE_LINKS: FeatureLinks = {
  discussion: demoSceneHref(PLK1, "statistics"), table: demoSceneHref(OXALIPLATIN, "image"),
  figure: demoSceneHref(PLK1, "figure"), ask: demoSceneHref(PLK1, "statistics"),
};
/** Image credits, in page order. Records: public/marketing/{hero-film,photo}-provenance.json and lp-evidence.json. */
const CREDITS: { label: string; sources: [string, string][]; note?: ReactNode }[] = [
  { label: "映像（冒頭と結び）", sources: [["CDC / Pexels", "https://www.pexels.com/photo/person-doing-an-experiment-3992927/"], ["Thirdman / Pexels", "https://www.pexels.com/video/close-up-of-a-machine-putting-liquid-on-vials-8940765/"], ["Pressmaster / Pexels", "https://www.pexels.com/video/drops-of-liquid-on-a-tray-to-be-use-as-samples-3195394/"], ["Tima Miroshnichenko / Pexels", "https://www.pexels.com/video/man-and-a-woman-using-microscope-9573740/"]] },
  { label: "ピペット", sources: [["Thirdman / Pexels", "https://www.pexels.com/photo/scientist-holding-a-pipette-8940473/"]] },
  { label: "解析例の画面", sources: [["JUMP Cell Painting Consortium / Cell Painting Gallery", "https://github.com/broadinstitute/cellpainting-gallery"], ["Schmidt HB, Rohatgi R, Brandman O (2022) / Zenodo", "https://doi.org/10.5281/zenodo.6643470"]],
    note: <>（公開画像をCytellectで解析した画面。<a href="https://creativecommons.org/publicdomain/zero/1.0/deed.ja" target="_blank" rel="noopener noreferrer">CC0 1.0</a>、<a href="https://creativecommons.org/licenses/by/4.0/deed.ja" target="_blank" rel="noopener noreferrer">CC BY 4.0</a>）</> },
];
function NavigationLinks(){return <><a href="#workflow">プロダクト</a><a data-lp-event="guide" href="#guide">ガイド</a><a href="https://yuto-matsui.com/">About the Developer</a><a data-lp-event="download_section" href="#download">ダウンロード</a><Link data-lp-event="example" href="/demo" className={lp.navDownload}>デモを体験 <span aria-hidden="true">→</span></Link></>;}

export default function PublicLanding() {
  return <div className={lp.page} data-cytellect-public-page="/">
    <LandingAnalytics page="/" />
    <a className={styles.skipLink} href="#main">本文へ</a>
    <header className={lp.header} data-lp-header data-tone="dark"><LandingHomeLink className={lp.wordmark} /><nav className={lp.navigation} aria-label="メインナビゲーション"><NavigationLinks /></nav><ProductMenu><NavigationLinks /></ProductMenu></header>
    <LandingHeaderTone />
    <main id="main">
      <section id="top" className={lp.hero} data-tone="dark" aria-labelledby="hero-title">
        <HeroFilm />
        <div className={lp.heroShade} />
        <div className={lp.heroCopy}>
          <h1 id="hero-title" lang="en" aria-label="Get your microscopy publication-ready."><span>Get your</span>{" "}<span>microscopy</span>{" "}<span>publication-<br className={lp.mobileBreak} />ready.</span></h1>
          <p className={lp.heroLead}>蛍光顕微鏡の画像をアップロードするだけで、測定・統計から、結論と考察、論文の図まで。</p>
          <div className={lp.heroActions}><Link data-lp-event="example" href="/demo" className={lp.primary}>デモを体験する <Forward /></Link><a data-lp-event="download_section" href="#download" className={lp.heroSecondary}>ダウンロード <span aria-hidden="true">↓</span></a></div>
        </div>
        <figure className={lp.heroResult}>
          <figcaption><span aria-hidden="true" />解析の結論</figcaption>
          <img src="/marketing/lp-focus-conclusion.webp" alt="解析の結論。「PLK1 KO で、視野あたりの核数が 79〜84% 減少」という一文と、3 回の実験すべてで減少したことを示す要点" width={426} height={180} />
        </figure>
        <ol className={lp.heroPath} aria-label="解析の流れ">{["画像", "検出と測定", "統計", "結論と考察", "論文の図"].map(step => <li key={step}>{step}</li>)}</ol>
      </section>

      <section className={lp.mission} aria-labelledby="mission-title">
        <LightField />
        <div className={lp.column}>
          <h2 id="mission-title" className={lp.manifesto} aria-label="画像解析を、一部の専門家の技術から、すべての生命科学研究者が使える研究基盤に。"><span><span>画像解析を、</span><span>一部の専門家の技術から、</span></span><span><span>すべての生命科学研究者が</span><span>使える研究基盤に。</span></span></h2>
        </div>
      </section>

      <LandingExperience links={FEATURE_LINKS} />

      <section className={lp.reasons} aria-labelledby="loop-title">
        <img className={lp.reasonsPhoto} src="/marketing/lp-pipetting.webp" alt="白い実験台でマルチチャンネルピペットを使う手元" width={2400} height={1600} loading="lazy" decoding="async" />
        <div className={lp.wide}>
          <h2 id="loop-title" className={lp.statement} aria-label="どんな研究の画像も、入れるだけで、自動で。"><span>どんな研究の画像も、</span><span>入れるだけで、自動で。</span></h2>
          <p className={lp.reasonsLead}>汎用のAIでは見つからない構造まで、輪郭を一つも描かずに測れます。</p>
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

      <LandingDownload />

    </main>
    <LandingDemoBar />
    <footer className={lp.footer}><div className={lp.sectionShell}>
      <div className={lp.footerPrimary}><div><a href="#top" className={lp.footerBrand}>cytellect</a><span>顕微鏡画像の解析から統計、論文用グラフの作成まで</span></div><nav aria-label="製品情報"><a href="https://github.com/genellect/cytellect" target="_blank" rel="noopener noreferrer">GitHub <Arrow /></a><a href="#top">ページの先頭へ <span aria-hidden="true">↑</span></a></nav></div>
      <details className={lp.credits}><summary>画像・映像の出典</summary><p>{CREDITS.map(({ label, sources, note }, index) => <span key={label}>{index > 0 && " · "}{label}：{sources.map(([name, href], i) => <span key={href}>{i > 0 && "、"}<a href={href} target="_blank" rel="noopener noreferrer">{name}</a></span>)}{note}</span>)}</p></details>
      <p className={lp.copyright}>&copy; 2026 Genellect Inc. All rights reserved.</p>
    </div></footer>
  </div>;
}
