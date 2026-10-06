"use client";
import {useCallback, useEffect, useMemo, useRef, useState} from "react";
import Link from "next/link";
import {API_CONFIGURED, ApiError, download, errorMessage, fetchBlob} from "@/lib/api";
import {createApiAdapter, figureIdentity, nuclearRecipe, savedDistribution, type ImportedField, type Recipe, type SavedFigure, type SavedResult} from "@/lib/workspace/api-adapter";
import {chooseNuclearChannel, groupFiles, isSupportedImage, type AddedFile, type Grouping} from "@/lib/workspace/grouping";
import {tiffInputMode} from "@/lib/workspace/tiff-intake";
import {FieldImage} from "./FieldImage";
import {FieldFigure} from "./FieldFigure";
import {WorkspaceComparison} from "./WorkspaceComparison";
import {ImportSummary, NuclearChoice} from "./ProposalPanels";
import styles from "./analysis-workspace.module.css";

type Item = {orphan?: boolean; revisionChoices?: Array<{id: string; created: number; config: {recipe: Recipe; exclusions?: SavedResult["exclusions"]}}> ; entryId: string; exclusionReason?: string | null; key: string; label: string; field?: ImportedField; status: "importing" | "ready" | "running" | "done" | "failed"; error?: string; result?: SavedResult; recipe?: Recipe; history: SavedResult[]; redo: SavedResult[]};
const statusLabel = {importing: "読込中", ready: "未解析", running: "解析中", done: "完了", failed: "処理失敗"};
const message = (error: unknown) => error instanceof ApiError ? errorMessage(error) : error instanceof Error ? error.message : "処理できませんでした";
const choiceKey = (channel: string | null, metric: string) => channel ? `${channel}:${metric}` : metric;

/** No mock adapter or browser quantitation is reachable from the real workspace. */
export default function ApiWorkspace() {
  const adapter = useMemo(() => createApiAdapter(), []);
  const [workspace, setWorkspace] = useState("");
  const [intakeMode, setIntakeMode] = useState<"automatic" | "single">("automatic");
  const [grouping, setGrouping] = useState<Grouping | null>(null);
  const [items, setItems] = useState<Item[]>([]);
  const [selected, setSelected] = useState("");
  const [channel, setChannel] = useState("");
  const [region, setRegion] = useState<number>();
  const [comparisonOpened, setComparisonOpened] = useState(false);
  const [gridZoom, setGridZoom] = useState<number | null>(null);
  const [imageLayout, setImageLayout] = useState<"grid" | "single">("grid");
  const [hiddenPlanes, setHiddenPlanes] = useState<string[]>([]);
  const [view, setView] = useState<"image" | "figure" | "comparison">("image");
  const [metric, setMetric] = useState("area_px");
  const [width, setWidth] = useState(178);
  const [height, setHeight] = useState(76);
  const [axisLabel, setAxisLabel] = useState("");
  const [operation, setOperation] = useState("");
  const [notice, setNotice] = useState("");
  const [fieldReason, setFieldReason] = useState("");
  const [selectionState, setSelectionState] = useState<"current" | "changed" | "unknown">("current");
  const [busy, setBusy] = useState(false);
  const [figureBusy, setFigureBusy] = useState(false);
  const [figureError, setFigureError] = useState("");
  const [figures, setFigures] = useState<Record<string, SavedFigure>>({});
  const [previews, setPreviews] = useState<Record<string, string>>({});
  const [drawer, setDrawer] = useState(false);
  const [panel, setPanel] = useState(false);
  const [figureRetry, setFigureRetry] = useState(0);
  const [goal, setGoal] = useState("");
  const [draftBusy, setDraftBusy] = useState(false);
  const [draft, setDraft] = useState("");
  const [draftQuestions, setDraftQuestions] = useState<string[]>([]);
  const [draftRetry, setDraftRetry] = useState(false);
  const [fileCount, setFileCount] = useState(0);
  const files = useRef(new Map<string, File>());
  const added = useRef<AddedFile[]>([]);
  const busyRef = useRef(false);
  const stopped = useRef(false);
  const channelChoices = useRef(new Map<string, string>());
  const mounted = useRef(true);
  const fileInput = useRef<HTMLInputElement>(null);
  const folderInput = useRef<HTMLInputElement>(null);
  const previewUrls = useRef(new Map<string, string>());
  const figurePending = useRef(new Map<string, Promise<SavedFigure>>());
  const item = items.find(value => value.key === selected) ?? items[0];
  const registeredImages = items.filter(value => value.field);
  const gridChannel = channel || grouping?.channels[0]?.token || "";
  const imagePlanes = registeredImages.flatMap(value => value.field!.image_info.channels.map(plane => ({value, plane})));
  const compareImages = imageLayout === "grid" && imagePlanes.length > 1;
  const visiblePlanes = imagePlanes.filter(({value, plane}) => !hiddenPlanes.includes(value.field!.id + ":" + plane.channel_id));
  const availableChannels = item?.field?.image_info.channels.map(value => value.channel_id);
  const actualChannel = channel && (!availableChannels || availableChannels.includes(channel)) ? channel : availableChannels?.[0] || grouping?.channels[0]?.token || "";
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
  const loadPreviews = useCallback(async (field: ImportedField) => {
    for (const value of field.image_info.channels) {
      const key = `${field.id}:${value.channel_id}`;
      if (previewUrls.current.has(key)) continue;
      try {const blob = await adapter.preview(field.id, value.channel_id); if (!mounted.current) return;
        const url = URL.createObjectURL(blob); previewUrls.current.set(key, url); setPreviews(current => ({...current, [key]: url}));
      } catch {setNotice("画像プレビューを読み込めませんでした。画像を再表示してください。測定用の画像は保存されています。");}
    }
  }, [adapter]);
  const restored = useRef(false);
  useEffect(() => {
    mounted.current = true;
    folderInput.current?.setAttribute("webkitdirectory", "");

    const wid = new URLSearchParams(window.location.search).get("id");
    if (wid && !restored.current && API_CONFIGURED) {
      restored.current = true; busyRef.current = true; setBusy(true);
      void adapter.restore(wid).then(async saved => {
        setWorkspace(wid);
        const first = saved.fields[0];
        const channels = first?.image_info.channels.map(value => ({token: value.channel_id, stain: value.stain, role: null, evidence: "filename" as const})) ?? [];
        setGrouping({channels, fields: saved.fields.map(field => ({key: field.id, candidates: {}, files: Object.fromEntries(field.image_info.channels.map(value => [value.channel_id, {path: `${field.id}/${value.channel_id}.tif`, size: 0}]))})), issues: []});
        setFileCount(saved.fields.reduce((count, field) => count + field.image_info.channels.length, 0));
        const recovered: Item[] = [];
        for (const [index, field] of saved.fields.entries()) {
          const revisions = saved.revisions.filter(value => ["succeeded", "queued", "running"].includes(value.state) && value.config.recipe.version === "1.2.0" && value.config.field_ids.length === 1 && value.config.field_ids[0] === field.id).sort((a,b) => b.created-a.created);
          const entry = saved.selection.entries.find(value => value.field_id === field.id);
          if (!entry) {recovered.push({entryId: "", key: field.id, label: `視野 ${index + 1}`, field, orphan: true, status: "failed", error: "画像は保存されていますが、解析対象への登録が完了していません。", history: [], redo: []}); void loadPreviews(field); continue;}
          const revision = entry.revision_id ? revisions.find(value => value.id === entry.revision_id) : revisions.find(value => value.state !== "succeeded");
          const value: Item = {entryId: entry.id, exclusionReason: entry.exclusion_reason, key: field.id, label: `視野 ${index + 1}`, field, status: "ready", history: [], redo: []};
          if (revision) {try {
            const pending = saved.jobs.find(job => job.kind === "analysis" && job.revision_id === revision.id && ["queued", "running"].includes(job.state));
            value.result = pending ? await adapter.resume(wid, pending, field.id) : await adapter.readResult(revision.id, field.id);
            value.recipe = revision.config.recipe; value.status = "done";
          } catch (error) {value.status = "failed"; value.error = message(error);}}
          if (!revision && revisions.filter(candidate => candidate.state === "succeeded").length > 0) {value.revisionChoices = revisions.filter(candidate => candidate.state === "succeeded"); value.status = "failed"; value.error = "採用する解析版を選択してください。";}
          if (!revision && !value.revisionChoices && saved.revisions.some(candidate => candidate.config.field_ids.includes(field.id) && ["failed", "cancelled"].includes(candidate.state))) {value.status = "failed"; value.error = "この視野の解析が完了していません。再実行または理由付き除外を選択してください。";}
          recovered.push(value); void loadPreviews(field);
        }
        for (const entry of saved.selection.entries.filter(value => !value.field_id)) recovered.push({entryId: entry.id, key: entry.id, label: "未登録の視野", exclusionReason: entry.exclusion_reason, status: "failed", error: "画像の登録が完了していません。再登録または理由を入力して除外してください。", history: [], redo: []});
        setItems(recovered); setSelected(recovered[0]?.key ?? "");
        const recipe = recovered.find(value => value.recipe)?.recipe;
        if (recipe) setGrouping(current => current ? chooseNuclearChannel(current, recipe.defining_channel_id) : current);
      }).catch(error => setNotice(message(error))).finally(() => {busyRef.current = false; setBusy(false);});
    }
    return () => {mounted.current = false;};
  }, [adapter, loadPreviews]);
  useEffect(() => () => {for (const url of previewUrls.current.values()) URL.revokeObjectURL(url);}, []);

  const selectionIdentity = JSON.stringify(adapter.selection());
  useEffect(() => {
    if (!workspace) return;
    let active = true; let checking = false;
    const refresh = async () => {
      if (checking || busyRef.current || document.visibilityState === "hidden") return;
      checking = true;
      try {const current = await adapter.isSelectionCurrent(workspace); if (active && !busyRef.current) setSelectionState(current ? "current" : "changed");}
      catch {if (active && !busyRef.current) setSelectionState("unknown");}
      finally {checking = false;}
    };
    void refresh();
    const timer = window.setInterval(() => void refresh(), 2000);
    window.addEventListener("focus", refresh);
    document.addEventListener("visibilitychange", refresh);
    return () => {active = false; window.clearInterval(timer); window.removeEventListener("focus", refresh); document.removeEventListener("visibilitychange", refresh);};
  }, [adapter, workspace, selectionIdentity]);

  async function addFiles(list: FileList | File[]) {
    if (busyRef.current || draftBusy || selectionState !== "current") return;
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
        fresh.push({path, size: file.size, inputMode: await tiffInputMode(file), sha256: Array.from(new Uint8Array(digest), value => value.toString(16).padStart(2, "0")).join("")});
        freshFiles.set(path, file);
      }
      const next = groupFiles([...added.current, ...fresh], intakeMode);
      if (grouping && grouping.channels.length && JSON.stringify(grouping.channels.map(value => value.token).sort()) !== JSON.stringify(next.channels.map(value => value.token).sort())) throw new Error("チャンネル構成が異なります。新しいワークスペースで追加してください。");
      if (grouping) next.channels = next.channels.map(value => grouping.channels.find(previous => previous.token === value.token) || value);
      added.current.push(...fresh); for (const [path, file] of freshFiles) files.current.set(path, file);
      setFileCount(current => current + fresh.length);
      for (const issue of next.issues) {if (issue.kind === "duplicate_channel") {const chosen = channelChoices.current.get(`${issue.field}:${issue.token}`); const source = added.current.find(value => value.path === chosen); const field = next.fields.find(value => value.key === issue.field); if (source && field) field.files[issue.token] = source;}}
      setGrouping(next);
      let wid = workspace;
      if (!wid && next.fields.length) {const created = await adapter.create(); wid = created.id; setWorkspace(wid); window.history.replaceState(null, "", `/workspace?id=${encodeURIComponent(wid)}`);}
      const pending = next.fields.filter(field => !items.some(value => value.key === field.key && value.field));
      const pendingItems: Item[] = pending.map(field => ({entryId: items.find(value => value.key === field.key)?.entryId || crypto.randomUUID(), key: field.key, label: field.key.split("/").at(-1) || field.key, status: "importing", history: [], redo: []}));
      setItems(current => [...current.filter(value => !pending.some(field => field.key === value.key)), ...pendingItems]);
      if (!selected && pending[0]) setSelected(pending[0].key);
      for (const field of pending) {
        try {
          await adapter.registerImport(wid, pendingItems.find(value => value.key === field.key)!.entryId);
          if (next.issues.some(issue => issue.kind === "duplicate_channel" && issue.field === field.key && !field.files[issue.token])) throw new Error("同じチャンネルの候補が複数あります。取り込み設定で使用する画像を指定してください。");
          const duplicate = next.issues.some(issue => issue.kind === "duplicate_content" && Object.values(field.files).some(file => issue.paths.includes(file.path)));
          if (duplicate) throw new Error("同じ内容の画像が複数あります。読み込み結果で重複を確認してください。");
          const uploaded = await adapter.upload(wid, field, next.channels, files.current, pendingItems.find(value => value.key === field.key)!.entryId); update(field.key, {field: uploaded, status: "ready", error: undefined}); void loadPreviews(uploaded);}
        catch (error) {update(field.key, {status: "failed", error: message(error)});}
      }
      if (unsupported) setNotice(`TIFF以外の ${unsupported} 件は追加していません。`);
    } catch (error) {setNotice(message(error));}
    finally {busyRef.current = false; setBusy(false);}
  }

  async function recoverImportedField(value: Item) {
    if (busyRef.current || !value.field || !workspace) return;
    busyRef.current = true; setBusy(true);
    try {const entry = await adapter.recoverField(workspace, value.field.id); update(value.key, {entryId: entry.id, orphan: false, status: "ready", error: undefined});}
    catch (error) {setNotice(message(error));}
    finally {busyRef.current = false; setBusy(false);}
  }

  async function run() {
    if (busyRef.current || selectionState !== "current" || nuclear.length !== 1 || !workspace) return;
    busyRef.current = true; setBusy(true); stopped.current = false; setNotice("");
    const recipe = nuclearRecipe(nuclear[0]);
    try {
      for (const value of items.filter(value => value.field && !value.orphan && !value.result && !value.exclusionReason)) {
        if (stopped.current) break;
        if (!value.field!.image_info.channels.some(channel => channel.channel_id === recipe.defining_channel_id)) {update(value.key, {status: "failed", error: "核検出チャンネルがありません。画像を追加するか、この視野を除外してください。"}); continue;}
        setSelected(value.key); setChannel(recipe.defining_channel_id); setView("image"); setOperation(`${value.label}：解析の受付中`);
        update(value.key, {status: "running", error: undefined, recipe});
        try {const result = await adapter.run(workspace, value.field!.id, recipe, state => setOperation(`${value.label}：${state === "queued" ? "解析の開始待ち" : state === "running" ? "核の検出・輝度の測定中" : state === "reading_results" || state === "succeeded" ? "測定結果を読み込み中" : state}`)); update(value.key, {status: "done", result, history: [], redo: []});}
        catch (error) {update(value.key, {status: "failed", error: message(error)});}
      }
    } finally {setOperation(""); busyRef.current = false; setBusy(false); if (stopped.current) setNotice("中断しました。完了した視野は保存されています。");}
  }

  async function correct(kind: "exclude" | "delete" | "undo" | "redo") {
    if (busyRef.current || selectionState !== "current" || !item?.result || !item.recipe || !workspace) return;
    const value = item; busyRef.current = true; setBusy(true); setNotice("");
    try {
      const target = kind === "undo" ? value.history.at(-1) : kind === "redo" ? value.redo.at(-1) : null;
      const result = target ? await adapter.selectRevision(workspace, target.revision, value.field!.id)
        : region !== undefined && (kind === "exclude" || kind === "delete") ? await adapter.correct(workspace, value.result!, kind, region, value.recipe!) : null;
      if (result) {update(value.key, {result,
        history: kind === "undo" ? value.history.slice(0, -1) : [...value.history, value.result!],
        redo: kind === "undo" ? [...value.redo, value.result!] : kind === "redo" ? value.redo.slice(0, -1) : []});}
    } catch (error) {setNotice(message(error));}
    finally {busyRef.current = false; setBusy(false);}
  }

  async function adoptSavedRevision(rid: string) {
    if (!item?.field || busyRef.current || selectionState !== "current") return;
    const recipe = item.revisionChoices?.find(value => value.id === rid)?.config.recipe;
    if (!recipe) return;
    busyRef.current = true; setBusy(true); setNotice("");
    try {const result = await adapter.selectRevision(workspace, rid, item.field.id); update(item.key, {result, recipe, status: "done", error: undefined, revisionChoices: undefined});}
    catch (error) {setNotice(message(error));}
    finally {busyRef.current = false; setBusy(false);}
  }

  async function excludeField(reason: string | null) {
    if (!item || busyRef.current || selectionState !== "current" || (reason !== null && !reason.trim())) return;
    busyRef.current = true; setBusy(true); setNotice("");
    try {await adapter.excludeField(workspace, item.entryId, reason?.trim() ?? null); update(item.key, {exclusionReason: reason?.trim() ?? null}); setFieldReason("");}
    catch (error) {setNotice(message(error));}
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

  async function requestDraft(retryFailed = false) {
    if ((!goal.trim() && !items.length) || draftBusy || busyRef.current) return;
    busyRef.current = true;
    setDraftBusy(true); setDraft(""); setDraftQuestions([]); setDraftRetry(false);
    try {
      let wid = workspace;
      if (!wid) {const created = await adapter.create(); wid = created.id; setWorkspace(wid); window.history.replaceState(null, "", `/workspace?id=${encodeURIComponent(wid)}`);}
      const response = await adapter.draft(wid, goal, retryFailed); setDraft(response.proposal.draft.rationale); setDraftQuestions(response.proposal.draft.missing_information);}
    catch (error) {if (error instanceof ApiError && error.code === "proposal_explicit_retry_required") {setDraftRetry(true); setDraft("前回のリクエストが完了していません。再送すると追加のAPI利用料が発生する場合があります。");} else setDraft(message(error));}
    finally {busyRef.current = false; setDraftBusy(false);}
  }
  const composer = <section className={styles.composer} aria-label="解析の指示">
    {operation && <p role="status" className={styles.operationStatus}>{operation}</p>}
    {!busy && item?.result && <p className={styles.operationStatus}>検出済み：{item.result.masks.regions.length} 領域 · 画像上の輪郭をクリックして修正できます。<button className={styles.secondary} onClick={() => setView("figure")}>グラフを表示</button></p>}
    {(draft || draftBusy) && <div className={styles.response} aria-live="polite">{draftBusy ? <p>解析方法を作成しています…</p> : <><p>{draft}</p>{draftQuestions.length > 0 && <ul>{draftQuestions.map((question, index) => <li key={index}>{question}</li>)}</ul>}</>}{draftRetry && <button className={styles.secondary} disabled={draftBusy || busy} onClick={() => void requestDraft(true)}>再送信（追加料金が発生する場合があります）</button>}</div>}
    <form onSubmit={event => {event.preventDefault(); void requestDraft();}}>
      <label htmlFor="analysis-instruction">解析の指示</label>
      <textarea id="analysis-instruction" value={goal} maxLength={1000} placeholder="画像を追加するか、行いたい解析を入力してください" onChange={event => {setGoal(event.target.value); setDraftRetry(false);}}/>
      {items.some(value => value.field && !value.orphan && !value.result && !value.exclusionReason) && grouping && <div className={styles.composerActions}><label htmlFor="nuclear-channel">核検出</label><select id="nuclear-channel" value={nuclear.length === 1 ? nuclear[0].token : ""} disabled={busy || draftBusy} onChange={event => {setGrouping(chooseNuclearChannel(grouping, event.target.value)); setChannel(event.target.value); setView("image"); setNotice("");}}><option value="" disabled>核を染めたチャンネル</option>{grouping.channels.map(value => <option key={value.token} value={value.token}>{value.stain || value.token}</option>)}</select><button type="button" className={styles.primary} disabled={busy || draftBusy} onClick={() => void run()}>一括解析</button></div>}
      {items.some(value => value.status === "failed" && !value.exclusionReason) && <details><summary>処理できなかった画像 {items.filter(value => value.status === "failed" && !value.exclusionReason).length} 件</summary>{items.filter(value => value.status === "failed" && !value.exclusionReason).map(value => <p key={value.key}><button type="button" className={styles.secondary} onClick={() => setSelected(value.key)}>{value.label}</button> {value.error}</p>)}</details>}
      <div className={styles.composerActions}><button type="button" className={styles.secondary} disabled={busy || draftBusy || !API_CONFIGURED} onClick={() => fileInput.current?.click()}>画像を追加</button><button type="button" className={styles.secondary} disabled={busy || draftBusy || !API_CONFIGURED} onClick={() => folderInput.current?.click()}>フォルダを追加</button><span>{items.length ? items.filter(value => value.field).length + " 視野を登録済み" : "TIFF / 複数選択可"}</span><button type="submit" className={styles.primary} disabled={(!goal.trim() && !items.length) || draftBusy || busy || draftRetry}>{draftBusy ? "処理中…" : "送信"}</button></div>
      {!items.length && <details><summary>画像の構成</summary><select aria-label="画像の構成" value={intakeMode} disabled={busy} onChange={event => setIntakeMode(event.target.value as "automatic" | "single")}><option value="automatic">チャンネル別画像をまとめる</option><option value="single">同じ染色の画像</option></select></details>}
    </form><small>送信内容：入力した指示と画像の構成情報。画像・ファイル名・測定値はOpenAIへ送りません。</small>
  </section>;
  const fileInputs = <><input ref={fileInput} type="file" multiple accept=".tif,.tiff" hidden data-testid="file-input" onChange={event => {if (event.target.files) void addFiles(event.target.files); event.target.value = "";}}/><input ref={folderInput} type="file" multiple hidden data-testid="folder-input" onChange={event => {if (event.target.files) void addFiles(event.target.files); event.target.value = "";}}/></>;
  const addActions = <><button className={styles.primary} disabled={busy || draftBusy || !API_CONFIGURED} onClick={() => fileInput.current?.click()}>画像を追加</button><button className={styles.secondary} disabled={busy || draftBusy || !API_CONFIGURED} onClick={() => folderInput.current?.click()}>フォルダを追加</button></>;
  const rows = item?.result?.rows.filter(row => row.channel_id === actualChannel) ?? [];
  const excluded = new Set(item?.result?.exclusions.filter(value => value.field_id === item.field?.id && value.region_id !== null).map(value => value.region_id));
  const shape = item?.field?.image_info.shape;
  const displayRgb = item?.field?.image_info.input_mode === "display-rgb";
  const savedFiles = figure ? adapter.figureFiles(figure) : null;
  return <main className={[styles.shell, !items.length ? styles.emptyWorkspace : ""].join(" ")} onDragOver={event => event.preventDefault()} onDrop={event => {event.preventDefault(); void addFiles(event.dataTransfer.files);}}>
    <header className={styles.header}><Link href="/" className={styles.brand}>cytellect</Link><h1 className={styles.title}>画像解析</h1><p role="status">{busy ? "処理中" : `${items.filter(value => value.result).length} / ${items.length} 視野`}</p><div className={styles.headerActions}>{addActions}<button className={styles.secondary} aria-label="操作パネル" aria-pressed={panel} onClick={() => setPanel(!panel)}>設定</button>{busy && <button className={styles.secondary} onClick={() => {stopped.current = true; setNotice("現在の視野を完了してから中断します。");}}>中断</button>}</div></header>
    {selectionState !== "current" && <p className={styles.banner} role="status">{selectionState === "changed" ? "別のタブで採用状態が更新されました。表示中の測定値・図は旧版です。" : "現在の採用状態を確認できません。表示中の結果は保存済みの版です。"} <button onClick={() => window.location.reload()}>最新の採用状態を読み込む</button></p>}
    {notice && <p className={styles.banner} role="status">{notice}</p>}
    {!API_CONFIGURED && <p className={styles.banner}>解析サーバーが設定されていません。ローカル版はランチャーから開いてください。 <Link href="/product#download">Windows版・セットアップ</Link></p>}
    <div className={[styles.layout, panel && view !== "comparison" ? "" : styles.layoutNoPanel].join(" ")}>
      <nav className={styles.sidebar} aria-label="画像とグラフ"><h2>画像</h2>{!items.length && <p>フォルダまたは複数画像を追加してください。</p>}<ul className={styles.fieldList}>{items.map(value => <li key={value.key}><button aria-current={item?.key === value.key ? "true" : undefined} onClick={() => {setSelected(value.key); setRegion(undefined);}}><span>{value.label}</span><span>{value.exclusionReason ? "除外" : statusLabel[value.status]}{value.field ? ` · ${value.field.image_info.channels.length} ch` : ""}</span></button></li>)}</ul><h2>表示</h2><button className={styles.secondary} onClick={() => setView("image")}>画像</button><button className={styles.secondary} onClick={() => setView("figure")}>グラフ</button><button className={styles.secondary} disabled={!items.some(value => value.result)} onClick={() => {setComparisonOpened(true); setView("comparison");}}>群を比較</button></nav>
      <section className={styles.center} aria-label="表示">{!items.length && <section className={styles.empty}><h2>画像をここにドロップ</h2><p>TIFF画像をまとめて取り込み、全視野を同じ条件で解析できます。</p><div className={styles.actions}>{addActions}</div><p>画像と結果は最後の操作から24時間保存されます。</p></section>}

        {panel && item && !item.orphan && <details className={styles.banner} aria-label="視野の除外"><summary>視野の操作</summary>{item.exclusionReason ? <><p>除外理由：{item.exclusionReason}</p><button disabled={busy} onClick={() => void excludeField(null)}>視野の除外を取り消す</button></> : <><label>解析から外す理由<input value={fieldReason} maxLength={300} onChange={event => setFieldReason(event.target.value)}/></label><button disabled={busy || !fieldReason.trim()} onClick={() => void excludeField(fieldReason)}>この視野を解析から外す</button></>}</details>}
        {!!item?.revisionChoices?.length && <label>採用する解析版<select value="" disabled={busy} onChange={event => void adoptSavedRevision(event.target.value)}><option value="" disabled>保存結果を選択</option>{item.revisionChoices.map(value => <option key={value.id} value={value.id}>{new Date(value.created * 1000).toLocaleString("ja-JP")} · 除外 {value.config.exclusions?.length ?? 0} 件 · {value.id}</option>)}</select></label>}
        {item?.error && <p className={styles.banner} role="alert">{item.error}{item.orphan && <button className={styles.secondary} disabled={busy} onClick={() => void recoverImportedField(item)}>この画像を解析対象に登録</button>}{!item.field && <button className={styles.secondary} disabled={busy} onClick={() => files.current.size ? void addFiles([]) : fileInput.current?.click()}>{fileCount ? "登録を再試行" : "画像を追加して再登録"}</button>}</p>}
        <div className={styles.comparisonMount} hidden={view !== "comparison"}>{comparisonOpened && <WorkspaceComparison workspace={workspace} sources={items.flatMap(value => value.result && value.field && !value.orphan && !value.exclusionReason ? [{field: value.field.id, revision: value.result.revision, label: value.label, result: value.result, metadata: value.field.metadata}] : [])} pendingFields={items.filter(value => !value.result && !value.exclusionReason).length} selection={adapter.selection()} selectionChanged={selectionState !== "current"} blocked={busy || selectionState !== "current"} options={metricOptions} regionSet={item?.recipe?.region_set_id || "nuclei"} onInspect={field => {const target = items.find(value => value.field?.id === field); if (target) {setSelected(target.key); setView("image");}}}/>}</div>{view === "comparison" ? null : view === "image" && items.length ? <div className={styles.imageStage}><div className={styles.imageToolbar}>{imagePlanes.length > 1 && <><label>表示<select aria-label="画像の表示" value={imageLayout} onChange={event => setImageLayout(event.target.value as "grid" | "single")}><option value="grid">並べる</option><option value="single">1画像</option></select></label>{compareImages && <details className={styles.imagePicker}><summary>表示する画像</summary>{imagePlanes.map(({value, plane}) => {const id = value.field!.id + ":" + plane.channel_id; return <label key={id}><input type="checkbox" checked={!hiddenPlanes.includes(id)} onChange={event => setHiddenPlanes(previous => event.target.checked ? previous.filter(key => key !== id) : [...previous, id])}/>{plane.stain || plane.label} · {value.label}</label>;})}</details>}</>}<strong>{item?.label}{displayRgb ? " · RGB表示画像" : ""}</strong><button className={styles.secondary} disabled={!item?.field || busy} onClick={() => item?.field && void loadPreviews(item.field)}>画像を再表示</button><div className={styles.segmented} hidden={compareImages}>{grouping?.channels.map(value => <button key={value.token} role="radio" aria-checked={(compareImages ? gridChannel : actualChannel) === value.token} onClick={() => setChannel(value.token)}>{value.stain || value.token}</button>)}</div></div>{compareImages ? <div className={styles.imageGrid} data-count={visiblePlanes.length}>{visiblePlanes.map(({value, plane}) => {const field = value.field!; const rejected = new Set(value.result?.exclusions.filter(exclusion => exclusion.field_id === field.id).map(exclusion => exclusion.region_id)); return <section className={styles.imageTile} data-active={item?.key === value.key} key={field.id + ":" + plane.channel_id}><button className={styles.tileHeading} onClick={() => {setSelected(value.key); setChannel(plane.channel_id); setRegion(undefined);}}>{plane.stain || plane.label} · {value.label} · {value.exclusionReason ? "除外" : statusLabel[value.status]}</button><FieldImage controlledZoom={gridZoom} onZoomChange={setGridZoom} src={previews[field.id + ":" + plane.channel_id] ?? null} size={{height: field.image_info.shape[0], width: field.image_info.shape[1]}} outlines={(value.result?.masks.regions ?? []).map(mask => ({outline: {id: String(mask.id), points: mask.points}, state: rejected.has(mask.id) ? "excluded" as const : "included" as const}))} analyzed={!!value.result} selected={item?.key === value.key ? region : undefined} onSelect={id => {setSelected(value.key); setChannel(plane.channel_id); setRegion(id);}} label={value.label + " · " + plane.channel_id}/></section>;})}</div> : <FieldImage src={item?.field ? previews[`${item.field.id}:${actualChannel}`] ?? null : null} size={shape ? {height: shape[0], width: shape[1]} : null} outlines={(item?.result?.masks.regions ?? []).map(value => ({outline: {id: String(value.id), points: value.points}, state: excluded.has(value.id) ? "excluded" as const : "included" as const}))} analyzed={!!item?.result} selected={region} onSelect={setRegion} label={`${item?.label || "視野"}の画像`}/>}</div>
          : <section className={styles.figureStage}>{figureBusy && !figure && <p role="status">測定値から図を作成しています。</p>}{figureError && <div role="alert"><p>{figureError} 測定値は保存されています。</p><button className={styles.secondary} onClick={() => setFigureRetry(value => value + 1)}>図を再作成</button></div>}{figure && savedFiles && <><p>未確認の検出結果 · {item?.label} · {metricOptions.find(value => value.key === metric)?.label} · 1点は1領域</p><SavedInteractiveFigure figure={figure} label={item?.label || "視野"} onSelect={selectedRegion => {setRegion(selectedRegion); setView("image");}}/>{(savedFiles.view.kind === "ready" || savedFiles.view.kind === "legacy") && <details><summary>書き出し図</summary>{savedFiles.view.pages.map(page => <PrivateFigure key={`${figure.job}:${page.files.png}`} path={`/v1/jobs/${figure.job}/files/${page.files.png}`}/>)}</details>}{savedFiles.view.kind === "tables_only" && <p>図を生成できませんでした。測定表は保存されています。</p>}<div className={styles.actions}>{savedFiles.files.map(file => <button className={styles.secondary} key={file} onClick={() => void download(`/v1/jobs/${figure.job}/files/${file}`, file).catch(error => setNotice(message(error)))}>{file} ↓</button>)}</div></>}{!item?.result && <p>解析後にグラフを表示します。</p>}</section>}
        {composer}
      </section>
      {panel && view !== "comparison" && <aside className={styles.panel} aria-label="選択対象の操作">
        {!items.some(value => value.result) && grouping && <section className={styles.panelSection}><h2>解析設定</h2><p role="status">登録済み {items.filter(value => value.field).length} / {items.length} 視野{busy ? " · 処理中" : ""}</p>{items.some(value => value.status === "failed") && <div role="alert">{items.filter(value => value.status === "failed").map(value => <p key={value.key}><button className={styles.secondary} onClick={() => setSelected(value.key)}>{value.label}</button> {value.error}</p>)}</div>}<details><summary>画像の構成</summary><ImportSummary grouping={grouping} files={fileCount}/></details><NuclearChoice grouping={grouping} preview={token => item?.field ? previews[`${item.field.id}:${token}`] ?? null : null} onChoose={token => setGrouping(chooseNuclearChannel(grouping, token))}/><p>核の検出・面積と輝度の測定・グラフ作成</p><details><summary>測定条件</summary><p>輝度は背景補正前の値です。RGB表示画像は表示輝度を測定します。</p></details><button className={styles.primary} disabled={busy || nuclear.length !== 1 || !items.some(value => value.field)} onClick={() => void run()}>解析を実行</button></section>}

        {items.some(value => value.field && !value.result) && items.some(value => value.result) && <button className={styles.primary} disabled={busy || nuclear.length !== 1} onClick={() => void run()}>未完了の視野を解析</button>}
        {item?.result && <><section className={styles.panelSection}><h3>領域を修正</h3><p>{region ? `領域 ${region}${excluded.has(region) ? "（除外）" : ""}` : "画像または測定表で領域を選択"}</p><div className={styles.actions}><button className={styles.secondary} disabled={busy || !region || excluded.has(region)} onClick={() => void correct("exclude")}>対象から除外</button><button className={styles.secondary} disabled={busy || !region} onClick={() => void correct("delete")}>領域を削除</button><button className={styles.secondary} disabled={busy || !item?.history.length} onClick={() => void correct("undo")}>元に戻す</button><button className={styles.secondary} disabled={busy || !item?.redo.length} onClick={() => void correct("redo")}>やり直す</button></div>{busy && item?.result && <p>更新中。直前の保存結果を表示しています。</p>}</section>
        <section className={styles.panelSection}><h3>グラフ設定</h3><label>測定項目<select value={metric} onChange={event => setMetric(event.target.value)}>{metricOptions.map(value => <option key={value.key} value={value.key}>{value.label}</option>)}</select></label><label>幅 (mm)<select value={width} onChange={event => setWidth(Number(event.target.value))}><option value={89}>89</option><option value={178}>178</option><option value={183}>183</option></select></label><label>高さ (mm)<input type="number" min={40} max={170} value={height} onChange={event => setHeight(Math.min(170, Math.max(40, Number(event.target.value) || 76)))}/></label><label>縦軸の名前<input value={axisLabel} maxLength={120} onChange={event => setAxisLabel(event.target.value)}/></label><p className={styles.hint}>設定変更は図だけを作り直します。原画像の測定値は変わりません。</p></section></>}
        <details className={styles.panelSection}><summary>取り込み設定</summary><label>画像の構成<select value={intakeMode} disabled={busy || items.length > 0} onChange={event => setIntakeMode(event.target.value as "automatic" | "single")}><option value="automatic">チャンネル別画像を視野ごとにまとめる</option><option value="single">同じ染色：1ファイルを1視野にする</option></select></label><p>ファイル名の変更は不要です。</p>{items.length > 0 && <Link href="/">別の画像構成で新しく取り込む</Link>}{grouping?.issues.filter(issue => issue.kind === "duplicate_channel").map(issue => issue.kind === "duplicate_channel" && <fieldset key={issue.field + issue.token}><legend>{issue.token} の画像</legend>{issue.paths.map(path => <button key={path} disabled={busy || draftBusy} className={styles.secondary} onClick={() => {channelChoices.current.set(issue.field + ":" + issue.token, path); void addFiles([]);}}>{path.split("/").at(-1)} を使用</button>)}</fieldset>)}</details>
        {item?.result && <details className={styles.panelSection}><summary>保存結果の出典</summary><p>解析版：{item.result.revision}</p><p>マスク版：{item.result.masks.metadata.mask_revision_id}</p><p>原値測定。検出結果の品質確認前。</p></details>}
      </aside>}
      <section className={[styles.drawer, drawer ? styles.drawerOpen : ""].join(" ")} aria-label="測定値"><button className={styles.drawerToggle} onClick={() => setDrawer(!drawer)} aria-expanded={drawer}>測定値 · {item?.label} · {rows.length} 領域</button>{drawer && <div className={styles.tableWrap}><table className={styles.table}><thead><tr><th>領域</th><th>面積 / px²</th><th>平均{displayRgb ? "（表示輝度）" : "（原値）"}</th><th>中央値{displayRgb ? "（表示輝度）" : "（原値）"}</th><th>積算{displayRgb ? "（表示輝度）" : "（原値）"}</th><th>採否</th></tr></thead><tbody>{rows.map(row => <tr key={row.region_id}><th><button className={styles.rowButton} aria-label={`領域 ${row.region_id} を選択`} onClick={() => {setRegion(row.region_id); setView("image");}}>{row.region_id}</button></th>{[row.area_px, row.mean, row.median, row.integrated].map((value, index) => <td key={index}>{value === null ? "—" : Number(value.toPrecision(6))}</td>)}<td>{excluded.has(row.region_id) ? "除外" : "採用"}</td></tr>)}</tbody></table></div>}</section>
    </div>{fileInputs}
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
