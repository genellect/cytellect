"use client";
import styles from "./intake.module.css";

/**
 * The three kinds of file a researcher may hold, shown on one field: the same 300 × 300 px region of BBBC007v1 A9
 * (CC0 1.0) as its DNA image, its actin image and its nuclei as a mask (the hand-drawn outlines, filled). The third is
 * drawn as the intake list draws a mask candidate (labelled pixels in white), and its caption is the list's own state
 * for such a file: only a 32-bit integer label image is one (8- and 16-bit masks are images). Display pictures for
 * this screen only (apps/web/public/samples/NOTICE.json); nothing is measured from them.
 */
const SAMPLES = [
  {file: "bbbc007-a9-dna", title: "測る蛍光画像", note: "例：a9-C01.tif · DNA"},
  {file: "bbbc007-a9-actin", title: "同じ視野の別の染色", note: "例：a9-C02.tif · アクチン"},
  {file: "bbbc007-a9-mask", title: "核のマスク", note: "マスクの候補 · 32-bit 整数ラベル"},
] as const;

interface Props {disabled: boolean; onFiles: () => void; onFolder: () => void; onExperiment: () => void; onMeasured: () => void}

/**
 * The empty workspace (#284 W5, Issue input 1 and 優先 1–2): images are added from here. It names what to choose
 * before the picker opens: the measured fluorescence images (each stain of a field is its own file) and, separately,
 * a mask, which is a mask candidate and not an image to measure. The screen is a start, so it is drawn on
 * the workspace's own surface and never as an empty image stage.
 */
export function EmptyStart({disabled, onFiles, onFolder, onExperiment, onMeasured}: Props) {
  return <section className={styles.start} aria-labelledby="empty-start-heading">
    <div className={styles.startPanel}>
      <h1 id="empty-start-heading">画像を追加</h1>
      <div className={styles.startActions}>
        <button type="button" className={styles.primary} disabled={disabled} onClick={onFiles}>画像を選択</button>
        <button type="button" disabled={disabled} onClick={onFolder}>フォルダーを選択</button>
      </div>
      <p className={styles.drop}>ここにドロップ · TIFF・OME-TIFF · 8/16-bit · 2D</p>
      <ul className={styles.samples} aria-label="選ぶ画像の見本">
        {SAMPLES.map(sample => <li key={sample.file}>
          {/* The caption beside each picture says what it is; the picture itself adds no text. */}
          <img src={`/samples/${sample.file}.webp`} width={264} height={264} alt="" decoding="async"/>
          <span><strong>{sample.title}</strong>{sample.note}</span>
        </li>)}
      </ul>
      <p className={styles.sampleSource}>見本：BBBC007v1 A9 · CC0 1.0</p>
      <p className={styles.alternatives}>
        <button type="button" className={styles.link} onClick={onExperiment}>実験デザインから開始</button>
        <button type="button" className={styles.link} onClick={onMeasured}>測定済みデータを使用</button>
      </p>
    </div>
  </section>;
}
