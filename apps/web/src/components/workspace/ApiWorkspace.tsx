"use client";
import {useCallback, useEffect, useMemo, useRef, useState} from "react";
import Link from "next/link";
import {API_CONFIGURED, ApiError, download, errorMessage, fetchBlob} from "@/lib/api";
import {createApiAdapter, figureIdentity, nuclearRecipe, savedDistribution, type ImportedField, type Recipe, type SavedFigure, type SavedResult} from "@/lib/workspace/api-adapter";
import {chooseNuclearChannel, groupFiles, isSupportedImage, type AddedFile, type Grouping} from "@/lib/workspace/grouping";
import {FieldImage} from "./FieldImage";
import {FieldFigure} from "./FieldFigure";
import {WorkspaceComparison} from "./WorkspaceComparison";
import {ImportSummary, NuclearChoice} from "./ProposalPanels";
import styles from "./analysis-workspace.module.css";

type Item = {key: string; label: string; field?: ImportedField; status: "importing" | "ready" | "running" | "done" | "failed"; error?: string; result?: SavedResult; recipe?: Recipe; history: SavedResult[]; redo: SavedResult[]};
const statusLabel = {importing: "読込中", ready: "待機", running: "解析中", done: "完了", failed: "要確認"};
const message = (error: unknown) => error instanceof ApiError ? errorMessage(error) : error instanceof Error ? error.message : "処理できませんでした";
const choiceKey = (channel: string | null, metric: string) => channel ? `${channel}:${metric}` : metric;

/** No mock adapter or browser quantitation is reachable from the real workspace. */
export default function ApiWorkspace() {
  const adapter = useMemo(() => createApiAdapter(), []);
  const [workspace, setWorkspace] = useState("");
  const [grouping, setGrouping] = useState<Grouping | null>(null);
  const [items, setItems] = useState<Item[]>([]);
  const [selected, setSelected] = useState("");
  const [channel, setChannel] = useState("");
  const [region, setRegion] = useState<number>();
  const [comparisonOpened, setComparisonOpened] = useState(false);
  const [view, setView] = useState<"image" | "figure" | "comparison">("image");
  const [metric, setMetric] = useState("area_px");
  const [width, setWidth] = useState(178);
  const [height, setHeight] = useState(76);
  const [axisLabel, setAxisLabel] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [figureBusy, setFigureBusy] = useState(false);
  const [figureError, setFigureError] = useState("");
  const [figures, setFigures] = useState<Record<string, SavedFigure>>({});
  const [previews, setPreviews] = useState<Record<string, string>>({});
  const [drawer, setDrawer] = useState(false);
  const [panel, setPanel] = useState(true);
  const [figureRetry, setFigureRetry] = useState(0);
  const [goal, setGoal] = useState("");
  const [transmission, setTransmission] = useState(false);
  const [draftBusy, setDraftBusy] = useState(false);
  const [draft, setDraft] = useState("");
  const [fileCount, setFileCount] = useState(0);
  const files = useRef(new Map<string, File>());
  const added = useRef<AddedFile[]>([]);
  const busyRef = useRef(false);
  const stopped = useRef(false);
  const mounted = useRef(true);
  const fileInput = useRef<HTMLInputElement>(null);
  const folderInput = useRef<HTMLInputElement>(null);
  const previewUrls = useRef(new Map<string, string>());
  const figurePending = useRef(new Map<string, Promise<SavedFigure>>());
  const item = items.find(value => value.key === selected) ?? items[0];
  const actualChannel = channel || grouping?.channels[0]?.token || "";
  const nuclear = grouping?.channels.filter(value => value.role === "nuclear") ?? [];
  const [metricChannel, metricName] = metric.includes(":") ? metric.split(":") : [null, metric];
  const figureChoice = useMemo(() => ({channel: metricChannel, metric: metricName, width, height, label: axisLabel}), [metricChannel, metricName, width, height, axisLabel]);
  const currentFigureKey = item?.result ? figureIdentity(item.result.revision, figureChoice) : "";
  const figure = figures[currentFigureKey];
  const metricOptions = [{key: "area_px", label: "核面積 / px²"}, ...(grouping?.channels ?? []).flatMap(value => [
    {key: choiceKey(value.token, "mean"), label: `${value.stain || value.token} 平均輝度（原値）`},
    {key: choiceKey(value.token, "median"), label: `${value.stain || value.token} 中央値（原値）`},
    {key: choiceKey(value.token, "integrated"), label: `${value.stain || value.token} 積算輝度（原値）`},
  ])];
  function update(key: string, patch: Partial<Item>) {setItems(current => current.map(value => value.key === key ? {...value, ...patch} : value));}
  function remember(wid: string, result: SavedResult) {
    // Only owned server identifiers are retained; pixels and measurements are never stored in the browser.
    try {const key = `cytellect-workspace-revisions:${wid}`; const saved = JSON.parse(sessionStorage.getItem(key) || "{}"); sessionStorage.setItem(key, JSON.stringify({...saved, [result.field]: result.revision}));} catch { /* Storage may be disabled. Server results still exist. */ }
  }
  const loadPreviews = useCallback(async (field: ImportedField) => {
    for (const value of field.image_info.channels) {
      const key = `${field.id}:${value.channel_id}`;
      if (previewUrls.current.has(key)) continue;
      try {const blob = await adapter.preview(field.id, value.channel_id); if (!mounted.current) return;
        const url = URL.createObjectURL(blob); previewUrls.current.set(key, url); setPreviews(current => ({...current, [key]: url}));
      } catch { /* The original input and measured values remain accessible when display fails. */ }
    }
  }, [adapter]);
  const restored = useRef(false);
  useEffect(() => {
    mounted.current = true;
    folderInput.current?.setAttribute("webkitdirectory", "");
    if (window.innerWidth < 1100) setPanel(false);
    const wid = new URLSearchParams(window.location.search).get("id");
    if (wid && !restored.current && API_CONFIGURED) {
      restored.current = true; busyRef.current = true; setBusy(true);
      void adapter.restore(wid).then(async saved => {
        setWorkspace(wid);
        const first = saved.fields[0];
        const channels = first?.image_info.channels.map(value => ({token: value.channel_id, stain: value.stain, role: null, evidence: "filename" as const})) ?? [];
        setGrouping({channels, fields: saved.fields.map(field => ({key: field.id, candidates: {}, files: Object.fromEntries(field.image_info.channels.map(value => [value.channel_id, {path: `${field.id}/${value.channel_id}.tif`, size: 0}]))})), issues: []});
        setFileCount(saved.fields.reduce((count, field) => count + field.image_info.channels.length, 0));
        let remembered: Record<string, string> = {}; try {remembered = JSON.parse(sessionStorage.getItem(`cytellect-workspace-revisions:${wid}`) || "{}");} catch {}
        const recovered: Item[] = [];
        for (const [index, field] of saved.fields.entries()) {
          const revisions = saved.revisions.filter(value => ["succeeded", "queued", "running"].includes(value.state) && value.config.recipe.version === "1.2.0" && value.config.field_ids.length === 1 && value.config.field_ids[0] === field.id).sort((a,b) => b.created-a.created);
          const revision = revisions.find(value => value.state !== "succeeded") ?? revisions.find(value => value.id === remembered[field.id]) ?? revisions[0];
          const value: Item = {key: field.id, label: `視野 ${index + 1}`, field, status: "ready", history: [], redo: []};
          if (revision) {try {
            const pending = saved.jobs.find(job => job.kind === "analysis" && job.revision_id === revision.id && ["queued", "running"].includes(job.state));
            value.result = pending ? await adapter.resume(wid, pending, field.id) : await adapter.readResult(revision.id, field.id);
            value.recipe = revision.config.recipe; value.status = "done";
          } catch (error) {value.status = "failed"; value.error = message(error);}}
          recovered.push(value); void loadPreviews(field);
        }
        setItems(recovered); setSelected(recovered[0]?.key ?? "");
        const recipe = recovered.find(value => value.recipe)?.recipe;
        if (recipe) setGrouping(current => current ? chooseNuclearChannel(current, recipe.defining_channel_id) : current);
      }).catch(error => setNotice(message(error))).finally(() => {busyRef.current = false; setBusy(false);});
    }
    return () => {mounted.current = false;};
  }, [adapter, loadPreviews]);
  useEffect(() => () => {for (const url of previewUrls.current.values()) URL.revokeObjectURL(url);}, []);

  async function addFiles(list: FileList | File[]) {
    if (busyRef.current) return;
    busyRef.current = true; setBusy(true); setNotice("");
    try {
      if (!API_CONFIGURED) throw new Error("解析サーバーが設定されていません。ローカル版はランチャーから開いてください。");
      const fresh: AddedFile[] = []; const freshFiles = new Map<string, File>(); let unsupported = 0;
      for (const file of Array.from(list)) {
        const path = file.webkitRelativePath || file.name;
        if (!isSupportedImage(path)) {unsupported++; continue;}
        if (file.size > 256 * 1024 * 1024) throw new Error("画像ファイルが256 MiBを超えています。画像サイズを確認してください。");
        if (files.current.has(path) || freshFiles.has(path)) throw new Error("同じ名前のファイルが登録済みです。登録内容を確認してください。");
        const digest = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
        fresh.push({path, size: file.size, sha256: Array.from(new Uint8Array(digest), value => value.toString(16).padStart(2, "0")).join("")});
        freshFiles.set(path, file);
      }
      const next = groupFiles([...added.current, ...fresh]);
      if (grouping && grouping.channels.length && JSON.stringify(grouping.channels.map(value => value.token).sort()) !== JSON.stringify(next.channels.map(value => value.token).sort())) throw new Error("チャンネル構成が異なります。新しいワークスペースで追加してください。");
      if (grouping) next.channels = grouping.channels;
      added.current.push(...fresh); for (const [path, file] of freshFiles) files.current.set(path, file);
      setFileCount(current => current + fresh.length);
      setGrouping(next);
      let wid = workspace;
      if (!wid && next.fields.length) {const created = await adapter.create(); wid = created.id; setWorkspace(wid); window.history.replaceState(null, "", `/workspace?id=${encodeURIComponent(wid)}`);}
      const pending = next.fields.filter(field => !items.some(value => value.key === field.key && value.field));
      setItems(current => [...current.filter(value => !pending.some(field => field.key === value.key)), ...pending.map(field => ({key: field.key, label: field.key.split("/").at(-1) || field.key, status: "importing" as const, history: [], redo: []}))]);
      if (!selected && pending[0]) setSelected(pending[0].key);
      for (const field of pending) {
        try {
          const duplicate = next.issues.some(issue => issue.kind === "duplicate_content" && Object.values(field.files).some(file => issue.paths.includes(file.path)));
          if (duplicate) throw new Error("同じ内容の画像が複数あります。読み込み結果で重複を確認してください。");
          const uploaded = await adapter.upload(wid, field, next.channels, files.current); update(field.key, {field: uploaded, status: "ready", error: undefined}); void loadPreviews(uploaded);}
        catch (error) {update(field.key, {status: "failed", error: message(error)});}
      }
      if (unsupported) setNotice(`TIFF以外の ${unsupported} 件は追加していません。`);
    } catch (error) {setNotice(message(error));}
    finally {busyRef.current = false; setBusy(false);}
  }

  async function run() {
    if (busyRef.current || nuclear.length !== 1 || !workspace) return;
    busyRef.current = true; setBusy(true); stopped.current = false; setNotice("");
    const recipe = nuclearRecipe(nuclear[0]);
    try {
      for (const value of items.filter(value => value.field && !value.result)) {
        if (stopped.current) break;
        update(value.key, {status: "running", error: undefined, recipe});
        try {const result = await adapter.run(workspace, value.field!.id, recipe); remember(workspace, result); update(value.key, {status: "done", result, history: [], redo: []});}
        catch (error) {update(value.key, {status: "failed", error: message(error)});}
      }
    } finally {busyRef.current = false; setBusy(false); if (stopped.current) setNotice("中断しました。完了した視野は保存されています。");}
  }

  async function correct(kind: "exclude" | "delete" | "undo" | "redo") {
    if (busyRef.current || !item?.result || !item.recipe || !workspace) return;
    const value = item; busyRef.current = true; setBusy(true); setNotice("");
    try {
      const target = kind === "undo" ? value.history.at(-1) : kind === "redo" ? value.redo.at(-1) : null;
      const result = target ? await adapter.selectRevision(workspace, target.revision, value.field!.id)
        : region !== undefined && (kind === "exclude" || kind === "delete") ? await adapter.correct(workspace, value.result!, kind, region, value.recipe!) : null;
      if (result) {remember(workspace, result); update(value.key, {result,
        history: kind === "undo" ? value.history.slice(0, -1) : [...value.history, value.result!],
        redo: kind === "undo" ? [...value.redo, value.result!] : kind === "redo" ? value.redo.slice(0, -1) : []});}
    } catch (error) {setNotice(message(error));}
    finally {busyRef.current = false; setBusy(false);}
  }

  // Styling submits only a descriptive job. It cannot rerun Fiji or mutate measured pixels.
  useEffect(() => {
    if (!item?.result || !workspace || figure) return;
    let active = true; setFigureBusy(true); setFigureError("");
    const result = item.result;
    const timer = setTimeout(() => {
      let pending = figurePending.current.get(currentFigureKey);
      if (!pending) {pending = adapter.figure(workspace, result, figureChoice); figurePending.current.set(currentFigureKey, pending);}
      void pending.then(saved => {if (active) setFigures(current => ({...current, [currentFigureKey]: saved}));})
        .catch(error => {figurePending.current.delete(currentFigureKey); if (active) setFigureError(message(error));})
        .finally(() => {if (active) setFigureBusy(false);});
    }, 350);
    return () => {active = false; clearTimeout(timer);};
  }, [adapter, item?.result, workspace, currentFigureKey, figureChoice, figure, figureRetry]);

  async function requestDraft() {
    if (!workspace || !transmission || draftBusy) return;
    setDraftBusy(true); setDraft("");
    try {const response = await adapter.draft(workspace, goal); setDraft([response.proposal.draft.rationale, ...response.proposal.draft.missing_information].join("\n"));}
    catch (error) {setDraft(`${message(error)} 登録済みの解析条件でそのまま実行できます。`);}
    finally {setDraftBusy(false);}
  }
  const fileInputs = <><input ref={fileInput} type="file" multiple accept=".tif,.tiff" hidden data-testid="file-input" onChange={event => {if (event.target.files) void addFiles(event.target.files); event.target.value = "";}}/><input ref={folderInput} type="file" multiple hidden data-testid="folder-input" onChange={event => {if (event.target.files) void addFiles(event.target.files); event.target.value = "";}}/></>;
  const addActions = <><button className={styles.primary} disabled={busy || !API_CONFIGURED} onClick={() => fileInput.current?.click()}>画像を追加</button><button className={styles.secondary} disabled={busy || !API_CONFIGURED} onClick={() => folderInput.current?.click()}>フォルダを追加</button></>;
  const rows = item?.result?.rows.filter(row => row.channel_id === actualChannel) ?? [];
  const excluded = new Set(item?.result?.exclusions.filter(value => value.field_id === item.field?.id && value.region_id !== null).map(value => value.region_id));
  const shape = item?.field?.image_info.shape;
  const savedFiles = figure ? adapter.figureFiles(figure) : null;
  return <main className={styles.shell} onDragOver={event => event.preventDefault()} onDrop={event => {event.preventDefault(); void addFiles(event.dataTransfer.files);}}>
    <header className={styles.header}><Link href="/" className={styles.brand}>cytellect</Link><h1 className={styles.title}>画像解析</h1><p role="status">{busy ? "処理中" : `${items.filter(value => value.result).length} / ${items.length} 視野`}</p><div className={styles.headerActions}>{addActions}<button className={styles.secondary} aria-label="操作パネル" aria-pressed={panel} onClick={() => setPanel(!panel)}>操作</button>{busy && <button className={styles.secondary} onClick={() => {stopped.current = true; setNotice("現在の視野を完了してから中断します。");}}>中断</button>}</div></header>
    {notice && <p className={styles.banner} role="status">{notice}</p>}
    {!API_CONFIGURED && <p className={styles.banner}>解析サーバーが設定されていません。ローカル版はランチャーから開いてください。</p>}
    {!items.length ? <section className={styles.empty}><h2>画像を追加</h2><p>チャンネル別の2D TIFFを追加すると、ファイル名から視野をまとめます。</p><p>画像と原値の測定は解析サーバーで処理します。</p><p>画像と結果は最終操作から24時間で失効します。</p>{grouping && <ImportSummary grouping={grouping} files={fileCount}/>}</section> : <div className={[styles.layout, panel && view !== "comparison" ? "" : styles.layoutNoPanel].join(" ")}>
      <nav className={styles.sidebar} aria-label="画像とグラフ"><h2>画像</h2><ul className={styles.fieldList}>{items.map(value => <li key={value.key}><button aria-current={item?.key === value.key ? "true" : undefined} onClick={() => {setSelected(value.key); setRegion(undefined);}}><span>{value.label}</span><span>{statusLabel[value.status]}</span></button></li>)}</ul><h2>表示</h2><button className={styles.secondary} onClick={() => setView("image")}>画像</button><button className={styles.secondary} onClick={() => setView("figure")}>グラフ</button><button className={styles.secondary} disabled={!items.some(value => value.result)} onClick={() => {setComparisonOpened(true); setView("comparison");}}>群を比較</button><p className={styles.hint}>結果は視野ごとに保存します。領域数を独立反復数には使いません。</p></nav>
      <section className={styles.center} aria-label="表示">
        {!items.some(value => value.result) && grouping && <section className={styles.proposal}><h2>解析案</h2><ImportSummary grouping={grouping} files={fileCount}/><NuclearChoice grouping={grouping} preview={token => item?.field ? previews[`${item.field.id}:${token}`] ?? null : null} onChoose={token => setGrouping(chooseNuclearChannel(grouping, token))}/><ol><li>選択したチャンネルから核を検出</li><li>核面積と全チャンネルの原値を測定</li><li>視野別の分布図と測定表を作成</li></ol><p>背景補正は行いません。核小体・核質の比と群間検定はこの解析には含みません。</p><button className={styles.primary} disabled={busy || nuclear.length !== 1 || !items.some(value => value.field)} onClick={() => void run()}>解析を実行</button></section>}
        {item?.error && <p className={styles.banner} role="alert">{item.error}{!item.field && <button className={styles.secondary} disabled={busy} onClick={() => void addFiles([])}>登録を再試行</button>}</p>}
        <div className={styles.comparisonMount} hidden={view !== "comparison"}>{comparisonOpened && <WorkspaceComparison workspace={workspace} sources={items.flatMap(value => value.result && value.field ? [{field: value.field.id, revision: value.result.revision, label: value.label, result: value.result, metadata: value.field.metadata}] : [])} pendingFields={items.filter(value => !value.result).length} blocked={busy} options={metricOptions} regionSet={item?.recipe?.region_set_id || "nuclei"} onInspect={field => {const target = items.find(value => value.field?.id === field); if (target) {setSelected(target.key); setView("image");}}}/>}</div>{view === "comparison" ? null : view === "image" ? <div className={styles.imageStage}><div className={styles.imageToolbar}><strong>{item?.label}</strong><div className={styles.segmented}>{grouping?.channels.map(value => <button key={value.token} role="radio" aria-checked={actualChannel === value.token} onClick={() => setChannel(value.token)}>{value.stain || value.token}</button>)}</div></div><FieldImage src={item?.field ? previews[`${item.field.id}:${actualChannel}`] ?? null : null} size={shape ? {height: shape[0], width: shape[1]} : null} outlines={(item?.result?.masks.regions ?? []).map(value => ({outline: {id: String(value.id), points: value.points}, state: excluded.has(value.id) ? "excluded" as const : "included" as const}))} analyzed={!!item?.result} selected={region} onSelect={setRegion} label={`${item?.label || "視野"}の画像`}/></div>
          : <section className={styles.figureStage}>{figureBusy && !figure && <p role="status">測定値から図を作成しています。</p>}{figureError && <div role="alert"><p>{figureError} 測定値は保存されています。</p><button className={styles.secondary} onClick={() => setFigureRetry(value => value + 1)}>図を再作成</button></div>}{figure && savedFiles && <><p>未確認の検出結果 · {item?.label} · {metricOptions.find(value => value.key === metric)?.label} · 1点は1領域</p><SavedInteractiveFigure figure={figure} label={item?.label || "視野"} onSelect={selectedRegion => {setRegion(selectedRegion); setView("image");}}/>{(savedFiles.view.kind === "ready" || savedFiles.view.kind === "legacy") && <details><summary>書き出し図</summary>{savedFiles.view.pages.map(page => <PrivateFigure key={`${figure.job}:${page.files.png}`} path={`/v1/jobs/${figure.job}/files/${page.files.png}`}/>)}</details>}{savedFiles.view.kind === "tables_only" && <p>図を生成できませんでした。測定表は保存されています。</p>}<div className={styles.actions}>{savedFiles.files.map(file => <button className={styles.secondary} key={file} onClick={() => void download(`/v1/jobs/${figure.job}/files/${file}`, file).catch(error => setNotice(message(error)))}>{file} ↓</button>)}</div></>}{!item?.result && <p>解析後にグラフを表示します。</p>}</section>}
      </section>
      {panel && view !== "comparison" && <aside className={styles.panel} aria-label="選択対象の操作">
        {items.some(value => value.field && !value.result) && items.some(value => value.result) && <button className={styles.primary} disabled={busy || nuclear.length !== 1} onClick={() => void run()}>未完了の視野を解析</button>}
        {item?.result && <><section className={styles.panelSection}><h3>領域を修正</h3><p>{region ? `領域 ${region}${excluded.has(region) ? "（除外）" : ""}` : "画像または測定表で領域を選択"}</p><div className={styles.actions}><button className={styles.secondary} disabled={busy || !region || excluded.has(region)} onClick={() => void correct("exclude")}>対象から除外</button><button className={styles.secondary} disabled={busy || !region} onClick={() => void correct("delete")}>領域を削除</button><button className={styles.secondary} disabled={busy || !item?.history.length} onClick={() => void correct("undo")}>元に戻す</button><button className={styles.secondary} disabled={busy || !item?.redo.length} onClick={() => void correct("redo")}>やり直す</button></div>{busy && item?.result && <p>更新中。直前の保存結果を表示しています。</p>}</section>
        <section className={styles.panelSection}><h3>グラフ設定</h3><label>測定項目<select value={metric} onChange={event => setMetric(event.target.value)}>{metricOptions.map(value => <option key={value.key} value={value.key}>{value.label}</option>)}</select></label><label>幅 (mm)<select value={width} onChange={event => setWidth(Number(event.target.value))}><option value={89}>89</option><option value={178}>178</option><option value={183}>183</option></select></label><label>高さ (mm)<input type="number" min={40} max={170} value={height} onChange={event => setHeight(Math.min(170, Math.max(40, Number(event.target.value) || 76)))}/></label><label>縦軸の名前<input value={axisLabel} maxLength={120} onChange={event => setAxisLabel(event.target.value)}/></label><p className={styles.hint}>設定変更は図だけを作り直します。原画像の測定値は変わりません。</p></section></>}
        <details className={styles.panelSection}><summary>解析案の補助（任意）</summary><label>解析の目的<textarea value={goal} maxLength={1000} onChange={event => setGoal(event.target.value)}/></label><p>目的とサーバーに保存されたチャンネル・画像の情報を Cytellect 提案サービスと OpenAI に送ります。画像・測定表は送りません。OpenAI は不正利用監視のため情報を保持する場合があります。</p><label><input type="checkbox" checked={transmission} onChange={event => setTransmission(event.target.checked)}/>この作業で上記の情報送信を許可する</label><button className={styles.secondary} disabled={!transmission || !workspace || draftBusy || busy} onClick={() => void requestDraft()}>解析案を相談</button>{draft && <p style={{whiteSpace: "pre-wrap"}}>{draft}</p>}<p>提案は測定条件へ自動適用しません。サービスが使えなくても解析を実行できます。</p></details>
        {item?.result && <details className={styles.panelSection}><summary>保存結果の出典</summary><p>解析版：{item.result.revision}</p><p>マスク版：{item.result.masks.metadata.mask_revision_id}</p><p>原値測定。検出結果の品質確認前。</p></details>}
      </aside>}
      <section className={[styles.drawer, drawer ? styles.drawerOpen : ""].join(" ")} aria-label="測定値"><button className={styles.drawerToggle} onClick={() => setDrawer(!drawer)} aria-expanded={drawer}>測定値 · {item?.label} · {rows.length} 領域</button>{drawer && <div className={styles.tableWrap}><table className={styles.table}><thead><tr><th>領域</th><th>面積 / px²</th><th>平均（原値）</th><th>中央値（原値）</th><th>積算（原値）</th><th>採否</th></tr></thead><tbody>{rows.map(row => <tr key={row.region_id}><th><button className={styles.rowButton} aria-label={`領域 ${row.region_id} を選択`} onClick={() => {setRegion(row.region_id); setView("image");}}>{row.region_id}</button></th>{[row.area_px, row.mean, row.median, row.integrated].map((value, index) => <td key={index}>{value === null ? "—" : Number(value.toPrecision(6))}</td>)}<td>{excluded.has(row.region_id) ? "除外" : "採用"}</td></tr>)}</tbody></table></div>}</section>
    </div>}{fileInputs}
  </main>;
}

function SavedInteractiveFigure({figure, label, onSelect}: {figure: SavedFigure; label: string; onSelect: (region: number) => void}) {
  let distribution: ReturnType<typeof savedDistribution>;
  try {distribution = savedDistribution(figure);} catch {return <p>図の出典を確認できません。測定表を確認してください。</p>;}
  const labels = Object.fromEntries(distribution.summaries.map(row => [row.field, label]));
  return <FieldFigure {...distribution} labels={labels} metricLabel={`${figure.result.metric} / ${figure.result.unit}`}
    widthMm={figure.choice.width} heightMm={figure.choice.height} yLabel={figure.choice.label}
    onSelect={(_, selectedRegion) => onSelect(selectedRegion)}/>;
}

function PrivateFigure({path}: {path: string}) {
  const [url, setUrl] = useState(""); const [failed, setFailed] = useState(false);
  useEffect(() => {const controller = new AbortController(); let objectUrl = "";
    void fetchBlob(path, controller.signal).then(blob => {if (!controller.signal.aborted) {objectUrl = URL.createObjectURL(blob); setUrl(objectUrl);}}).catch(() => {if (!controller.signal.aborted) setFailed(true);});
    return () => {controller.abort(); if (objectUrl) URL.revokeObjectURL(objectUrl);};
  }, [path]);
  return failed ? <p>図の表示を読み込めません。保存ファイルから確認できます。</p> : url ? <img src={url} alt="保存された領域測定値の分布図" style={{maxWidth: "100%"}}/> : <p>図を読み込んでいます。</p>;
}
