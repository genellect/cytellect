"use client";

import {Suspense, useEffect, useMemo, useRef, useState, type CSSProperties} from "react";
import {useSearchParams} from "next/navigation";
import {API_CONFIGURED} from "@/lib/api";
import {loadReviewPreview, releaseReviewPreview, type ReviewData, type ReviewField, type ReviewTarget} from "@/lib/workspace/review-preview";
import {ReviewImageCanvas} from "./ReviewImageCanvas";
import {ReviewMeasurementPlot, type PlotObservation} from "./ReviewMeasurementPlot";
import styles from "./review-workspace.module.css";

type Mode = "image" | "statistics" | "figure";
type Metric = "area_px" | "mean" | "median" | "integrated";
const targets: Record<ReviewTarget, string> = {nuclei: "核", nucleoli: "核小体", nucleoplasm: "核質", cell: "細胞ROI"};
const metrics: Record<Metric, string> = {area_px: "面積 / px²", mean: "平均輝度", median: "輝度中央値", integrated: "積算輝度"};
const englishMetrics: Record<Metric, string> = {area_px: "Area (px²)", mean: "Mean intensity", median: "Median intensity", integrated: "Integrated intensity"};
const iconPaths = {images: "M4 5h13v13H4zM7 2h13v13M4 14l4-5 4 4 2-2 3 4", compare: "M3 4h7v16H3zM14 4h7v16h-7z", settings: "M4 7h16M4 17h16M8 4v6M16 14v6", close: "m6 6 12 12M6 18 18-12", back: "m10 5-7 7 7 7M3 12h18", table: "M3 4h18v16H3zM3 10h18M9 4v16", ai: "M4 4h16v12H9l-5 4V4M8 8h8M8 12h5", send: "M12 20V4m-7 7 7-7 7 7", plus: "M12 4v16M4 12h16"};
function Icon({name}: {name: keyof typeof iconPaths}) { return <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={iconPaths[name]}/></svg>; }
function ChannelImage({src, label}: {src?: string; label: string}) { return src ? <img src={src} alt={label} draggable={false}/> : <span className={styles.noThumb}>画像なし</span>; }

export default function ReviewWorkspace() { return <Suspense fallback={<p>読み込み中…</p>}><ReviewRoute/></Suspense>; }
function ReviewRoute() {
  const id = useSearchParams().get("id") || undefined;
  const [data, setData] = useState<ReviewData | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!API_CONFIGURED) return;
    let active = true; let loaded: ReviewData | undefined;
    loadReviewPreview(id).then(value => {loaded = value; if (active) setData(value); else releaseReviewPreview(value);}).catch(() => {if (active) setError("保存した作業を開けません。解析画面で作業を開いてから、もう一度アクセスしてください。");});
    return () => {active = false; if (loaded) releaseReviewPreview(loaded);};
  }, [id]);
  if (!API_CONFIGURED) return <main className={styles.load}><h1>Cytellect</h1><p>この画面はローカルの解析環境から開けます。</p></main>;
  if (!data) return <main className={styles.load}><h1>Cytellect</h1><p role="status">{error || "保存した画像と測定結果を読み込み中…"}</p>{error && <a href="/workspace">解析画面を開く</a>}</main>;
  return <ReviewSession data={data}/>;
}

function ReviewSession({data}: {data: ReviewData}) {
  const initial = data.fields.find(field => field.results.nuclei) || data.fields[0];
  const [mode, setMode] = useState<Mode>("image");
  const [fieldId, setFieldId] = useState(initial?.id || "");
  const [channelId, setChannelId] = useState(initial?.nuclearChannelId || initial?.channels.find(channel => channel.role === "nuclear")?.id || initial?.channels[0]?.id || "");
  const [target, setTarget] = useState<ReviewTarget>("nuclei");
  const [region, setRegion] = useState<number>();
  const [metric, setMetric] = useState<Metric>("mean");
  const [compare, setCompare] = useState(false);
  const [selectedPlanes, setSelectedPlanes] = useState<string[]>([]);
  const [comparisonPicker, setComparisonPicker] = useState(false);
  const [tableOpen, setTableOpen] = useState(false);
  const [assignmentsOpen, setAssignmentsOpen] = useState(false);
  const [inspectorOpen, setInspectorOpen] = useState(true);
  const [aiOpen, setAiOpen] = useState(false);
  const [instruction, setInstruction] = useState("");
  const [search, setSearch] = useState("");
  const [returnMode, setReturnMode] = useState<Mode | null>(null);
  const [statistic, setStatistic] = useState("distribution");
  const [nucleolarSource, setNucleolarSource] = useState("dapi_poor");
  const [gfpFilter, setGfpFilter] = useState("all");
  const [xLabel, setXLabel] = useState("Field");
  const [yLabel, setYLabel] = useState("");
  const [yMin, setYMin] = useState("");
  const [yMax, setYMax] = useState("");
  const [paperWidth, setPaperWidth] = useState("183");
  const [roleDrafts, setRoleDrafts] = useState<Record<string, string>>({});
  const instructionRef = useRef<HTMLTextAreaElement>(null);
  const field = data.fields.find(item => item.id === fieldId) || initial;
  const channel = field?.channels.find(item => item.id === channelId) || field?.channels[0];
  const result = field?.results[target];
  const planeKey = (item: ReviewField, ch: string) => `${item.id}:${ch}`;
  const planes = data.fields.flatMap(item => item.channels.map(ch => ({field: item, channel: ch, key: planeKey(item, ch.id)})));
  const shownPlanes = compare ? planes.filter(plane => selectedPlanes.includes(plane.key)) : planes.filter(plane => plane.field.id === field?.id && plane.channel.id === channel?.id);
  const points = useMemo<PlotObservation[]>(() => data.fields.flatMap(item => {
    const saved = item.results[target];
    const seen = new Set<number>();
    return (saved?.rows || []).flatMap(row => {
      if (metric !== "area_px" && row.channel_id !== channelId) return [];
      if (seen.has(row.region_id) || saved?.exclusions.some(exclusion => exclusion.field_id === item.id && (exclusion.region_id === row.region_id || exclusion.region_id === null))) return [];
      seen.add(row.region_id);
      const value = row[metric];
      return value === null || !Number.isFinite(value) ? [] : [{fieldId: item.id, fieldLabel: item.label, regionId: row.region_id, value}];
    });
  }), [data.fields, target, channelId, metric]);
  const rows = (result?.rows || []).filter(row => row.channel_id === channel?.id);
  const selectedRow = rows.find(row => row.region_id === region);
  const currentValueLabel = `${targets[target]} · ${metric === "area_px" ? metrics[metric] : `${channel?.stain || channel?.label || ""} ${metrics[metric]}`}`;
  function selectField(item: ReviewField) {
    setFieldId(item.id); setRegion(undefined);
    if (!item.channels.some(ch => ch.id === channelId)) setChannelId(item.nuclearChannelId || item.channels.find(ch => ch.role === "nuclear")?.id || item.channels[0]?.id || "");
  }
  function inspect(point: PlotObservation) {setReturnMode(mode); setFieldId(point.fieldId); setRegion(point.regionId); setCompare(false); setMode("image");}
  function openComparison() {
    if (!selectedPlanes.length && field) setSelectedPlanes(field.channels.map(ch => planeKey(field, ch.id)));
    setCompare(true); setComparisonPicker(true);
  }
  function switchMode(value: Mode) {setMode(value); setReturnMode(null); setAssignmentsOpen(false); setComparisonPicker(false);}
  function changeTarget(value: ReviewTarget) {setTarget(value); setRegion(undefined);}
  const figureLabel = yLabel || englishMetrics[metric];
  return <main className={styles.workspace} data-mode={mode} data-inspector={inspectorOpen || aiOpen}>
    <header className={styles.header}>
      <a className={styles.brand} href={`/workspace?id=${encodeURIComponent(data.workspaceId)}`}>cytellect</a>
      <nav aria-label="作業の切替" className={styles.navigation}>{([["image", "画像"], ["statistics", "統計"], ["figure", "グラフ"]] as const).map(([value,label]) => <button key={value} aria-current={mode === value ? "page" : undefined} onClick={() => switchMode(value)}>{label}</button>)}</nav>
      <div className={styles.headerActions}><span className={styles.previewLabel} title="画面構成の確認用です。保存した画像・測定値を表示し、解析やAI送信は実行しません。">操作確認</span><button className={styles.iconButton} aria-label="設定パネル" aria-pressed={inspectorOpen} onClick={() => {setInspectorOpen(!inspectorOpen); setAiOpen(false);}}><Icon name="settings"/></button><button className={styles.primary} disabled title="画面確認後に実際の測定へ接続します">{mode === "figure" ? "保存" : mode === "statistics" ? "計算" : "測定"}</button></div>
    </header>

    <aside className={styles.sidebar} aria-label={mode === "image" ? "視野一覧" : mode === "statistics" ? "解析一覧" : "図一覧"}>
      {mode === "image" ? <><div className={styles.sidebarHeading}><span>視野</span><span>{data.fields.length}</span></div><label className={styles.search}><span className={styles.srOnly}>視野を検索</span><input placeholder="視野を検索" value={search} onChange={event => setSearch(event.target.value)}/></label><div className={styles.fieldList}>{data.fields.filter(item => item.label.toLowerCase().includes(search.toLowerCase())).map((item,index) => {
        const ch = item.channels.find(value => value.id === item.nuclearChannelId) || item.channels.find(value => value.role === "nuclear") || item.channels[0];
        return <button key={item.id} className={styles.fieldCard} aria-pressed={item.id === field?.id} onClick={() => {selectField(item); setCompare(false);}} title={item.label}><ChannelImage src={item.previews[ch?.id]} label={item.label}/><span className={styles.fieldNumber}>{index+1}</span><span className={styles.fieldName}>{item.label}</span><span className={styles.fieldState}>{item.results[target] ? `${targets[target]} ${new Set(item.results[target]!.masks.regions.map(value => value.id)).size}` : `${targets[target]} 未測定`}</span></button>;
      })}</div><button className={styles.addButton} disabled title="操作確認画面では画像を登録しません"><Icon name="plus"/><span>画像を追加</span></button></> : <><div className={styles.sidebarHeading}><span>{mode === "statistics" ? "解析" : "図"}</span></div><button className={styles.resultListItem} aria-current="true" onClick={() => {setStatistic("distribution");}}><Icon name={mode === "figure" ? "images" : "table"}/><span>{targets[target]}の分布<small>{metrics[metric]}</small></span></button><p className={styles.sidebarNote}>保存済み測定値</p></>}
    </aside>

    <section className={styles.content} aria-label={mode === "image" ? "画像と測定値" : "解析結果"}>
      <div className={styles.contextBar}>
        {returnMode && <button className={styles.iconButton} aria-label="元の結果へ戻る" onClick={() => {setMode(returnMode); setReturnMode(null);}}><Icon name="back"/></button>}
        <strong title={field?.label}>{mode === "image" ? compare ? `${shownPlanes.length}画像を比較` : field?.label || "画像" : currentValueLabel}</strong>
        <div className={styles.contextActions}>{mode === "image" && <><button className={styles.textButton} onClick={() => setAssignmentsOpen(!assignmentsOpen)}>染色対応</button><button className={styles.iconButton} aria-label="画像を比較" aria-pressed={compare} onClick={openComparison}><Icon name="compare"/></button></>}</div>
      </div>
      {mode === "image" && <div className={styles.channelBar} aria-label="表示チャンネル">{field?.channels.map(ch => <button key={ch.id} aria-pressed={channel?.id === ch.id && !compare} onClick={() => {setChannelId(ch.id); setCompare(false);}}>{ch.stain || ch.label}<small>{ch.stain ? ch.id : ""}</small></button>)}<span className={styles.targetIndicator}>{targets[target]}{result ? ` ${new Set(result.masks.regions.map(value => value.id)).size}` : " 未測定"}</span></div>}

      {assignmentsOpen && mode === "image" && <section className={styles.inlinePanel} aria-label="染色対応の編集"><div className={styles.panelHeading}><strong>染色対応</strong><button className={styles.iconButton} aria-label="染色対応を閉じる" onClick={() => setAssignmentsOpen(false)}><Icon name="close"/></button></div><div className={styles.assignmentGrid}>{field?.channels.map(ch => <label key={ch.id}><ChannelImage src={field.previews[ch.id]} label={ch.label}/><span>{ch.id}{ch.role === "nuclear" ? " · 核検出" : ""}</span><input aria-label={`${ch.id}の染色名`} value={roleDrafts[ch.id] ?? ch.stain ?? ""} placeholder="染色名" onChange={event => setRoleDrafts({...roleDrafts, [ch.id]:event.target.value})}/></label>)}</div><small>対応変更の操作確認です。保存済みの割当は変更しません。</small></section>}

      {comparisonPicker && mode === "image" && <div className={styles.comparisonPicker}><span>比較する画像</span>{planes.map(plane => <label key={plane.key}><input type="checkbox" checked={selectedPlanes.includes(plane.key)} onChange={event => setSelectedPlanes(previous => event.target.checked ? [...previous, plane.key] : previous.filter(key => key !== plane.key))}/>{data.fields.indexOf(plane.field)+1} / {plane.channel.stain || plane.channel.label}</label>)}<button className={styles.iconButton} aria-label="比較する画像の選択を閉じる" onClick={() => setComparisonPicker(false)}><Icon name="close"/></button></div>}

      {mode === "image" ? <>
        <ImageArea planes={shownPlanes} target={target} selectedField={fieldId} region={region} onSelect={(item,ch,id) => {setFieldId(item.id);setChannelId(ch);setRegion(id);}} onOpen={(item,ch) => {selectField(item); setChannelId(ch); setCompare(false); setComparisonPicker(false);}}/>
        <div className={styles.measurementToggle}><button className={styles.textButton} aria-expanded={tableOpen} onClick={() => setTableOpen(!tableOpen)}><Icon name="table"/>測定値 {rows.length ? `(${rows.length})` : ""}</button><span>{selectedRow ? `${targets[target]} ${selectedRow.region_id} · ${metrics[metric]} ${selectedRow[metric]?.toLocaleString() ?? "—"}` : ""}</span></div>
        {tableOpen && <div className={styles.measurementTable}><table><caption>{currentValueLabel}</caption><thead><tr><th>{targets[target]}</th><th>面積 / px²</th><th>平均輝度</th><th>中央値</th><th>積算輝度</th></tr></thead><tbody>{rows.map(row => <tr key={row.region_id} aria-selected={region === row.region_id}><td><button className={styles.textButton} onClick={() => setRegion(row.region_id)}>{row.region_id}</button></td>{([row.area_px,row.mean,row.median,row.integrated]).map((value,index) => <td key={index}>{value?.toLocaleString(undefined,{maximumFractionDigits:3}) ?? "—"}</td>)}</tr>)}</tbody></table>{!rows.length && <p>この対象の測定値はありません。</p>}</div>}
      </> : <div className={styles.resultCanvas}>
        {mode === "statistics" && <div className={styles.statTabs} aria-label="統計の目的">{[["distribution","分布"],["comparison","群間比較"],["association","関連"]].map(([value,label]) => <button key={value} aria-pressed={statistic === value} onClick={() => setStatistic(value)}>{label}</button>)}</div>}
        {mode === "statistics" && statistic !== "distribution" && <p className={styles.inlineNotice}>{statistic === "comparison" ? "比較条件を右側で設定します。現在は保存済みの個別測定値を表示しています。" : "関連の設定を右側で確認できます。現在の図は視野別の測定値です。"}</p>}
        <div className={styles.figurePaper} style={{"--paper-width":paperWidth === "89" ? "62%" : "100%"} as CSSProperties}><ReviewMeasurementPlot points={points} yLabel={figureLabel} xLabel={xLabel} yMin={yMin === "" ? undefined : Number(yMin)} yMax={yMax === "" ? undefined : Number(yMax)} onSelect={inspect} selected={region === undefined ? undefined : {fieldId,regionId:region}}/></div>
        <div className={styles.figureFooter}><span>{points.length} {targets[target]} · 保存済み測定値</span><button className={styles.textButton} onClick={() => switchMode(mode === "statistics" ? "figure" : "statistics")}>{mode === "statistics" ? "図を編集" : "測定項目を確認"}</button></div>
      </div>}
    </section>

    {(inspectorOpen || aiOpen) && <aside key={aiOpen ? "ai" : mode} className={styles.inspector} aria-label={aiOpen ? "AI" : "設定"}>
      <div className={styles.panelHeading}><h2>{aiOpen ? "AI" : mode === "image" ? "画像解析" : mode === "statistics" ? "解析条件" : "図の設定"}</h2><button className={styles.iconButton} aria-label="パネルを閉じる" onClick={() => {setAiOpen(false);setInspectorOpen(false);}}><Icon name="close"/></button></div>
      <div className={styles.inspectorBody}>
      {aiOpen ? <><p className={styles.aiIntro}>解析の指示を入力</p><div className={styles.aiContext}><span>現在の対象</span><strong>{targets[target]}</strong><span>測定項目</span><strong>{metrics[metric]}</strong><span>表示</span><strong>{{image:"画像",statistics:"統計",figure:"グラフ"}[mode]}</strong></div>{instruction && <div className={styles.instructionDraft}>{instruction}</div>}<p className={styles.smallNote}>この操作確認画面ではAIへ送信しません。</p></> : <>
        <label className={styles.control}>対象<select value={target} onChange={event => changeTarget(event.target.value as ReviewTarget)}>{Object.entries(targets).map(([value,label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        {mode === "image" ? <>
          <section className={styles.controlSection}><h3>検出</h3>{target === "nuclei" ? <><div className={styles.settingLine}><span>核染色</span><strong>{field?.channels.find(ch => ch.id === field.nuclearChannelId || ch.role === "nuclear")?.stain || field?.nuclearChannelId || "未設定"}</strong></div><div className={styles.settingLine}><span>方法</span><strong>StarDist 2D</strong></div><details><summary>検出条件</summary><label className={styles.control}>確率閾値<input type="number" min="0" max="1" step="0.05" defaultValue="0.5"/></label><label className={styles.control}>NMS閾値<input type="number" min="0" max="1" step="0.05" defaultValue="0.3"/></label></details></> : target === "nucleoli" ? <><label className={styles.control}>定義に使う画像<select value={nucleolarSource} onChange={event => setNucleolarSource(event.target.value)}><option value="dapi_poor">核染色の低輝度領域</option><option value="marker">核小体マーカー</option><option value="ncl_legacy">NCL（既存解析の再現）</option></select></label><p className={styles.smallNote}>採用した核の内側で検出</p></> : target === "nucleoplasm" ? <p>核から核小体を除いた範囲</p> : <p>細胞の輪郭を画像上で指定</p>}</section>
          <section className={styles.controlSection}><h3>測定</h3><label className={styles.control}>指標<select value={metric} onChange={event => setMetric(event.target.value as Metric)}>{Object.entries(metrics).map(([value,label]) => <option key={value} value={value}>{label}</option>)}</select></label><label className={styles.control}>測定チャンネル<select value={channel?.id || ""} onChange={event => setChannelId(event.target.value)}>{field?.channels.map(ch => <option key={ch.id} value={ch.id}>{ch.stain || ch.label}</option>)}</select></label><details><summary>背景補正</summary><p className={styles.smallNote}>背景ROIの指定は次段階で接続します。表示中の値は保存された原値です。</p></details></section>
          <section className={styles.controlSection}><h3>GFPによる選別</h3><label className={styles.control}>対象<select value={gfpFilter} onChange={event => setGfpFilter(event.target.value)}><option value="all">全対象</option><option value="positive">GFP陽性</option></select></label>{gfpFilter === "positive" && <><p className={styles.smallNote}>1核を1細胞として判定。陽性の画素数では数えません。</p><p className={styles.smallNote}>この画面では保存値への選別は未適用です。</p></>}</section>
        </> : <>
          <label className={styles.control}>指標<select value={metric} onChange={event => {setMetric(event.target.value as Metric);setYLabel("");}}>{Object.entries(metrics).map(([value,label]) => <option key={value} value={value}>{label}</option>)}</select></label>
          <label className={styles.control}>測定チャンネル<select value={channelId} onChange={event => setChannelId(event.target.value)}>{data.channels.map(ch => <option value={ch.id} key={ch.id}>{ch.stain || ch.label}</option>)}</select></label>
          {mode === "statistics" ? statistic === "distribution" ? <p className={styles.smallNote}>点を選ぶと、その対象の元画像を開きます。</p> : <section className={styles.controlSection}><h3>{statistic === "comparison" ? "実験デザイン" : "関連の設定"}</h3><label className={styles.control}>{statistic === "comparison" ? "対応関係" : "Y軸の指標"}<select>{statistic === "comparison" ? <><option>独立した群</option><option>対応のある測定</option></> : Object.entries(metrics).map(([value,label]) => <option key={value}>{label}</option>)}</select></label><label className={styles.control}>方法<select>{(statistic === "comparison" ? ["Welch t検定","対応ありt検定","Mann–Whitney U","Wilcoxon","Welch ANOVA","Kruskal–Wallis"] : ["Pearson","Spearman"]).map(label => <option key={label}>{label}</option>)}</select></label><details><summary>群・実験単位</summary><p className={styles.smallNote}>試料と独立実験単位の入力は、次段階で保存情報へ接続します。</p></details></section> : <>
            <section className={styles.controlSection}><h3>軸</h3><label className={styles.control}>X軸ラベル<input value={xLabel} onChange={event => setXLabel(event.target.value)}/></label><label className={styles.control}>Y軸ラベル<input value={figureLabel} onChange={event => setYLabel(event.target.value)}/></label><div className={styles.twoControls}><label className={styles.control}>下限<input type="number" placeholder="自動" value={yMin} onChange={event => setYMin(event.target.value)}/></label><label className={styles.control}>上限<input type="number" placeholder="自動" value={yMax} onChange={event => setYMax(event.target.value)}/></label></div></section>
            <section className={styles.controlSection}><h3>図のサイズ</h3><label className={styles.control}>幅<select value={paperWidth} onChange={event => setPaperWidth(event.target.value)}><option value="89">89 mm</option><option value="183">183 mm</option></select></label><p className={styles.smallNote}>配置と軸編集の操作確認です。論文用ファイルは既存のMatplotlib出力へ接続します。</p></section>
          </>}
        </>}
      </>}
      </div>
    </aside>}

    <footer className={styles.composer}><button className={styles.iconButton} aria-label="AIの会話を開く" aria-pressed={aiOpen} onClick={() => {setAiOpen(!aiOpen); instructionRef.current?.focus();}}><Icon name="ai"/></button><textarea ref={instructionRef} rows={1} aria-label="AIへの指示" placeholder="AIに指示" value={instruction} onChange={event => setInstruction(event.target.value)}/><button className={styles.sendButton} disabled title="操作確認画面では有料APIを呼びません" aria-label="AIへ送信"><Icon name="send"/></button></footer>
  </main>;
}

function ImageArea({planes,target,selectedField,region,onSelect,onOpen}: {planes:Array<{field:ReviewField;channel:{id:string;label:string;stain:string|null};key:string}>;target:ReviewTarget;selectedField:string;region?:number;onSelect:(field:ReviewField,channel:string,id:number)=>void;onOpen:(field:ReviewField,channel:string)=>void}) {
  const root = useRef<HTMLDivElement>(null);
  const [bounds,setBounds] = useState({width:800,height:600});
  useEffect(() => {const node=root.current;if (!node)return;const observer=new ResizeObserver(entries=>{const {width,height}=entries[0].contentRect;setBounds({width,height});});observer.observe(node);return()=>observer.disconnect();},[]);
  let columns=1;let best=0;const count=Math.max(1,planes.length);const ratio=planes[0] ? planes[0].field.width/planes[0].field.height:1;
  for(let c=1;c<=count;c++){const rows=Math.ceil(count/c);const w=(bounds.width-(c-1)*8)/c;const h=(bounds.height-(rows-1)*8)/rows-34;const edge=Math.min(w,h*ratio);if(edge>best){best=edge;columns=c;}}
  if(best<240 && count>1)columns=Math.max(1,Math.floor(bounds.width/280));
  return <div ref={root} className={styles.imageArea} style={{"--image-columns":columns,"--image-rows":Math.ceil(count/columns),"--minimum-tile":planes.length>1?"260px":"0px"} as CSSProperties}>
    {!planes.length && <p className={styles.empty}>比較する画像を選択してください。</p>}
    {planes.map(plane => <div key={plane.key} className={styles.imageTile}>{planes.length>1 && <div className={styles.tileCaption}><span>{plane.field.label}</span><strong>{plane.channel.stain || plane.channel.label}</strong></div>}{plane.field.previews[plane.channel.id] ? <ReviewImageCanvas src={plane.field.previews[plane.channel.id]} width={plane.field.width} height={plane.field.height} label={`${plane.field.label} ${plane.channel.stain || plane.channel.label}`} contours={plane.field.results[target]?.masks.regions || []} selected={selectedField===plane.field.id?region:undefined} onSelect={id=>onSelect(plane.field,plane.channel.id,id)} onOpen={planes.length>1?()=>onOpen(plane.field,plane.channel.id):undefined}/> : <div className={styles.empty}>画像を読み込めませんでした</div>}</div>)}
  </div>;
}
