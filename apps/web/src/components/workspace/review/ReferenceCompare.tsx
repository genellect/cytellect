"use client";
import type {ShowcaseReference} from "@/lib/showcase";
import styles from "./reference-compare.module.css";

const perField = (value: number) => value.toLocaleString("ja-JP", {maximumFractionDigits: 1});
const percent = (value: number) => `${(value * 100).toLocaleString("ja-JP", {maximumFractionDigits: 0})}%`;
const area = (value: number | null) => value === null ? "—" : `${Math.round(value).toLocaleString("ja-JP")} px²`;

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
    {control && treatment && reference.ratio && <p className={styles.headline}>
      {treatment.label} の視野あたりの核数は {control.label} の <strong>{percent(reference.ratio.cytellect)}</strong>（Cytellect）、<strong>{percent(reference.ratio.cellprofiler)}</strong>（CellProfiler）。
      {treatment.referenceOnly > control.referenceOnly && <> CellProfiler は {treatment.label} で、Cytellect が核として採用しなかった対象を視野あたり {perField(treatment.referenceOnly)} 個数えています（面積の中央値 {area(treatment.referenceOnlyMedianAreaPx)}、一致した核は {area(treatment.matchedMedianAreaPx)}）。</>}
    </p>}
    {reference.groups.length > 0 && <div className={styles.tableWrap}><table className={styles.table}>
      <caption>視野あたりの平均（画像の端にかかる核は両方とも数えない）</caption>
      <thead><tr><th scope="col">群</th><th scope="col">視野</th><th scope="col">Cytellect</th><th scope="col">CellProfiler</th><th scope="col">CellProfiler だけ</th><th scope="col">CellProfiler が分けた</th><th scope="col">Cytellect だけ</th><th scope="col">一致の割合</th></tr></thead>
      <tbody>{reference.groups.map(group => <tr key={group.id}><th scope="row">{group.label}</th><td>{group.fields}</td><td>{perField(group.cytellect)}</td><td>{perField(group.cellprofiler)}</td>
        <td>{perField(group.referenceOnly)}</td><td>{perField(group.split)}</td><td>{perField(group.labelsOnly)}</td><td>{group.matchedFraction === null ? "—" : percent(group.matchedFraction)}</td></tr>)}</tbody>
    </table></div>}
    {reference.runs.some(run => run.ratio) && <p className={styles.runs}>実験回ごとの比（{treatment?.label ?? "処理"} ÷ {control?.label ?? "対照"}）：{reference.runs.filter(run => run.ratio).map(run =>
      `${run.label} ${percent(run.ratio!.cytellect)}／${percent(run.ratio!.cellprofiler)}`).join("、")}（Cytellect／CellProfiler）</p>}
    {shown.map(({id, value}) => <p key={id} className={styles.field}>この視野：Cytellect {value.labelsInterior ?? "—"} 個・CellProfiler {value.countNuclei ?? "—"} 個（一致 {value.both}・分けた {value.split}・CellProfiler だけ {value.referenceOnly}・Cytellect だけ {value.labelsOnly}）</p>)}
    <p className={styles.note}>桃色の円が、CellProfiler だけが数えた対象です。画像で形を確かめてください。小さな対象が核の断片や小核かどうかは、このデモでは確定していません。照合は核の中心の位置で行い、表示だけに使います（測定と統計には使いません）。</p>
  </section>;
}
