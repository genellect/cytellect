"use client";

import {useEffect, useMemo, useRef, useState} from "react";
import {download, errorCodeMessage, fetchBlob} from "@/lib/api";
import {descriptiveFigureView} from "@/lib/descriptive-view";
import {figureIdentity, type ApiAdapter, type FigureChoice, type SavedFigure, type SavedResult} from "@/lib/workspace/api-adapter";
import styles from "./analysis-workspace.module.css";

type Props = {adapter: ApiAdapter; workspace: string; result: SavedResult; options: Array<{key: string; label: string}>; disabled?: boolean};

/** Preview the saved vector artifact itself; browser rendering never recalculates graph coordinates. */
export function WorkspaceFigureEditor({adapter, workspace, result, options, disabled = false}: Props) {
  const [metric, setMetric] = useState("area_px");
  const [width, setWidth] = useState(178);
  const [height, setHeight] = useState(100);
  const [label, setLabel] = useState("");
  const [xLabel, setXLabel] = useState("");
  const [fontSize, setFontSize] = useState(7);
  const [language, setLanguage] = useState<"ja" | "en">("en");
  const [yMin, setYMin] = useState("");
  const [yMax, setYMax] = useState("");
  const [yTickStep, setYTickStep] = useState("");
  const [pointSize, setPointSize] = useState("");
  const [saved, setSaved] = useState<SavedFigure | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const lock = useRef(false);
  const [channel, metricName] = metric.includes(":") ? metric.split(":") : [null, metric];
  const optionalNumber = (value: string) => value === "" ? null : Number(value);
  const choice: FigureChoice = useMemo(() => ({channel, metric: metricName, width, height, label, xLabel, fontSize, language, yMin: optionalNumber(yMin), yMax: optionalNumber(yMax), yTickStep: optionalNumber(yTickStep), pointSize: optionalNumber(pointSize)}),
    [channel, metricName, width, height, label, xLabel, fontSize, language, yMin, yMax, yTickStep, pointSize]);
  const current = saved && figureIdentity(saved.revision, saved.choice) === figureIdentity(result.revision, choice) ? saved : null;
  const axisValid = [choice.yMin, choice.yMax, choice.yTickStep, choice.pointSize].every(value => value == null || Number.isFinite(value)) &&
    [choice.yMin, choice.yMax].every(value => value == null || Math.abs(value) <= 1e15) &&
    (choice.yMin == null || choice.yMax == null || choice.yMin < choice.yMax) &&
    (choice.yTickStep == null || choice.yTickStep > 0 && choice.yTickStep <= 1e15 &&
      (choice.yMin == null || choice.yMax == null || (choice.yMax - choice.yMin) / choice.yTickStep <= 99)) &&
    (choice.pointSize == null || choice.pointSize > 0 && choice.pointSize <= 400);
  const valid = axisValid && [width, height, fontSize].every(Number.isFinite) && width >= 76.2 && width <= 406.4 && height >= 25.4 && height <= 406.4 && fontSize >= 5 && fontSize <= 24 && options.some(option => option.key === metric);
  const view = current ? descriptiveFigureView(current.result) : null;
  const pages = view?.kind === "ready" || view?.kind === "legacy" ? view.pages : [];
  async function generate() {
    if (lock.current || disabled || !valid) return;
    lock.current = true; setBusy(true); setError("");
    try {setSaved(await adapter.figure(workspace, result, choice));}
    catch (cause) {setError(errorCodeMessage(cause instanceof Error ? cause.message : "図を作成できませんでした。"));}
    finally {lock.current = false; setBusy(false);}
  }
  async function save() {
    if (!current || !pages.length || lock.current) return;
    lock.current = true; setBusy(true); setError("");
    try {await download(`/v1/jobs/${current.job}/files/figure.zip`, "Cytellect-figure.zip");}
    catch (cause) {setError(errorCodeMessage(cause instanceof Error ? cause.message : "図を作成できませんでした。"));}
    finally {lock.current = false; setBusy(false);}
  }
  return <section className={styles.panelSection} aria-label="グラフ編集">
    <h3>グラフ</h3>
    <label>測定項目<select value={metric} disabled={busy} onChange={event => setMetric(event.target.value)}>{options.map(option => <option key={option.key} value={option.key}>{option.label}</option>)}</select></label>
    <label>横軸ラベル<input value={xLabel} maxLength={120} onChange={event => setXLabel(event.target.value)} placeholder="空欄で自動"/></label>
    <label>縦軸ラベル<input value={label} maxLength={120} onChange={event => setLabel(event.target.value)} placeholder="空欄で測定項目と単位を表示"/></label>
    <div style={{display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 12}}>
      <label>幅 (mm)<input type="number" min={76.2} max={406.4} step={1} value={width} onChange={event => setWidth(Number(event.target.value))}/></label>
      <label>高さ (mm)<input type="number" min={25.4} max={406.4} step={1} value={height} onChange={event => setHeight(Number(event.target.value))}/></label>
      <label>文字サイズ (pt)<input type="number" min={5} max={24} step={0.5} value={fontSize} onChange={event => setFontSize(Number(event.target.value))}/></label>
      <label>図中の言語<select value={language} onChange={event => setLanguage(event.target.value as "ja" | "en")}><option value="en">English</option><option value="ja">日本語</option></select></label>
    </div>
    <details><summary>縦軸・点の表示</summary>
      <p>空欄の項目は自動で設定します。</p>
      <label>縦軸の最小値<input type="number" value={yMin} onChange={event => setYMin(event.target.value)} placeholder="自動"/></label>
      <label>縦軸の最大値<input type="number" value={yMax} onChange={event => setYMax(event.target.value)} placeholder="自動"/></label>
      <label>目盛の間隔<input type="number" min={0} value={yTickStep} onChange={event => setYTickStep(event.target.value)} placeholder="自動"/></label>
      <label>点の面積 (pt²)<input type="number" min={0.1} max={400} value={pointSize} onChange={event => setPointSize(event.target.value)} placeholder="自動"/></label>
    </details>
    <div className={styles.actions}><button className={styles.primary} disabled={busy || disabled || !valid} onClick={() => void generate()}>{busy ? "処理中…" : current ? "図を更新" : "図を作成"}</button><button className={styles.secondary} disabled={busy || disabled || !pages.length} onClick={() => void save()}>図を保存</button></div>
    {!valid && <p role="alert">寸法・文字サイズ・軸の範囲を確認してください。目盛は100個以内に設定します。</p>}
    {error && <p role="alert">{error}</p>}
    {saved && !current && <p>設定を変更しました。「図を作成」で反映します。</p>}
    {pages.map(page => <SavedVectorPreview key={`${current!.job}:${page.files.svg}`} path={`/v1/jobs/${current!.job}/files/${page.files.svg}`}/>)}
    {pages.length > 0 && <p>表示中の図と同じSVG・PDF、測定値、作図条件をZIPで保存します。</p>}
    {view?.kind === "tables_only" && <p role="alert">この設定では図を作成できません。寸法や文字サイズを調整してください。</p>}
  </section>;
}

function SavedVectorPreview({path}: {path: string}) {
  const [image, setImage] = useState<{path: string; url: string} | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    let url: string | undefined;
    void fetchBlob(path, controller.signal).then(blob => {
      if (controller.signal.aborted) return;
      url = URL.createObjectURL(blob); setImage({path, url});
    }).catch(() => {if (!controller.signal.aborted) setFailed(true);});
    return () => {controller.abort(); if (url) URL.revokeObjectURL(url);};
  }, [path]);
  if (failed) return <p role="alert">図を表示できません。図を更新してください。</p>;
  if (image?.path !== path) return <p role="status">図を読み込んでいます。</p>;
  // Private blob URL; no remote image optimizer or public cache.
  return <img src={image.url} alt="保存するグラフ" style={{display: "block", width: "100%", height: "auto", background: "white"}}/>;
}
