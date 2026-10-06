"use client";

import Link from "next/link";
import { useState } from "react";
import {useRouter} from "next/navigation";
import { buildPlan, emptyPlan, planReceipt, planReferences, type PlanAnswers,type CandidateId } from "@/lib/analysis-plan";
import {planningVersion} from "@/lib/planning-runtime";
import {API_CONFIGURED,LOCAL_MODE} from "@/lib/api";
import {usePlanMemory} from "./PlanMemory";
import { planningDisplay } from "@/lib/planning-display";
import styles from "./planner.module.css";

type ChoiceProps<K extends keyof PlanAnswers> = {
  label: string; name: K; value: PlanAnswers[K]; hint?: string;
  options: readonly [PlanAnswers[K], string][];
  onChange: (key: K, value: PlanAnswers[K]) => void;
};
function Choice<K extends keyof PlanAnswers>({ label, name, value, hint, options, onChange }: ChoiceProps<K>) {
  return <label className={styles.choice} htmlFor={name}>
    <span id={`${name}-label`}>{label}</span>
    <select id={name} value={value} aria-labelledby={`${name}-label`} aria-describedby={hint ? `${name}-hint` : undefined} onChange={e => onChange(name, e.target.value as PlanAnswers[K])}>
      {options.map(([key, text]) => <option key={key} value={key}>{text}</option>)}
    </select>
    {hint && <small id={`${name}-hint`}>{hint}</small>}
  </label>;
}

export function AnalysisPlanner() {
  const [answers, setAnswers] = useState<PlanAnswers>({ ...emptyPlan });
  const [selected,setSelected]=useState<CandidateId|"">("");const memory=usePlanMemory();const router=useRouter();
  const version=planningVersion(LOCAL_MODE,API_CONFIGURED);const result = buildPlan(answers,version);
  const allArea=result.candidates.length>0&&result.candidates.every(candidate=>candidate.measurement?.mode==="area_only");
  const started = Object.keys(emptyPlan).some(key => answers[key as keyof PlanAnswers] !== emptyPlan[key as keyof PlanAnswers]);
  const change = <K extends keyof PlanAnswers>(key: K, value: PlanAnswers[K]) => {setSelected("");setAnswers(a => ({ ...a, [key]: value }));};
  function save() {
    const url = URL.createObjectURL(new Blob([JSON.stringify(planReceipt(answers,version), null, 2)], { type: "application/json" }));
    const anchor = document.createElement("a");
    anchor.href = url; anchor.download = "cytellect-analysis-plan.json"; anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return <main className={styles.page}>
    <header className={styles.header}><Link href="/" className={styles.brand}>cytellect</Link><nav aria-label="ナビゲーション"><Link href="/">{API_CONFIGURED || LOCAL_MODE ? "ワークスペース" : "ホーム"}</Link><Link href="/demo">解析例</Link></nav></header>
    <div className={styles.intro}>
      <h1>解析設定</h1>
      <p>測定項目、画像形式、実験条件を入力してください。対応する解析方法と必要な設定を表示します。</p>
    </div>
    <div className={styles.layout}>
      <div className={styles.questions}>
        <section className={styles.section} aria-labelledby="purpose"><h2 id="purpose">測定</h2><div className={styles.fields}>
          <Choice name="measurement" label="測定項目" value={answers.measurement} onChange={change} options={[["unknown","未設定"],["area","面積"],["mean","平均輝度"],["integrated","積算輝度"],["ncl-ratio","核質／核小体のNCL輝度比"]]}/>
          <Choice name="region" label="測定対象" value={answers.region} onChange={change} options={[["unknown", "未設定"], ["nucleus", "核"], ["nucleolus", "核小体"],["nucleoplasm","核質"], ["custom", "その他の領域"]]} />
          <Choice name="definition" label="領域の作成方法" value={answers.definition} onChange={change} options={[["unknown","未設定"],["manual","手動"],["imported","ラベル画像の取り込み"],["nuclear-stain","核染色からの自動検出"],["ncl-enrichment","NCLからの核小体候補検出"]]}/>
          {(answers.measurement!=="area"||answers.gating!=="none")&&<Choice name="signal" label={answers.measurement==="area"?"陽性選別に使うチャンネル":"測定する蛍光チャンネル"} value={answers.signal} onChange={change} options={[["unknown", "未確認"], ["gfp", "GFP"], ["ncl", "NCL"], ["other", "その他のマーカー"]]} hint="蛍光色ではなく、撮影記録にある対象を選びます。汎用領域の解析では実際のチャンネル名を登録できます。" />}
        </div></section>
        <section className={styles.section} aria-labelledby="images"><h2 id="images">画像</h2><div className={styles.fields}>
          <Choice name="input" label="測定に使う画像" value={answers.input} onChange={change} options={[["unknown", "未確認"], ["grayscale-2d", "2DグレースケールTIFF / OME-TIFF"], ["rgb", "表示用RGB画像"], ["zt", "Zスタック・時系列"]]} />
          <Choice name="nuclear_stain" label="核染色チャンネル" value={answers.nuclear_stain} onChange={change} options={[["unknown", "未確認"], ["yes", "ある（撮影記録で確認）"], ["no", "ない"]]} />
          {allArea?<p className={styles.note}>面積のみの測定では、背景ROIは不要です。</p>:<Choice name="background" label="画像内の背景領域" value={answers.background} onChange={change} options={[["unknown", "画像で確認が必要"], ["yes", "対象の蛍光を含まない領域がある"], ["no", "適切な領域がない"]]} />}
          <Choice name="acquisition" label="比較する画像の撮影・染色条件" value={answers.acquisition} onChange={change} options={[["unknown", "未確認"], ["matched", "比較可能な条件で取得している"], ["different", "露光・染色条件などが異なる"]]} />
        </div></section>
        <section className={styles.section} aria-labelledby="design"><h2 id="design">統計</h2><div className={styles.fields}>
          <Choice name="comparison" label="解析内容" value={answers.comparison} onChange={change} options={[["unknown", "未設定"], ["descriptive", "測定値の分布"], ["independent", "対応のない群間比較"], ["paired", "対応のある群間比較"]]} />
          {answers.comparison !== "descriptive" && <Choice name="allocation" label="処置を割り付けた単位" value={answers.allocation} onChange={change} options={[["unknown", "未確認"], ["biological", "独立した動物・培養など"], ["fields", "同一試料内の細胞・視野"]]} hint="同じ動物から得た10視野は、独立した10実験にはなりません。別wellや別日の試料についても、培養条件と処置の割り付けを確認してください。" />}
          <Choice name="gating" label="GFPによる陽性選別" value={answers.gating} onChange={change} options={[["none", "行わない"], ["negative-control", "陽性選別用の陰性対照がある"], ["exploratory", "手動閾値・Otsuを使いたい"]]} />
        </div></section>
      </div>
      <aside className={styles.result} aria-label="解析方法">
        <h2>解析方法</h2>
        <p className={styles.resultLead}>{result.candidates.length?"入力条件に対応する解析方法です。使用する方法を指定してください。":"測定項目と画像の条件を入力すると、利用できる解析方法が表示されます。"}</p>
        {!!result.candidates.length&&<fieldset className={styles.candidates}><legend>使用する方法</legend>{result.candidates.map(candidate=><label key={candidate.id}><input type="radio" name="plan-candidate" value={candidate.id} checked={selected===candidate.id} onChange={()=>setSelected(candidate.id)}/>{candidate.label}</label>)}</fieldset>}
        {(API_CONFIGURED||LOCAL_MODE)&&<button className={styles.save} disabled={!selected} onClick={()=>{if(selected){memory.setPending({input:planReceipt(answers,version),candidateId:selected});router.push("/legacy");}}}>この設定で作成</button>}
        <button className={styles.export} onClick={save}>設定を書き出す</button>
        <p className={styles.note}>設定をJSONファイルに保存します。{API_CONFIGURED||LOCAL_MODE?"画像登録後の確認は別途必要です。":"Windows版で読み込むと、設定を引き継げます。"}ページを再読み込みすると入力内容は消去されます。</p>
        {started && <>
          <div role="status" className={styles.status}>{result.questions.length ? `要確認 ${result.questions.length}件` : "追加の確認項目はありません"}{result.limits.length > 0 && ` · 適用条件 ${result.limits.length}件`}</div>
          {result.questions.length > 0 && <div className={styles.findings}><h3>確認が必要な項目</h3>{result.questions.map(planningDisplay).map(f => <article key={f.id}><h4>{f.title}</h4><p>{f.detail}</p></article>)}</div>}
          {result.limits.length > 0 && <div className={styles.findings}><h3>適用条件・制限</h3>{result.limits.map(planningDisplay).map(f => <article key={f.id}><h4>{f.title}</h4><p>{f.detail}</p></article>)}</div>}
          {result.decisions.length > 0 && <details className={styles.findings}><summary>測定・集計の説明</summary>{result.decisions.map(planningDisplay).map(f => <article key={f.id}><h4>{f.title}</h4><p>{f.detail}</p></article>)}</details>}
        </>}
      </aside>
    </div>
    <details className={styles.sources}><summary>参考文献・解析方法について</summary><p>各方法の適用には実験条件の確認が必要です。この画面では、実験に必要な反復数の算出や、画像を用いた適合性の判定は行いません。</p><ul>{planReferences.map(r => <li key={r.id}><a href={r.url} rel="noreferrer" target="_blank">{r.label} ↗</a></li>)}</ul></details>
    <footer className={styles.footer}><span>入力内容はブラウザ内で処理します。外部への送信はありません。</span><span>解析設定 {version}</span></footer>
  </main>;
}
