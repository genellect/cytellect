"use client";
import {Suspense, useCallback, useEffect, useMemo, useRef, useState} from "react";
import Link from "next/link";
import {useSearchParams} from "next/navigation";
import {routeIdentity, promoteIdentity, resolveIdentity} from "@/lib/workspace/route-identity";
import {API_CONFIGURED, ApiError, errorMessage} from "@/lib/api";
import {automaticBackground, createApiAdapter, nuclearRecipe, rawMeasurement, type CompartmentSummaryFile, type GfpGateResult, type ValidatedProposal, type MaskOperation, type ImportedField, type Recipe, type SavedResult} from "@/lib/workspace/api-adapter";
import {chooseNuclearChannel, groupFiles, isSupportedImage, restoredChannels, type AddedFile, type Grouping} from "@/lib/workspace/grouping";
import {targetOf, validTargetResults, type Target} from "@/lib/workspace/target-results";
import {tiffInputMode} from "@/lib/workspace/tiff-intake";
import {nucleolarDetectorV2, nucleolarSourceText, type NucleolarDefinition, type NucleolarSource} from "@/lib/workspace/nucleolar-definition";
import type {Point} from "@/lib/types";
import {FieldImage} from "./FieldImage";
import {WorkspaceFigureEditor} from "./WorkspaceFigureEditor";
import {WorkspaceComparison} from "./WorkspaceComparison";
import {MethodPanel, type MethodStep} from "./MethodPanel";
import {ImportSummary} from "./ProposalPanels";
import {MethodSheet, methodReferences, type MethodDetail} from "./MethodSheet";
import styles from "./analysis-workspace.module.css";

const compartmentTargetsEnabled = true;
const targetLabel: Record<Target, string> = {nuclei: "核", gfp: "GFP陽性領域", ncl: "NCL陽性領域（画像全体）", nucleoli: "核小体", nucleoplasm: "核質"};
const isCompartment = (target: Target) => target === "nucleoli" || target === "nucleoplasm";
const signalKey = (target: Target): "gfp" | "ncl" => target === "gfp" ? "gfp" : "ncl";
type Item = {targetResults?: Partial<Record<Target, {result: SavedResult; recipe: Recipe}>>; orphan?: boolean; revisionChoices?: Array<{id: string; created: number; config: {recipe: Recipe; exclusions?: SavedResult["exclusions"]}}> ; entryId: string; exclusionReason?: string | null; key: string; label: string; field?: ImportedField; status: "importing" | "ready" | "running" | "done" | "failed"; error?: string; result?: SavedResult; recipe?: Recipe; history: SavedResult[]; redo: SavedResult[]};
const statusLabel = {importing: "読込中", ready: "未解析", running: "解析中", done: "完了", failed: "処理失敗"};
const message = (error: unknown) => error instanceof ApiError ? errorMessage(error) : error instanceof Error ? error.message : "処理できませんでした";
const choiceKey = (channel: string | null, metric: string) => channel ? `${channel}:${metric}` : metric;

/** No mock adapter or browser quantitation is reachable from the real workspace. */
export default function ApiWorkspace() {
  return <Suspense fallback={<p role="status">ワークスペースを読み込み中…</p>}><WorkspaceRoute/></Suspense>;
}
function WorkspaceRoute() {
  const route = useSearchParams().get("id") || "";
  const [identity, setIdentity] = useState(() => routeIdentity(route));
  const current = resolveIdentity(identity, route);
  if (current !== identity) setIdentity(current);
  // The address follows a session's own creation after the identity has been promoted.
  useEffect(() => {if (current.pendingUrl) window.history.replaceState(null, "", `/workspace?id=${encodeURIComponent(current.route)}`);}, [current.pendingUrl, current.route]);
  return <WorkspaceSession key={current.generation} initialWorkspace={current.initial} onCreated={id => setIdentity(previous => promoteIdentity(previous, id))}/>;
}
function WorkspaceSession({initialWorkspace, onCreated}: {initialWorkspace: string; onCreated: (id: string) => void}) {
  const adapter = useMemo(() => createApiAdapter(), []);
  const [workspace, setWorkspace] = useState("");
  const [intakeMode, setIntakeMode] = useState<"automatic" | "single">("automatic");
  const [grouping, setGrouping] = useState<Grouping | null>(null);
  const [items, setItems] = useState<Item[]>([]);
  const itemsRef = useRef<Item[]>([]);
  useEffect(() => {itemsRef.current = items;}, [items]);
  const [selected, setSelectedState] = useState("");
  const [channel, setChannelState] = useState("");
  const [displayTarget, setDisplayTarget] = useState<Target>("nuclei");
  const [signalMethod, setSignalMethod] = useState<"otsu" | "manual">("otsu");
  const [signalThreshold, setSignalThreshold] = useState(0);
  const [compartmentSettings, setCompartmentSettings] = useState({smoothing:0, minimumArea:1, maximumArea:null as number|null, split:false});
  const [nuclearMaxSide, setNuclearMaxSide] = useState<number | null>(null);
  // Nucleolar definition source (detector 2.0.0): DNA-poor holes by default; the researcher can change it.
  const [nucleolarDefinition, setNucleolarDefinition] = useState<NucleolarDefinition>({source: "dapi_poor", marker: "", pixelUm: null, relative: 0.7});
  const [methodSheet, setMethodSheet] = useState(false);
  const [definitionOpen, setDefinitionOpen] = useState(false);
  const [, setSelectionTick] = useState(0);
  const [proposal, setProposal] = useState<ValidatedProposal | null>(null);
  const [background, setBackground] = useState<"automatic" | "raw">("raw");
  const [gfp, setGfp] = useState<{enabled: boolean; channel: string; controls: string[]; result: GfpGateResult | null; error: string}>({enabled: false, channel: "", controls: [], result: null, error: ""});
  const [aiTrialStarted, setAiTrialStarted] = useState(false);
  const [summary, setSummary] = useState<{revision: string; value: CompartmentSummaryFile} | null>(null);
  const [signalChannels, setSignalChannels] = useState({gfp: "", ncl: ""});
  const [region, setRegion] = useState<number>();
  const [comparisonOpened, setComparisonOpened] = useState(false);
  const [gridZoom, setGridZoom] = useState<number | null>(null);
  const [imageLayout, setImageLayoutState] = useState<"grid" | "single" | "all">("single");
  const [hiddenPlanes, setHiddenPlanes] = useState<string[]>([]);
  const [view, setView] = useState<"image" | "figure" | "comparison">("image");
  const [metric, setMetric] = useState("area_px");
  const [operation, setOperation] = useState("");
  const [notice, setNotice] = useState("");
  const [fieldReason, setFieldReason] = useState("");
  const [selectionState, setSelectionState] = useState<"current" | "changed" | "unknown">("current");
  const [busy, setBusy] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const figureBusy = false;
  const [previews, setPreviews] = useState<Record<string, string>>({});
  const [drawer, setDrawer] = useState(false);
  const [panel, setPanel] = useState(false);
  const [aiOpen, setAiOpen] = useState(false);
  const [runRange, setRunRange] = useState<"selected"|"all">("selected");
  const [goal, setGoal] = useState("");
  const [draftBusy, setDraftBusy] = useState(false);
  const [draft, setDraft] = useState("");
  const [draftQuestions, setDraftQuestions] = useState<string[]>([]);
  const [draftRetry, setDraftRetry] = useState(false);
  const [fileCount, setFileCount] = useState(0);
  const files = useRef(new Map<string, File>());
  const added = useRef<AddedFile[]>([]);
  const busyRef = useRef(false);
  const [drawing, setDrawing] = useState(false);
  const drawingRef = useRef<{key:string; revision:string; channel:string} | null>(null);
  const setSelected = (value:string) => {if (!drawingRef.current) setSelectedState(value);};
  const setChannel = (value:string) => {if (!drawingRef.current) setChannelState(value);};
  const setImageLayout = (value:"grid"|"single"|"all") => {if (!drawingRef.current) setImageLayoutState(value);};
  const needsReconcile = useRef(false);
  const stopped = useRef(false);
  const channelChoices = useRef(new Map<string, string>());
  const mounted = useRef(true);
  const fileInput = useRef<HTMLInputElement>(null);
  const folderInput = useRef<HTMLInputElement>(null);
  const previewUrls = useRef(new Map<string, string>());
  const item = items.find(value => value.key === selected && !value.exclusionReason) ?? items.find(value => !value.exclusionReason);
  // A failed or excluded field keeps its reason and its undo visible; the image area shows analysable fields only.
  const selectedItem = items.find(value => value.key === selected);
  const fieldActions = selectedItem && !selectedItem.orphan && (panel || selectedItem.status === "failed" || selectedItem.exclusionReason) ? selectedItem : undefined;
  const registeredImages = items.filter(value => value.field && !value.exclusionReason);
  const gridChannel = channel || grouping?.channels[0]?.token || "";
  // The chosen input is independent of the channel used by an older result.
  const nuclearToken = grouping?.channels.find(value => value.role === "nuclear")?.token;
  const imagePlanes = registeredImages.flatMap(value => [...value.field!.image_info.channels].sort((left, right) => Number(right.channel_id === (value.recipe?.defining_channel_id || nuclearToken)) - Number(left.channel_id === (value.recipe?.defining_channel_id || nuclearToken))).map(plane => ({value, plane})));
  const compareImages = imageLayout !== "single" && imagePlanes.length > 1;
  const visiblePlanes = imagePlanes.filter(({value, plane}) => (imageLayout === "all" || value.key === item?.key) && !hiddenPlanes.includes(value.field!.id + ":" + plane.channel_id));
  const availableChannels = item?.field?.image_info.channels.map(value => value.channel_id);
  const actualChannel = [channel, item?.recipe?.defining_channel_id, nuclearToken, ...(availableChannels || [])].find(token => token && (!availableChannels || availableChannels.includes(token))) || "";
  const nuclear = grouping?.channels.filter(value => value.role === "nuclear") ?? [];
  useEffect(() => {
    if (!busy && !draftBusy && !figureBusy) return;
    const started = Date.now(); setElapsedSeconds(0);
    const timer = window.setInterval(() => setElapsedSeconds(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => window.clearInterval(timer);
  }, [busy, draftBusy, figureBusy]);
  const metricOptions = [{key: "area_px", label: "領域面積 / px²"}, ...(grouping?.channels ?? []).flatMap(value => [
    {key: choiceKey(value.token, "mean"), label: `${value.stain || value.token} 平均輝度（原値）`},
    {key: choiceKey(value.token, "median"), label: `${value.stain || value.token} 中央値（原値）`},
    {key: choiceKey(value.token, "integrated"), label: `${value.stain || value.token} 積算輝度（原値）`},
  ])];
  function storedTargets(value: Item) {
    return validTargetResults(value.targetResults, value.result && value.recipe ? {result: value.result, recipe: value.recipe} : undefined, {nuclear: nuclear.length === 1 ? nuclear[0].token : undefined, ncl: signalChannels.ncl || undefined, gfp: signalChannels.gfp || undefined});
  }
  function changeTargetChannel(token: string) {
    if (drawingRef.current) {setNotice("描画を保存するか、取り消してから操作してください。"); return;}
    if (!grouping || busyRef.current) return;
    const channels = {nuclear: nuclearToken, ncl: signalChannels.ncl || undefined, gfp: signalChannels.gfp || undefined};
    if (displayTarget === "nuclei") {channels.nuclear = token; setGrouping(chooseNuclearChannel(grouping, token));}
    else {channels[signalKey(displayTarget)] = token; setSignalChannels(previous => ({...previous, [signalKey(displayTarget)]: token}));}
    setItems(current => current.map(value => {
      const targets = validTargetResults(value.targetResults, value.result && value.recipe ? {result: value.result, recipe: value.recipe} : undefined, channels);
      const saved = targets[displayTarget];
      return {...value, targetResults: targets, result: saved?.result, recipe: saved?.recipe, history: [], redo: [], status: saved ? "done" : value.field ? "ready" : value.status};
    }));
    setChannel(token); setRegion(undefined); setView("image");
  }
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

    const wid = initialWorkspace;
    if (wid && !restored.current && API_CONFIGURED) {
      restored.current = true; busyRef.current = true; setBusy(true);
      void adapter.restore(wid).then(async saved => {
        if (!mounted.current) return;
        setWorkspace(wid);
        const channels = restoredChannels(saved.fields);
        setGrouping({channels, fields: saved.fields.map(field => ({key: field.id, candidates: {}, files: Object.fromEntries(field.image_info.channels.map(value => [value.channel_id, {path: `${field.id}/${value.channel_id}.tif`, size: 0}]))})), issues: []});
        setFileCount(saved.fields.reduce((count, field) => count + field.image_info.channels.length, 0));
        const recovered: Item[] = [];
        for (const [index, field] of saved.fields.entries()) {
          const revisions = saved.revisions.filter(value => ["succeeded", "queued", "running"].includes(value.state) && ["1.2.0", "1.3.0", "1.4.0", "1.5.0"].includes(value.config.recipe.version) && value.config.field_ids.length === 1 && value.config.field_ids[0] === field.id).sort((a,b) => b.created-a.created);
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
          value.targetResults = {};
          // The server's adopted version is authoritative, including undo in another tab.
          // Never resurrect the newest historical result for an unselected target.
          const adoptedIds = new Set(Object.values(entry.target_revisions ?? {}));
          if (entry.revision_id) adoptedIds.add(entry.revision_id);
          for (const candidate of revisions.filter(candidate => candidate.state === "succeeded" && adoptedIds.has(candidate.id))) {const target = targetOf(candidate.config.recipe); if (!value.targetResults[target]) {try {value.targetResults[target] = {result: value.result?.revision === candidate.id ? value.result : await adapter.readResult(candidate.id, field.id), recipe: candidate.config.recipe};} catch { /* Retain other explicitly adopted results if one is unavailable. */ }}}
          value.targetResults = validTargetResults(value.targetResults, value.result && value.recipe ? {result: value.result, recipe: value.recipe} : undefined);
          if (value.recipe && isCompartment(targetOf(value.recipe)) && !value.targetResults[targetOf(value.recipe)]) {value.result = undefined; value.status = "ready"; value.error = "核の領域が変更されています。核小体・核質を再計算してください。";}
          recovered.push(value); void loadPreviews(field);
        }
        for (const entry of saved.selection.entries.filter(value => !value.field_id)) recovered.push({entryId: entry.id, key: entry.id, label: "未登録の視野", exclusionReason: entry.exclusion_reason, status: "failed", error: "画像の登録が完了していません。再登録または理由を入力して除外してください。", history: [], redo: []});
        if (!mounted.current) return;
        setItems(recovered); setSelected(recovered.find(value => !value.exclusionReason)?.key ?? "");
        const recipe = recovered.find(value => !value.exclusionReason)?.recipe;
        if (recipe) {setDisplayTarget(targetOf(recipe)); setChannel(recipe.defining_channel_id); if (recipe.source === "stardist_nuclear") setGrouping(current => current ? chooseNuclearChannel(current, recipe.defining_channel_id) : current);}
        const allRecipes = recovered.filter(value => !value.exclusionReason).flatMap(value => Object.values(value.targetResults || {}).map(saved => saved!.recipe));
        const savedNuclear = allRecipes.find(value => value.source === "stardist_nuclear");
        if (savedNuclear) {
          setNuclearMaxSide(savedNuclear.detection_max_side_px ?? null);
          setGrouping(current => current ? chooseNuclearChannel(current, savedNuclear.defining_channel_id) : current);
          for (const value of recovered) {
            value.targetResults = validTargetResults(value.targetResults, value.result && value.recipe ? {result: value.result, recipe: value.recipe} : undefined, {nuclear: savedNuclear.defining_channel_id});
            if (value.recipe && !value.targetResults[targetOf(value.recipe)]) {
              value.result = undefined; value.history = []; value.redo = [];
              value.status = "ready";
              value.error = "核検出のチャンネルが変更されています。現在の画像で再検出してください。";
            }
            if (!value.exclusionReason && value.field && !value.field.image_info.channels.some(plane => plane.channel_id === savedNuclear.defining_channel_id)) {
              value.status = "failed";
              value.error = `核検出用の画像（${savedNuclear.defining_channel_id}）がありません。対応する画像を追加してください。`;
            }
          }
          setItems([...recovered]);
        }
        setSignalChannels({gfp: allRecipes.find(value => value.region_set_id === "gfp_positive")?.defining_channel_id || "", ncl: allRecipes.find(value => value.region_set_id === "ncl_positive" || value.source === "fiji_nuclear_compartment")?.defining_channel_id || ""});
      }).catch(error => setNotice(message(error))).finally(() => {busyRef.current = false; setBusy(false);});
    }
    return () => {mounted.current = false;};
  }, [adapter, loadPreviews, initialWorkspace]);
  useEffect(() => () => {for (const url of previewUrls.current.values()) URL.revokeObjectURL(url);}, []);

  const selectionIdentity = JSON.stringify(adapter.selection());
  useEffect(() => {
    if (!workspace) return;
    let active = true; let checking = false;
    const refresh = async () => {
      if (checking || busyRef.current || document.visibilityState === "hidden") return;
      if (needsReconcile.current) {setSelectionState("changed"); return;}
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
    if (drawingRef.current) {setNotice("描画を保存するか、取り消してから操作してください。"); return;}
    if (busyRef.current || draftBusy) {setNotice("現在の処理が終わると画像を追加できます。"); return;}
    busyRef.current = true; setBusy(true); setNotice("");
    try {
      if (!API_CONFIGURED) throw new Error("解析サーバーが設定されていません。ローカル版はランチャーから開いてください。");
      let currentItems = items;
      if (workspace) {
        needsReconcile.current = true; setSelectionState("changed");
        const saved = await adapter.restore(workspace);
        const reconciled: Item[] = [];
        for (const [index, field] of saved.fields.entries()) {
          const previous = items.find(value => value.field?.id === field.id);
          const entry = saved.selection.entries.find(value => value.field_id === field.id);
          let result = entry?.revision_id && previous?.result?.revision === entry.revision_id ? previous.result : undefined;
          const recipe = entry?.revision_id ? saved.revisions.find(value => value.id === entry.revision_id)?.config.recipe : undefined;
          let readError: string | undefined;
          if (entry?.revision_id && !result) {try {result = await adapter.readResult(entry.revision_id, field.id);} catch (error) {readError = message(error);}}
          const targets = validTargetResults(previous ? storedTargets(previous) : undefined, result && recipe ? {result, recipe} : undefined, {nuclear: nuclear.length === 1 ? nuclear[0].token : undefined, ncl: signalChannels.ncl || undefined, gfp: signalChannels.gfp || undefined});
          const staleDerived = recipe && !targets[targetOf(recipe)];
          if (staleDerived) result = undefined;
          reconciled.push({...previous, key: previous?.key || field.id, label: previous?.label || "視野 " + (index + 1), entryId: entry?.id || "", field, orphan: !entry, exclusionReason: entry?.exclusion_reason, result, recipe, targetResults: targets, status: !entry ? "failed" : result ? "done" : "ready", error: !entry ? "画像の解析対象への登録が完了していません。" : staleDerived ? "核の領域またはチャンネルが変更されています。核小体・核質を再計算してください。" : undefined, history: staleDerived ? [] : previous?.history || [], redo: staleDerived ? [] : previous?.redo || []});
          void loadPreviews(field);
          if (readError) Object.assign(reconciled[reconciled.length - 1], {status: "failed", error: readError, result: undefined});
        }
        for (const entry of saved.selection.entries.filter(value => !value.field_id)) reconciled.push({...items.find(value => value.entryId === entry.id), key: entry.id, label: "未登録の視野", entryId: entry.id, exclusionReason: entry.exclusion_reason, status: "failed", error: "画像を追加して登録してください。", history: [], redo: []});
        currentItems = reconciled; setItems(reconciled); needsReconcile.current = false; setSelectionState("current");
        const selectedRecipe = reconciled.find(value => !value.exclusionReason && value.recipe)?.recipe; if (selectedRecipe) setDisplayTarget(targetOf(selectedRecipe));
      }
      const fresh: AddedFile[] = []; const freshFiles = new Map<string, File>(); let unsupported = 0;
      for (const file of Array.from(list)) {
        const path = file.webkitRelativePath || file.name;
        if (!isSupportedImage(path)) {unsupported++; continue;}
        if (file.size > 256 * 1024 * 1024) throw new Error("画像ファイルが256 MiBを超えています。画像サイズを確認してください。");

        const digest = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
        const sha256 = Array.from(new Uint8Array(digest), value => value.toString(16).padStart(2, "0")).join("");
        const existing = [...added.current, ...fresh].find(value => value.path === path);
        if (existing) {if (existing.sha256 === sha256) continue; throw new Error("同じ名前で内容が異なる画像があります。別の名前で追加してください。");}
        fresh.push({path, size: file.size, inputMode: await tiffInputMode(file), sha256: Array.from(new Uint8Array(digest), value => value.toString(16).padStart(2, "0")).join("")});
        freshFiles.set(path, file);
      }
      const next = groupFiles([...added.current, ...fresh], intakeMode);
      if (grouping) next.channels = [...grouping.channels, ...next.channels.filter(value => !grouping.channels.some(previous => previous.token === value.token))];
      added.current.push(...fresh); for (const [path, file] of freshFiles) files.current.set(path, file);
      setFileCount(current => current + fresh.length);
      for (const issue of next.issues) {if (issue.kind === "duplicate_channel") {const chosen = channelChoices.current.get(`${issue.field}:${issue.token}`); const source = added.current.find(value => value.path === chosen); const field = next.fields.find(value => value.key === issue.field); if (source && field) field.files[issue.token] = source;}}
      setGrouping(next);
      let wid = workspace;
      if (!wid && next.fields.length) {const created = await adapter.create(); wid = created.id; setWorkspace(wid); onCreated(wid);}
      const pending = next.fields.filter(field => !currentItems.some(value => value.key === field.key && value.field));
      const pendingItems: Item[] = pending.map(field => ({entryId: currentItems.find(value => value.key === field.key)?.entryId || crypto.randomUUID(), key: field.key, label: field.key.split("/").at(-1) || field.key, status: "importing", history: [], redo: []}));
      setItems(current => [...current.filter(value => !pending.some(field => field.key === value.key)), ...pendingItems]);
      if (!selected && pending[0]) setSelected(pending[0].key);
      for (const field of pending) {
        try {
          await adapter.registerImport(wid, pendingItems.find(value => value.key === field.key)!.entryId);
          if (next.issues.some(issue => issue.kind === "duplicate_channel" && issue.field === field.key && !field.files[issue.token])) throw new Error("同じチャンネルの候補が複数あります。取り込み設定で使用する画像を指定してください。");
          const uploaded = await adapter.upload(wid, field, next.channels, files.current, pendingItems.find(value => value.key === field.key)!.entryId); const adoptedEntry = adapter.selection()?.entries.find(entry => entry.field_id === uploaded.id);
          setItems(current => {const existing = current.find(value => value.field?.id === uploaded.id && value.key !== field.key); if (existing) return current.filter(value => value.key !== field.key); return current.map(value => value.key === field.key ? {...value, entryId: adoptedEntry?.id || value.entryId, exclusionReason: adoptedEntry?.exclusion_reason, field: uploaded, status: "ready", error: undefined} : value);});
          void loadPreviews(uploaded);}
        catch (error) {update(field.key, {status: "failed", error: message(error)});}
      }
      // Identical images are kept as separate fields; the researcher decides whether to exclude one.
      setItems(current => {const seen = new Map<string, string>(); const duplicates: string[] = [];
        for (const value of current) {if (!value.field) continue; const inputs = (value.field.image_info as {inputs?: unknown}).inputs; if (!inputs) continue; const signature = JSON.stringify(inputs); const first = seen.get(signature); if (first) duplicates.push(`${first} と ${value.label}`); else seen.set(signature, value.label);}
        if (duplicates.length) setNotice(`同じ画像の視野があります（${duplicates.join("、")}）。両方を残しています。不要なら一方を対象から除外してください。`);
        return current;});
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

  async function switchTarget(target: Target) {
    if (drawingRef.current) {setNotice("描画を保存するか、取り消してから操作してください。"); return;}
    if (busyRef.current || draftBusy) return;
    busyRef.current = true; setBusy(true); setOperation("保存した検出結果を切り替え中");
    try {
      // Viewing another target never writes adoption; comparisons align it explicitly (alignSelection).
      setItems(current => current.map(value => {const targets = storedTargets(value); const saved = targets[target]; return {...value, targetResults: targets, result: saved?.result, recipe: saved?.recipe, status: saved ? "done" : value.field ? "ready" : value.status, history: [], redo: []};}));
      setDisplayTarget(target); setRegion(undefined); setView("image"); const selectedResult = item ? storedTargets(item)[target] : undefined; const token = selectedResult?.recipe.defining_channel_id || (target === "nuclei" ? nuclearToken : signalChannels[signalKey(target)]); if (token) setChannel(token); setMetric("area_px"); const saved = items.find(value => value.targetResults?.[target])?.targetResults?.[target]?.recipe.detector; const detector = saved && !("source" in saved) ? saved : undefined; if (saved && "source" in saved) setNucleolarDefinition(previous => ({...previous, source: saved.source})); setSignalMethod(detector?.threshold_method || "otsu"); setSignalThreshold(detector?.threshold || 0); if (isCompartment(target)) setCompartmentSettings({smoothing:detector?.smoothing_sigma_px ?? 0, minimumArea:detector?.minimum_area_px ?? 1, maximumArea:detector?.maximum_area_px ?? null, split:detector?.split_touching ?? false});
    } catch (error) {setNotice(message(error));} finally {setOperation(""); busyRef.current = false; setBusy(false);}
  }

  async function alignSelection(target: Target) {
    // Called only by an explicit comparison: adopt the compared target's saved result per field.
    for (const value of items.filter(value => !value.exclusionReason && !value.orphan && value.field)) {
      const saved = storedTargets(value)[target];
      if (saved && workspace) await adapter.selectRevision(workspace, saved.result.revision, value.field!.id);
    }
    setSelectionTick(tick => tick + 1);
    return adapter.selection();
  }
  async function run(onlyKey?: string, target: Target = displayTarget) {
    if (drawingRef.current) {setNotice("描画を保存するか、取り消してから操作してください。"); return;}
    if (busyRef.current || selectionState !== "current" || !workspace) return;
    if ((target === "nuclei" || isCompartment(target)) && nuclear.length !== 1) {setNotice("核検出に使うチャンネルを指定してください。"); return;}
    const signalChannel = target === "nuclei" ? "" : isCompartment(target) && nucleolarDefinition.source !== "ncl"
      ? (nucleolarDefinition.source === "dapi_poor" ? nuclear[0]?.token || "" : nucleolarDefinition.marker) : signalChannels[signalKey(target)];
    if (target !== "nuclei" && !signalChannel) {setNotice(isCompartment(target) && nucleolarDefinition.source === "marker" ? "核小体マーカーのチャンネルを指定してください。" : "検出するチャンネルを指定してください。"); return;}
    busyRef.current = true; setBusy(true); stopped.current = false; setNotice("");
    try {
      for (const value of itemsRef.current.filter(value => value.field && !value.orphan && !value.exclusionReason && (!onlyKey || value.key === onlyKey))) {
        if (stopped.current) break;
        const targets = storedTargets(itemsRef.current.find(current => current.key === value.key) ?? value);
        const progress = (label: string) => (state: string) => setOperation(value.label + "：" + (state === "queued" ? label + "の開始待ち" : state === "running" ? label + "の検出・測定中" : "測定結果を読み込み中"));
        try {
          let recipe: Recipe;
          if (isCompartment(target)) {
            let nucleus = targets.nuclei;
            if (!nucleus || nucleus.recipe.defining_channel_id !== nuclear[0].token) {
              const parentRecipe = nuclearRecipe(nuclear[0], nuclearMaxSide); setSelected(value.key); setChannel(parentRecipe.defining_channel_id); setOperation(value.label + "：先に核を検出しています"); update(value.key, {status: "running", error: undefined});
              const parentResult = await adapter.run(workspace, value.field!.id, parentRecipe, progress("核"));
              nucleus = {result: parentResult, recipe: parentRecipe}; targets.nuclei = nucleus; delete targets.nucleoli; delete targets.nucleoplasm;
              update(value.key, {targetResults: targets});
            }
            if (target === "nucleoplasm" && !targets.nucleoli) throw new Error("先に核小体を検出・確認してください。核質は採用した核小体から求めます。");
            recipe = {id: "region-2d", version: "1.4.0", source: "fiji_nuclear_compartment", region_set_id: target, label: targetLabel[target], compartment: target as "nucleoli" | "nucleoplasm", nuclear_revision_id: nucleus.result.revision, nuclear_channel_id: nucleus.recipe.defining_channel_id, defining_channel_id: signalChannel, detector: nucleolarDefinition.source === "ncl" ? {engine:"fiji-nucleolar-compartments", protocol_version:"1.1.0", threshold_method:signalMethod, threshold:signalMethod === "manual" ? signalThreshold : null, smoothing_sigma_px:compartmentSettings.smoothing, minimum_area_px:compartmentSettings.minimumArea, maximum_area_px:compartmentSettings.maximumArea, split_touching:compartmentSettings.split} : nucleolarDetectorV2(nucleolarDefinition), ...(target === "nucleoplasm" && targets.nucleoli ? {nucleolar_revision_id: targets.nucleoli.result.revision} : {})};
          } else recipe = target === "nuclei" ? nuclearRecipe(nuclear[0], nuclearMaxSide) : {id: "region-2d", version: "1.3.0", region_set_id: target + "_positive", label: targetLabel[target], source: "fiji_positive_regions", defining_channel_id: signalChannel, detector: {threshold_method: signalMethod, threshold: signalMethod === "manual" ? signalThreshold : null, smoothing_sigma_px: 0, minimum_area_px: 1, split_touching: false}};
          const measurement = target === "nucleoplasm" && background === "automatic" ? automaticBackground : rawMeasurement;
          const saved = targets[target];
          if (saved && JSON.stringify(saved.recipe) === JSON.stringify(recipe) && (target !== "nucleoplasm" || (saved.result.protocol === "4.0.0") === (background === "automatic"))) continue;
          if (!value.field!.image_info.channels.some(channel => channel.channel_id === recipe.defining_channel_id)) throw new Error("検出用チャンネルがありません。");
          setSelected(value.key); setChannel(recipe.defining_channel_id); setView("image"); setOperation(value.label + "：" + recipe.label + "の受付中"); update(value.key, {status: "running", error: undefined, recipe});
          const result = await adapter.run(workspace, value.field!.id, recipe, progress(recipe.label), measurement);
          if (target === "nuclei") {delete targets.nucleoli; delete targets.nucleoplasm;}
          targets[target] = {result, recipe}; update(value.key, {status: "done", result, recipe, targetResults: targets, history: [], redo: []});
        } catch (error) {update(value.key, {status: "failed", error: message(error), targetResults: targets});}
      }
    } finally {setOperation(""); busyRef.current = false; setBusy(false); if (stopped.current) setNotice("中断しました。完了した視野は保存されています。");}
  }

  function drawingChanged(active: boolean) {
    drawingRef.current = active && item?.result ? {key:item.key, revision:item.result.revision, channel:actualChannel} : null;
    setDrawing(active);
  }
  async function saveDrawing(operation: MaskOperation, polygon: Point[], selectedRegion?: number, merged: number[] = []) {
    const identity = drawingRef.current;
    const value = item;
    if (busyRef.current || selectionState !== "current" || !identity || !value?.result || !value.recipe || !workspace || identity.key !== value.key || identity.revision !== value.result.revision || identity.channel !== actualChannel || actualChannel !== value.recipe.defining_channel_id) throw new Error("描画対象が変更されました。保存できません。");
    if (value.recipe.compartment === "nucleoplasm") throw new Error("核質は核と核小体の領域から計算します。");
    busyRef.current = true; setBusy(true); setOperation(operation === "merge" ? "領域をつなげて再測定中" : operation === "split" ? "領域を分けて再測定中" : "描画した領域を保存・再測定中");
    try {
      const result = await adapter.editMask(workspace, value.result, value.recipe, operation, polygon, selectedRegion, merged);
      const targets = storedTargets(value);
      targets[targetOf(value.recipe)] = {result, recipe:value.recipe};
      if (value.recipe.source === "stardist_nuclear") {delete targets.nucleoli;delete targets.nucleoplasm;}
      if (value.recipe.compartment === "nucleoli") delete targets.nucleoplasm;
      update(value.key, {result, targetResults:targets, status:"done", error:undefined, history:[...value.history,value.result], redo:[]});
    } finally {busyRef.current=false;setBusy(false);setOperation("");}
  }

  async function correct(kind: "exclude" | "delete" | "undo" | "redo") {
    if (drawingRef.current) {setNotice("描画を保存するか、取り消してから操作してください。"); return;}
    if (busyRef.current || selectionState !== "current" || !item?.result || !item.recipe || !workspace) return;
    const value = item; busyRef.current = true; setBusy(true); setNotice("");
    try {
      const target = kind === "undo" ? value.history.at(-1) : kind === "redo" ? value.redo.at(-1) : null;
      const result = target ? await adapter.selectRevision(workspace, target.revision, value.field!.id)
        : region !== undefined && (kind === "exclude" || kind === "delete") ? await adapter.correct(workspace, value.result!, kind, region, value.recipe!) : null;
      if (result) {const targets = storedTargets(value); targets[targetOf(value.recipe)] = {result, recipe: value.recipe!}; if (value.recipe!.compartment === "nucleoli") delete targets.nucleoplasm; if (value.recipe!.source === "stardist_nuclear") {delete targets.nucleoli; delete targets.nucleoplasm;} update(value.key, {result, targetResults: targets,
        history: kind === "undo" ? value.history.slice(0, -1) : [...value.history, value.result!],
        redo: kind === "undo" ? [...value.redo, value.result!] : kind === "redo" ? value.redo.slice(0, -1) : []});}
    } catch (error) {setNotice(message(error));}
    finally {busyRef.current = false; setBusy(false);}
  }

  async function adoptSavedRevision(rid: string) {
    if (drawingRef.current) {setNotice("描画を保存するか、取り消してから操作してください。"); return;}
    if (!item?.field || busyRef.current || selectionState !== "current") return;
    const recipe = item.revisionChoices?.find(value => value.id === rid)?.config.recipe;
    if (!recipe) return;
    busyRef.current = true; setBusy(true); setNotice("");
    try {
      const candidate = await adapter.readResult(rid, item.field.id);
      const targets = validTargetResults(storedTargets(item), {result: candidate, recipe}, {nuclear: nuclear.length === 1 ? nuclear[0].token : undefined, ncl: signalChannels.ncl || undefined});
      if (isCompartment(targetOf(recipe)) && !targets[targetOf(recipe)]) throw new Error("核の領域またはチャンネルが変更されています。核小体・核質を再計算してください。");
      const result = await adapter.selectRevision(workspace, rid, item.field.id);
      if (recipe.source === "stardist_nuclear") {delete targets.nucleoli; delete targets.nucleoplasm;}
      update(item.key, {result, recipe, targetResults: targets, status: "done", error: undefined, revisionChoices: undefined, history: [], redo: []}); setDisplayTarget(targetOf(recipe)); setChannel(recipe.defining_channel_id);
    }
    catch (error) {setNotice(message(error));}
    finally {busyRef.current = false; setBusy(false);}
  }

  async function excludeField(reason: string | null, targetItem = item) {
    if (drawingRef.current) {setNotice("描画を保存するか、取り消してから操作してください。"); return;}
    if (!targetItem || busyRef.current || selectionState !== "current" || (reason !== null && !reason.trim())) return;
    busyRef.current = true; setBusy(true); setNotice("");
    try {await adapter.excludeField(workspace, targetItem.entryId, reason?.trim() ?? null); update(targetItem.key, {exclusionReason: reason?.trim() ?? null}); setFieldReason("");}
    catch (error) {setNotice(message(error));}
    finally {busyRef.current = false; setBusy(false);}
  }

  async function requestDraft(retryFailed = false) {
    if (drawingRef.current) {setNotice("描画を保存するか、取り消してから操作してください。"); return;}
    if ((!goal.trim() && !items.length) || draftBusy || busyRef.current) return;
    busyRef.current = true;
    setDraftBusy(true); setDraft(""); setDraftQuestions([]); setDraftRetry(false);
    try {
      let wid = workspace;
      if (!wid) {const created = await adapter.create(); wid = created.id; setWorkspace(wid); onCreated(wid);}
      const response = await adapter.draft(wid, goal, retryFailed); setDraft(response.proposal.draft.rationale); setDraftQuestions(response.proposal.draft.missing_information);
      // The AI chooses the method: its validated selection fills the method card directly.
      setProposal(response.proposal); setAiTrialStarted(false);
      const nuclearChoice = response.proposal.draft.channels.filter(value => value.role === "nuclear");
      if (grouping && nuclearChoice.length === 1 && !response.proposal.needs_confirmation.includes(nuclearChoice[0].token) && grouping.channels.some(value => value.token === nuclearChoice[0].token)) {setGrouping(chooseNuclearChannel(grouping, nuclearChoice[0].token)); setChannel(nuclearChoice[0].token);}}
    catch (error) {if (error instanceof ApiError && error.code === "proposal_explicit_retry_required") {setDraftRetry(true); setDraft("前回のリクエストが完了していません。再送すると追加のAPI利用料が発生する場合があります。");} else setDraft(message(error));}
    finally {busyRef.current = false; setDraftBusy(false);}
  }
  const composer = <section className={styles.composer} aria-label="解析の指示">


    {(draft || draftBusy) && <div className={styles.response} aria-live="polite">{draftBusy ? <p>解析方法を作成しています…</p> : <><p>{draft}</p>{draftQuestions.length > 0 && <ul>{draftQuestions.map((question, index) => <li key={index}>{question}</li>)}</ul>}</>}{draftRetry && <button className={styles.secondary} disabled={draftBusy || busy} onClick={() => void requestDraft(true)}>再送信（追加料金が発生する場合があります）</button>}</div>}
    <form onSubmit={event => {event.preventDefault(); void requestDraft();}}>
      <label htmlFor="analysis-instruction">AIに指示</label>
      <textarea id="analysis-instruction" value={goal} maxLength={1000} placeholder="AIに指示：例）核を検出し、各チャンネルの輝度を測定" onChange={event => {setGoal(event.target.value); setDraftRetry(false);}}/>

      {items.some(value => value.status === "failed" && !value.exclusionReason) && <details><summary>処理できなかった画像 {items.filter(value => value.status === "failed" && !value.exclusionReason).length} 件</summary>{items.filter(value => value.status === "failed" && !value.exclusionReason).map(value => <p key={value.key}><button type="button" className={styles.secondary} onClick={() => setSelected(value.key)}>{value.label}</button> {value.error}</p>)}</details>}
      <div className={styles.composerActions}><button type="button" className={styles.secondary} disabled={drawing || busy || draftBusy || !API_CONFIGURED} onClick={() => fileInput.current?.click()}>画像を追加</button><button type="button" className={styles.secondary} disabled={drawing || busy || draftBusy || !API_CONFIGURED} onClick={() => folderInput.current?.click()}>フォルダを追加</button><span>{items.length ? items.filter(value => value.field && !value.exclusionReason).length + " 視野を登録済み" : "TIFF / 複数選択可"}</span><button type="submit" className={styles.primary} disabled={(!goal.trim() && !items.length) || draftBusy || busy || draftRetry}>{draftBusy ? "処理中…" : "AIに送信"}</button></div>
      {!items.length && <details><summary>画像の構成</summary><select aria-label="画像の構成" value={intakeMode} disabled={drawing || busy} onChange={event => setIntakeMode(event.target.value as "automatic" | "single")}><option value="automatic">チャンネル別画像をまとめる</option><option value="single">同じ染色の画像</option></select></details>}
      <details className={styles.transmissionInfo}><summary>送信内容</summary><p>入力した指示と画像の構成情報をOpenAIへ送信します。画像・ファイル名・測定値は送りません。</p></details></form>
  </section>;
  const fileInputs = <><input ref={fileInput} type="file" multiple accept=".tif,.tiff" hidden data-testid="file-input" onChange={event => {if (event.target.files) void addFiles(event.target.files); event.target.value = "";}}/><input ref={folderInput} type="file" multiple hidden data-testid="folder-input" onChange={event => {if (event.target.files) void addFiles(event.target.files); event.target.value = "";}}/></>;
  const addActions = <><button className={styles.primary} disabled={drawing || busy || draftBusy || !API_CONFIGURED} onClick={() => fileInput.current?.click()}>画像を追加</button><button className={styles.secondary} disabled={drawing || busy || draftBusy || !API_CONFIGURED} onClick={() => folderInput.current?.click()}>フォルダを追加</button></>;
  const rows = item?.result?.rows.filter(row => row.channel_id === actualChannel) ?? [];
  const excluded = new Set(item?.result?.exclusions.filter(value => value.field_id === item.field?.id && value.region_id !== null).map(value => value.region_id));
  const shape = item?.field?.image_info.shape;
  const displayRgb = item?.field?.image_info.input_mode === "display-rgb";
  const activeItems = items.filter(value => !value.exclusionReason);
  const completedItems = activeItems.filter(value => value.result).length;
  const statusText = operation ? `${operation} · 検出チャンネル ${displayTarget === "nuclei" ? nuclearToken || "未指定" : signalChannels[signalKey(displayTarget)] || "未指定"}`
    : draftBusy ? "入力した指示から解析方法を作成中"
    : busy ? `画像を登録中 · ${items.filter(value => value.field).length} / ${items.length} 視野`
    : figureBusy ? `${item?.label || "選択視野"}：保存済みの測定値からグラフを作成中`
    : !items.length ? "画像を追加するか、解析の指示を入力してください。"
    : completedItems === activeItems.length && completedItems > 0 ? "領域の検出・輝度測定が完了しました。画像上の検出領域と測定値を表示しています。"
    : displayTarget !== "nuclei" ? `${targetLabel[displayTarget]} · チャンネルを指定して検出を実行します。`
    : nuclear.length !== 1 ? "核検出に使うチャンネルを指定すると、画像で確認できます。"
    : `核検出 ${nuclear[0].stain || nuclear[0].token} · 「一括解析」で核の検出と輝度測定を開始します。`;
  const targetChannel = displayTarget === "nuclei" ? nuclearToken || "" : signalChannels[signalKey(displayTarget)];
  const targetControls = grouping && items.some(value => value.field) && <section className={styles.targetBar} aria-label="画像と測定対象"><div className={styles.segmented} role="group" aria-label="表示対象">{([{id: "nuclei", label: "核"}, {id: "gfp", label: "GFP陽性領域"}, {id: "ncl", label: "NCL陽性領域（画像全体）"}, {id: "nucleoli", label: "核小体"}, {id: "nucleoplasm", label: "核質"}] as const).filter(target => target.id !== "nucleoplasm" && (compartmentTargetsEnabled || !isCompartment(target.id))).map(target => <button key={target.id} aria-pressed={displayTarget === target.id} disabled={drawing || busy || draftBusy} onClick={() => void switchTarget(target.id)}>{target.label}</button>)}</div><label>{displayTarget === "nuclei" ? "核を染めた画像" : (displayTarget === "gfp" ? "GFP" : "NCL") + " の画像"}<select value={targetChannel} disabled={drawing || busy || draftBusy} onChange={event => changeTargetChannel(event.target.value)}><option value="">チャンネルを指定</option>{grouping.channels.map(value => <option key={value.token} value={value.token}>{value.stain || value.token}</option>)}</select></label><details className={styles.detectorOptions}><summary>検出設定</summary><div>{displayTarget === "nuclei" && <label>検出用画像の長辺<select value={nuclearMaxSide ?? 0} disabled={drawing || busy} onChange={event => {setNuclearMaxSide(Number(event.target.value) || null); setNotice("検出条件を変更しました。「この視野で検出」で新しい輪郭を確認してください。");}}><option value={0}>容量に合わせる</option>{[320, 640, 1024, 1643, 2048].map(size => <option key={size} value={size}>{size} px</option>)}</select></label>}<label>方法<select aria-label="解析方法" value={displayTarget === "nuclei" ? "stardist" : signalMethod} disabled={drawing || busy || draftBusy || displayTarget === "nuclei"} onChange={event => setSignalMethod(event.target.value as "otsu" | "manual")}>{displayTarget === "nuclei" ? <option value="stardist">StarDist 2D</option> : <><option value="otsu">Fiji・Otsu</option><option value="manual">Fiji・手動しきい値</option></>}</select></label>{displayTarget !== "nuclei" && signalMethod === "manual" && <label>しきい値<input type="number" min={0} max={65535} value={signalThreshold} disabled={drawing || busy} onChange={event => setSignalThreshold(Number(event.target.value))}/></label>}{isCompartment(displayTarget) && <><label>平滑化 σ (px)<input type="number" min={0} step={0.1} value={compartmentSettings.smoothing} disabled={drawing || busy} onChange={event => setCompartmentSettings(previous => ({...previous,smoothing:Number(event.target.value)}))}/></label><label>最小面積 (px²)<input type="number" min={1} value={compartmentSettings.minimumArea} disabled={drawing || busy} onChange={event => setCompartmentSettings(previous => ({...previous,minimumArea:Number(event.target.value)}))}/></label><label>最大面積 (px²)<input type="number" min={1} placeholder="上限なし" value={compartmentSettings.maximumArea ?? ""} disabled={drawing || busy} onChange={event => setCompartmentSettings(previous => ({...previous,maximumArea:event.target.value ? Number(event.target.value) : null}))}/></label><label><input type="checkbox" checked={compartmentSettings.split} disabled={drawing || busy} onChange={event => setCompartmentSettings(previous => ({...previous,split:event.target.checked}))}/>接触した領域を分離</label></>}</div></details><div className={styles.runControls}><select aria-label="解析する視野" value={runRange} disabled={drawing || busy} onChange={event => setRunRange(event.target.value as "selected"|"all")}><option value="selected">選択視野</option><option value="all">全視野</option></select><button className={styles.secondary} disabled={drawing || busy || draftBusy || !item?.field} onClick={() => void run(runRange === "selected" ? item?.key : undefined)}>{item?.result ? "再計算" : "解析"}</button></div></section>;
  const methodFields = items.filter(value => value.field && !value.exclusionReason && !value.orphan);
  const doneCount = (target: Target) => methodFields.filter(value => storedTargets(value)[target]).length;
  const progressText = (target: Target) => methodFields.length ? `${doneCount(target)}/${methodFields.length} 視野` : "画像を追加してください";
  const tone = (target: Target): MethodStep["tone"] => methodFields.length && doneCount(target) === methodFields.length ? "done" : doneCount(target) ? "current" : "todo";
  const nuclearName = nuclear[0]?.stain || nuclear[0]?.token || "核染色";
  const markerChoices = (grouping?.channels ?? []).filter(value => value.token !== nuclear[0]?.token);
  const nucleiReady = methodFields.length > 0 && doneCount("nuclei") === methodFields.length;
  const definitionForm = definitionOpen && <div className={styles.definitionForm}>
    <label>核小体の決め方<select value={nucleolarDefinition.source} disabled={busy} onChange={event => setNucleolarDefinition(previous => ({...previous, source: event.target.value as NucleolarSource}))}>
      {(Object.keys(nucleolarSourceText) as NucleolarSource[]).map(source => <option key={source} value={source}>{nucleolarSourceText[source].label}</option>)}</select></label>
    <p className={styles.definitionHint}>{nucleolarSourceText[nucleolarDefinition.source].description}</p>
    {nucleolarDefinition.source === "marker" && <label>マーカーのチャンネル<select value={nucleolarDefinition.marker} disabled={busy} onChange={event => setNucleolarDefinition(previous => ({...previous, marker: event.target.value}))}><option value="">選択してください</option>{markerChoices.map(value => <option key={value.token} value={value.token}>{value.stain || value.token}</option>)}</select></label>}
    {nucleolarDefinition.source !== "ncl" && <>
      <label>画素サイズ（µm/px、撮影記録の値）<input type="number" min={0.005} max={5} step={0.0001} value={nucleolarDefinition.pixelUm ?? ""} placeholder="不明なら空欄" disabled={busy} onChange={event => setNucleolarDefinition(previous => ({...previous, pixelUm: event.target.value ? Number(event.target.value) : null}))}/></label>
      {nucleolarDefinition.source === "dapi_poor" && <label>暗さのしきい値（核内の中央値に対する比）<input type="number" min={0.3} max={0.95} step={0.05} value={nucleolarDefinition.relative} disabled={busy} onChange={event => setNucleolarDefinition(previous => ({...previous, relative: Number(event.target.value) || 0.7}))}/></label>}
    </>}
    <p className={styles.definitionHint}>変更後に「代表視野で試す」で輪郭を確認し、問題なければ「全視野に適用」を押します。</p>
  </div>;
  const metricName: Record<string, string> = {area: "面積", mean_raw: "平均輝度（元の値）", integral_raw: "積分輝度（元の値）", mean_corrected: "平均輝度（背景補正）", integral_corrected: "積分輝度（背景補正）", ncl_log2_nucleoplasm_over_nucleoli: "NCL の核質/核小体 比（log2）", nucleolar_area_fraction: "核小体の面積比", nucleolar_count: "核小体の数"};
  const testName: Record<string, string> = {"welch-t": "Welch の t 検定", "paired-t": "対応のある t 検定", "mann-whitney-u": "Mann–Whitney U 検定", wilcoxon: "Wilcoxon 符号付き順位検定"};
  const figureName: Record<string, string> = {"field-distribution": "視野ごとの分布", "unit-comparison": "実験単位の比較", paired: "対応のある比較", "association-scatter": "散布図"};
  const aiDraft = proposal?.draft;
  const aiNuclear = aiDraft?.channels.find(value => value.role === "nuclear");
  const aiNeedsConfirmation = aiNuclear && proposal!.needs_confirmation.includes(aiNuclear.token) && nuclear.length !== 1;
  const compartmentsUsed = !aiDraft || aiDraft.recipe === "nuclear-ncl";
  const aiMark = (text: string) => aiDraft ? `${text}（AI が選択）` : text;
  async function runGfpGate() {
    if (!workspace || !gfp.channel || !gfp.controls.length) return;
    const chosen = methodFields.flatMap(value => {const nucleus = storedTargets(value).nuclei; return nucleus ? [{field_id: value.field!.id, revision_id: nucleus.result.revision, control: gfp.controls.includes(value.field!.id)}] : [];});
    try {setGfp(previous => ({...previous, error: "", result: null})); const result = await adapter.gfpGate(workspace, {gfp_channel_id: gfp.channel, percentile: 99, fields: chosen}); setGfp(previous => ({...previous, result}));}
    catch (error) {setGfp(previous => ({...previous, error: message(error)}));}
  }
  const gfpCounts = gfp.result ? Object.values(gfp.result.field_counts).reduce((total, value) => ({positive: total.positive + value.positive, negative: total.negative + value.negative}), {positive: 0, negative: 0}) : null;
  const gfpForm = gfp.enabled && <div className={styles.definitionForm}>
    <label>GFP のチャンネル<select value={gfp.channel} onChange={event => setGfp(previous => ({...previous, channel: event.target.value, result: null}))}><option value="">選択してください</option>{(grouping?.channels ?? []).filter(value => value.token !== nuclear[0]?.token).map(value => <option key={value.token} value={value.token}>{value.stain || value.token}</option>)}</select></label>
    <fieldset style={{border: 0, padding: 0, margin: 0, display: "grid", gap: 2}}><legend style={{color: "var(--muted)"}}>陰性対照の視野（未導入・GFP 陰性の細胞）</legend>
      {methodFields.map(value => <label key={value.key} style={{display: "flex", gap: 6, alignItems: "center"}}><input type="checkbox" checked={gfp.controls.includes(value.field!.id)} onChange={event => setGfp(previous => ({...previous, result: null, controls: event.target.checked ? [...previous.controls, value.field!.id] : previous.controls.filter(id => id !== value.field!.id)}))}/>{value.label}</label>)}</fieldset>
    <p className={styles.definitionHint}>陰性対照の核の GFP 平均の 99 パーセンタイルを、撮影日ごとのしきい値にします。</p>
    <span className={styles.goalActions}><button type="button" className={styles.linkButton} disabled={!gfp.channel || !gfp.controls.length || !nucleiReady || busy} onClick={() => void runGfpGate()}>判定する</button></span>
    {gfp.error && <p role="alert">{gfp.error}</p>}
  </div>;
  const plasmResult = item ? storedTargets(item).nucleoplasm?.result : undefined;
  // Nucleoplasm from adopted nucleoli adds the per-nucleus summary metrics (compartment-summary selection 1.0.0).
  const plasmReady = methodFields.some(value => !!storedTargets(value).nucleoplasm?.recipe.nucleolar_revision_id);
  const adoptedPlasm = displayTarget === "nucleoplasm" && plasmReady;
  const comparisonOptions = adoptedPlasm ? [
    ...(grouping?.channels ?? []).filter(value => value.token !== nuclear[0]?.token).map(value => ({key: choiceKey(value.token, "log2_nucleoplasm_over_nucleolus"), label: `${value.stain || value.token} 核質/核小体 比（log2、核ごと）`})),
    {key: "nucleolar_count", label: "核小体の数（核ごと）"}, {key: "nucleolar_area_fraction", label: "核小体面積の割合（核ごと）"}, ...metricOptions] : metricOptions;
  useEffect(() => {
    if (!plasmResult || !item?.field) return;
    let active = true;
    void adapter.compartmentSummary(plasmResult.revision, item.field.id).then(value => {if (active) setSummary({revision: plasmResult.revision, value});}).catch(() => {});
    return () => {active = false;};
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [adapter, plasmResult?.revision, item?.field?.id]);
  const summaryChannels = summary && summary.revision === plasmResult?.revision ? Object.keys(summary.value.channels).filter(token => token !== nuclear[0]?.token) : [];
  const summaryChannel = summaryChannels.includes(actualChannel) ? actualChannel : summaryChannels[0];
  const correctedSummary = summaryChannel ? summary!.value.corrected_channels?.[summaryChannel] : undefined;
  const backgroundMissing = correctedSummary?.missing_reason ? correctedSummary.missing_reason : null;
  const summaryRows = !summaryChannel ? [] : correctedSummary && !backgroundMissing ? correctedSummary.rows : summary!.value.channels[summaryChannel].rows;
  const backgroundReason: Record<string, string> = {automatic_background_insufficient_tiles: "核のない領域が足りません", automatic_background_insufficient_coverage: "核のない領域が画像の一部に偏っています"};
  const backgroundState = !doneCount("nucleoplasm") ? "核質の計算時に求めます" : backgroundMissing ? `この視野では背景を決められません（${backgroundReason[backgroundMissing] ?? backgroundMissing}）。元の値を表示しています` : correctedSummary ? "背景を引いた値を表示しています" : background === "automatic" ? "「全視野に適用」で背景を求め直します" : "元の値を表示しています";
  const reasonText: Record<string, string> = {no_nucleolus: "核小体なし", no_nucleoplasm: "核質なし", nonpositive_signal: "輝度が0以下"};
  const steps: MethodStep[] = [
    {id: "nuclei", number: 1, title: "核", description: nuclear.length === 1 ? `${nuclearName} から核を自動検出（StarDist 2D）` : "核を染めたチャンネルから核を自動検出（StarDist 2D）", state: nuclear.length !== 1 && methodFields.length ? "核を染めたチャンネルを選んでください" : progressText("nuclei"), tone: nuclear.length !== 1 && methodFields.length ? "attention" : tone("nuclei"),
      action: {label: "輪郭を見る", onClick: () => void switchTarget("nuclei"), disabled: !doneCount("nuclei") || busy},
      details: aiNeedsConfirmation && grouping ? <span className={styles.goalActions}><span className={styles.definitionHint}>AI は {aiNuclear!.token} を核染色と推定しました（{aiNuclear!.reason}）。確認して選んでください。</span></span> : nuclear.length !== 1 && grouping && methodFields.length > 0 ? <span className={styles.goalActions}>{grouping.channels.map(value => <button key={value.token} type="button" className={styles.secondary} disabled={busy || drawing}
        onClick={() => {setGrouping(chooseNuclearChannel(grouping, value.token)); setChannel(value.token);}}>{(value.stain || value.token) + " で核を検出"}</button>)}</span> : undefined},
    {id: "nucleoli", number: 2, title: "核小体", description: compartmentsUsed ? `${nucleolarSourceText[nucleolarDefinition.source].label}を核小体とする` : "この目的では使いません（AI が選択）", state: !compartmentsUsed ? "—" : nucleiReady ? progressText("nucleoli") : "核の検出後に試せます", tone: compartmentsUsed ? tone("nucleoli") : "todo",
      action: {label: definitionOpen ? "閉じる" : "定義を変える", onClick: () => setDefinitionOpen(value => !value)}, details: <>{definitionForm}<span className={styles.goalActions}><button type="button" className={styles.linkButton} disabled={!nucleiReady || busy || !item} onClick={() => {if (item) void run(item.key, "nucleoli").then(() => switchTarget("nucleoli"));}}>代表視野で試す</button>{doneCount("nucleoli") > 0 && <button type="button" className={styles.linkButton} disabled={busy} onClick={() => void switchTarget("nucleoli")}>輪郭を見る</button>}</span></>},
    {id: "nucleoplasm", number: 3, title: "核質", description: "核から、確認・修正した核小体を除いた領域", state: doneCount("nucleoli") ? progressText("nucleoplasm") : "核小体の確定後に計算します", tone: tone("nucleoplasm")},
    {id: "background", number: 4, title: "背景", description: background === "automatic" ? "核の外から自動で選んだ背景を引く（元の値も残す）" : "背景を引かない（元の値で比べる）", state: backgroundState, tone: background === "automatic" && backgroundMissing ? "attention" : doneCount("nucleoplasm") ? "done" : "todo",
      action: {label: background === "automatic" ? "背景を引かない" : "自動の背景を使う", onClick: () => setBackground(value => value === "automatic" ? "raw" : "automatic"), disabled: busy}},
    {id: "values", number: 5, title: "測る値", description: aiDraft?.metrics.length ? aiMark(aiDraft.metrics.map(value => (value.channel ? value.channel + " " : "") + (metricName[value.metric] ?? value.metric)).join("、")) : "NCL の核質/核小体 比（log2）、核小体の数と面積", state: doneCount("nucleoplasm") ? "下の「核ごとの値」に表示" : "核質の計算後に表示", tone: doneCount("nucleoplasm") ? "done" : "todo"},
    {id: "gfp", number: 6, title: "対象", description: gfp.enabled ? "GFP 陽性の核に限る（陰性対照を基準）" : "すべての核", state: gfp.result && gfpCounts ? `陽性 ${gfpCounts.positive}・陰性 ${gfpCounts.negative} 核` : gfp.enabled ? "GFP チャンネルと陰性対照の視野を選んでください" : "—", tone: gfp.result ? "done" : gfp.enabled ? "attention" : "todo",
      action: {label: gfp.enabled ? "限定しない" : "GFP 陽性に限る", onClick: () => setGfp(previous => ({...previous, enabled: !previous.enabled, result: null}))}, details: gfpForm || undefined},
    {id: "compare", number: 7, title: "比較", description: aiDraft?.statistics.test ? aiMark(`${testName[aiDraft.statistics.test] ?? aiDraft.statistics.test}（独立した実験を n とする）`) : "独立した実験を n として群を比べる", state: background === "automatic" ? "背景を引いた値の比較はまだできません。比べるときは背景を「引かない」にしてください" : "群と実験単位を入力してから計算します", tone: background === "automatic" ? "attention" : "todo", action: {label: "開く", onClick: () => {if (plasmReady && displayTarget !== "nucleoplasm") void switchTarget("nucleoplasm"); setComparisonOpened(true); setView("comparison");}, disabled: !methodFields.length || background === "automatic"}},
    {id: "figure", number: 8, title: "図", description: aiDraft?.figures.length ? aiMark(aiDraft.figures.map(value => figureName[value.kind] ?? value.kind).join("、") + "（英語の図と説明文）") : "実験単位の点と細胞の分布（英語の図と説明文）", state: "—", tone: "todo", action: {label: "開く", onClick: () => setView("figure"), disabled: !item?.result}},
  ];
  async function applyMethod() {
    // One explicit action applies the current nucleolar definition to every field, then derives nucleoplasm.
    await run(undefined, "nucleoli");
    await new Promise(resolve => window.setTimeout(resolve, 50)); // let the adopted nucleoli commit
    await run(undefined, "nucleoplasm");
  }
  const methodPanel = <MethodPanel goal={goal} onGoal={value => {setGoal(value); setDraftRetry(false);}} onAi={() => void requestDraft()} aiBusy={draftBusy} aiDisabled={(!goal.trim() && !items.length) || busy || draftRetry}
    aiResponse={(draft || draftBusy) && <div className={styles.response} aria-live="polite">{draftBusy ? <p>解析方法を作成しています…</p> : <><p>{draft}</p>{draftQuestions.length > 0 && <ul>{draftQuestions.map((question, index) => <li key={index}>{question}</li>)}</ul>}</>}{draftRetry && <button className={styles.secondary} disabled={draftBusy || busy} onClick={() => void requestDraft(true)}>再送信（追加料金が発生する場合があります）</button>}</div>}
    steps={steps} onApply={() => void applyMethod()} applyLabel="全視野に適用" applyDisabled={!nucleiReady || busy || selectionState !== "current" || (nucleolarDefinition.source === "marker" && !nucleolarDefinition.marker)} onMethodDetails={() => setMethodSheet(true)}/>;
  const methodDetails: MethodDetail[] = [
    {id: "nuclei", title: "1 核の検出", summary: "Fiji の StarDist 2D（蛍光核用 Versatile モデル）で核を検出します。大きな画像は検出用の複製だけを縮小し、輪郭は元画像の座標に戻します。測定は元の画素値で行います。", settings: [["確率しきい値", "0.5"], ["NMS", "0.3"], ["正規化", "1–99.8 パーセンタイル"]], references: [methodReferences.stardist], limits: ["開始値であり、画像ごとの検出精度は保証しません。輪郭を確認して修正してください。"]},
    {id: "nucleoli", title: "2 核小体の決め方", summary: nucleolarDefinition.source === "dapi_poor" ? "核ごとに、平滑化した核染色が核内中央値の一定割合より暗い部分を核小体とします。NCL がストレスで核小体から出ても核小体の位置を失いません。" : nucleolarDefinition.source === "marker" ? "核小体マーカー（UBF／FBL など）の背景を除き、核ごとに最小〜最大の 40% をしきい値にします。UBF は核小体の中心部（rDNA）を示し、核小体全体ではありません。" : "核ごとに NCL の Otsu しきい値で明るい部分を核小体とします（旧方式）。", settings: Object.entries(nucleolarDefinition.source === "ncl" ? {} : nucleolarDetectorV2(nucleolarDefinition)).filter(([key]) => !["engine", "protocol_version"].includes(key)).map(([key, value]) => [key, String(value)] as [string, string]), references: nucleolarDefinition.source === "dapi_poor" ? [methodReferences.kodiha] : nucleolarDefinition.source === "marker" ? [methodReferences.potapova] : [], limits: nucleolarDefinition.source === "dapi_poor" ? ["DAPI で決めた核小体はタンパク質マーカーより小さめになり、比は 1 に近づく（群の差が小さく出る）方向に偏ります。"] : nucleolarDefinition.source === "ncl" ? ["測る対象（NCL）で領域を決めるため、NCL が移動すると核小体を誤ります。"] : ["マーカーの染色（特異性、他チャンネルからの漏れ込み）を確認してから使ってください。"]},
    {id: "nucleoplasm", title: "3 核質", summary: "核から、確認・修正した核小体の和集合を除いた領域です。しきい値を引き直すことはありません。核小体がない核は核質の値を欠測とします。", settings: [], references: [methodReferences.potapova, methodReferences.white], limits: []},
    {id: "background", title: "4 背景", summary: background === "automatic" ? "核（除外した核も含む）から離れた領域を小さなタイルに分け、明るさが揃った暗いタイルを画像の複数の区画から集め、その中央値を背景とします。核小体と核質の両方から同じ値を引きます。条件を満たすタイルが足りない視野は背景を欠測とし、補正値を出しません。元の値は常に残します。" : "背景を引かずに元の画素値で比べます。比は背景の分だけ 1 に近づきます。", settings: background === "automatic" ? [["方式", "自動の背景候補（未確認、測定プロトコル 4.0.0）"], ["背景値", "選んだ画素の中央値"]] : [["方式", "元の値（測定プロトコル 3.0.0）"]], references: [], limits: ["自動の背景候補は研究者の確認を経ていません。"]},
    {id: "values", title: "5 測る値", summary: "主な指標は NCL の核小体と核質の平均輝度の比で、log2(核質 ÷ 核小体) として表示します（値が大きいほど核質に移動）。分母が無効な場合は 0 にせず欠測とします。", settings: [], references: [methodReferences.white, methodReferences.potapova], limits: []},
    {id: "compare", title: "6 比較", summary: "細胞ではなく独立した実験（導入・実験回）を n として比べます。細胞・視野・実験単位の値を重ねて示します。", settings: [["集計", "視野の中央値 → サンプルの平均 → 実験単位の平均"]], references: [methodReferences.lord, methodReferences.aarts], limits: []},
  ];
  const summaryTable = summaryRows.length > 0 && <section className={styles.panelSection} aria-label="核ごとの核質/核小体">
    <h3>核ごとの値（{summaryChannel}・{summaryRows[0].values === "raw" ? "元の値" : "背景補正後"}）</h3>
    <div className={styles.tableWrap}><table className={styles.table}><thead><tr><th>核</th><th>核小体数</th><th>核小体面積比</th><th>核小体 平均</th><th>核質 平均</th><th>log2(核質/核小体)</th></tr></thead>
    <tbody>{summaryRows.map(row => <tr key={row.nucleus_id}><th>{row.nucleus_id}</th><td>{row.nucleolar_count}</td><td>{row.nucleolar_area_fraction == null ? "—" : row.nucleolar_area_fraction.toFixed(3)}</td><td>{row.nucleolar_mean == null ? "—" : row.nucleolar_mean.toFixed(1)}</td><td>{row.nucleoplasm_mean == null ? "—" : row.nucleoplasm_mean.toFixed(1)}</td><td>{row.log2_nucleoplasm_over_nucleolus == null ? (row.missing_reason ? "欠測：" + (reasonText[row.missing_reason] ?? row.missing_reason) : "—") : row.log2_nucleoplasm_over_nucleolus.toFixed(3)}</td></tr>)}</tbody></table></div>
  </section>;
  // After the AI chooses an NCL method, the representative field is tried automatically; applying to all stays explicit.
  useEffect(() => {
    if (!proposal || aiTrialStarted || proposal.draft.recipe !== "nuclear-ncl" || busy || !item || !nucleiReady || storedTargets(item).nucleoli) return;
    setAiTrialStarted(true);
    void run(item.key, "nucleoli");
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [proposal, aiTrialStarted, busy, item?.key, nucleiReady]);
  // Nuclei first: once the nuclear channel is known, detect nuclei on every field without a separate step.
  useEffect(() => {
    if (!workspace || busy || draftBusy || drawing || nuclear.length !== 1 || selectionState !== "current") return;
    if (!items.some(value => value.field && !value.exclusionReason && !value.orphan && value.status === "ready" && !storedTargets(value).nuclei)) return;
    void run(undefined, "nuclei");
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspace, busy, draftBusy, drawing, nuclear.length, selectionState, items]);
  return <main className={[styles.shell, !items.length ? styles.emptyWorkspace : ""].join(" ")} onDragOver={event => event.preventDefault()} onDrop={event => {event.preventDefault(); void addFiles(event.dataTransfer.files);}}>
    <header className={styles.header}><Link href="/" className={styles.brand}>cytellect</Link><h1 className={styles.title} hidden={items.length > 0}>画像解析</h1><div className={styles.headerActions}><button className={[styles.secondary,styles.aiToggle].join(" ")} aria-expanded={aiOpen} onClick={() => setAiOpen(value => !value)}>AI</button><button className={styles.secondary} aria-label="操作パネル" aria-pressed={panel} onClick={() => {setPanel(true);setView("image");}}>解析</button>{busy && <button className={styles.secondary} onClick={() => {stopped.current = true; setNotice("現在の視野を完了してから中断します。");}}>中断</button>}</div></header>
    <div className={styles.operationStatus} hidden={items.length > 0 && !busy && !draftBusy && !figureBusy} role="status" aria-live="polite">{statusText}{(busy || draftBusy || figureBusy) && <span> · {elapsedSeconds} 秒経過</span>}{items.length > 0 && <span> · 測定済み {completedItems} / {activeItems.length} 視野</span>}</div>
    {selectionState !== "current" && <p className={styles.banner} role="status">{selectionState === "changed" ? "別のタブで採用状態が更新されました。表示中の測定値・図は旧版です。" : "現在の採用状態を確認できません。表示中の結果は保存済みの版です。"} <button onClick={() => window.location.reload()}>最新の採用状態を読み込む</button></p>}
    {notice && <p className={styles.banner} role="status">{notice}</p>}
    {!API_CONFIGURED && <p className={styles.banner}>解析サーバーが設定されていません。ローカル版はランチャーから開いてください。 <Link href="/#download">Windows版・セットアップ</Link></p>}
    <div className={[styles.layout, items.length ? styles.integratedLayout : styles.layoutNoPanel].join(" ")}>
      <nav className={styles.sidebar} aria-label="画像とグラフ"><h2>画像</h2>{grouping && fileCount > 0 && <ImportSummary grouping={grouping} files={fileCount}/>}{!items.length && <p>フォルダまたは複数画像を追加してください。</p>}<ul className={styles.fieldList}>{items.filter(value => !value.exclusionReason).map(value => <li key={value.key}><button disabled={drawing} aria-current={item?.key === value.key ? "true" : undefined} onClick={() => {setSelected(value.key); setRegion(undefined);}}><span>{value.label}</span><span>{value.exclusionReason ? "除外" : statusLabel[value.status]}</span></button>{value.field?.image_info.channels.map(plane => <button key={plane.channel_id} className={styles.channelRow} disabled={drawing} aria-pressed={item?.key === value.key && actualChannel === plane.channel_id} onClick={() => {setSelected(value.key); setChannel(plane.channel_id); setImageLayout("single"); setRegion(undefined);}}>{previews[value.field!.id + ":" + plane.channel_id] && <img src={previews[value.field!.id + ":" + plane.channel_id]} alt=""/>}<span>{plane.stain || plane.label}{plane.channel_id === (value.targetResults?.nuclei?.recipe.defining_channel_id || nuclearToken) ? " · 核検出" : ""}</span></button>)}</li>)}</ul>{items.some(value => value.exclusionReason) && <details><summary>除外した画像 {items.filter(value => value.exclusionReason).length} 件</summary>{items.filter(value => value.exclusionReason).map(value => <p key={value.key}>{value.label}：{value.exclusionReason}<button className={styles.secondary} disabled={drawing || busy} onClick={() => void excludeField(null, value)}>除外を取り消す</button></p>)}</details>}</nav>
      <section className={styles.center} aria-label="表示"><div className={styles.inspection}>{!items.length && <section className={styles.empty}><h2>画像をここにドロップ</h2><p>TIFF画像をまとめて取り込み、全視野を同じ条件で解析できます。</p><div className={styles.actions}>{addActions}</div><p>画像と結果は最後の操作から24時間保存されます。</p></section>}

        {fieldActions && <details className={styles.banner} aria-label="視野の除外" open={fieldActions.status === "failed" || !!fieldActions.exclusionReason || undefined}><summary>視野の操作</summary>{fieldActions.exclusionReason ? <><p>除外理由：{fieldActions.exclusionReason}</p><button disabled={drawing || busy} onClick={() => void excludeField(null, fieldActions)}>視野の除外を取り消す</button></> : <><label>解析から外す理由<input value={fieldReason} maxLength={300} onChange={event => setFieldReason(event.target.value)}/></label><button disabled={drawing || busy || !fieldReason.trim()} onClick={() => void excludeField(fieldReason, fieldActions)}>この視野を解析から外す</button></>}</details>}
        {!!item?.revisionChoices?.length && <label>採用する解析版<select value="" disabled={drawing || busy} onChange={event => void adoptSavedRevision(event.target.value)}><option value="" disabled>保存結果を選択</option>{item.revisionChoices.map(value => <option key={value.id} value={value.id}>{new Date(value.created * 1000).toLocaleString("ja-JP")} · 除外 {value.config.exclusions?.length ?? 0} 件 · {value.id}</option>)}</select></label>}
        {item?.error && <p className={styles.banner} role="alert">{item.error}{item.orphan && <button className={styles.secondary} disabled={drawing || busy} onClick={() => void recoverImportedField(item)}>この画像を解析対象に登録</button>}{!item.field && <button className={styles.secondary} disabled={drawing || busy} onClick={() => files.current.size ? void addFiles([]) : fileInput.current?.click()}>{fileCount ? "登録を再試行" : "画像を追加して再登録"}</button>}</p>}
        {items.length > 0 && <div className={styles.imageStage}><div className={styles.imageToolbar}>{imagePlanes.length > 1 && <><label>表示<select aria-label="画像の表示" disabled={drawing} value={imageLayout} onChange={event => setImageLayout(event.target.value as "grid" | "single" | "all")}><option value="grid">同じ視野を並べる</option><option value="all">全視野を並べる</option><option value="single">1画像</option></select></label>{compareImages && <details className={styles.imagePicker}><summary>表示する画像</summary>{imagePlanes.map(({value, plane}) => {const id = value.field!.id + ":" + plane.channel_id; return <label key={id}><input type="checkbox" checked={!hiddenPlanes.includes(id)} onChange={event => setHiddenPlanes(previous => event.target.checked ? previous.filter(key => key !== id) : [...previous, id])}/>{plane.channel_id === (value.recipe?.defining_channel_id || nuclearToken) ? (value.recipe?.label || "核検出") + " · " : ""}{plane.stain || plane.label} · {value.label}</label>;})}</details>}</>}<strong>{item?.label}{displayRgb ? " · RGB表示画像" : ""}</strong>{targetChannel && actualChannel !== targetChannel && <button className={styles.secondary} disabled={drawing || busy} onClick={() => setChannel(targetChannel)}>検出に使う画像を表示</button>}<button className={styles.secondary} disabled={!item?.field || busy} onClick={() => item?.field && void loadPreviews(item.field)}>画像を再表示</button><div className={styles.segmented} hidden={compareImages}>{grouping?.channels.map(value => <button key={value.token} disabled={drawing} role="radio" aria-checked={(compareImages ? gridChannel : actualChannel) === value.token} onClick={() => setChannel(value.token)}>{value.stain || value.token}</button>)}</div></div>{compareImages ? <div className={styles.imageGrid} data-count={visiblePlanes.length}>{visiblePlanes.map(({value, plane}) => {const field = value.field!; const rejected = new Set(value.result?.exclusions.filter(exclusion => exclusion.field_id === field.id).map(exclusion => exclusion.region_id)); return <section className={styles.imageTile} data-active={item?.key === value.key} key={field.id + ":" + plane.channel_id}><button className={styles.tileHeading} onClick={() => {setSelected(value.key); setChannel(plane.channel_id); setRegion(undefined);}}>{plane.channel_id === (value.recipe?.defining_channel_id || nuclearToken) ? (value.recipe?.label || "核検出") + " · " : ""}{plane.stain || plane.label} · {value.label} · {value.exclusionReason ? "除外" : statusLabel[value.status]}</button><FieldImage controlledZoom={gridZoom} onZoomChange={setGridZoom} src={previews[field.id + ":" + plane.channel_id] ?? null} size={{height: field.image_info.shape[0], width: field.image_info.shape[1]}} outlines={(plane.channel_id === value.recipe?.defining_channel_id ? value.result?.masks.regions ?? [] : []).map(mask => ({outline: {id: String(mask.id), points: mask.points}, state: rejected.has(mask.id) ? "excluded" as const : "included" as const}))} analyzed={!!value.result && plane.channel_id === value.recipe?.defining_channel_id} selected={item?.key === value.key ? region : undefined} onSelect={id => {setSelected(value.key); setChannel(plane.channel_id); setRegion(id);}} label={value.label + " · " + plane.channel_id}/></section>;})}</div> : <FieldImage onDrawSave={item?.result && item.recipe?.compartment !== "nucleoplasm" && actualChannel === item.recipe?.defining_channel_id ? saveDrawing : undefined} onDrawingChange={drawingChanged} editDisabled={busy || selectionState !== "current"} src={item?.field ? previews[`${item.field.id}:${actualChannel}`] ?? null : null} size={shape ? {height: shape[0], width: shape[1]} : null} outlines={(actualChannel === item?.recipe?.defining_channel_id ? item?.result?.masks.regions ?? [] : []).map(value => ({outline: {id: String(value.id), points: value.points}, state: excluded.has(value.id) ? "excluded" as const : "included" as const}))} analyzed={!!item?.result && actualChannel === item?.recipe?.defining_channel_id} selected={region} onSelect={setRegion} label={`${item?.label || "視野"}の画像`}/>}</div>
}

        </div>{!items.length && composer}
      </section>
      {items.length > 0 && <aside className={[styles.panel,styles.integratedPanel].join(" ")} aria-label="解析と結果"><nav className={styles.workTabs} aria-label="解析メニュー"><button aria-pressed={view === "image"} onClick={() => setView("image")}>方法</button><button aria-pressed={view === "comparison"} onClick={() => {setComparisonOpened(true);setView("comparison");}}>統計</button><button aria-pressed={view === "figure"} onClick={() => setView("figure")}>グラフ</button></nav><div hidden={view !== "image"}>{methodPanel}{summaryTable}<details className={styles.panelSection}><summary>表示と検出の設定</summary>{targetControls}</details>
        {item?.result && <><section className={styles.panelSection}><h3>領域を修正</h3><p>{region ? `領域 ${region}${excluded.has(region) ? "（除外）" : ""}` : "画像または測定表で領域を選択"}</p><div className={styles.actions}><button className={styles.secondary} disabled={drawing || busy || !region || excluded.has(region)} onClick={() => void correct("exclude")}>対象から除外</button><button className={styles.secondary} disabled={drawing || busy || !region} onClick={() => void correct("delete")}>領域を削除</button><button className={styles.secondary} disabled={drawing || busy || !item?.history.length} onClick={() => void correct("undo")}>元に戻す</button><button className={styles.secondary} disabled={drawing || busy || !item?.redo.length} onClick={() => void correct("redo")}>やり直す</button></div>{busy && item?.result && <p>更新中。直前の保存結果を表示しています。</p>}</section>
</>}
        <details className={styles.panelSection}><summary>取り込み設定</summary><label>画像の構成<select value={intakeMode} disabled={drawing || busy || items.length > 0} onChange={event => setIntakeMode(event.target.value as "automatic" | "single")}><option value="automatic">チャンネル別画像を視野ごとにまとめる</option><option value="single">同じ染色：1ファイルを1視野にする</option></select></label><p>ファイル名の変更は不要です。</p>{items.length > 0 && <Link href="/">別の画像構成で新しく取り込む</Link>}{grouping?.issues.filter(issue => issue.kind === "duplicate_channel").map(issue => issue.kind === "duplicate_channel" && <fieldset key={issue.field + issue.token}><legend>{issue.token} の画像</legend>{issue.paths.map(path => <button key={path} disabled={drawing || busy || draftBusy} className={styles.secondary} onClick={() => {channelChoices.current.set(issue.field + ":" + issue.token, path); void addFiles([]);}}>{path.split("/").at(-1)} を使用</button>)}</fieldset>)}</details>
        {item?.result && <details className={styles.panelSection}><summary>保存結果の出典</summary><p>解析版：{item.result.revision}</p><p>マスク版：{item.result.masks.metadata.mask_revision_id}</p><p>原値測定。検出結果の品質確認前。</p></details>}
</div><div className={styles.comparisonMount} hidden={view !== "comparison"}>{comparisonOpened && <WorkspaceComparison beforePrepare={() => alignSelection(displayTarget)} workspace={workspace} sources={items.flatMap(value => value.result && value.field && !value.orphan && !value.exclusionReason ? [{field: value.field.id, revision: value.result.revision, label: value.label, result: value.result, metadata: value.field.metadata}] : [])} pendingFields={items.filter(value => !value.result && !value.exclusionReason).length} selection={adapter.selection()} selectionChanged={selectionState !== "current"} blocked={busy || selectionState !== "current"} options={comparisonOptions} regionSet={item?.recipe?.region_set_id || "nuclei"} gfp={gfp.enabled ? {channel: gfp.channel, controls: gfp.controls} : null} onInspect={field => {const target = items.find(value => value.field?.id === field); if (target) {setSelected(target.key);}}}/>}</div><div hidden={view !== "figure"}>{item?.result ? <WorkspaceFigureEditor adapter={adapter} workspace={workspace} result={item.result} options={metricOptions} disabled={drawing || busy || selectionState !== "current"}/> : <p className={styles.panelSection}>領域を検出すると、測定値からグラフを作成できます。</p>}</div>
      </aside>}
      <section className={[styles.drawer, drawer ? styles.drawerOpen : ""].join(" ")} aria-label="測定値"><button className={styles.drawerToggle} onClick={() => setDrawer(!drawer)} aria-expanded={drawer}>測定値 · {item?.label} · {rows.length} 領域</button>{drawer && <div className={styles.tableWrap}><table className={styles.table}><thead><tr><th>領域</th><th>面積 / px²</th><th>平均{displayRgb ? "（表示輝度）" : "（原値）"}</th><th>中央値{displayRgb ? "（表示輝度）" : "（原値）"}</th><th>積算{displayRgb ? "（表示輝度）" : "（原値）"}</th><th>採否</th></tr></thead><tbody>{rows.map(row => <tr key={row.region_id}><th><button className={styles.rowButton} aria-label={`領域 ${row.region_id} を選択`} onClick={() => {setRegion(row.region_id); setView("image");}}>{row.region_id}</button></th>{[row.area_px, row.mean, row.median, row.integrated].map((value, index) => <td key={index}>{value === null ? "—" : Number(value.toPrecision(6))}</td>)}<td>{excluded.has(row.region_id) ? "除外" : "採用"}</td></tr>)}</tbody></table></div>}</section>
    </div>{fileInputs}{methodSheet && <MethodSheet details={methodDetails} onClose={() => setMethodSheet(false)}/>}
  </main>;
}
