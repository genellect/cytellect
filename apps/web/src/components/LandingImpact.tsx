import lp from "./optical-landing.module.css";

/** The future research can lead to, ending with the patients it is for. Each step is shown, not drawn. */
const PATH: { lines: string[]; src: string; alt: string; width: number; height: number }[] = [
  { lines: ["病気のしくみを", "解き明かす"], src: "/marketing/lp-field.webp", alt: "公開の蛍光画像。青い核と桃色の核小体を、Cytellectが検出した輪郭が囲んでいる", width: 1536, height: 864 },
  { lines: ["新しい薬の可能性を", "見つける"], src: "/marketing/lp-impact-discovery.webp", alt: "桃色の培地が入った6穴プレートに、ピペットで分注する", width: 960, height: 640 },
  { lines: ["患者へ届ける"], src: "/marketing/lp-impact-patient.webp", alt: "ベッドに横たわる人の手を、もう一人の手が握る", width: 1800, height: 1200 },
];

export function LandingImpact() {
  return <section id="impact" className={lp.impact} aria-labelledby="impact-title">
    <div className={lp.wide}>
      <div className={lp.impactPanel}>
        <h2 id="impact-title" className={lp.impactTitle} aria-label="研究の先に、待っている患者さんがいる。"><span>研究の先に、</span><span><span>待っている</span><span>患者さんがいる。</span></span></h2>
        <ol className={lp.path} aria-label="研究から患者さんまで">
          {PATH.map(({ lines, src, alt, width, height }) => <li key={lines[0]}>
            <img src={src} alt={alt} width={width} height={height} loading="lazy" />
            <b>{lines.map(line => <span key={line}>{line}</span>)}</b>
          </li>)}
        </ol>
      </div>
    </div>
  </section>;
}
