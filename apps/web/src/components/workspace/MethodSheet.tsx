"use client";
import styles from "./analysis-workspace.module.css";

type Reference = {label: string; url: string};
export type MethodDetail = {id: string; title: string; summary: string; settings: Array<[string, string]>; references: Reference[]; limits: string[]};

const ref = {
  stardist: {label: "Schmidt U et al. Cell detection with star-convex polygons. MICCAI 2018", url: "https://doi.org/10.1007/978-3-030-00934-2_30"},
  kodiha: {label: "Kodiha M et al. Quantitative analysis of nucleolar proteins. BMC Cell Biol 2011", url: "https://doi.org/10.1186/1471-2121-12-25"},
  potapova: {label: "Potapova TA et al. Nucleolar normality score. eLife 2023", url: "https://doi.org/10.7554/eLife.88799"},
  white: {label: "White MR et al. C9orf72 poly(PR) and NPM1 nucleolar mislocalisation. Mol Cell 2019", url: "https://doi.org/10.1016/j.molcel.2019.03.019"},
  lord: {label: "Lord SJ et al. SuperPlots. J Cell Biol 2020", url: "https://doi.org/10.1083/jcb.202001064"},
  aarts: {label: "Aarts E et al. Nested data in neuroscience. Nat Neurosci 2014", url: "https://doi.org/10.1038/nn.3648"},
} satisfies Record<string, Reference>;
export const methodReferences = ref;

/** Method details are reachable from each step; they never clutter the main screen. */
export function MethodSheet({details, onClose}: {details: MethodDetail[]; onClose: () => void}) {
  return <aside className={styles.methodSheet} role="dialog" aria-modal="false" aria-label="手法の詳細と文献">
    <div style={{display: "flex", justifyContent: "space-between", alignItems: "center"}}><h2>手法の詳細と文献</h2><button type="button" className={styles.secondary} onClick={onClose}>閉じる</button></div>
    {details.map(detail => <section key={detail.id}>
      <h3>{detail.title}</h3>
      <p>{detail.summary}</p>
      {detail.settings.length > 0 && <dl>{detail.settings.map(([key, value]) => <div key={key}><dt style={{display: "inline", color: "#4b5563"}}>{key}：</dt><dd style={{display: "inline", margin: 0}}>{value}</dd></div>)}</dl>}
      {detail.references.length > 0 && <ul>{detail.references.map(item => <li key={item.url}><a href={item.url} target="_blank" rel="noreferrer">{item.label}</a></li>)}</ul>}
      {detail.limits.map(text => <p key={text} style={{color: "#4b5563"}}>限界：{text}</p>)}
    </section>)}
  </aside>;
}
