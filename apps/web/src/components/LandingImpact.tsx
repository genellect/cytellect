import lp from "./optical-landing.module.css";

/** From what a researcher measures to the patients it is for, on one line. */
const PATH = [
  ["測る", "核・核小体・細胞質・蛍光シグナル。見たいものを"],
  ["解き明かす", "病気のしくみを"],
  ["見つける", "新しい薬の候補を"],
  ["届ける", "待っている患者さんへ"],
];

export function LandingImpact() {
  return <section id="impact" className={lp.impact} aria-labelledby="impact-title">
    <div className={lp.wide}>
      <div className={lp.impactPanel}>
        <h2 id="impact-title" className={lp.impactTitle} aria-label="研究の先に、待っている患者さんがいる。"><span>研究の先に、</span><span>待っている患者さんがいる。</span></h2>
        <ol className={lp.path} aria-label="研究から患者さんまで">
          {PATH.map(([verb, object]) => <li key={verb}><span>{object}</span><b>{verb}</b></li>)}
        </ol>
      </div>
    </div>
  </section>;
}
