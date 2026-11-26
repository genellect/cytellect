"use client";
import styles from "./intake.module.css";

/** Schematic samples, not data: a nuclear stain, another stain of the same field, and an outline mask. */
function Sample({kind}: {kind: "nuclei" | "actin" | "mask"}) {
  const nuclei = [[22, 24, 7], [44, 18, 6], [58, 40, 8], [30, 50, 7], [14, 46, 5], [48, 60, 6]];
  return <svg viewBox="0 0 72 72" aria-hidden="true" className={styles.sample} data-kind={kind}>
    <rect width="72" height="72" fill={kind === "mask" ? "#0e1726" : "#05070b"}/>
    {kind === "nuclei" && nuclei.map(([x, y, r]) => <circle key={`${x}-${y}`} cx={x} cy={y} r={r} fill="#6ea8ff" opacity=".9"/>)}
    {kind === "actin" && nuclei.map(([x, y, r]) => <circle key={`${x}-${y}`} cx={x} cy={y} r={r + 5} fill="none" stroke="#7ce3a0" strokeWidth="2.4" opacity=".85"/>)}
    {kind === "mask" && nuclei.map(([x, y, r]) => <circle key={`${x}-${y}`} cx={x} cy={y} r={r} fill="none" stroke="#e8edf4" strokeWidth="1.4"/>)}
  </svg>;
}

interface Props {disabled: boolean; onFiles: () => void; onFolder: () => void; onExperiment: () => void; onMeasured: () => void}

/**
 * The empty workspace (#284 W5, Issue input 1 and 優先 1–2): the image stage itself is where images are added. It
 * names what to choose before the picker opens: the measured fluorescence images (each stain of a field is its own
 * file) and, separately, an outline mask, which is a mask candidate and not an image to measure.
 */
export function EmptyStart({disabled, onFiles, onFolder, onExperiment, onMeasured}: Props) {
  return <section className={styles.start} aria-labelledby="empty-start-heading">
    <h1 id="empty-start-heading">画像を追加</h1>
    <div className={styles.startActions}>
      <button type="button" className={styles.primary} disabled={disabled} onClick={onFiles}>画像を選択</button>
      <button type="button" disabled={disabled} onClick={onFolder}>フォルダーを選択</button>
    </div>
    <p className={styles.drop}>ここにドロップ · TIFF・OME-TIFF · 8/16-bit · 2D</p>
    <ul className={styles.samples} aria-label="選ぶ画像の見本">
      <li><Sample kind="nuclei"/><span><strong>測る蛍光画像</strong>例：BBBC007-a9-C01（DNA）</span></li>
      <li><Sample kind="actin"/><span><strong>同じ視野の別の染色</strong>例：BBBC007-a9-C02（アクチン）</span></li>
      <li><Sample kind="mask"/><span><strong>輪郭のマスク</strong>マスクの候補 · 測定の対象外</span></li>
    </ul>
    <p className={styles.alternatives}>
      <button type="button" className={styles.link} onClick={onExperiment}>実験デザインから開始</button>
      <button type="button" className={styles.link} onClick={onMeasured}>測定済みデータを使用</button>
    </p>
  </section>;
}
