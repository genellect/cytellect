"use client";

import { useEffect, useState } from "react";
import styles from "./landing.module.css";

type Measurement = { nucleus_id: number; area_px: number; ncl_nucleus_mean_raw: number };
type PublicSample = {
  width: number; height: number;
  labels: { id: number; points: number[][] }[];
  measurements: Measurement[];
};

// These are the saved Fiji/analysis results already served by the public viewer.
// The browser only maps recorded values to plot coordinates; it measures no pixels.
export default function LinkedImageFigure() {
  const [sample, setSample] = useState<PublicSample | null>(null);
  const [selected, setSelected] = useState(1);
  const [outlines, setOutlines] = useState(true);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    fetch("/demo/4dn-ncl/data.json", { signal: controller.signal })
      .then(response => { if (!response.ok) throw new Error(); return response.json(); })
      .then((data: PublicSample) => setSample(data))
      .catch(() => { if (!controller.signal.aborted) setFailed(true); });
    return () => controller.abort();
  }, []);
  const row = sample?.measurements.find(value => value.nucleus_id === selected);
  const xMaximum = sample ? Math.ceil(Math.max(...sample.measurements.map(value => value.area_px)) / 1000) * 1000 : 4000;
  const yMaximum = sample ? Math.ceil(Math.max(...sample.measurements.map(value => value.ncl_nucleus_mean_raw)) / 1000) * 1000 : 4000;
  const x = (value: number) => 48 + value / xMaximum * 216;
  const y = (value: number) => 214 - value / yMaximum * 174;
  return <figure className={styles.visual} aria-labelledby="linked-figure-title">
    <div className={styles.visualHeading}><span id="linked-figure-title">同じ領域を、画像と数値で。</span><span className={styles.publicBadge}>公開実画像</span></div>
    <div className={styles.visualPanels}>
      <div className={styles.imagePanel}>
        <div className={styles.panelHeading}><span>01 / 検出領域</span><label><input type="checkbox" checked={outlines} onChange={event => setOutlines(event.target.checked)} />輪郭</label></div>
        <div className={styles.imageFrame}>
          <img src="/demo/4dn-ncl/demo-preview.png" width={1739} height={1536} alt="4DN公開蛍光画像の領域と測定値の対応例" fetchPriority="high" />
          {sample && <svg viewBox={`0 0 ${sample.width} ${sample.height}`} aria-label="公開画像の検出領域">{sample.labels.map((label, index) => <polygon key={`${label.id}-${index}`} points={label.points.map(point => point.join(",")).join(" ")} fill={label.id === selected ? "#c8ee7633" : "transparent"} stroke={outlines ? label.id === selected ? "#d8f28c" : "#dae6e17a" : "none"} strokeWidth={label.id === selected ? 5 : 1.8} role="button" tabIndex={-1} aria-label={`画像の領域 ${label.id}`} onClick={() => setSelected(label.id)} onKeyDown={event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); setSelected(label.id); } }} />)}</svg>}
        </div>
        <p className={styles.channelCaption}><span className={styles.channelBlue} />DAPI <span className={styles.channelRed} />NCL <span>4DN / Fowler Lab</span></p>
      </div>
      <div className={styles.plotPanel}>
        <div className={styles.panelHeading}><span>02 / 領域ごとの測定値</span></div>
        <svg viewBox="0 0 288 254" className={styles.plot} aria-label="核面積とNCL平均輝度の散布図。点を選ぶと同じ領域を画像に表示します。">
          {[0, 1, 2].map(tick => <g key={tick}><line x1={48} x2={264} y1={y(tick * yMaximum / 2)} y2={y(tick * yMaximum / 2)} stroke="#e3e8e5" /><text x={40} y={y(tick * yMaximum / 2) + 4} textAnchor="end">{tick * yMaximum / 2}</text><text x={x(tick * xMaximum / 2)} y={232} textAnchor="middle">{tick * xMaximum / 2}</text></g>)}
          <text x={48} y={18} className={styles.axisTitle}>NCL 平均輝度（原値）</text>
          <path d="M48 40 V214 H264" fill="none" stroke="#98aaa3" />
          <text x={156} y={251} textAnchor="middle" className={styles.axisTitle}>核面積（px²）</text>
          {sample?.measurements.map(value => <circle key={value.nucleus_id} cx={x(value.area_px)} cy={y(value.ncl_nucleus_mean_raw)} r={value.nucleus_id === selected ? 5.5 : 3} className={value.nucleus_id === selected ? styles.selectedPoint : styles.point} role="button" tabIndex={-1} aria-label={`図の領域 ${value.nucleus_id}`} onClick={() => setSelected(value.nucleus_id)} onKeyDown={event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); setSelected(value.nucleus_id); } }}><title>{`領域 ${value.nucleus_id} · ${value.area_px} px² · 平均輝度 ${value.ncl_nucleus_mean_raw.toFixed(1)}`}</title></circle>)}
        </svg>
        <div className={styles.selection} aria-live="polite" aria-atomic="true">
          <label>選択領域<select aria-label="表示する領域" value={selected} disabled={!sample} onChange={event => setSelected(Number(event.target.value))}>{sample?.measurements.map(value => <option key={value.nucleus_id} value={value.nucleus_id}>{String(value.nucleus_id).padStart(2, "0")}</option>)}</select></label>
          <span>{row ? `${row.area_px.toLocaleString("ja-JP")} px²` : "—"}<small>面積</small></span>
          <span>{row ? row.ncl_nucleus_mean_raw.toFixed(1) : "—"}<small>平均輝度</small></span>
        </div>
      </div>
    </div>
    <div className={styles.visualHint}>{failed ? <span role="alert">測定値を読み込めませんでした。公開サンプルからご確認ください。</span> : <><span className={styles.linkMark} aria-hidden="true">↔</span><span>画像の領域や図の点を選ぶと、同じ測定対象を確認できます。</span></>}</div>
    <figcaption className={styles.sourceNote}>
      <a href="https://data.4dnucleome.org/files-microscopy/4DNFI7FAWT6C/" target="_blank" rel="noreferrer">出典：4DN / Fowler Lab, UW ↗</a><span>1視野・100核の解析済みデータ。背景補正・群間比較なし。</span>
      <details><summary>この表示の条件</summary><p>16-bit原画像とFijiによる検出結果を用いた記述的な図です。点は独立した実験の反復ではありません。検出精度の保証や生物学的結論を示すものではありません。</p><p>チャンネル順の原記載に不一致があるため、OME名と画像形態に基づく暫定対応です。提供元による確認済みとはしていません。<a href="https://registry.opendata.aws/4dnucleome/" target="_blank" rel="noreferrer">4DN公開データの利用条件 ↗</a></p><a href="/demo/4dn-ncl/data.json" download="cytellect-4dn-source-data.json">図の元データを保存 ↓</a></details>
    </figcaption>
  </figure>;
}
