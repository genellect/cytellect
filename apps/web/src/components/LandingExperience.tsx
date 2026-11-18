"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
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
  /** The shot of experience-scene the camera flies to, and an optional slower second one. */
  shot: number; then?: number;
  back?: Plate; front: Plate[]; kind: "layers" | "strip";
};

const chapters = (links: FeatureLinks): Chapter[] => [
  {
    id: "measure", number: "01", label: "検出と測定", shot: 2, then: 3, kind: "strip",
    title: "測りたい値が、細胞ひとつひとつに並びます。",
    lead: "輪郭ごとに面積や蛍光強度を測ります。下の表は、核ごとの測定結果です。",
    extra: <>
      <ul className={lp.params} aria-label="測れる値">{["数と密度", "大きさと形", "明るさ", "陽性の割合", "位置と分布", "区画のあいだの比"].map(item => <li key={item}>{item}</li>)}</ul>
      <div className={lp.example}>
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
    id: "discussion", number: "02", label: "要約と考察", shot: 4, kind: "layers",
    title: "結果を読み解く時間を、次の実験を考える時間に。",
    lead: "群間比較では、差の大きさと実験回ごとの値を確認できます。クラウド機能では、保存した比較結果をもとに AI に考察を依頼できます。",
    link: <Link data-lp-event="demo_statistics" href={links.discussion} className={lp.button}>この結果をデモで開く <Forward /></Link>,
    back: { file: "lp-screen-statistics.webp", alt: "Cytellectの統計の画面。結果のまとめ、図、解析の設定が並ぶ", width: 1600, height: 790 },
    front: [
      { file: "lp-focus-conclusion.webp", alt: "結果のまとめ。「PLK1 KO で、視野あたりの核数が 79〜84% 減少」という結論の一文と、3 回の実験すべてで減少したことを示す要点", width: 426, height: 180 },
      { file: "lp-focus-discussion.webp", alt: "結果の考察。解釈、限界・代替説明、追加検証の 3 つの見出しに、それぞれ箇条書きが並ぶ", width: 426, height: 305 },
    ],
  },
  {
    id: "ask", number: "03", label: "AIによる設定", shot: 1, kind: "layers",
    title: "調べたいことを伝えると、AI が解析条件を提案します。",
    lead: "提案を確認し、必要に応じて直してから採用できます。Windows 版で AI の提案を使うには、クラウド利用の承認とログインが必要です。",
    link: <Link data-lp-event="example" href={links.ask} className={lp.button}>デモで提案の例を見る <Forward /></Link>,
    back: { file: "lp-screen-ai.webp", alt: "Cytellectの統計の画面。右に AI のパネルが開いている", width: 1600, height: 790 },
    front: [{ file: "lp-focus-ai.webp", alt: "AI への指示「核の数と面積を視野ごとに確認したい」と、組み立てた設定の説明", width: 320, height: 132 }],
  },
  {
    id: "figure", number: "04", label: "統計と論文の図", shot: 5, kind: "layers",
    title: "実験回ごとの結果を、図で確かめる。",
    lead: "登録した実験デザインをもとに条件を比較します。図の幅、レイアウト、文字の大きさを調整し、SVG や PDF で保存できます。",
    link: <Link data-lp-event="demo_figure" href={links.figure} className={lp.button}>この図をデモで開く <Forward /></Link>,
    back: { file: "lp-screen-figure.webp", alt: "Cytellectのグラフの画面。実験回ごとの図と、図の設定が並ぶ", width: 1600, height: 790 },
    front: [
      { file: "lp-focus-figure-layout.webp", alt: "グラフの設定。図の幅は「2段幅 · 183 mm」、図のレイアウトは「実験回ごと（視野・実験回・平均）」", width: 288, height: 226 },
      { file: "lp-focus-figure-size.webp", alt: "グラフの設定。幅 183 mm、高さ 100 mm、文字 7 pt", width: 288, height: 250 },
    ],
  },
];

/** What Cytellect does, one tab at a time: detection and measurement first, then the summary and discussion. On a wide screen with motion
 *  allowed, the tabs sit beside one 3D space and the camera flies to the chosen screen; elsewhere (phones,
 *  reduced motion, no WebGL) the chosen tab shows the same screens as glass plates. */
export function LandingExperience({ links }: { links: FeatureLinks }) {
  const host = useRef<HTMLDivElement>(null);
  const tabs = useRef<(HTMLButtonElement | null)[]>([]);
  const scene = useRef<ExperienceController | null>(null);
  const [mode, setMode] = useState<"plates" | "space">("plates");
  const [active, setActive] = useState(0);
  const list = chapters(links);
  const activeRef = useRef(0);

  useEffect(() => {
    const wide = matchMedia("(min-width: 1024px)"), still = matchMedia("(prefers-reduced-motion: reduce)");
    let abort: AbortController | null = null, seen: IntersectionObserver | null = null;
    const stop = () => { abort?.abort(); abort = null; seen?.disconnect(); seen = null; scene.current?.dispose(); scene.current = null; setMode("plates"); };
    const sync = async () => {
      stop();
      if (!wide.matches || still.matches || !document.createElement("canvas").getContext("webgl2") || !host.current) return;
      setMode("space");
      abort = new AbortController();
      const signal = abort.signal;
      try {
        const { mountExperience } = await import("./experience-scene");
        if (signal.aborted || !host.current) return;
        const mounted = await mountExperience(host.current, PANELS, signal);
        if (signal.aborted) { mounted.dispose(); return; }
        scene.current = mounted;
        // The space opens on the overview and flies to the chosen screen when the visitor reaches it.
        seen = new IntersectionObserver(([entry]) => {
          if (!entry.isIntersecting) return;
          seen?.disconnect();
          const chapter = chapters(links)[activeRef.current];
          mounted.show(chapter.shot, chapter.then);
        }, { threshold: 0.45 });
        seen.observe(host.current);
      } catch {
        if (!signal.aborted) stop();
      }
    };
    sync();
    wide.addEventListener("change", sync); still.addEventListener("change", sync);
    return () => { wide.removeEventListener("change", sync); still.removeEventListener("change", sync); stop(); };
  }, [links]);

  // The segmented control's filled pill slides under the chosen tab.
  const [pill, setPill] = useState<{ left: number; width: number } | null>(null);
  useEffect(() => {
    const place = () => { const tab = tabs.current[active]; if (tab) setPill({ left: tab.offsetLeft, width: tab.offsetWidth }); };
    place();
    addEventListener("resize", place);
    document.fonts?.ready.then(place);
    return () => removeEventListener("resize", place);
  }, [active, mode]);

  // With the 3D space, the bar plays by itself: a line fills along the foot of the chosen tab, then the next one opens.
  // It pauses while the pointer rests on the bar, the bar is off screen or the browser tab is hidden, and
  // stops for good once the visitor chooses or moves the keyboard focus into it.
  const bar = useRef<HTMLDivElement>(null);
  const [auto, setAuto] = useState(true);
  const [inView, setInView] = useState(false);
  const [hover, setHover] = useState(false);
  const [shown, setShown] = useState(true);
  useEffect(() => {
    const node = bar.current;
    if (!node) return;
    const seen = new IntersectionObserver(([entry]) => setInView(entry.isIntersecting), { threshold: 1 });
    seen.observe(node);
    const visibility = () => setShown(!document.hidden);
    document.addEventListener("visibilitychange", visibility);
    return () => { seen.disconnect(); document.removeEventListener("visibilitychange", visibility); };
  }, []);
  const playing = mode === "space" && auto;
  const running = playing && inView && !hover && shown;

  const select = (index: number, focus = false, chosen = true) => {
    const next = (index + list.length) % list.length;
    setActive(next);
    activeRef.current = next;
    if (chosen) setAuto(false);
    const tab = tabs.current[next];
    if (focus) tab?.focus();
    // On a phone the bar scrolls sideways; bring the chosen tab into view.
    const rail = tab?.parentElement;
    if (tab && rail && rail.scrollWidth > rail.clientWidth) rail.scrollTo({ left: tab.offsetLeft - rail.clientWidth / 2 + tab.offsetWidth / 2, behavior: "smooth" });
    scene.current?.show(list[next].shot, list[next].then);
  };
  const onKeyDown = (event: KeyboardEvent) => {
    const last = list.length - 1;
    const next = ["ArrowRight", "ArrowDown"].includes(event.key) ? (active === last ? 0 : active + 1)
      : ["ArrowLeft", "ArrowUp"].includes(event.key) ? (active === 0 ? last : active - 1)
      : event.key === "Home" ? 0 : event.key === "End" ? last : null;
    if (next === null) return;
    event.preventDefault();
    select(next, true);
  };

  return <section id="workflow" className={lp.experience} data-mode={mode} aria-labelledby="workflow-title">
    <header className={lp.experienceIntro}>
      <p className={lp.eyebrow}><span>Cytellect</span>画像から、論文まで</p>
      <h2 id="workflow-title" className={lp.statement} aria-label="顕微鏡画像の測定から、表と図の保存まで。"><span>顕微鏡画像の測定から、</span><span>表と図の保存まで。</span></h2>
      <p className={lp.experienceLead}>公開画像の解析例で、輪郭と測定表、条件間の比較、書き出す図を見られます。</p>
    </header>
    {/* Keyboard focus anywhere in the bar or the open panel stops the tour for good, so a focused link is never
        hidden by the next tab. */}
    <div className={lp.tour} onFocusCapture={() => setAuto(false)}>
      <div className={lp.experienceStage} aria-hidden="true"><div ref={host} className={lp.experienceCanvas} /><div className={lp.experienceVeil} /></div>
      <div className={lp.tourInner}>
        <div ref={bar} className={lp.switcher} onPointerEnter={() => setHover(true)} onPointerLeave={() => setHover(false)}>
          <div role="tablist" aria-label="Cytellectでできること" aria-orientation="horizontal" className={lp.tablist} onKeyDown={onKeyDown}
            onScroll={event => { const rail = event.currentTarget; rail.dataset.end = String(Math.ceil(rail.scrollLeft + rail.clientWidth) >= rail.scrollWidth); }}>
            {pill && <span className={lp.tabPill} style={{ transform: `translateX(${pill.left}px)`, width: pill.width }} aria-hidden="true">
              {playing && <span key={active} className={lp.tabSweep} data-running={running} onAnimationEnd={() => select(active + 1, false, false)} />}
            </span>}
            {list.map((chapter, index) => <button key={chapter.id} ref={node => { tabs.current[index] = node; }} type="button" role="tab"
              id={`feature-tab-${chapter.id}`} aria-controls={`feature-${chapter.id}`} aria-selected={index === active} tabIndex={index === active ? 0 : -1}
              className={lp.tab} onClick={() => select(index)}><span aria-hidden="true">{chapter.number}</span>{chapter.label}</button>)}
          </div>
          <div className={lp.switchNav}>
            <span className={lp.switchCount} aria-hidden="true"><b>{active + 1}</b> / {list.length}</span>
            <button type="button" className={lp.switchArrow} aria-label="前の機能" onClick={() => select(active - 1)}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14.5 6.5 9 12l5.5 5.5" /></svg></button>
            <button type="button" className={lp.switchArrow} aria-label="次の機能" onClick={() => select(active + 1)}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9.5 6.5 15 12l-5.5 5.5" /></svg></button>
          </div>
        </div>
        {list.map((chapter, index) => <div key={chapter.id} role="tabpanel" id={`feature-${chapter.id}`} aria-labelledby={`feature-tab-${chapter.id}`}
          hidden={index !== active} className={lp.chapter} data-chapter={chapter.id}>
          <div className={lp.chapterText}>
            <h3 className={lp.chapterTitle}>{chapter.title}</h3>
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
        </div>)}
      </div>
    </div>
  </section>;
}
