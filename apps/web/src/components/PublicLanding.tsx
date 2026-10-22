import Link from "next/link";
import { LandingAnalytics } from "./LandingAnalytics";
import { PUBLISHED_RELEASE, WINDOWS_RELEASE_URL } from "@/lib/release";
import { ProductMenu } from "./ProductMenu";
import { OpticalHero } from "./OpticalHero";
import { LandingHomeLink } from "./LandingHomeLink";
import { ProductVideo } from "./ProductVideo";
import { heroMedia } from "./landing-media";
import lp from "./optical-landing.module.css";
import s from "./landing-sections.module.css";

const repo = "https://github.com/genellect/cytellect";
const docs = `${repo}/blob/main/docs/`;
const Arrow = () => <span aria-hidden="true" className={s.arrow}>↗</span>;
const Forward = () => <span aria-hidden="true" className={s.arrow}>→</span>;
/** A section heading set in deliberate lines; "|" marks each break. Its accessible name stays one sentence. */
function Heading({ id, text }: { id: string; text: string }) {
  return <h2 id={id} aria-label={text.replaceAll("|", "")}>{text.split("|").map(line => <span key={line} className={s.line}>{line}</span>)}</h2>;
}

function NavigationLinks() {
  return <>
    <a href="#product">プロダクト</a>
    <a href="#how">使い方</a>
    <a data-lp-event="guide" href="#guide">ガイド</a>
    <a data-lp-event="download_section" href="#download">ダウンロード</a>
  </>;
}

const DEMO = "/demo";
const PROOF = ["技育展2026 書類審査通過", "オープンソース（Apache-2.0）", "研究室で日々の解析に利用中"];

const NUMBERS = [
  { value: "90", unit: "%", from: "0%", label: "核小体の検出成功率", note: "追加学習前 0/15、追加学習後 18/20。テストセット、IoU 0.5 以上", href: `${repo}#画像認識と測定`, source: "追加学習の方法" },
  { value: "0.92", label: "核検出の F1", note: "BBBC039 の 479 核、IoU 0.5 以上。一部は学習データと重なる", href: `${docs}public-validation.md`, source: "BBBC039 の評価" },
  { value: "817", unit: "/817", label: "ImageJ と測定値が一致した核", note: "BBBC013 の公開画像 3 視野", href: `${docs}public-gfp-validation.md`, source: "BBBC013 の照合" },
  { value: "482", unit: "/482", label: "ImageJ と測定値が一致した領域", note: "4DN の DAPI・NCL 画像（核・核小体・核質）", href: `${docs}public-nucleolar-validation.md`, source: "4DN の照合" },
];

const TRUST = [
  { title: "PCの中で解析", body: "画像の読み込みから図の書き出しまで、研究室のPCで完結します。画像が外部に送られることはありません。" },
  { title: "AIに画像も数値も送らない", body: "AIが受け取るのは、指示文と、染色名や画像サイズなどの設定情報だけ。使うかどうかも選べます。" },
  { title: "オープンソース、重みも公開", body: "解析コードは Apache-2.0。追加学習したモデルの重みは Hugging Face で公開しています。" },
  { title: "再現できる解析記録", body: "検出モデル、条件、設定のバージョンを結果と一緒に保存。Methods の記述もそこから書き出します。" },
];

const STEPS = [
  { title: "画像を入れる", body: "TIFFをフォルダごと。チャンネルと実験条件は、ファイル名やフォルダから読み取ります。" },
  { title: "検出を確かめる", body: "核と核小体の輪郭を画像の上で確認し、必要な輪郭だけ直します。" },
  { title: "統計と図を書き出す", body: "独立した実験を単位にした比較と SuperPlot を、誌面サイズの SVG・PDF で。" },
];

const PROPOSAL = [
  { term: "検出", value: "核（StarDist）・核小体（Cellpose-SAM）" },
  { term: "選別", value: "GFP陽性の細胞" },
  { term: "測定", value: "核小体の平均輝度" },
  { term: "統計", value: "独立した実験を単位に群間比較" },
  { term: "図", value: "SuperPlot・89 mm" },
];

export default function PublicLanding() {
  const hero = heroMedia();
  const release = PUBLISHED_RELEASE?.url === WINDOWS_RELEASE_URL ? PUBLISHED_RELEASE : null;
  return <div className={lp.page} data-cytellect-public-page="/">
    <OpticalHero />
    <LandingAnalytics page="/" />
    <a className={lp.skipLink} href="#main">本文へ</a>
    <header className={lp.header}>
      <LandingHomeLink className={lp.wordmark} />
      <nav className={lp.navigation} aria-label="メインナビゲーション"><NavigationLinks /></nav>
      <div className={lp.headerActions}>
        <Link data-lp-event="example" href={DEMO} className={lp.headerCta}>デモを触る</Link>
        <ProductMenu><NavigationLinks /><a href="https://yuto-matsui.com/">About the Developer</a></ProductMenu>
      </div>
    </header>

    <main id="main">
      <section id="top" className={lp.hero} aria-labelledby="hero-title">
        <div className={lp.heroShade} />
        <div className={lp.heroCopy}>
          <h1 id="hero-title" lang="en" aria-label="Get your microscopy publication-ready."><span>Get your</span>{" "}<span>microscopy</span>{" "}<span>publication-ready.</span></h1>
          <p className={lp.heroLead}>画像をアップロードするだけで、<wbr />論文の図まで。</p>
          <p className={lp.heroSub}><span>核と核小体の検出、測定、統計、作図。</span><span>研究者のための解析を、ひとつのワークスペースで。</span></p>
          <div className={lp.heroActions}>
            <Link data-lp-event="example" href={DEMO} className={lp.primary}>デモを触る <Forward /></Link>
            <a data-lp-event="download_section" href="#download" className={lp.secondary}>ダウンロード <span aria-hidden="true" className={s.arrow}>↓</span></a>
          </div>
          <p className={lp.heroNote}>登録不要。公開画像で、すぐに試せます。</p>
        </div>
        <div className={lp.heroStage}>
          <ProductVideo {...hero} priority controls="below" className={lp.heroVideo} />
        </div>
      </section>

      <ul className={s.proof} aria-label="Cytellectについて">
        {PROOF.map(item => <li key={item}>{item}</li>)}
      </ul>

      <div id="product" className={s.sheet}>
        <section className={s.statement} aria-labelledby="statement-title">
          <Heading id="statement-title" text="一枚ずつの測定。|ソフトの行き来。|統計の手探り。" />
          <p>Cytellectは、顕微鏡画像の解析から統計、論文用のグラフまでを、ひと続きの作業にします。</p>
        </section>

        <section className={s.moment} aria-labelledby="nucleoli-title">
          <div className={s.momentCopy}>
            <Heading id="nucleoli-title" text="核小体まで、|自動で見える。" />
            <p>核は StarDist、核小体は NCL・NPM1・FBL 染色の画像で追加学習した Cellpose-SAM が検出します。小さく形の定まらない構造も、一つずつ輪郭として数えられます。</p>
            <p className={s.inlineStat}><span className={s.inlineFrom}>0%</span><span aria-hidden="true">→</span><b>90%</b><small>核小体の検出成功率（テストセット）</small></p>
            <Link data-lp-event="example" href={`${DEMO}?step=image`} className={s.textLink}>検出をデモで見る <Forward /></Link>
          </div>
          <figure className={[s.momentVisual, s.microscopy].join(" ")}>
            <ProductVideo video="/marketing/hero-microscopy.mp4" poster="/marketing/hero-microscopy-poster.webp" width={1600} height={900}
              alt="4DNの公開蛍光画像。青のDNA染色の核の中に、マゼンタのNCLで示した核小体が点状に集まっている。" />
            <figcaption>青が DNA（DAPI）、マゼンタが核小体のタンパク質 NCL。<a href="https://data.4dnucleome.org/files-microscopy/4DNFI7FAWT6C/">4DN / Fowler Lab の公開画像 <Arrow /></a></figcaption>
          </figure>
        </section>

        <section className={[s.moment, s.reverse].join(" ")} aria-labelledby="linked-title">
          <div className={s.momentCopy}>
            <Heading id="linked-title" text="すべての数値が、|元の画像につながる。" />
            <p>表の一行を選べば、画像の上の同じ細胞へ。輪郭を直せば、測定値も統計も図も、その場で更新されます。変更はすべて履歴に残ります。</p>
            <Link data-lp-event="example" href={`${DEMO}?step=image`} className={s.textLink}>測定値と画像をデモで見る <Forward /></Link>
          </div>
          <figure className={[s.momentVisual, s.screen, s.detail].join(" ")}>
            <img src="/marketing/workspace-public.png" alt="公開蛍光画像の核の輪郭と、核ごとの測定値の表を並べたCytellectの解析画面" width={1520} height={744} loading="lazy" decoding="async" />
          </figure>
        </section>

        <section className={s.moment} aria-labelledby="figures-title">
          <div className={s.momentCopy}>
            <Heading id="figures-title" text="統計と論文の図まで、|ひと続きで。" />
            <p>細胞・視野・独立した実験を区別して集計するので、擬似反復になりません。SuperPlot を誌面サイズ（89 mm・183 mm）の編集できる SVG・PDF で。Methods の記述と元データの CSV も一緒に書き出せます。</p>
            <div className={s.linkRow}>
              <Link data-lp-event="example" href={`${DEMO}?step=statistics`} className={s.textLink}>統計をデモで見る <Forward /></Link>
              <Link data-lp-event="example" href={`${DEMO}?step=figure`} className={s.textLink}>図をデモで見る <Forward /></Link>
            </div>
          </div>
          <figure className={[s.momentVisual, s.layered].join(" ")}>
            <a className={s.screen} href="/marketing/planning-public.png" aria-label="統計画面を拡大"><img src="/marketing/planning-public.png" alt="公開画像3視野の核の平均輝度を、視野ごとの分布と集計表で示した統計画面" width={1440} height={950} loading="lazy" decoding="async" /></a>
            <a className={s.paper} href="/marketing/figure-public.svg" aria-label="グラフを拡大"><picture><source media="(max-width: 760px)" srcSet="/marketing/figure-public-mobile.svg" /><img src="/marketing/figure-public.svg" alt="公開画像の817領域の面積分布を示すCytellectの出力図" width={518.74} height={216} loading="lazy" decoding="async" /></picture></a>
            <figcaption>公開画像の測定値から書き出した図。<a href="/marketing/figure-public.csv">測定値 CSV</a><a data-lp-event="figures" href={`${docs}figures.md`}>出力できる図と形式 <Arrow /></a></figcaption>
          </figure>
        </section>
      </div>

      <section className={s.numbers} aria-labelledby="numbers-title">
        <div className={s.numbersInner}>
          <Heading id="numbers-title" text="主張ではなく、|検証した数字を。" />
          <dl>
            {NUMBERS.map(item => <div key={item.label}>
              <dt>{item.label}</dt>
              <dd className={s.figure}>{item.from && <span className={s.from}>{item.from} →</span>}<b>{item.value}</b>{item.unit && <span className={s.unit}>{item.unit}</span>}</dd>
              <dd className={s.note}>{item.note}<br /><a href={item.href}>{item.source} <Arrow /></a></dd>
            </div>)}
          </dl>
        </div>
      </section>

      <div className={s.sheet}>
        <section className={s.ai} aria-labelledby="ai-title">
          <div className={s.momentCopy}>
            <Heading id="ai-title" text="やりたいことを書けば、|解析の設定ができる。" />
            <p>一文の目的を、AIが検出・測定・統計・図の設定に組み立てます。提案は画面で確かめてから実行。AIに送るのは指示文と設定の情報だけで、画像と測定値は送りません。</p>
            <Link data-lp-event="example" href={DEMO} className={s.textLink}>デモで提案を見る <Forward /></Link>
          </div>
          <figure className={s.proposal} aria-labelledby="proposal-caption">
            <div className={s.prompt}><span className={s.promptLabel}>AIに指示</span><p>GFP陽性細胞の核小体の輝度を群間比較したい</p></div>
            <div className={s.card}>
              <p className={s.cardTitle}>解析案</p>
              <dl>{PROPOSAL.map(row => <div key={row.term}><dt>{row.term}</dt><dd>{row.value}</dd></div>)}</dl>
              <div className={s.cardFoot}><span>画像と測定値は送信しません</span><span className={s.fakeButton} aria-hidden="true">解析を実行</span></div>
            </div>
            <figcaption id="proposal-caption">解析案の表示例</figcaption>
          </figure>
        </section>

        <section className={s.trust} aria-labelledby="trust-title">
          <Heading id="trust-title" text="研究データは、|あなたの手元に。" />
          <ul>{TRUST.map(item => <li key={item.title}><h3>{item.title}</h3><p>{item.body}</p></li>)}</ul>
        </section>

        <section id="how" className={s.how} aria-labelledby="how-title">
          <Heading id="how-title" text="3つの手順で、|論文の図まで。" />
          <ol>{STEPS.map(step => <li key={step.title}><h3>{step.title}</h3><p>{step.body}</p></li>)}</ol>
        </section>

        <section className={s.offer} aria-labelledby="offer-title">
          <h2 id="offer-title">まずは無料で。</h2>
          <div className={s.plans}>
            <article className={s.plan}>
              <h3>無料</h3>
              <p className={s.planKind}>オープンソース・Windows版</p>
              <p>解析の全機能を、研究室のPCで。画像はPCの外に出ません。Docker でも動かせます。</p>
              <div className={s.planActions}>
                {WINDOWS_RELEASE_URL ? <a data-lp-event="download_section" href="#download" className={lp.primary}>ダウンロード <span aria-hidden="true" className={s.arrow}>↓</span></a> : <Link data-lp-event="example" href={DEMO} className={lp.primary}>デモを触る <Forward /></Link>}
                <a href={repo} className={s.textLink}>GitHub <Arrow /></a>
              </div>
            </article>
            <article className={[s.plan, s.planSoon].join(" ")}>
              <h3>研究室向けクラウド</h3>
              <p className={s.planKind}>準備中</p>
              <p>インストールなしで、研究室の画像と解析をチームで共有。導入のお手伝いも含めて提供する予定です。</p>
              <div className={s.planActions}><a href={`${repo}/releases`} className={s.textLink}>リリースで最新情報を見る <Arrow /></a></div>
            </article>
          </div>
        </section>

        <section id="guide" className={s.guide} aria-labelledby="guide-title">
          <h2 id="guide-title">使い方と解析方法</h2>
          <div className={s.guideLinks}>
            <a data-lp-event="quickstart" href={`${docs}quickstart.ja.md`}><b>はじめての解析</b><small>公開画像を使って操作する</small><Arrow /></a>
            <a data-lp-event="methods" href={`${docs}methods.md`}><b>解析方法</b><small>測定値と統計の定義を読む</small><Arrow /></a>
            <Link data-lp-event="planning" href="/plan"><b>解析設定を見る</b><small>測りたいものから設定を選ぶ</small><Forward /></Link>
            <a data-lp-event="setup" href={`${docs}local.md`}><b>セットアップ</b><small>動作環境と導入手順を確認する</small><Arrow /></a>
          </div>
        </section>
      </div>

      <section id="download" className={s.final} aria-labelledby="download-title">
        <div className={s.finalPanel}>
          <Heading id="download-title" text="その画像を、|論文の図に。" />
          <p>Cytellectは、Windows PCで動作します。初回セットアップ後は、ブラウザから画像を登録して解析できます。</p>
          <div className={s.finalActions}>
            <Link data-lp-event="example" href={DEMO} className={lp.primary}>デモを触る <Forward /></Link>
            {WINDOWS_RELEASE_URL && <a className={lp.secondary} data-lp-event="download" href={WINDOWS_RELEASE_URL} rel="noreferrer">Windows版をダウンロード <span aria-hidden="true" className={s.arrow}>↓</span></a>}
          </div>
          {release && <a className={s.release} href={`${repo}/releases/tag/v${release.version}`}>v{release.version} · リリース情報 <Arrow /></a>}
        </div>
        <div className={s.details}>
          <div id="launch">
            <h3>インストール済みの方</h3>
            <p>デスクトップの「Cytellect」を開くと、解析画面がブラウザに表示されます。起動済みの場合は、Cytellectの起動画面で「ブラウザで開く」を選択してください。</p>
            <p>再ダウンロード・再インストールは不要です。</p>
          </div>
          <div id="scope">
            <details><summary>対応する画像と解析</summary><p>汎用の領域解析は8／16-bitグレースケールのチャンネル別2D TIFFを扱います。核・核小体・GFPの専用レシピでは、対応範囲の単一シリーズOME-TIFF（Z=1、T=1）も読み込めます。手動・整数ラベル・確認した核染色からの検出領域で、面積・輝度を測定できます。</p><p>3D、時系列、自動細胞境界検出、任意の構造の自動検出は対象外です。大きな画像では、検出用に縮小した複製で核を検出し、測定は元の画素で行います。</p></details>
            <details><summary>インストールと動作環境</summary><p>Windows x64用のZIPを展開し、Cytellect Setup.cmdを開いてください。初回はインターネットに接続して解析環境を取得します。その後はショートカットから起動できます。</p><p>解析はPC内で実行します。アップロードした研究画像が、この公開サイトに送られることはありません。</p><a data-lp-event="setup" href={`${docs}local.md`}>詳しいセットアップ手順 <Arrow /></a></details>
            <details><summary>保存先と削除について</summary><p>画像と解析結果はPC内のCytellect専用フォルダーに保存します。公開サイトや外部AIには送信しません。</p><p>保存期限は最後の明示的な操作から24時間です。終了中に期限を迎えたデータは次回起動時に削除します。</p><p>必要な結果は保存機能から書き出してください。作業の削除はワークスペース内から実行できます。</p></details>
          </div>
        </div>
      </section>
    </main>

    <footer className={lp.footer}>
      <div className={lp.footerInner}>
        <a href="#top" className={lp.footerBrand}>cytellect</a>
        <nav aria-label="製品情報">
          <a href={repo}>GitHub <Arrow /></a>
          <a href={`${repo}/blob/main/SECURITY.md`}>セキュリティ <Arrow /></a>
          <a href="/marketing/provenance.json">画像・映像の出典 <Arrow /></a>
          <a href="https://yuto-matsui.com/">About the Developer <Arrow /></a>
        </nav>
        <p className={lp.copyright}>&copy; 2026 Yuto Matsui. All rights reserved.</p>
      </div>
    </footer>
  </div>;
}
