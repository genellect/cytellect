"use client";

import Link from "next/link";
import { useState } from "react";
import { buildPlan, emptyPlan, planReceipt, planReferences, PLAN_VERSION, type PlanAnswers } from "@/lib/analysis-plan";
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
  const result = buildPlan(answers);
  const change = <K extends keyof PlanAnswers>(key: K, value: PlanAnswers[K]) => setAnswers(a => ({ ...a, [key]: value }));
  function save() {
    const url = URL.createObjectURL(new Blob([JSON.stringify(planReceipt(answers), null, 2)], { type: "application/json" }));
    const anchor = document.createElement("a");
    anchor.href = url; anchor.download = "cytellect-analysis-plan.json"; anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return <main className={styles.page}>
    <header className={styles.header}><Link href="/" className={styles.brand}>cytellect</Link><Link href="/demo">公開画像の解析例を見る →</Link></header>
    <div className={styles.intro}>
      <p className={styles.eyebrow}>解析計画</p><h1>何を測るか、<br />から始める。</h1>
      <p>測定の目的と実験の組み方から、使える解析と確認事項を整理します。<br className={styles.desktopBreak} />画像の登録は不要です。選択内容は外部へ送信されません。</p>
    </div>
    <div className={styles.layout}>
      <div className={styles.questions}>
        <section className={styles.section} aria-labelledby="purpose"><span className={styles.number}>01</span><div><h2 id="purpose">測る対象</h2>
          <Choice name="region" label="測定する領域" value={answers.region} onChange={change} options={[["unknown", "選択してください"], ["nucleus", "核の面積・核内の蛍光量"], ["nucleolus", "核小体と核質の蛍光分布"], ["custom", "自分で決めた領域・その他の構造"]]} />
          <Choice name="signal" label="測定する蛍光チャンネル" value={answers.signal} onChange={change} options={[["unknown", "未確認"], ["gfp", "GFP"], ["ncl", "NCL"], ["other", "その他のマーカー"]]} hint="蛍光色ではなく、撮影記録にある対象を選びます。汎用領域の解析では実際のチャンネル名を登録できます。" />
        </div></section>
        <section className={styles.section} aria-labelledby="images"><span className={styles.number}>02</span><div><h2 id="images">画像の条件</h2>
          <Choice name="input" label="測定に使う画像" value={answers.input} onChange={change} options={[["unknown", "未確認"], ["grayscale-2d", "2DグレースケールTIFF / OME-TIFF"], ["rgb", "表示用RGB画像"], ["zt", "Zスタック・時系列"]]} />
          <Choice name="nuclearStain" label="核染色チャンネル" value={answers.nuclearStain} onChange={change} options={[["unknown", "未確認"], ["yes", "ある（染色名を確認済み）"], ["no", "ない"]]} />
          <Choice name="background" label="画像内の背景領域" value={answers.background} onChange={change} options={[["unknown", "画像で確認が必要"], ["yes", "対象の蛍光を含まない領域がある"], ["no", "適切な領域がない"]]} />
          <Choice name="acquisition" label="比較する画像の撮影・染色条件" value={answers.acquisition} onChange={change} options={[["unknown", "未確認"], ["matched", "比較可能な条件で取得している"], ["different", "露光・染色条件などが異なる"]]} />
        </div></section>
        <section className={styles.section} aria-labelledby="design"><span className={styles.number}>03</span><div><h2 id="design">比較の組み方</h2>
          <Choice name="comparison" label="まず確認したいこと" value={answers.comparison} onChange={change} options={[["unknown", "まだ決めていない"], ["descriptive", "測定値と分布を確認したい"], ["independent", "別々の試料に割り付けた群を比較したい"], ["paired", "同じ個体・対応する試料の条件を比較したい"]]} />
          {answers.comparison !== "descriptive" && <Choice name="allocation" label="独立して条件を割り付けた単位" value={answers.allocation} onChange={change} options={[["unknown", "まだ整理できていない"], ["biological", "動物・培養などに処置を独立して割り付けた"], ["fields", "同じ試料内の細胞・視野を数えている"]]} hint="例：1匹から撮った10視野は、10匹の独立反復ではありません。別wellや別日が独立かは、培養・割付と結論の対象によります。" />}
          <Choice name="gating" label="GFPによる陽性選別" value={answers.gating} onChange={change} options={[["none", "行わない"], ["negative-control", "陽性選別用の陰性対照がある"], ["exploratory", "手動閾値・Otsuを使いたい"]]} />
        </div></section>
      </div>
      <aside className={styles.result} aria-label="解析計画の概要">
        <p className={styles.eyebrow}>計画の概要</p><h2>{result.recipeLabel ?? "条件を整理して、解析へ"}</h2>
        <p className={styles.resultLead}>{result.recipe ? "現在のレシピ候補です。領域・背景を実画像で確認してから採用します。" : "選択した条件から、先に確認する内容を表示しています。"}</p>
        <div role="status" className={styles.status}>{result.questions.length ? `確認する項目 ${result.questions.length}件` : "計画上の確認項目を整理できました"}{result.limits.length > 0 && ` · 制約 ${result.limits.length}件`}</div>
        {result.questions.length > 0 && <div className={styles.findings}><h3>解析の前に</h3>{result.questions.map(f => <article key={f.id}><h4>{f.title}</h4><p>{f.detail}</p></article>)}</div>}
        {result.decisions.length > 0 && <div className={styles.findings}><h3>進め方</h3>{result.decisions.map(f => <article key={f.id}><h4>{f.title}</h4><p>{f.detail}</p></article>)}</div>}
        {result.limits.length > 0 && <div className={styles.findings}><h3>解釈と対応範囲</h3>{result.limits.map(f => <article key={f.id}><h4>{f.title}</h4><p>{f.detail}</p></article>)}</div>}
        <button className={styles.save} onClick={save}>計画メモを保存 <span>↓</span></button>
        <p className={styles.note}>出典付きのJSONを保存します。解析条件への自動反映は行いません。この画面を離れると選択内容は消えます。</p>
      </aside>
    </div>
    <section className={styles.sources} aria-labelledby="sources"><h2 id="sources">判断の根拠</h2><p>公開された方法論に基づく整理です。個々の実験への適合性や、必要な反復数を自動で保証するものではありません。</p><ul>{planReferences.map(r => <li key={r.id}><a href={r.url} rel="noreferrer" target="_blank">{r.label} ↗</a></li>)}</ul></section>
    <footer className={styles.footer}><Link href="/">Cytellect</Link><span>計画ガイド {PLAN_VERSION} · 画像・研究条件のアップロード不要</span></footer>
  </main>;
}
