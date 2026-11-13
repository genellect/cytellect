"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type ReactNode } from "react";
import type { ExperienceController, ExperiencePanel } from "./experience-scene";
import lp from "./optical-landing.module.css";

const Forward = () => <span aria-hidden="true">→</span>;

/** Where each chapter's screen opens in the demo (resolved on the server, see lib/showcase/scene-links). */
export type FeatureLinks = { discussion: string; table: string; figure: string; ask: string };

const shot = (file: string) => `/marketing/${file}`;
/** Every plate is a capture of the public demo (scripts/capture-lp-evidence.mjs, public/marketing/lp-evidence.json). */
const PANELS: ExperiencePanel[] = [
  { id: "stats", src: shot("lp-screen-statistics.webp") },
  { id: "ai", src: shot("lp-screen-ai.webp") },
  { id: "figure", src: shot("lp-screen-figure.webp") },
  { id: "ask", src: shot("lp-focus-ai.webp") },
  { id: "table", src: shot("lp-focus-table.webp") },
  { id: "conclusion", src: shot("lp-focus-conclusion.webp") },
  { id: "discussion", src: shot("lp-focus-discussion.webp") },
  { id: "layout", src: shot("lp-focus-figure-layout.webp") },
  { id: "size", src: shot("lp-focus-figure-size.webp") },
];

type Plate = { file: string; alt: string; width: number; height: number };
const Img = ({ plate, className }: { plate: Plate; className?: string }) =>
  <img className={className} src={shot(plate.file)} alt={plate.alt} width={plate.width} height={plate.height} loading="lazy" decoding="async" />;

type Chapter = {
  id: string; number: string; label: string; title: string; lead: string; extra?: ReactNode; link: ReactNode;
  /** Scroll positions (fractions of the chapter's height) where the camera holds one shot of experience-scene. */
  anchors: number[];
  back?: Plate; front: Plate[]; kind: "layers" | "strip";
};

const chapters = (links: FeatureLinks): Chapter[] => [
  {
    id: "ask", number: "01", label: "AIによる設定", anchors: [0.5], kind: "layers",
    title: "やりたいことを一文で。解析の設定は、AIが組み立てます。",
    lead: "どの値を、どの群で、どう比べるか。メニューを一つずつ選ぶ必要はありません。",
    link: <Link data-lp-event="example" href={links.ask} className={lp.button}>デモで指示する <Forward /></Link>,
    back: { file: "lp-screen-ai.webp", alt: "Cytellectの統計の画面。右に AI のパネルが開いている", width: 1600, height: 790 },
    front: [{ file: "lp-focus-ai.webp", alt: "AI への指示「核の数と面積を視野ごとに確認したい」と、組み立てた設定の説明", width: 320, height: 132 }],
  },
  {
    id: "measure", number: "02", label: "検出と測定", anchors: [0.3, 0.72], kind: "strip",
    title: "測りたい値が、細胞ひとつひとつに並びます。",
    lead: "汎用のAIでは見つからない構造まで、輪郭を一つも描かずに。測った値は、細胞ごとに一行に並びます。",
    extra: <>
      <ul className={lp.params} aria-label="測れる値">{["数と密度", "大きさと形", "明るさ", "陽性の割合", "位置と分布", "区画のあいだの比"].map(item => <li key={item}>{item}</li>)}</ul>
      <div className={lp.example}>
        <p className={lp.exampleLabel}>一例：核小体の研究</p>
        <div className={lp.numbers}>
          <p><strong>0% → 90%</strong><span>核小体の検出率<br />（汎用のAI → Cytellect）</span></p>
          <p><strong>92%</strong><span>核の検出精度</span></p>
        </div>
      </div>
    </>,
    link: <Link data-lp-event="demo_image" href={links.table} className={lp.button}>この表をデモで開く <Forward /></Link>,
    front: [{ file: "lp-focus-table.webp", alt: "核ごとの表。1 つの核の行に、核面積、3 つの染色それぞれの積算・平均と背景補正値、核小体の数・面積・核に占める割合・離心率が並ぶ", width: 1750, height: 373 }],
  },
  {
    id: "discussion", number: "03", label: "要約と考察", anchors: [0.5], kind: "layers",
    title: "結果を読み解く時間を、次の実験を考える時間に。",
    lead: "解析が終わると、結論の一文と考察が並びます。解釈も、ほかの説明も、次に確かめることも。",
    link: <Link data-lp-event="demo_statistics" href={links.discussion} className={lp.button}>この結果をデモで開く <Forward /></Link>,
    back: { file: "lp-screen-statistics.webp", alt: "Cytellectの統計の画面。結果のまとめ、図、解析の設定が並ぶ", width: 1600, height: 790 },
    front: [
      { file: "lp-focus-conclusion.webp", alt: "結果のまとめ。「PLK1 KO で、視野あたりの核数が 79〜84% 減少」という結論の一文と、3 回の実験すべてで減少したことを示す要点", width: 426, height: 180 },
      { file: "lp-focus-discussion.webp", alt: "結果の考察。解釈、限界・代替説明、追加検証の 3 つの見出しに、それぞれ箇条書きが並ぶ", width: 426, height: 305 },
    ],
  },
  {
    id: "figure", number: "04", label: "統計と論文の図", anchors: [0.5], kind: "layers",
    title: "統計の検定も、論文に載せる図も、クリックだけで。",
    lead: "結果に合った検定で比べ、論文の体裁で図を組みます。幅も、レイアウトも、文字の大きさも。",
    link: <Link data-lp-event="demo_figure" href={links.figure} className={lp.button}>この図をデモで開く <Forward /></Link>,
    back: { file: "lp-screen-figure.webp", alt: "Cytellectのグラフの画面。実験回ごとの図と、図の設定が並ぶ", width: 1600, height: 790 },
    front: [
      { file: "lp-focus-figure-layout.webp", alt: "グラフの設定。図の幅は「2段幅 · 183 mm」、図のレイアウトは「実験回ごと（視野・実験回・平均）」", width: 288, height: 226 },
      { file: "lp-focus-figure-size.webp", alt: "グラフの設定。幅 183 mm、高さ 100 mm、文字 7 pt", width: 288, height: 250 },
    ],
  },
];

/** Where the scroll is, as a shot of experience-scene: each anchor is the moment its chapter fills the middle of the screen. */
function shotAt(track: HTMLElement): number {
  const anchors: number[] = [];
  for (const node of track.querySelectorAll<HTMLElement>("[data-anchors]"))
    for (const fraction of node.dataset.anchors!.split(",")) anchors.push(node.offsetTop + Number(fraction) * node.offsetHeight);
  const middle = innerHeight / 2 - track.getBoundingClientRect().top;
  if (middle <= anchors[0]) return 0;
  for (let i = 1; i < anchors.length; i++) if (middle < anchors[i]) return i - 1 + (middle - anchors[i - 1]) / (anchors[i] - anchors[i - 1]);
  return anchors.length - 1;
}

/** The product, one chapter at a time. On a wide screen with motion allowed, the chapters scroll over one
 *  3D space in which the camera moves from screen to screen; elsewhere (phones, reduced motion, no WebGL)
 *  each chapter shows the same screens as layered glass plates. */
export function LandingExperience({ links }: { links: FeatureLinks }) {
  const track = useRef<HTMLDivElement>(null);
  const host = useRef<HTMLDivElement>(null);
  const [mode, setMode] = useState<"plates" | "space">("plates");
  const [active, setActive] = useState("intro");
  const list = chapters(links);

  useEffect(() => {
    const wide = matchMedia("(min-width: 1024px)"), still = matchMedia("(prefers-reduced-motion: reduce)");
    let controller: ExperienceController | null = null, abort: AbortController | null = null, frame = 0;
    const follow = () => { frame = 0; if (track.current) controller?.setProgress(shotAt(track.current)); };
    const onScroll = () => { if (!frame) frame = requestAnimationFrame(follow); };
    const stop = () => { abort?.abort(); abort = null; controller?.dispose(); controller = null; setMode("plates"); };
    const sync = async () => {
      stop();
      const canvas = document.createElement("canvas");
      if (!wide.matches || still.matches || !canvas.getContext("webgl2") || !host.current) return;
      setMode("space");
      abort = new AbortController();
      const signal = abort.signal;
      try {
        const { mountExperience } = await import("./experience-scene");
        if (signal.aborted || !host.current) return;
        const mounted = await mountExperience(host.current, PANELS, signal);
        if (signal.aborted) { mounted.dispose(); return; }
        controller = mounted;
        follow();
      } catch {
        if (!signal.aborted) stop();
      }
    };
    sync();
    wide.addEventListener("change", sync); still.addEventListener("change", sync);
    addEventListener("scroll", onScroll, { passive: true }); addEventListener("resize", onScroll);
    return () => {
      wide.removeEventListener("change", sync); still.removeEventListener("change", sync);
      removeEventListener("scroll", onScroll); removeEventListener("resize", onScroll);
      cancelAnimationFrame(frame); abort?.abort(); controller?.dispose();
    };
  }, []);

  useEffect(() => {
    const nodes = track.current?.querySelectorAll<HTMLElement>("[data-anchors]");
    if (!nodes) return;
    const observer = new IntersectionObserver(entries => {
      for (const entry of entries) if (entry.isIntersecting) setActive((entry.target as HTMLElement).dataset.chapter!);
    }, { rootMargin: "-45% 0px -45% 0px" });
    nodes.forEach(node => observer.observe(node));
    return () => observer.disconnect();
  }, []);

  return <section id="workflow" className={lp.experience} data-mode={mode} aria-labelledby="workflow-title">
    <div ref={track} className={lp.experienceTrack}>
      <div className={lp.experienceStage} aria-hidden="true"><div ref={host} className={lp.experienceCanvas} /><div className={lp.experienceVeil} /></div>
      <header className={lp.experienceIntro} data-anchors="0.55" data-chapter="intro" data-active={active === "intro"}>
        <p className={lp.eyebrow}><span>Cytellect</span>画像から、論文まで</p>
        <h2 id="workflow-title" className={lp.statement} aria-label="手作業で数週間かかっていた解析を、一つの画面で数分に。"><span>手作業で数週間かかっていた</span><span>解析を、一つの画面で数分に。</span></h2>
        <p className={lp.experienceLead}>画像を入れるだけ。輪郭を手で描く、表に写す、統計ソフトに移す。その作業がなくなります。</p>
      </header>
      {list.map(chapter => <article key={chapter.id} id={`feature-${chapter.id}`} className={lp.chapter} data-chapter={chapter.id} data-anchors={chapter.anchors.join(",")}
        data-active={active === chapter.id} aria-labelledby={`feature-${chapter.id}-title`}>
        <div className={lp.chapterText}>
          <p className={lp.eyebrow}><span>{chapter.number}</span>{chapter.label}</p>
          <h3 id={`feature-${chapter.id}-title`} className={lp.chapterTitle}>{chapter.title}</h3>
          <p className={lp.chapterLead}>{chapter.lead}</p>
          {chapter.extra}
          {chapter.link}
        </div>
        <figure className={lp.plates} data-kind={chapter.kind}>
          {chapter.back && <Img plate={chapter.back} className={lp.plateBack} />}
          {chapter.kind === "strip"
            ? <div className={lp.plateScroll}><Img plate={chapter.front[0]} className={lp.plateWide} /></div>
            : <div className={lp.plateFront}>{chapter.front.map(plate => <Img key={plate.file} plate={plate} className={lp.plate} />)}</div>}
        </figure>
      </article>)}
    </div>
  </section>;
}
