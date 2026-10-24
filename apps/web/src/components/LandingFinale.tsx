import Link from "next/link";
import { HeroFilm } from "./HeroFilm";
import lp from "./optical-landing.module.css";

/** The closing scene returns to the hero film and asks for one thing: open the demo. */
export function LandingFinale() {
  return <section id="start" className={lp.finale} aria-labelledby="finale-title">
    <HeroFilm testId="finale-film" deferred />
    <div className={lp.finaleShade} />
    <div className={lp.finaleCopy}>
      <h2 id="finale-title" className={lp.finaleTitle} aria-label="次の発見は、あなたの顕微鏡画像から。"><span><span>次の発見は、</span></span><span><span>あなたの</span><span>顕微鏡画像から。</span></span></h2>
      <div className={lp.heroActions}>
        <Link data-lp-event="example_final" href="/demo" className={lp.primary}>デモを体験する <span aria-hidden="true">→</span></Link>
        <a data-lp-event="download_section" href="#download" className={lp.heroSecondary}>Windows版をダウンロード <span aria-hidden="true">↓</span></a>
      </div>
    </div>
  </section>;
}
