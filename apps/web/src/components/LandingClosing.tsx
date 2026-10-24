import Link from "next/link";
import lp from "./optical-landing.module.css";

/** One line per screen, two phrases each, set at the hero's scale. */
function Line({ id, phrases }: { id: string; phrases: [string, string] }) {
  return <h2 id={id} className={lp.sceneTitle} aria-label={phrases.join("")}><span>{phrases[0]}</span><span>{phrases[1]}</span></h2>;
}

/** What can be measured turns over in one place, ending open on "what you want to see". */
const MEASURED = ["核", "核小体", "細胞質", "蛍光シグナル", "見たいもの"];

/** The closing chapter: three screens that move from the light page into deep green and end on the demo.
 *  Measuring, understanding disease and finding new medicines share the first screen; reaching patients is the second. */
export function LandingClosing() {
  return <div className={lp.chapter}>
    <section id="future" className={lp.scene} aria-labelledby="future-title">
      <div className={lp.sceneBody}>
        <Line id="future-title" phrases={["治せない病気を、", "過去のものに。"]} />
        <p className={lp.measure}>
          <span className={lp.visuallyHidden}>核、核小体、細胞質、蛍光シグナル、見たいものを測る。病気を解き明かし、新しい薬を見つける。</span>
          <span className={lp.slot} aria-hidden="true">{MEASURED.map((word, index) => <span key={word} style={{ animationDelay: `${index * 2.4}s` }}>{word}</span>)}</span>
          <span aria-hidden="true">を測る。病気を解き明かし、新しい薬を見つける。</span>
        </p>
      </div>
    </section>
    <section className={[lp.scene, lp.sceneDark].join(" ")} aria-labelledby="waiting-title">
      <Line id="waiting-title" phrases={["その日を、", "待っている人がいる。"]} />
    </section>
    <section id="start" className={lp.finale} aria-labelledby="finale-title">
      <div className={lp.finaleCopy}>
        <Line id="finale-title" phrases={["その未来を、", "あなたの研究から。"]} />
        <div className={lp.heroActions}>
          <Link data-lp-event="example" href="/demo" className={lp.primary}>デモを体験する <span aria-hidden="true">→</span></Link>
          <a data-lp-event="download_section" href="#download" className={lp.heroSecondary}>Windows版をダウンロード <span aria-hidden="true">↑</span></a>
        </div>
      </div>
    </section>
  </div>;
}
