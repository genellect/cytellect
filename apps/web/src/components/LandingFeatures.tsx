"use client";

import Link from "next/link";
import { useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import lp from "./optical-landing.module.css";

const Forward = () => <span aria-hidden="true">→</span>;

type Feature = { id: string; label: string; title: string; body: ReactNode; visual: ReactNode };

/** Each tab states one thing Cytellect does, with the real screen or image that shows it. */
const features: Feature[] = [
  {
    id: "flow",
    label: "解析の流れ",
    title: "検出・修正・測定から、統計と論文用の図まで一つの画面で。",
    body: <>
      <div className={lp.prose}><p>画像解析ソフトで輪郭を手で描き、表計算ソフトに写し、統計ソフトで検定と作図をしていた作業を置き換えます。検出の設定、手で直した輪郭、除外の記録が残るので、後から同じ結果を再現できます。</p></div>
      <Link data-lp-event="example" href="/demo" className={lp.button}>解析例を操作する <Forward /></Link>
    </>,
    visual: <figure className={lp.screen}><picture><source media="(max-width: 760px)" srcSet="/marketing/lp-workspace-mobile.webp" width={1080} height={871} /><img src="/marketing/lp-workspace.webp" alt="Cytellectの解析例。視野の一覧、核の輪郭を重ねた蛍光画像、核ごとの測定値、解析の設定が一つの画面に並ぶ" width={2880} height={1800} /></picture></figure>,
  },
  {
    id: "nucleoli",
    label: "核小体の検出",
    title: "汎用のモデルでは見つからない核小体を、追加学習で検出。",
    body: <>
      <div className={lp.prose}><p>研究室の抗NCL抗体で染色した画像では、汎用の深層学習モデルが検出できた核小体は15個中0個でした。研究者が修正した輪郭で追加学習したモデルは、20個中18個を検出します。核は、正解の輪郭が付いた公開画像で、人が描いた輪郭とのF1が0.92です。</p></div>
      <div className={lp.numbers}>
        <p><strong>0% → 90%</strong><span>核小体の検出成功率（研究室の画像、追加学習の前と後）</span></p>
        <p><strong>0.92</strong><span>核の検出のF1（正解付きの公開画像）</span></p>
      </div>
      <Link data-lp-event="demo_image" href="/demo?step=image" className={lp.button}>この画像を解析例で見る <Forward /></Link>
    </>,
    visual: <figure className={lp.specimen}>
      <picture><source media="(max-width: 760px)" srcSet="/marketing/lp-field-mobile.webp" width={1080} height={1080} /><img src="/marketing/lp-field.webp" alt="解析例の蛍光画像。青い核と桃色の核小体を、Cytellectが検出した輪郭が囲んでいる" width={1536} height={864} /></picture>
      <figcaption>解析例の公開画像に、Cytellectの検出結果を重ねたもの。核（青）と核小体（桃）の輪郭。左の数値はこの画像で測ったものではありません。画像：Schmidt, Rohatgi, Brandman (2022), Zenodo, CC BY 4.0</figcaption>
    </figure>,
  },
  {
    id: "ai",
    label: "AIによる設定",
    title: "やりたい解析を一文で書くと、解析の設定に分解して提案します。",
    body: <>
      <div className={lp.prose}><p>たとえば「NPM1の核内平均輝度を未処理とActD処理で比較したい」と書くと、測る対象と指標、統計の方法を組み立て、その理由と一緒に示します。採用するかは研究者が決め、計算はAIではなくCytellectの解析処理が行い、その測定値はImageJによる独立計算と一致することを確かめています。AIに送るのは入力した文だけで、画像・測定値・ファイル名は送りません。</p></div>
      <Link data-lp-event="example" href="/demo" className={lp.button}>解析例でAIに指示する <Forward /></Link>
    </>,
    visual: <figure className={lp.screen}><picture><source media="(max-width: 760px)" srcSet="/marketing/lp-ai-mobile.webp" width={580} height={1050} /><img src="/marketing/lp-ai.webp" alt="解析例でAIに指示した画面。指示の文と、反復を対応とした対応ありt検定で比べるという提案が表示されている" width={2880} height={1800} /></picture></figure>,
  },
  {
    id: "statistics",
    label: "統計と論文の図",
    title: "nは細胞の数ではなく、独立した実験の数として検定します。",
    body: <>
      <div className={lp.prose}><p>細胞の数をnにすると、差のないデータからも誤った有意差が生まれます。Cytellectは視野と試料を独立した実験に対応づけ、その単位で検定します。輪郭を直せば測定値・統計・図が更新され、図の点からはその値のもとになった画像を開けます。図は編集できるSVG・PDFで、測定値はCSVで書き出せます。</p></div>
      <div className={lp.links}><Link data-lp-event="demo_figure" href="/demo?step=figure" className={lp.button}>統計とグラフを解析例で見る <Forward /></Link><Link data-lp-event="planning" href="/plan" className={lp.button}>解析の計画を立てる <Forward /></Link></div>
    </>,
    visual: <div className={lp.stack}>
      <figure className={lp.screen}><img src="/marketing/lp-statistics.webp" alt="解析例の統計の画面。視野ごとに群・試料・独立実験単位を対応づけた表と、反復ごとの平均値" width={2880} height={1800} /></figure>
      <figure className={lp.paper}>
        <a href="/marketing/lp-figure.svg" aria-label="図を拡大"><img src="/marketing/lp-figure.svg" alt="解析例から書き出した図。反復ごとに、未処理とアクチノマイシンD処理の核のNPM1平均輝度を線で結んでいる" width={518.74} height={283.46} /></a>
        <figcaption>解析例から書き出した図。核のNPM1平均輝度を、反復（Rep）ごとに未処理とActD処理で結んだもの（n = 3）。この公開データは同じ日の撮影で、反復の独立性は出典に記載がありません。</figcaption>
      </figure>
    </div>,
  },
];

export function LandingFeatures() {
  const [active, setActive] = useState(0);
  const tabs = useRef<(HTMLButtonElement | null)[]>([]);
  const select = (index: number) => { setActive(index); tabs.current[index]?.focus(); };
  const onKeyDown = (event: KeyboardEvent) => {
    const last = features.length - 1;
    const next = event.key === "ArrowRight" ? (active === last ? 0 : active + 1)
      : event.key === "ArrowLeft" ? (active === 0 ? last : active - 1)
      : event.key === "Home" ? 0 : event.key === "End" ? last : null;
    if (next === null) return;
    event.preventDefault();
    select(next);
  };
  return <div className={[lp.wide, lp.tabs].join(" ")}>
    <div role="tablist" aria-label="Cytellectでできること" className={lp.tablist} onKeyDown={onKeyDown}>
      {features.map((feature, index) => <button key={feature.id} ref={node => { tabs.current[index] = node; }} type="button" role="tab"
        id={`feature-tab-${feature.id}`} aria-controls={`feature-${feature.id}`} aria-selected={index === active} tabIndex={index === active ? 0 : -1}
        className={lp.tab} onClick={() => setActive(index)}>{feature.label}</button>)}
    </div>
    {features.map((feature, index) => <div key={feature.id} role="tabpanel" id={`feature-${feature.id}`} aria-labelledby={`feature-tab-${feature.id}`}
      hidden={index !== active} className={lp.panel}>
      <div><h3 className={lp.panelTitle}>{feature.title}</h3>{feature.body}</div>
      <div>{feature.visual}</div>
    </div>)}
  </div>;
}
