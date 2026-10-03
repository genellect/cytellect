import Link from "next/link";
import { WINDOWS_RELEASE_URL } from "@/lib/release";
import LinkedImageFigure from "./LinkedImageFigure";
import WindowsDownload from "./WindowsDownload";
import styles from "./landing.module.css";

const steps = [
  { title: "何を測るか、決める。", body: "測る領域、背景、比較する群を設定。視野と独立した実験の反復を分けて登録します。", detail: "測定項目・背景・実験単位" },
  { title: "領域を見て、確かめる。", body: "代表画像で検出を試し、輪郭を修正。条件を決めて一括解析し、除外の理由も残します。", detail: "試行・修正・一括解析" },
  { title: "実験単位で、比較する。", body: "細胞数と実験の反復数を混同せずに集計。比較方法と対象を確認して、統計と図を作ります。", detail: "群間比較・対応あり・探索的回帰" },
  { title: "図から、測定値へ戻れる。", body: "編集可能な図に、測定表と解析条件を添えて保存。領域の修正後は新しい解析版で更新します。", detail: "SVG・PDF・CSV・再実行パッケージ" },
];

export default function PublicLanding() {
  return <div className={styles.page}>
    <a className={styles.skipLink} href="#main">本文へ</a>
    <header className={styles.header}><Link href="/" aria-label="Cytellect ホーム" className={styles.wordmark}><span className={styles.mark} aria-hidden="true"><i /><i /><i /></span>cytellect</Link><nav aria-label="メインナビゲーション"><a href="#workflow">解析の流れ</a><a href="#scope">対応範囲</a><a className={styles.navStart} href="#download">はじめる <span aria-hidden="true">↗</span></a></nav></header>
    <main id="main">
      <section className={styles.hero}>
        <div className={styles.heroCopy}><p className={styles.eyebrow}>実験する人のための、蛍光画像解析。</p><h1>蛍光画像から、<br />論文の図まで。</h1><p className={styles.lead}>領域を確かめ、定量し、実験ごとに比較する。<br className={styles.desktopBreak} />画像解析から統計・作図までを、<br className={styles.desktopBreak} />ひとつのワークスペースで。</p><div className={styles.heroActions}><Link href="/demo" className={styles.primary}>サンプルを試す <span aria-hidden="true">↗</span></Link><a href="#download" className={styles.textLink}>Windows版について <span aria-hidden="true">↓</span></a></div><p className={styles.availability}>2D蛍光画像に対応{WINDOWS_RELEASE_URL ? " · Windows版を無償公開中" : " · 公開サンプルを提供中"}<br />開発プレビュー／実験ごとの妥当性確認が必要です。</p></div>
        <LinkedImageFigure />
      </section>
      <section className={styles.workflow} id="workflow" aria-labelledby="workflow-title"><div className={styles.sectionIntro}><p className={styles.eyebrow}>解析の流れ</p><h2 id="workflow-title">測定の設計から、<br className={styles.mobileBreak} />図の出力まで。</h2><p>Fijiによる検出処理に、領域の確認、定量、統計、作図をつなぎます。<br className={styles.desktopBreak} />どの画像を、どの条件で解析したかを、結果と一緒に残します。</p></div><ol className={styles.steps}>{steps.map((step, index) => <li key={step.title}><span className={styles.stepNumber}>{String(index + 1).padStart(2, "0")}</span><h3>{step.title}</h3><p>{step.body}</p><span className={styles.stepDetail}>{step.detail}</span></li>)}</ol><div className={styles.planLink}><span><b>解析を始める前に。</b> 目的に合う測定項目と、確認する条件を整理します。</span><Link href="/plan">解析計画を確認する <span aria-hidden="true">→</span></Link></div></section>
      <section className={styles.outputs} aria-labelledby="outputs-title"><div><p className={styles.eyebrow}>結果を、説明できる形に。</p><h2 id="outputs-title">図だけでなく、<br />その根拠も手元に。</h2><p>投稿用の図を整えるときも、解析を見直すときも。<br />測定値・領域・条件を、対応づけて書き出せます。</p><a href="https://github.com/genellect/cytellect/blob/main/docs/methods.md" target="_blank" rel="noreferrer" className={styles.textLink}>測定と統計の定義を読む ↗</a></div><dl className={styles.deliverables}><div><dt><span>01</span>編集できる図</dt><dd>SVG・PDF・PNG。軸、単位、比較対象を明示し、日本語・英語のラベルに対応。</dd></div><div><dt><span>02</span>たどれる測定値</dt><dd>領域ID付きの測定表、マスク、Fiji用ROI。細胞・視野・独立反復を分けて記録。</dd></div><div><dt><span>03</span>再実行に必要な条件</dt><dd>解析版、背景、除外、統計条件、Methods文、環境情報をまとめて保存。</dd></div></dl></section>
      <section className={styles.scope} id="scope" aria-labelledby="scope-title"><div><p className={styles.eyebrow}>現在の対応範囲</p><h2 id="scope-title">まずは、2D蛍光画像の<br />領域定量から。</h2><p>解析の流れを確かめながら使える初期版です。<br />対象や撮影条件に合わせて、検出結果と測定条件を確認してください。</p></div><div className={styles.scopeDetails}><dl><div><dt>入力</dt><dd>8 / 16-bitのチャンネル別TIFF、対応範囲のOME-TIFF（単一シリーズ・Z=1・T=1）。</dd></div><div><dt>測定</dt><dd>核・核小体候補の検出と修正、領域の面積・平均・中央値・積算輝度、背景補正。</dd></div><div><dt>比較</dt><dd>独立実験単位での群間比較、対応あり比較、探索的な回帰。数値CSVの取り込み。</dd></div></dl><details><summary>解析対象と制約を確認</summary><p>手動で囲んだ領域、整数ラベル画像、核染色から検出した核を使い、指定した蛍光チャンネルを測定できます。NCLによる核小体候補とGFP陽性選別は専用の解析として用意しています。細胞全体など、核以外の任意の構造を自動検出する機能は提供していません。</p><p>3D・時系列・スポット解析・自動細胞境界検出は対象外です。通常の核自動検出は1辺2,048 px・270万画素以内が上限です。撮影装置に固有の定量処理には対応していません。</p><p>手法の自動選定やAIによる結果の解釈は行いません。実画像での実験ごとの妥当性検証と、研究者による利用評価を継続します。</p></details></div></section>
      <section className={styles.download} id="download" aria-labelledby="download-title"><div className={styles.downloadIntro}><p className={styles.eyebrow}>はじめる</p><h2 id="download-title">自分の画像で、<br />解析を始める。</h2><p>現在はWindows版を提供しています。<br />解析はPC内で実行し、操作はブラウザで。<br />この公開サイトに研究画像を送る必要はありません。</p><div className={styles.privateNote}><span aria-hidden="true">↳</span><p><b>研究データは、PC内に。</b><br />保存期間は最後の操作から24時間。<br />必要な結果は書き出して保存してください。</p></div><a href="https://github.com/genellect/cytellect/blob/main/docs/local.md" target="_blank" rel="noreferrer" className={styles.textLink}>セットアップと動作環境 ↗</a></div><div className={styles.downloadBody}>{WINDOWS_RELEASE_URL ? <WindowsDownload url={WINDOWS_RELEASE_URL} /> : <><h3>公開サンプルからお試しください</h3><p>Windows版の配布は現在このページでは案内していません。研究画像のアップロードは受け付けていません。</p><Link href="/demo" className={styles.primary}>公開画像を見る ↗</Link></>}</div></section>
    </main>
    <footer className={styles.footer}><div><span className={styles.footerBrand}>cytellect</span><p>蛍光画像の解析から、再現できる図へ。</p></div><nav aria-label="製品情報"><a href="https://github.com/genellect/cytellect" target="_blank" rel="noreferrer">ソースコード ↗</a><a href="https://github.com/genellect/cytellect/blob/main/docs/validation.md" target="_blank" rel="noreferrer">検証状況 ↗</a><a href="https://github.com/genellect/cytellect/blob/main/SECURITY.md" target="_blank" rel="noreferrer">セキュリティ ↗</a></nav><span className={styles.footerStatus}>開発プレビュー</span></footer>
  </div>;
}
