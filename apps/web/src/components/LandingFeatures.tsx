"use client";

import Link from "next/link";
import { useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import lp from "./optical-landing.module.css";

const Forward = () => <span aria-hidden="true">→</span>;

type Feature = { id: string; label: string; title: string; lead: string; extra?: ReactNode; link: ReactNode; visual: ReactNode };

/** An example instruction and the settings it fills in. */
const proposal = [
  ["測る場所", "核"],
  ["測る値", "GFPの核内平均輝度と、陽性細胞の割合"],
  ["比べる群", "薬の濃度ごと"],
  ["統計", "実験の繰り返しを単位にした比較"],
];

/** Each tab states one thing Cytellect does in a line, and shows it. */
const features: Feature[] = [
  {
    id: "flow",
    label: "解析の流れ",
    title: "画像を入れるだけ。検出から論文の図まで、一つの画面で。",
    lead: "輪郭を手で描く、表に写す、統計ソフトに移す。その作業がなくなります。",
    extra: <ol className={lp.flow} aria-label="解析の流れ"><li>画像を読み込む</li><li>核と核小体を自動で検出</li><li>統計</li><li>論文の図</li></ol>,
    link: <Link data-lp-event="example" href="/demo" className={lp.button}>デモで操作する <Forward /></Link>,
    visual: <figure className={lp.screen}><picture><source media="(max-width: 760px)" srcSet="/marketing/lp-workspace-mobile.webp" width={1080} height={871} /><img src="/marketing/lp-workspace.webp" alt="Cytellectのデモ。視野の一覧、核の輪郭を重ねた蛍光画像、核ごとの測定値、解析の設定が一つの画面に並ぶ" width={2880} height={1800} /></picture></figure>,
  },
  {
    id: "nucleoli",
    label: "自動検出",
    title: "汎用のAIでは見つからない構造も、検出できます。",
    lead: "たとえば核小体。汎用のAIでは見つからなかった核小体を、Cytellectは見分けます。",
    extra: <div className={lp.numbers}>
      <p><strong>0% → 90%</strong><span>核小体の検出率<br />（汎用のAI → Cytellect）</span></p>
      <p><strong>92%</strong><span>核の検出精度</span></p>
    </div>,
    link: <Link data-lp-event="demo_image" href="/demo?step=image" className={lp.button}>この画像をデモで解析する <Forward /></Link>,
    visual: <figure className={lp.specimen}>
      <picture><source media="(max-width: 760px)" srcSet="/marketing/lp-field-mobile.webp" width={1080} height={1080} /><img src="/marketing/lp-field.webp" alt="デモの蛍光画像。青い核と桃色の核小体を、Cytellectが検出した輪郭が囲んでいる" width={1536} height={864} /></picture>
      <figcaption>デモの公開画像と、Cytellectが検出した核（青）と核小体（桃）の輪郭。数値は研究室の画像と正解付きの公開画像で測ったもので、この画像の結果ではありません。画像：Schmidt, Rohatgi, Brandman (2022), Zenodo, CC BY 4.0</figcaption>
    </figure>,
  },
  {
    id: "ai",
    label: "AIによる設定",
    title: "やりたいことを一文で。解析の設定は、AIが組み立てます。",
    lead: "どの値を、どの群で、どの検定で比べるか。メニューを一つずつ選ぶ必要はありません。",
    link: <Link data-lp-event="example" href="/demo" className={lp.button}>デモでAIに頼む <Forward /></Link>,
    visual: <figure className={lp.prompt}>
      <p className={lp.before}><span>これまで</span>処理の選択、組み合わせ、条件の調整を、すべて自分で。</p>
      <p className={lp.ask}><span>Cytellect</span>GFPが核に移った細胞の割合を、薬の濃度ごとに比べたい</p>
      <span className={lp.arrow} aria-hidden="true">↓</span>
      <dl className={lp.answer} aria-label="AIが組み立てた設定">{proposal.map(([name, value]) => <div key={name}><dt>{name}</dt><dd>{value}</dd></div>)}</dl>
      <figcaption>一文から組み立てた設定の例。採用するかはあなたが決め、計算はCytellectの解析処理が行います。AIに送るのは入力した文だけで、画像や測定値は送りません。</figcaption>
    </figure>,
  },
  {
    id: "statistics",
    label: "統計と論文の図",
    title: "統計の検定も、論文に載せる図も、クリックだけで。",
    lead: "nは細胞の数ではなく、独立した実験の数。統計の落とし穴を、Cytellectが避けます。",
    extra: <ul className={lp.formats} aria-label="書き出せる形式"><li>SVG</li><li>PDF</li><li>CSV</li></ul>,
    link: <Link data-lp-event="demo_figure" href="/demo?step=figure" className={lp.button}>デモで統計と図を作る <Forward /></Link>,
    visual: <figure className={lp.paper}>
      <a href="/marketing/lp-figure.svg" aria-label="図を拡大"><img src="/marketing/lp-figure.svg" alt="デモから書き出した図。反復ごとに、未処理とアクチノマイシンD処理の核のNPM1平均輝度を線で結んでいる" width={518.74} height={283.46} /></a>
      <figcaption>デモから書き出した図（核のNPM1平均輝度、反復ごとに未処理とActD処理を結んだもの、n = 3）。この公開データの反復は同じ日の撮影で、独立性は出典に記載がありません。</figcaption>
    </figure>,
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
      <div>
        <h3 className={lp.panelTitle}>{feature.title}</h3>
        <p className={lp.panelLead}>{feature.lead}</p>
        {feature.extra}
        {feature.link}
      </div>
      <div>{feature.visual}</div>
    </div>)}
  </div>;
}
