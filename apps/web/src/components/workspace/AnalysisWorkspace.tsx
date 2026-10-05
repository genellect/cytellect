"use client";
import { useCallback, useEffect, useMemo, useReducer, useRef, useState, type DragEvent, type RefObject } from "react";
import { fieldDistribution, type WorkspaceAdapter } from "@/lib/workspace/adapter";
import { groupFiles, isSupportedImage, type AddedFile } from "@/lib/workspace/grouping";
import { initialState, phase, progress, reducer, regionState, type Selection } from "@/lib/workspace/model";
import { FieldFigure } from "./FieldFigure";
import { FieldImage } from "./FieldImage";
import { NuclearChoice, ProposalSummary, channelText } from "./ProposalPanels";
import styles from "./analysis-workspace.module.css";

const STATUS_LABEL = { waiting: "待機", running: "解析中", done: "完了", failed: "要確認" } as const;

function toAdded(list: FileList | File[]): { files: AddedFile[]; skipped: number } {
  const files: AddedFile[] = [];
  let skipped = 0;
  for (const file of Array.from(list)) {
    const path = (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name;
    if (isSupportedImage(path)) files.push({ path, size: file.size }); else skipped += 1;
  }
  return { files, skipped };
}

export default function AnalysisWorkspace({ adapter }: { adapter: WorkspaceAdapter }) {
  const [state, dispatch] = useReducer(reducer, undefined, initialState);
  const [added, setAdded] = useState<AddedFile[]>([]);
  const [notice, setNotice] = useState("");
  const [source, setSource] = useState("");
  const [channel, setChannel] = useState<string | null>(null);
  const [drawer, setDrawer] = useState(false);
  const [panel, setPanel] = useState(true);
  const fileInput = useRef<HTMLInputElement>(null);
  const folderInput = useRef<HTMLInputElement>(null);
  const running = useRef(false);
  const current = phase(state);
  const counts = progress(state);
  const grouping = state.grouping;
  const fields = useMemo(() => grouping?.fields.map((field) => field.key) ?? [], [grouping]);

  useEffect(() => {
    folderInput.current?.setAttribute("webkitdirectory", "");
    // Tablet and phone: the operation panel starts folded so the image stays large.
    if (window.innerWidth < 1100) setPanel(false);
  }, []);

  const addFiles = useCallback((files: AddedFile[], name: string, skipped = 0) => {
    if (state.adopted) return;
    const all = [...added, ...files];
    setAdded(all);
    dispatch({ type: "imported", name: state.name || name, grouping: groupFiles(all) });
    setNotice(skipped ? `${skipped} 件はTIFF以外のため追加しませんでした。` : "");
  }, [added, state.adopted, state.name]);

  const loadSample = async () => {
    try {
      const sample = await adapter.loadSample();
      setAdded(sample.files);
      dispatch({ type: "imported", name: sample.name, grouping: groupFiles(sample.files) });
      setNotice("");
      setSource(sample.attribution);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "公開画像を読み込めませんでした。");
    }
  };

  // Concurrency 1: run the next waiting field; every field commits independently.
  useEffect(() => {
    if (running.current || state.stopped) return;
    const next = Object.entries(state.runs).find(([, run]) => run.status === "waiting")?.[0];
    if (!next) return;
    running.current = true;
    dispatch({ type: "field-started", field: next });
    adapter.run(next)
      .then((result) => dispatch({ type: "field-done", field: next, result }))
      .catch((error: unknown) => dispatch({ type: "field-failed", field: next, error: error instanceof Error ? error.message : "解析できませんでした。" }))
      .finally(() => { running.current = false; });
  }, [adapter, state.runs, state.stopped]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (!(event.ctrlKey || event.metaKey) || (event.target as HTMLElement)?.closest("input, textarea, select")) return;
      if (event.key.toLowerCase() === "z") { event.preventDefault(); dispatch({ type: event.shiftKey ? "redo" : "undo" }); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const onDrop = (event: DragEvent) => {
    event.preventDefault();
    const { files, skipped } = toAdded(event.dataTransfer.files);
    if (files.length) addFiles(files, "新しいワークスペース", skipped);
    else setNotice("TIFF画像が見つかりませんでした。");
  };

  const select = (selection: Selection | null) => dispatch({ type: "select", selection });
  const selection = state.selection;
  const selectedField = selection?.field ?? fields[0];
  const proposal = state.adopted?.proposal ?? state.proposal;
  const metrics = proposal?.metrics ?? [];
  const metric = metrics.find((item) => item.key === state.figure.metric) ?? metrics[0];
  const labels = Object.fromEntries(fields.map((field) => [field, adapter.label(field)]));
  const distribution = useMemo(() => metric ? fieldDistribution(state, metric.key) : { points: [], summaries: [] }, [state, metric]);
  const displayChannel = channel ?? proposal?.nuclearChannel?.token ?? grouping?.channels[0]?.token ?? "";
  const result = selectedField ? state.results[selectedField] : undefined;
  const selectedRegion = selection?.region;
  const figures = state.adopted ? metrics : [];

  if (current === "empty") {
    return (
      <main className={styles.shell}>
        <header className={styles.header}><span className={styles.brand}>cytellect</span></header>
        <section className={styles.empty} onDragOver={(event) => event.preventDefault()} onDrop={onDrop} aria-labelledby="empty-title">
          <h1 id="empty-title">画像を追加</h1>
          <p>TIFF・OME-TIFFのファイル、またはフォルダをここにドロップします。視野とチャンネルは自動で整理します。</p>
          <div className={styles.actions}>
            <button type="button" className={styles.primary} onClick={() => fileInput.current?.click()}>画像を追加</button>
            <button type="button" className={styles.secondary} onClick={() => folderInput.current?.click()}>フォルダを追加</button>
            <button type="button" className={styles.link} onClick={loadSample}>公開画像で試す</button>
          </div>
          <label className={styles.goal}>解析の目的（任意）
            <textarea value={state.goal} rows={2} placeholder="例: GFP陽性の細胞で、核小体と核質のNCL輝度を比較したい"
              onChange={(event) => dispatch({ type: "goal", goal: event.target.value })} />
          </label>
          {notice && <p className={styles.notice} role="status">{notice}</p>}
        </section>
        <FileInputs fileInput={fileInput} folderInput={folderInput} onFiles={(list) => { const { files, skipped } = toAdded(list); if (files.length) addFiles(files, "新しいワークスペース", skipped); else setNotice("TIFF画像が見つかりませんでした。"); }} />
      </main>
    );
  }

  const exports = adapter.exports(state);
  return (
    <main className={styles.shell} onDragOver={(event) => event.preventDefault()} onDrop={onDrop}>
      <header className={styles.header}>
        <span className={styles.brand}>cytellect</span>
        <h1 className={styles.title}>{state.name}</h1>
        <p className={styles.status} role="status" aria-live="polite">
          {current === "proposal" && `${fields.length} 視野 · 解析案を確認`}
          {current === "running" && `解析中 ${counts.done}/${counts.total}`}
          {current === "results" && `完了 ${counts.done}/${counts.total}${counts.failed ? ` · 要確認 ${counts.failed}` : ""}${state.stopped ? " · 中断" : ""}`}
        </p>
        <div className={styles.headerActions}>
          {current === "running" && <button type="button" className={styles.secondary} onClick={() => dispatch({ type: "stop" })}>中断</button>}
          <button type="button" className={styles.secondary} disabled={Boolean(state.adopted)} title={state.adopted ? "解析開始後の追加は解析APIの接続後に対応します" : undefined}
            onClick={() => fileInput.current?.click()}>画像を追加</button>
          <details className={styles.menu}>
            <summary className={styles.secondary}>書き出し</summary>
            <ul>
              {exports.map((item) => (
                <li key={item.label}>{item.href ? <a href={item.href} download>{item.label}</a> : <span aria-disabled="true" title={item.reason}>{item.label}<small>{item.reason}</small></span>}</li>
              ))}
            </ul>
          </details>
          <button type="button" className={styles.iconButton} aria-pressed={panel} aria-label="操作パネル" onClick={() => setPanel(!panel)}>☰</button>
        </div>
      </header>
      {notice && <p className={styles.banner} role="status">{notice}</p>}

      <div className={[styles.layout, panel ? "" : styles.layoutNoPanel].join(" ")}>
        <nav className={styles.sidebar} aria-label="画像とグラフ">
          <h2>画像 <small>{fields.length}</small></h2>
          <ul className={styles.fieldList}>
            {fields.map((field) => {
              const run = state.runs[field];
              const active = selection?.view !== "figure" && selectedField === field;
              return (
                <li key={field}>
                  <button type="button" aria-current={active ? "true" : undefined} onClick={() => select({ view: "image", field })}>
                    <span>{labels[field]}</span>
                    {run && <span className={styles[`status_${run.status}`]}>{STATUS_LABEL[run.status]}</span>}
                    {!run && grouping && Object.keys(grouping.fields.find((item) => item.key === field)?.files ?? {}).length < grouping.channels.length && <span className={styles.status_failed}>チャンネル不足</span>}
                  </button>
                </li>
              );
            })}
          </ul>
          {figures.length > 0 && <>
            <h2>グラフ</h2>
            <ul className={[styles.fieldList, styles.figureList].join(" ")}>
              {figures.map((item) => {
                const active = selection?.view === "figure" && state.figure.metric === item.key;
                return <li key={item.key}><button type="button" aria-current={active ? "true" : undefined}
                  onClick={() => { dispatch({ type: "figure", settings: { metric: item.key } }); select({ view: "figure", figure: item.key }); }}>
                  <span>{item.label}</span><span className={styles.muted}>視野ごとの分布</span></button></li>;
              })}
            </ul>
          </>}
          {source && <p className={styles.source}>出典: {source}</p>}
        </nav>

        <section className={styles.center} aria-label="表示">
          {current === "proposal" && proposal && grouping && (
            <ProposalSummary proposal={proposal} grouping={grouping} onRun={() => dispatch({ type: "adopt" })}
              onName={(token, stain) => dispatch({ type: "name-channel", token, stain })}>
              <NuclearChoice grouping={grouping} preview={(token) => adapter.preview(fields[0], token)}
                onChoose={(token) => { dispatch({ type: "choose-nuclear", token }); setChannel(token); }} />
            </ProposalSummary>
          )}
          {selection?.view === "figure" && metric ? (
            <div className={styles.figureStage}>
              <FieldFigure points={distribution.points} summaries={distribution.summaries} labels={labels} metricLabel={metric.label}
                widthMm={state.figure.widthMm} heightMm={state.figure.heightMm} yLabel={state.figure.yLabel}
                selected={selection.field && selection.region ? { field: selection.field, region: selection.region } : undefined}
                onSelect={(field, region) => select({ view: "image", field, region })} />
            </div>
          ) : selectedField ? (
            <div className={styles.imageStage}>
              <div className={styles.imageToolbar}>
                <strong>{labels[selectedField]}</strong>
                <div role="radiogroup" aria-label="表示チャンネル" className={styles.segmented}>
                  {grouping?.channels.map((item) => (
                    <button key={item.token} type="button" role="radio" aria-checked={displayChannel === item.token} onClick={() => setChannel(item.token)}>
                      {item.stain ?? item.token}
                    </button>
                  ))}
                </div>
                {state.runs[selectedField]?.status === "running" && <span className={styles.updating}>解析中</span>}
              </div>
              <FieldImage src={adapter.preview(selectedField, displayChannel)} size={adapter.size(selectedField)} label={`${labels[selectedField]}の画像`}
                analyzed={Boolean(result)} outlines={(result?.outlines ?? []).map((outline) => ({ outline, state: regionState(state, selectedField, Number(outline.id)) }))}
                selected={selectedRegion} onSelect={(region) => select({ view: "image", field: selectedField, region })} />
              {state.runs[selectedField]?.status === "failed" && (
                <div className={styles.fieldError} role="alert">
                  <p>{state.runs[selectedField].error}</p>
                  <button type="button" className={styles.secondary} onClick={() => dispatch({ type: "retry", field: selectedField })}>再実行</button>
                </div>
              )}
            </div>
          ) : null}
        </section>

        {panel && (
          <aside className={styles.panel} aria-label="選択対象の操作">
            {current === "proposal" && (
              <section className={styles.panelSection}>
                <h3>解析の目的（任意）</h3>
                <textarea className={styles.textarea} rows={3} value={state.goal} onChange={(event) => dispatch({ type: "goal", goal: event.target.value })} />
              </section>
            )}
            {current !== "proposal" && selection?.view !== "figure" && selectedField && (
              <RegionPanel field={selectedField} region={selectedRegion} state={state} dispatch={dispatch} metrics={metrics} />
            )}
            {current !== "proposal" && selection?.view === "figure" && metric && (
              <section className={styles.panelSection} aria-labelledby="figure-settings">
                <h3 id="figure-settings">グラフ設定</h3>
                <label>測定項目<select value={metric.key} onChange={(event) => dispatch({ type: "figure", settings: { metric: event.target.value } })}>
                  {metrics.map((item) => <option key={item.key} value={item.key}>{item.label}</option>)}
                </select></label>
                <label>幅<select value={state.figure.widthMm} onChange={(event) => dispatch({ type: "figure", settings: { widthMm: Number(event.target.value) } })}>
                  <option value={89}>89 mm（1段）</option><option value={183}>183 mm（2段）</option>
                </select></label>
                <label>高さ (mm)<input type="number" min={40} max={170} value={state.figure.heightMm}
                  onChange={(event) => dispatch({ type: "figure", settings: { heightMm: Math.min(170, Math.max(40, Number(event.target.value) || 60)) } })} /></label>
                <label>縦軸の名前<input value={state.figure.yLabel} placeholder={metric.label} onChange={(event) => dispatch({ type: "figure", settings: { yLabel: event.target.value } })} /></label>
                <p className={styles.hint}>体裁の変更では解析を再実行しません。</p>
                <h3>比較条件</h3>
                <p className={styles.hint}>群と独立した実験単位が未設定のため、比較の検定は行いません。各視野の群と実験単位を設定すると、実験単位での比較を作成できます（解析API接続後）。</p>
              </section>
            )}
            {current !== "proposal" && grouping && (
              <details className={styles.panelSection}>
                <summary>解析条件と履歴</summary>
                <ul className={styles.history}>
                  {grouping.channels.map((item) => <li key={item.token}>{item.token} → {channelText(item)}</li>)}
                  <li>解析案を採用: {state.adopted?.inputFields.length ?? 0} 視野</li>
                  <li>修正: {state.corrections.length} 件</li>
                </ul>
              </details>
            )}
          </aside>
        )}

        <section className={[styles.drawer, drawer ? styles.drawerOpen : ""].join(" ")} aria-label="測定値">
          <button type="button" className={styles.drawerToggle} aria-expanded={drawer} onClick={() => setDrawer(!drawer)}>
            測定値{result ? `（${labels[selectedField!]} · ${result.measurements.length} 領域）` : ""}
          </button>
          {drawer && result && selectedField && (
            <div className={styles.tableWrap}>
              <table className={styles.table}>
                <thead><tr><th scope="col">領域</th>{metrics.map((item) => <th key={item.key} scope="col">{item.label}</th>)}<th scope="col">状態</th></tr></thead>
                <tbody>
                  {result.measurements.map((row) => {
                    const status = regionState(state, selectedField, row.region_id);
                    if (status === "deleted") return null;
                    return (
                      <tr key={row.region_id} aria-selected={row.region_id === selectedRegion} onClick={() => select({ view: "image", field: selectedField, region: row.region_id })}>
                        <th scope="row">{row.region_id}</th>
                        {metrics.map((item) => <td key={item.key}>{typeof row[item.key] === "number" ? Number(row[item.key].toPrecision(6)) : "—"}</td>)}
                        <td>{status === "excluded" ? "除外" : ""}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
      <FileInputs fileInput={fileInput} folderInput={folderInput} onFiles={(list) => { const { files, skipped } = toAdded(list); if (files.length) addFiles(files, "新しいワークスペース", skipped); }} />
    </main>
  );
}

function RegionPanel({ field, region, state, dispatch, metrics }: {
  field: string;
  region?: number;
  state: ReturnType<typeof initialState>;
  dispatch: (action: Parameters<typeof reducer>[1]) => void;
  metrics: { key: string; label: string }[];
}) {
  const row = state.results[field]?.measurements.find((item) => item.region_id === region);
  const status = region ? regionState(state, field, region) : null;
  return (
    <section className={styles.panelSection} aria-labelledby="region-title">
      <h3 id="region-title">領域を修正</h3>
      {!state.results[field] && <p className={styles.hint}>この画像の解析が完了すると領域を選択できます。</p>}
      {state.results[field] && !row && <p className={styles.hint}>画像の領域、表の行、またはグラフの点を選択します。</p>}
      {row && status !== "deleted" && (
        <>
          <p className={styles.regionTitle}>領域 {row.region_id}{status === "excluded" ? "（除外）" : ""}</p>
          <dl className={styles.values}>
            {metrics.map((item) => <div key={item.key}><dt>{item.label}</dt><dd>{typeof row[item.key] === "number" ? Number(row[item.key].toPrecision(6)) : "—"}</dd></div>)}
          </dl>
          <div className={styles.actions}>
            <button type="button" className={styles.secondary} disabled={status === "excluded"} onClick={() => dispatch({ type: "correct", correction: { kind: "exclude", field, region: row.region_id } })}>対象から除外</button>
            <button type="button" className={styles.secondary} onClick={() => dispatch({ type: "correct", correction: { kind: "delete", field, region: row.region_id } })}>領域を削除</button>
          </div>
        </>
      )}
      <div className={styles.actions}>
        <button type="button" className={styles.secondary} disabled={!state.corrections.length} onClick={() => dispatch({ type: "undo" })}>元に戻す</button>
        <button type="button" className={styles.secondary} disabled={!state.redo.length} onClick={() => dispatch({ type: "redo" })}>やり直す</button>
      </div>
      <p className={styles.hint}>修正は、この画像の測定値とグラフだけに反映します。領域の形の修正は解析APIの接続後に対応します。</p>
    </section>
  );
}

function FileInputs({ fileInput, folderInput, onFiles }: {
  fileInput: RefObject<HTMLInputElement | null>;
  folderInput: RefObject<HTMLInputElement | null>;
  onFiles: (files: FileList) => void;
}) {
  return (
    <>
      <input ref={fileInput} type="file" multiple accept=".tif,.tiff" hidden data-testid="file-input"
        onChange={(event) => { if (event.target.files) onFiles(event.target.files); event.target.value = ""; }} />
      <input ref={folderInput} type="file" multiple hidden data-testid="folder-input"
        onChange={(event) => { if (event.target.files) onFiles(event.target.files); event.target.value = ""; }} />
    </>
  );
}
