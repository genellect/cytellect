import lp from "./optical-landing.module.css";

/** The future research can lead to, ending with the patients it is for. */
const PATH = [
  ["病気のしくみを", "解き明かす"],
  ["新しい薬の可能性を", "見つける"],
  ["患者へ届ける"],
];

export function LandingImpact() {
  return <section id="impact" className={lp.impact} aria-labelledby="impact-title">
    <div className={lp.wide}>
      <div className={lp.impactPanel}>
        <h2 id="impact-title" className={lp.impactTitle} aria-label="研究の先に、待っている患者さんがいる。"><span>研究の先に、</span><span><span>待っている</span><span>患者さんがいる。</span></span></h2>
        <ol className={lp.path} aria-label="研究から患者さんまで">
          {PATH.map(lines => <li key={lines[0]}><b>{lines.map(line => <span key={line}>{line}</span>)}</b></li>)}
        </ol>
      </div>
    </div>
  </section>;
}
