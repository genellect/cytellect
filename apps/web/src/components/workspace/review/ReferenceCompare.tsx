"use client";
import type {ShowcaseReference} from "@/lib/showcase";
import styles from "./reference-compare.module.css";

const perField = (value: number) => value.toLocaleString("ja-JP", {maximumFractionDigits: 1});
const percent = (value: number) => `${(value * 100).toLocaleString("ja-JP", {maximumFractionDigits: 0})}%`;
const area = (value: number | null) => value === null ? "—" : `${Math.round(value).toLocaleString("ja-JP")} px²`;

/** Objects only the demo adopted are much smaller than the matched nuclei (under a quarter of their median area). */
const small = (group: ShowcaseReference["groups"][number]) => group.labelsOnlyMedianAreaPx !== null && group.matchedMedianAreaPx !== null && group.labelsOnlyMedianAreaPx < group.matchedMedianAreaPx / 4;

const TONES = [
  ["both", "一致した核"],
  ["split", "CellProfiler が分けた核"],
  ["reference_only", "CellProfiler だけが数えた対象"],
  ["labels_only", "Cytellect だけが採用した核"],
] as const;

/** Another method's published objects for the same images, beside the demo's adopted nuclei
 * (display only: the numbers come from the demo build and are never measured or tested here). */
export function ReferenceCompare({reference, fieldIds}: {reference: ShowcaseReference; fieldIds: string[]}) {
  const [control, treatment] = reference.groups;
  const shown = fieldIds.flatMap(id => reference.fields[id] ? [{id, value: reference.fields[id]}] : []);
  return <section className={styles.panel} aria-label={`${reference.label}との比較`}>
    <ul className={styles.legend}>{TONES.map(([tone, label]) => <li key={tone}><span className={styles.swatch} data-tone={tone} aria-hidden="true"/>{label}</li>)}</ul>
    {control && treatment && reference.ratio && <>
      <p className={styles.headline}>{treatment.label} の視野あたりの核数は、{control.label} の <strong>{percent(reference.ratio.cytellect)}</strong>（Cytellect）と <strong>{percent(reference.ratio.cellprofiler)}</strong>（CellProfiler）。</p>
    </>}
    <details className={styles.details}><summary>違いの内訳と表</summary>
      {control && treatment && <>
      <p>違いは、片方の方法だけが数えた対象から生まれています（{treatment.label}、視野あたり）。</p>
      <ul className={styles.reasons}>
        <li><span className={styles.swatch} data-tone="reference_only" aria-hidden="true"/>CellProfiler だけ：{perField(treatment.referenceOnly)} 個（{control.label} では {perField(control.referenceOnly)} 個）。{treatment.referenceOnlyWithoutSignal !== null && <>そのうち {percent(treatment.referenceOnlyWithoutSignal)} は、中心の核染色（3 × 3 画素の平均）が視野全体の中央値の 1.2 倍未満でした（{control.label} では {control.referenceOnlyWithoutSignal === null ? "—" : percent(control.referenceOnlyWithoutSignal)}。この表示のための探索的な目安で、核でないと確かめたものではありません）。</>}</li>
        <li><span className={styles.swatch} data-tone="labels_only" aria-hidden="true"/>Cytellect だけ：{perField(treatment.labelsOnly)} 個。面積の中央値は {area(treatment.labelsOnlyMedianAreaPx)}（両方が数えた核は {area(treatment.matchedMedianAreaPx)}）{small(treatment) ? "で、小核や核の断片ほどの大きさです。" : "。"}</li>
        {treatment.both !== null && control.both !== null && <li><span className={styles.swatch} data-tone="both" aria-hidden="true"/>両方が数えた核：{perField(treatment.both)} 個（{control.label} では {perField(control.both)} 個）。</li>}
      </ul>
      </>}
    {reference.groups.length > 0 && <div className={styles.tableWrap}><table className={styles.table}>
      <caption>視野あたりの平均（画像の端にかかる核は両方とも数えない）</caption>
      <thead><tr><th scope="col">群</th><th scope="col">視野</th><th scope="col">Cytellect</th><th scope="col">CellProfiler</th><th scope="col">両方</th><th scope="col">CellProfiler だけ</th><th scope="col">CellProfiler が分けた</th><th scope="col">Cytellect だけ</th><th scope="col">一致の割合</th></tr></thead>
      <tbody>{reference.groups.map(group => <tr key={group.id}><th scope="row">{group.label}</th><td>{group.fields}</td><td>{perField(group.cytellect)}</td><td>{perField(group.cellprofiler)}</td>
        <td>{group.both === null ? "—" : perField(group.both)}</td><td>{perField(group.referenceOnly)}</td><td>{perField(group.split)}</td><td>{perField(group.labelsOnly)}</td><td>{group.matchedFraction === null ? "—" : percent(group.matchedFraction)}</td></tr>)}</tbody>
    </table></div>}
    {reference.runs.some(run => run.ratio) && <p className={styles.runs}>実験回ごとの比（{treatment?.label ?? "処理"} ÷ {control?.label ?? "対照"}）：{reference.runs.filter(run => run.ratio).map(run =>
      `${run.label} ${percent(run.ratio!.cytellect)}／${percent(run.ratio!.cellprofiler)}`).join("、")}（Cytellect／CellProfiler）</p>}
    {shown.map(({id, value}) => <p key={id} className={styles.field}>この視野：Cytellect {value.labelsInterior ?? "—"} 個・CellProfiler {value.countNuclei ?? "—"} 個（一致 {value.both}・分けた {value.split}・CellProfiler だけ {value.referenceOnly}・Cytellect だけ {value.labelsOnly}）</p>)}
    <p className={styles.note}>画像の円で、それぞれの対象を確かめてください。どちらの方法の数え方が研究の目的に合うか（小核を核に数えるか、など）は研究者が決めます。小さな対象が小核や核の断片かどうかは、このデモでは確定していません。照合は中心の位置だけで行い、輪郭の一致や正解の判定ではありません。表示だけに使います（測定と統計には使いません）。</p>
    </details>
  </section>;
}
