"use client";
import { useCallback, useEffect, useMemo, useReducer, useRef, useState, type DragEvent, type RefObject } from "react";
import Link from "next/link";
import { fieldDistribution, type WorkspaceAdapter } from "@/lib/workspace/adapter";
import { groupFiles, isSupportedImage, type AddedFile } from "@/lib/workspace/grouping";
import { initialState, phase, progress, reducer, regionState, type Selection } from "@/lib/workspace/model";
import { FieldFigure } from "./FieldFigure";
import { FieldImage } from "./FieldImage";
import { ImportSummary, NuclearChoice, ProposalSummary, channelText } from "./ProposalPanels";
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

export default function AnalysisWorkspace({ adapter, demo = false }: { adapter: WorkspaceAdapter; demo?: boolean }) {
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
    setNotice(skipped ? `TIFF以外の ${skipped} 件は追加していません` : "");
  }, [added, state.adopted, state.name]);

  const loadSample = async () => {
    try {
      const sample = await adapter.loadSample();
      setAdded(sample.files);
      dispatch({ type: "imported", name: sample.name, grouping: groupFiles(sample.files) });
      setNotice("");
      setSource(sample.attribution);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "公開画像を読み込めません");
    }
  };

  // Review and test entry only (?demo=bbbc013); the public demo itself belongs to the site.
  const demoLoaded = useRef(false);
  useEffect(() => {
    if (!demo || demoLoaded.current) return;
    demoLoaded.current = true;
    void loadSample();
  });

  // Concurrency 1: run the next waiting field; every field commits independently.
  useEffect(() => {
    if (running.current || state.stopped) return;
    const next = Object.entries(state.runs).find(([, run]) => run.status === "waiting")?.[0];
    if (!next) return;
    running.current = true;
    dispatch({ type: "field-started", field: next });
    adapter.run(next)
      .then((result) => dispatch({ type: "field-done", field: next, result }))
      .catch((error: unknown) => dispatch({ type: "field-failed", field: next, error: error instanceof Error ? error.message : "解析できません" }))
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
    else setNotice("TIFF画像がありません");
  };

  const select = (selection: Selection | null) => dispatch({ type: "select", selection });
  const selection = state.selection;
  const selectedField = selection?.field ?? fields[0];
  const proposal = state.adopted?.proposal ?? state.proposal;
  const metrics = proposal?.metrics ?? [];
  const metric = metrics.find((item) => item.key === state.figure.metric) ?? metrics[0];
  const labels = Object.fromEntries(fields.map((field) => [field, adapter.label(field)]));
  const { results, corrections } = state;
  const order = state.figure.order;
  // Recompute only when results, corrections or field order change; styling and selection do not.
  const distribution = useMemo(
    () => metric ? fieldDistribution({ results, corrections, figure: { order } }, metric.key) : { points: [], summaries: [] },
    [results, corrections, order, metric],
  );
  const displayChannel = channel ?? proposal?.nuclearChannel?.token ?? grouping?.channels[0]?.token ?? "";
  const result = selectedField ? state.results[selectedField] : undefined;
  const selectedRegion = selection?.region;
  const figures = state.adopted ? metrics : [];

  if (current === "empty") {
    return (
      <main className={styles.shell}>
        <header className={styles.header}><Link href="/" className={styles.brand}>cytellect</Link></header>
        <div className={styles.start}>
          <section className={styles.empty} onDragOver={(event) => event.preventDefault()} onDrop={onDrop} aria-labelledby="empty-title">
            <h1 id="empty-title">画像を追加</h1>
            <p>TIFF / OME-TIFF のファイル、またはフォルダをここにドロップ</p>
            <div className={styles.actions}>
              <button type="button" className={styles.primary} onClick={() => fileInput.current?.click()}>ファイルを選択</button>
              <button type="button" className={styles.secondary} onClick={() => folderInput.current?.click()}>フォルダを選択</button>
            </div>
            <label className={styles.goal}>解析の目的（任意）
              <textarea value={state.goal} rows={2} placeholder="例：GFP陽性細胞で、核小体と核質のNCL輝度を比較"
                onChange={(event) => dispatch({ type: "goal", goal: event.target.value })} />
            </label>
            {notice && <p className={styles.notice} role="status">{notice}</p>}
          </section>
          <ol className={styles.steps} aria-label="解析の流れ">
            <li><b>画像を追加</b><span>同じ視野のチャンネル（例：A01_DAPI.tif と A01_GFP.tif）は、ファイル名から1つの視野にまとめます。</span></li>
            <li><b>解析案を確認して実行</b><span>検出する領域・測定項目・グラフが表示されます。「解析を実行」で、核の検出から測定、グラフ作成まで進みます。</span></li>
            <li><b>確認・修正・書き出し</b><span>画像の核を選んで除外・削除すると、測定値とグラフに反映されます。グラフと測定値は SVG / CSV で保存できます。</span></li>
          </ol>
        </div>
        <FileInputs fileInput={fileInput} folderInput={folderInput} onFiles={(list) => { const { files, skipped } = toAdded(list); if (files.length) addFiles(files, "新しいワークスペース", skipped); else setNotice("TIFF画像がありません"); }} />
      </main>
    );
  }

  const exports = adapter.exports(state);
  return (
    <main className={styles.shell} onDragOver={(event) => event.preventDefault()} onDrop={onDrop}>
      <header className={styles.header}>
        <Link href="/" className={styles.brand}>cytellect</Link>
        <h1 className={styles.title}>{state.name}</h1>
        <p className={styles.status} role="status" aria-live="polite">
          {current === "proposal" && `${fields.length} 視野`}
          {current === "running" && `解析中 ${counts.done}/${counts.total}`}
          {current === "results" && `完了 ${counts.done}/${counts.total}${counts.failed ? ` · 要確認 ${counts.failed}` : ""}${state.stopped ? " · 中断" : ""}`}
        </p>
        <div className={styles.headerActions}>
          {current === "running" && <button type="button" className={styles.secondary} onClick={() => dispatch({ type: "stop" })}>中断</button>}
          {state.stopped && Object.values(state.runs).some((run) => run.status === "waiting") && (
            <button type="button" className={styles.secondary} onClick={() => dispatch({ type: "resume" })}>再開</button>
          )}
          <button type="button" className={styles.secondary} disabled={Boolean(state.adopted)} title={state.adopted ? "プロトタイプでは解析開始後に追加できません" : undefined}
            onClick={() => fileInput.current?.click()}>画像を追加</button>
          <details className={styles.menu}>
            <summary className={styles.secondary}>書き出し</summary>
            <ul>
              {exports.map((item) => (
                <li key={item.label}>{item.href
                  ? <a href={item.href} download>{item.label}<small>{item.detail}</small></a>
                  : <span aria-disabled="true">{item.label}<small>{item.reason}</small></span>}</li>
              ))}
            </ul>
          </details>
          <button type="button" className={styles.iconButton} aria-pressed={panel} aria-label="操作パネル" onClick={() => setPanel(!panel)}>
            <svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><rect x="2.5" y="3.5" width="15" height="13" rx="1" fill="none" stroke="currentColor" /><path d="M12.5 3.5v13" stroke="currentColor" /></svg>
          </button>
        </div>
      </header>
      {notice && <p className={styles.banner} role="status">{notice}</p>}
      {current === "running" && <p className={styles.banner}>完了した画像から順に結果を確認できます。</p>}

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
                  <span>{item.label}</span><span className={styles.muted}>視野別の分布</span></button></li>;
              })}
            </ul>
          </>}
          {source && <p className={styles.source}>出典　{source}</p>}
        </nav>

        <section className={styles.center} aria-label="表示">
          {current === "proposal" && proposal && grouping && (
            <ProposalSummary proposal={proposal} grouping={grouping} onRun={() => dispatch({ type: "adopt" })}
              onName={(token, stain) => dispatch({ type: "name-channel", token, stain })}>
              <ImportSummary grouping={grouping} files={added.length} />
              {grouping.fields.length > 0 && (
                <NuclearChoice grouping={grouping} preview={(token) => adapter.preview(fields[0], token)}
                  onChoose={(token) => { dispatch({ type: "choose-nuclear", token }); setChannel(token); }} />
              )}
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
            {current === "results" && !selectedRegion && selection?.view !== "figure" && (
              <section className={styles.panelSection} aria-labelledby="next-title">
                <h3 id="next-title">次の操作</h3>
                <ol className={styles.nextSteps}>
                  <li><b>領域を確認</b>画像上の核をクリックすると、測定値の確認と除外・削除ができます。</li>
                  <li><b>グラフを見る</b>左の「グラフ」から、視野別の分布を開きます。</li>
                  <li><b>書き出し</b>右上の「書き出し」から、グラフ（SVG）と測定値（CSV）を保存します。</li>
                </ol>
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
                  <option value={89}>89 mm（1段）</option><option value={178}>178 mm</option><option value={183}>183 mm（2段）</option>
                </select></label>
                <label>高さ (mm)<input type="number" min={40} max={170} value={state.figure.heightMm}
                  onChange={(event) => dispatch({ type: "figure", settings: { heightMm: Math.min(170, Math.max(40, Number(event.target.value) || 76)) } })} /></label>
                <label>縦軸の名前<input value={state.figure.yLabel} placeholder={metric.label} onChange={(event) => dispatch({ type: "figure", settings: { yLabel: event.target.value } })} /></label>
                <p className={styles.hint}>点をクリックすると、その領域の画像に移動します。</p>
                <h3>比較</h3>
                <p className={styles.hint}>群・実験単位：未設定</p>
                <button type="button" className={styles.secondary} disabled title="プロトタイプでは未対応">比較を作成</button>
              </section>
            )}
            {current !== "proposal" && grouping && (
              <details className={styles.panelSection}>
                <summary>解析条件・履歴</summary>
                <ImportSummary grouping={grouping} files={added.length} />
                <ul className={styles.history}>
                  {grouping.channels.map((item) => <li key={item.token}>{item.token} → {channelText(item)}</li>)}
                  <li>解析案を採用（{state.adopted?.inputFields.length ?? 0} 視野）</li>
                  <li>修正 {state.corrections.length} 件</li>
                </ul>
              </details>
            )}
          </aside>
        )}

        <section className={[styles.drawer, drawer ? styles.drawerOpen : ""].join(" ")} aria-label="測定値">
          <button type="button" className={styles.drawerToggle} aria-expanded={drawer} onClick={() => setDrawer(!drawer)}>
            測定値{result ? `　${labels[selectedField!]} · ${result.measurements.length} 領域` : ""}
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
                      <tr key={row.region_id} className={row.region_id === selectedRegion ? styles.rowSelected : undefined}
                        onClick={() => select({ view: "image", field: selectedField, region: row.region_id })}>
                        <th scope="row">
                          {/* Keyboard path to every region; the image outlines and figure points mirror it. */}
                          <button type="button" className={styles.rowButton} aria-current={row.region_id === selectedRegion ? "true" : undefined}
                            aria-label={`領域 ${row.region_id} を選択`} onClick={(event) => { event.stopPropagation(); select({ view: "image", field: selectedField, region: row.region_id }); }}>
                            {row.region_id}
                          </button>
                        </th>
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
      {!state.results[field] && <p className={styles.hint}>解析後に選択できます</p>}
      {state.results[field] && !row && <p className={styles.hint}>領域が選択されていません</p>}
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
