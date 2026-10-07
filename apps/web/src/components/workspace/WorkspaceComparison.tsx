"use client";
import {useEffect, useMemo, useState} from "react";
import {ApiError, download, errorMessage, request} from "@/lib/api";
import {comparisonMethodLabel} from "@/lib/common-statistics";
import {comparisonWarnings, probabilityLabel} from "@/lib/region-comparison-view";
import {formatValue, type Job} from "@/lib/types";
import {usePrivateImage} from "@/lib/usePrivateImage";
import {comparisonRequest, createComparisonAdapter, type ComparisonChoices, type ComparisonResult, type ComparisonSource, type GfpChoice, type Metadata} from "@/lib/workspace/comparison-adapter";
import type {WorkspaceSelection} from "@/lib/workspace/api-adapter";
import styles from "./analysis-workspace.module.css";

interface Props {beforePrepare?: () => Promise<WorkspaceSelection | null>; selectionChanged?: boolean; selection?: WorkspaceSelection | null; workspace: string; sources: ComparisonSource[]; pendingFields: number; blocked: boolean; options: Array<{key: string; label: string}>; regionSet: string; onInspect: (field: string) => void; gfp?: GfpChoice | null}
const blank: Metadata = {condition: null, sample: null, experimental_unit: null, pair: null, acquisition_date: null, repeat_length: null};
const fail = (error: unknown) => error instanceof ApiError ? errorMessage(error) : error instanceof Error ? error.message : "比較を完了できませんでした。";
const initial: ComparisonChoices = {metric: "area_px", channel: null, regionSet: "nuclei", design: "independent", method: "parametric", unitDefinition: "", pairingBasis: "", contrasts: [], independence: false, acquisition: false, sampling: false, missingness: false, kind: "distribution", width: 178, height: 76, yLabel: ""};

/** Progressive inference: metadata and human decisions are never prerequisites for raw analysis. */
export function WorkspaceComparison({beforePrepare, selection = null, selectionChanged = false, workspace, sources, pendingFields, blocked, options, regionSet, onInspect, gfp = null}: Props) {
  const adapter = useMemo(() => createComparisonAdapter(), []);
  const [selectedFields, setSelectedFields] = useState<string[]>([]);
  const [batchKey, setBatchKey] = useState<keyof Metadata>("condition");
  const [batchValue, setBatchValue] = useState("");
  const [metadata, setMetadata] = useState<Record<string, Metadata>>({});
  const [choices, setChoices] = useState<ComparisonChoices>(initial);
  const [prepared, setPrepared] = useState<{revision: string; identity: string} | null>(null);
  const [review, setReview] = useState(false);
  const [storedMetadata, setStoredMetadata] = useState<{revision: string; fields: Record<string, Metadata>} | null>(null);
  const [history, setHistory] = useState<Job[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState<{job: string; result: ComparisonResult; identity: string; spec: string} | null>(null);
  const fields = Object.fromEntries(sources.map(source => [source.field, metadata[source.field] ?? {...blank, ...source.metadata}]));
  const identity = JSON.stringify([sources.map(source => [source.field, source.revision]), fields, selection]);
  const currentPrepared = prepared?.identity === identity ? prepared : null;
  const conditions = [...new Set(Object.values(fields).map(value => value.condition?.trim()).filter((value): value is string => !!value))];
  const pairs = conditions.flatMap((a, i) => conditions.slice(i + 1).map(b => [a, b]));
  const contrastKey = (pair: string[]) => JSON.stringify(pair);
  const metadataReady = sources.length >= 2 && pendingFields === 0 && Object.values(fields).every(value => value.condition?.trim() && value.experimental_unit?.trim() && value.sample?.trim() && (choices.design !== "paired" || value.pair?.trim()) && (choices.metric.startsWith("area_") || value.acquisition_date?.trim()));
  const validContrasts = choices.contrasts.length > 0 && choices.contrasts.every(pair => pair.every(group => conditions.includes(group)));
  let spec: ReturnType<typeof comparisonRequest> | null = null;
  // An enabled but incomplete GFP step leaves no request, never a silently ungated one.
  try {if (validContrasts) spec = comparisonRequest({...choices, regionSet, gfp});} catch { /* Readiness is represented by the unchecked visible decisions. */ }
  const ready = !!currentPrepared && review && !!spec && metadataReady && !busy && !blocked;
  const changed = saved && (selectionChanged || saved.identity !== identity || saved.spec !== JSON.stringify(spec));
  // Any source/metadata change revokes human decisions; old output remains visibly historical.
  useEffect(() => {setReview(false); setChoices(value => ({...value, independence: false, acquisition: false, sampling: false, missingness: false}));}, [identity]);
  useEffect(() => {let active = true; void adapter.history(workspace).then(value => {if (active) setHistory(value);}).catch(() => {}); return () => {active = false;};}, [adapter, workspace]);
  const sourceIdentity = JSON.stringify([sources.map(source => [source.field, source.revision]), selection]);
  useEffect(() => {let active = true; void adapter.metadata(workspace, sources, selection).then(value => {if (active) setStoredMetadata(value);}).catch(() => {}); return () => {active = false;}; /* IDs, rather than render-time array identity, bind this lookup. */
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [adapter, workspace, sourceIdentity]);
  function choice(next: Partial<ComparisonChoices>, affectsDesign = false) {
    setChoices(value => ({...value, ...next, ...(affectsDesign ? {independence: false, acquisition: false, sampling: false, missingness: false} : {})}));
  }
  function edit(field: string, key: keyof Metadata, text: string) {
    setMetadata(value => ({...value, [field]: {...fields[field], [key]: text || null}}));
  }
  async function prepare() {
    if (!metadataReady || busy || blocked || selectionChanged) return; setBusy(true); setError("");
    // The compared target is adopted only now, by this explicit action, never by viewing it.
    try {const adopted = beforePrepare ? await beforePrepare() : selection; const revision = await adapter.cohort(workspace, sources, fields, adopted); setPrepared({revision, identity: JSON.stringify([sources.map(source => [source.field, source.revision]), fields, adopted])}); setReview(false);}
    catch (cause) {setError(fail(cause));} finally {setBusy(false);}
  }
  async function calculate() {
    if (!ready || !spec || !currentPrepared) return; setBusy(true); setError("");
    try {await adapter.review(currentPrepared.revision, review); const result = await adapter.compare(workspace, currentPrepared.revision, spec); setSaved({...result, identity, spec: JSON.stringify(spec)});}
    catch (cause) {setError(fail(cause));} finally {setBusy(false);}
  }
  return <section className={styles.comparison} aria-label="独立実験単位の比較">
    {selectionChanged && <p role="status">採用状態が変更されたか確認できません。保存された比較は旧版として表示します。</p>}
    <h2>群を比較</h2><p>1点は独立実験単位です。領域の中央値 → 試料内の視野平均 → 独立実験単位内の試料平均で集計します。</p>
    {gfp && (!gfp.channel || !gfp.controls.length) && <p role="status">GFP 陽性の核に限る設定が未完了です。方法の「対象」で GFP のチャンネルと陰性対照の視野を選ぶか、「限定しない」に戻してください。</p>}
    {!!pendingFields && <p role="status">未完了の視野が {pendingFields} 件あります。解析を完了するか、失敗した視野を理由付きで除外してください。</p>}
    {!!selection?.entries.some(entry => entry.exclusion_reason) && <details><summary>比較から除外した視野</summary>{selection.entries.filter(entry => entry.exclusion_reason).map(entry => <p key={entry.id}>{entry.field_id || "未登録の視野"}：{entry.exclusion_reason}</p>)}</details>}
    {storedMetadata && <button className={styles.secondary} disabled={busy || blocked} onClick={() => {setMetadata(storedMetadata.fields); setPrepared({revision: storedMetadata.revision, identity: JSON.stringify([sources.map(source => [source.field, source.revision]), storedMetadata.fields, selection])}); setReview(false);}}>保存した実験情報を復元</button>}
    <details open={!saved}><summary>比較条件</summary><fieldset disabled={busy || blocked}>
      <legend>比較する測定値と実験デザイン</legend>
      <div className={styles.comparisonControls}><label>測定値<select value={choices.channel ? `${choices.channel}:${choices.metric}` : choices.metric} onChange={event => {const parts = event.target.value.split(":"); choice({metric: parts.at(-1)! as ComparisonChoices["metric"], channel: parts.length > 1 ? parts[0] : null}, true);}}>{options.map(option => <option key={option.key} value={option.key}>{option.label}</option>)}</select></label>
      <label>対応<select value={choices.design} onChange={event => choice({design: event.target.value as ComparisonChoices["design"], kind: event.target.value === "paired" ? "paired" : "distribution"}, true)}><option value="independent">独立した群</option><option value="paired">同じ対象の対応あり</option></select></label>
      <label>独立実験単位の定義<input maxLength={200} value={choices.unitDefinition} placeholder="例：独立した培養、個体" onChange={event => choice({unitDefinition: event.target.value}, true)}/></label>
      {choices.design === "paired" && <label>対応の根拠<input maxLength={200} value={choices.pairingBasis} onChange={event => choice({pairingBasis: event.target.value}, true)}/></label>}</div>
      <details open={!currentPrepared}><summary>視野の群・試料・実験単位</summary><details><summary>IDの付け方</summary><p>同じ試料の視野には同じ試料ID、同じ独立反復には同じ単位IDを入力します。撮影日や細胞数から独立性を推定しません。</p></details><div className={styles.comparisonControls}><button className={styles.secondary} onClick={() => setSelectedFields(sources.map(source => source.field))}>全視野を選択</button><label>まとめて入力<select value={batchKey} onChange={event => setBatchKey(event.target.value as keyof Metadata)}><option value="condition">群</option><option value="sample">試料ID</option><option value="experimental_unit">独立単位ID</option><option value="acquisition_date">撮影日／バッチ</option>{choices.design === "paired" && <option value="pair">対応ペアID</option>}</select></label><label>入力する値<input value={batchValue} maxLength={80} onChange={event => setBatchValue(event.target.value)}/></label><button className={styles.secondary} disabled={!selectedFields.length || !batchValue.trim()} onClick={() => setMetadata(value => ({...value, ...Object.fromEntries(selectedFields.map(field => [field, {...fields[field], [batchKey]: batchValue.trim()}]))}))}>選択した {selectedFields.length} 視野に適用</button></div>
      <div className={styles.tableWrap}><table className={styles.table}><thead><tr><th>選択</th><th>視野</th><th>群</th><th>試料ID</th><th>独立単位ID</th>{choices.design === "paired" && <th>対応ペアID</th>}{!choices.metric.startsWith("area_") && <th>撮影日／バッチ</th>}<th>元結果</th></tr></thead><tbody>{sources.map(source => <tr key={source.field}><td><input type="checkbox" aria-label={`${source.label} をまとめて入力`} checked={selectedFields.includes(source.field)} onChange={event => setSelectedFields(value => event.target.checked ? [...value, source.field] : value.filter(field => field !== source.field))}/></td><th>{source.label}</th>{(["condition", "sample", "experimental_unit", ...(choices.design === "paired" ? ["pair"] : []), ...(!choices.metric.startsWith("area_") ? ["acquisition_date"] : [])] as Array<keyof Metadata>).map(key => <td key={key}><input aria-label={`${source.label} ${key}`} maxLength={80} value={String(fields[source.field][key] ?? "")} onChange={event => edit(source.field, key, event.target.value)}/></td>)}<td><button className={styles.secondary} onClick={() => onInspect(source.field)}>画像を見る</button></td></tr>)}</tbody></table></div>
      <button className={styles.secondary} disabled={!metadataReady} onClick={() => void prepare()}>{currentPrepared ? "比較対象を保存済み" : "比較対象を保存"}</button><p>元画像・保存マスク・除外を引き継ぎます。核検出は再実行しません。</p></details>
      <h3>比較する組（Holm補正の対象）</h3>{!pairs.length && <p>視野の群名を2種類以上入力してください。</p>}
      <div className={styles.comparisonControls}>{pairs.map(pair => <label key={contrastKey(pair)}><input type="checkbox" checked={choices.contrasts.some(value => contrastKey(value) === contrastKey(pair))} onChange={event => choice({contrasts: event.target.checked ? [...choices.contrasts, pair] : choices.contrasts.filter(value => contrastKey(value) !== contrastKey(pair))}, true)}/>{pair.join(" と ")}</label>)}</div>
      <label>検定<select value={choices.method} onChange={event => choice({method: event.target.value as ComparisonChoices["method"]}, true)}><option value="parametric">平均の比較（t検定／Welch ANOVA）</option><option value="rank">順位の比較（Mann–Whitney／Wilcoxon／Kruskal–Wallis）</option></select></label>
      <p>{comparisonMethodLabel(choices.method, choices.design, new Set(choices.contrasts.flat()).size)}。{choices.method === "rank" ? choices.design === "paired" ? "対応差の対称性を仮定します。ゼロ差・同順位の処理はMethodsに記録します。" : "群間の分布を比較します。分布の形が異なる場合、中央値の差だけの検定ではありません。" : "独立単位の要約値を比較します。個別の95%信頼区間はHolm補正前です。"}</p>
      {new Set(choices.contrasts.flat()).size >= 3 && choices.design === "independent" && <p>全体検定と宣言した群間比較を両方実行します。得られたp値で実行する検定を変えません。</p>}
      {currentPrepared && <><h3>画像と採否を確認</h3><div className={styles.tableWrap}><table className={styles.table}><thead><tr><th>視野</th><th>検出領域</th><th>明示除外</th></tr></thead><tbody>{sources.map(source => <tr key={source.field}><th>{source.label}</th><td>{source.result.masks.regions.length}</td><td>{source.result.exclusions.filter(value => value.field_id === source.field).length}</td></tr>)}</tbody></table></div>
      <label><input type="checkbox" checked={review} onChange={event => setReview(event.target.checked)}/>各視野の画像・領域と除外を確認しました。比較の実行時に、この解析版をレビュー済みとして記録します。</label></>}
      <div className={styles.comparisonDecisions}>
      <label><input type="checkbox" checked={choices.independence} onChange={event => choice({independence: event.target.checked})}/>入力した単位の独立性と対応関係を確認しました。</label>
      <label><input type="checkbox" checked={choices.acquisition} onChange={event => choice({acquisition: event.target.checked})}/>{choices.metric.startsWith("area_") ? "領域の定義と面積の尺度を群間で比較できます。" : "撮影・標識・背景と非飽和の原値信号を群間で比較できます（背景補正はしません）。"}</label>
      {(choices.metric === "area_px" || choices.metric.includes("integrated")) && <label><input type="checkbox" checked={choices.sampling} onChange={event => choice({sampling: event.target.checked})}/>画素の大きさと空間サンプリングが同じです。</label>}
      <label><input type="checkbox" checked={choices.missingness} onChange={event => choice({missingness: event.target.checked})}/>保存測定表の値・欠測・除外と比較対象を確認しました。</label></div>
      <details><summary>欠測・反復数と検定の前提</summary><p>未除外の単位に値がない場合や不完全なペアは、黙って落とさず比較を止めます。各群2単位または2ペア以上が必要ですが、十分な検出力を保証する数ではありません。</p></details>
      <details><summary>図の設定</summary><div className={styles.comparisonControls}>
      <label>図の種類<select value={choices.kind} onChange={event => choice({kind: event.target.value as ComparisonChoices["kind"]})}><option value="distribution">独立単位の点</option>{choices.design === "paired" && <option value="paired">対応ペアを結ぶ</option>}<option value="box">箱ひげ図と点</option><option value="violin">バイオリン図と点</option><option value="histogram">ヒストグラム</option></select></label>
      <label>比較図の幅 (mm)<input type="number" min={77} max={400} value={choices.width} onChange={event => choice({width: Math.min(400, Math.max(77, Number(event.target.value) || 178))})}/></label><label>比較図の高さ (mm)<input type="number" min={26} max={400} value={choices.height} onChange={event => choice({height: Math.min(400, Math.max(26, Number(event.target.value) || 76))})}/></label>
      <label>縦軸名<input maxLength={120} value={choices.yLabel} onChange={event => choice({yLabel: event.target.value})}/></label></div><p>設定を変更後に再実行すると、保存測定値から同じ検定を再計算して図を生成します。SVG/PDFは編集可能です。</p></details>
      <button className={styles.primary} disabled={!ready} onClick={() => void calculate()}>{busy ? "比較を処理中" : saved ? "比較と図を再実行" : "比較と図を作成"}</button>
    </fieldset></details>
    {error && <p role="alert">{error}</p>}
    {!!history.length && <details><summary>保存した比較を開く</summary>{history.map(job => <button className={styles.secondary} key={job.id} disabled={busy} onClick={() => {setBusy(true); void adapter.saved(job).then(value => setSaved({...value, identity: "historical", spec: JSON.stringify(value.result.spec)})).catch(cause => setError(fail(cause))).finally(() => setBusy(false));}}>{new Date(job.created * 1000).toLocaleString("ja-JP")} · 保存済み解析版</button>)}</details>}
    {saved && <ComparisonOutput saved={saved} changed={!!changed} sources={sources} onInspect={onInspect} onError={setError}/>}
  </section>;
}
function ComparisonOutput({saved, changed, sources, onInspect, onError}: {saved: {job: string; result: ComparisonResult}; changed: boolean; sources: ComparisonSource[]; onInspect: Props["onInspect"]; onError: (value: string) => void}) {
  const [adoption, setAdoption] = useState<WorkspaceSelection | null>(null);
  useEffect(() => {let active = true; setAdoption(null); void request<WorkspaceSelection>(`/v1/revisions/${saved.result.revision_id}/workspace-selection`).then(value => {if (active) setAdoption(value);}).catch(() => {}); return () => {active = false;};}, [saved.result.revision_id]);
  const result = saved.result; const image = usePrivateImage(`/v1/jobs/${saved.job}/files/figure.png`);
  const files = Array.isArray(result.figure.source_files) ? result.figure.source_files.filter((value): value is string => typeof value === "string") : [];
  return <section aria-label="保存された比較結果"><h3>保存された比較結果 {changed && "· 設定変更前の結果"}</h3><p>{result.metric} / {result.unit} · {result.spec.test} · 1点は独立実験単位</p>{image && <img src={image} alt="保存された独立実験単位の比較図" style={{maxWidth: "100%"}}/>}
    <p>集計条件：{result.spec.design.unit_definition} · {result.spec.design.kind === "paired" ? `対応あり：${result.spec.design.pairing_basis}` : "独立群"} · Holm補正は宣言した {result.spec.comparison_family.contrasts.length} 比較</p>
    {result.omnibus && <p>全体検定：{String(result.omnibus.method)} · p={probabilityLabel(result.omnibus.p_value)}</p>}
    <div className={styles.tableWrap}><table className={styles.table}><thead><tr><th>比較</th><th>平均差</th><th>順位効果量</th><th>95% CI（個別）</th><th>p</th><th>p Holm</th></tr></thead><tbody>{result.comparisons.map((row, index) => <tr key={index}><th>{String(row.group_a)} / {String(row.group_b)}</th><td>{formatValue(row.estimate)}</td><td>{formatValue(row.effect)} {String(row.effect_name ?? "")}</td><td>{formatValue(row.ci_low)} ～ {formatValue(row.ci_high)}</td><td>{probabilityLabel(row.p_value)}</td><td>{probabilityLabel(row.p_holm)}</td></tr>)}</tbody></table></div>
    <div className={styles.tableWrap}><table className={styles.table}><thead><tr><th>群</th><th>領域</th><th>視野</th><th>試料</th><th>独立単位</th><th>完全ペア</th></tr></thead><tbody>{result.counts.map((row, index) => <tr key={index}>{["condition", "observations", "selected_fields", "samples", "experimental_units", "complete_pairs"].map(key => <td key={key}>{formatValue(row[key])}</td>)}</tr>)}</tbody></table></div>
    {!!result.warnings.length && <ul>{result.warnings.map(warning => <li key={warning}>{comparisonWarnings[warning] ?? warning}</li>)}</ul>}
    <details><summary>採否・欠測と元視野</summary><p>採用 {formatValue(result.selection.selected)} · 除外 {formatValue(result.selection.excluded)} · 欠測 {formatValue(result.selection.missing)} · 対象外 {formatValue(result.selection.out_of_scope)}</p>{result.source_field_ledger.map((row, index) => <p key={index}>{sources.find(source => source.field === row.field_id)?.label ?? String(row.field_id)} · 群 {String(row.condition)} · 単位 {String(row.experimental_unit)} · {row.explicitly_excluded ? "除外" : row.in_scope ? "対象" : "対象外"} <button className={styles.secondary} disabled={changed} onClick={() => onInspect(String(row.field_id))}>元画像を見る</button></p>)}<p>解析版：{result.revision_id}</p></details>
    {adoption && <details><summary>比較時の視野採否</summary>{adoption.entries.filter(entry => entry.exclusion_reason).map(entry => <p key={entry.id}>{entry.field_id || "未登録の視野"}：{entry.exclusion_reason}</p>)}<button className={styles.secondary} onClick={() => void download(`/v1/revisions/${result.revision_id}/workspace-selection`, "workspace-selection.json").catch(error => onError(fail(error)))}>視野採否を保存 ↓</button></details>}
    <div className={styles.actions}>{files.map(file => <button className={styles.secondary} key={file} onClick={() => void download(`/v1/jobs/${saved.job}/files/${file}`, file).catch(error => onError(fail(error)))}>{file} ↓</button>)}</div>
  </section>;
}
