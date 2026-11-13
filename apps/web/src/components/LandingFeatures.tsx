"use client";

import Link from "next/link";
import { useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import lp from "./optical-landing.module.css";

const Forward = () => <span aria-hidden="true">→</span>;

/** Where each tab's evidence opens in the demo (resolved on the server, see lib/showcase/scene-links). */
export type FeatureLinks = { discussion: string; table: string; figure: string; ask: string };

type Feature = { id: string; label: string; title: string; lead: string; extra?: ReactNode; link: ReactNode; stage: ReactNode };

const shot = (file: string) => `/marketing/${file}`;

/** The whole screen: it tells the visitor which screen this is. Captured at 1600 × 790. */
function Screen({ file, alt }: { file: string; alt: string }) {
  return <img className={lp.stageScreen} src={shot(file)} alt={alt} width={1600} height={790} loading="lazy" />;
}
/** The part that carries the claim, in front and large enough to read. Sizes are the capture's CSS pixels. */
function Focus({ file, alt, width, height }: { file: string; alt: string; width: number; height: number }) {
  return <img className={lp.stageFocus} src={shot(file)} alt={alt} width={width} height={height} loading="lazy" />;
}

/** Each tab states one thing Cytellect does in a line, and shows it on one large stage. Every image is a
 *  capture of the public demo (scripts/capture-lp-evidence.mjs, public/marketing/lp-evidence.json).
 *  The summary and discussion come first: of everything here, they are worth the most to a researcher. */
const features = (links: FeatureLinks): Feature[] => [
  {
    id: "discussion",
    label: "要約と考察",
    title: "結果を読み解く時間を、次の実験を考える時間に。",
    lead: "解析が終わると、結論の一文と考察が並びます。解釈も、ほかの説明も、次に確かめることも。",
    link: <Link data-lp-event="demo_statistics" href={links.discussion} className={lp.button}>この結果をデモで開く <Forward /></Link>,
    stage: <figure className={lp.stage} data-kind="layers">
      <Screen file="lp-screen-statistics.webp" alt="Cytellectの統計の画面。結果のまとめ、図、解析の設定が並ぶ" />
      <div className={lp.stageFront} data-width="reading">
        <Focus file="lp-focus-conclusion.webp" alt="結果のまとめ。「PLK1 KO で、視野あたりの核数が 79〜84% 減少」という結論の一文と、3 回の実験すべてで減少したことを示す要点" width={426} height={180} />
        <Focus file="lp-focus-discussion.webp" alt="結果の考察。解釈、限界・代替説明、追加検証の 3 つの見出しに、それぞれ箇条書きが並ぶ" width={426} height={305} />
      </div>
    </figure>,
  },
  {
    id: "flow",
    label: "解析の流れ",
    title: "画像を入れるだけ。検出から論文の図まで、一つの画面で。",
    lead: "輪郭を手で描く、表に写す、統計ソフトに移す。その作業がなくなります。",
    extra: <ol className={lp.flow} aria-label="解析の流れ"><li>画像を読み込む</li><li>細胞構造を自動検出</li><li>統計</li><li>結論と考察</li><li>論文の図</li></ol>,
    link: <Link data-lp-event="example" href="/demo" className={lp.button}>デモで操作する <Forward /></Link>,
    stage: <figure className={lp.stage} data-kind="screen">
      <Screen file="lp-screen-statistics.webp" alt="Cytellectの画面。実験、画像、統計、グラフの順に進み、統計では結果のまとめと図が並ぶ" />
    </figure>,
  },
  {
    id: "measure",
    label: "検出と測定",
    title: "測りたい値が、細胞ひとつひとつに並びます。",
    lead: "汎用のAIでは見つからなかった核小体まで、輪郭を描かずに検出。細胞ごとに、測った値が一行に並びます。",
    extra: <div className={lp.numbers}>
      <p><strong>0% → 90%</strong><span>核小体の検出率<br />（汎用のAI → Cytellect）</span></p>
      <p><strong>92%</strong><span>核の検出精度</span></p>
    </div>,
    link: <Link data-lp-event="demo_image" href={links.table} className={lp.button}>この表をデモで開く <Forward /></Link>,
    stage: <figure className={lp.stage} data-kind="strip">
      <div className={lp.stageScroll}><Focus file="lp-focus-table.webp" alt="核ごとの表。1 つの核の行に、核面積、3 つの染色それぞれの積算・平均と背景補正値、核小体の数・面積・核に占める割合・離心率が並ぶ" width={1750} height={373} /></div>
    </figure>,
  },
  {
    id: "ai",
    label: "AIによる設定",
    title: "やりたいことを一文で。解析の設定は、AIが組み立てます。",
    lead: "どの値を、どの群で、どの検定で比べるか。メニューを一つずつ選ぶ必要はありません。",
    link: <Link data-lp-event="example" href={links.ask} className={lp.button}>デモで指示する <Forward /></Link>,
    stage: <figure className={lp.stage} data-kind="layers">
      <Screen file="lp-screen-ai.webp" alt="Cytellectの統計の画面。右に AI のパネルが開いている" />
      <div className={lp.stageFront} data-width="ask">
        <Focus file="lp-focus-ai.webp" alt="AI への指示「核の数と面積を視野ごとに確認したい」と、組み立てた設定の説明" width={320} height={132} />
      </div>
    </figure>,
  },
  {
    id: "statistics",
    label: "統計と論文の図",
    title: "統計の検定も、論文に載せる図も、クリックだけで。",
    lead: "nは細胞の数ではなく、独立した実験の数。統計の落とし穴を、Cytellectが避けます。",
    extra: <ul className={lp.formats} aria-label="書き出せる形式"><li>SVG</li><li>PDF</li><li>CSV</li></ul>,
    link: <Link data-lp-event="demo_figure" href={links.figure} className={lp.button}>この図をデモで開く <Forward /></Link>,
    stage: <figure className={lp.stage} data-kind="layers">
      <Screen file="lp-screen-figure.webp" alt="Cytellectのグラフの画面。実験回ごとの図と、図の設定が並ぶ" />
      <div className={lp.stageFront} data-width="controls">
        <Focus file="lp-focus-figure-layout.webp" alt="グラフの設定。図の幅は「2段幅 · 183 mm」、図のレイアウトは「実験回ごと（視野・実験回・平均）」" width={288} height={226} />
        <Focus file="lp-focus-figure-size.webp" alt="グラフの設定。幅 183 mm、高さ 100 mm、文字 7 pt" width={288} height={250} />
      </div>
    </figure>,
  },
];

export function LandingFeatures({ links }: { links: FeatureLinks }) {
  const [active, setActive] = useState(0);
  const tabs = useRef<(HTMLButtonElement | null)[]>([]);
  const list = features(links);
  const select = (index: number) => { setActive(index); tabs.current[index]?.focus(); };
  const onKeyDown = (event: KeyboardEvent) => {
    const last = list.length - 1;
    const next = event.key === "ArrowRight" ? (active === last ? 0 : active + 1)
      : event.key === "ArrowLeft" ? (active === 0 ? last : active - 1)
      : event.key === "Home" ? 0 : event.key === "End" ? last : null;
    if (next === null) return;
    event.preventDefault();
    select(next);
  };
  return <div className={[lp.wide, lp.tabs].join(" ")}>
    <div role="tablist" aria-label="Cytellectでできること" className={lp.tablist} onKeyDown={onKeyDown}>
      {list.map((feature, index) => <button key={feature.id} ref={node => { tabs.current[index] = node; }} type="button" role="tab"
        id={`feature-tab-${feature.id}`} aria-controls={`feature-${feature.id}`} aria-selected={index === active} tabIndex={index === active ? 0 : -1}
        className={lp.tab} onClick={() => setActive(index)}>{feature.label}</button>)}
    </div>
    {list.map((feature, index) => <div key={feature.id} role="tabpanel" id={`feature-${feature.id}`} aria-labelledby={`feature-tab-${feature.id}`}
      hidden={index !== active} className={lp.panel}>
      <div className={lp.panelHead}>
        <h3 className={lp.panelTitle}>{feature.title}</h3>
        <div>
          <p className={lp.panelLead}>{feature.lead}</p>
          {feature.extra}
          {feature.link}
        </div>
      </div>
      {feature.stage}
    </div>)}
  </div>;
}
