import {measureLabel, metricChoice, metricStructure, metricTarget, metricUnit, subjectName} from "./metric-catalog";
import type {ReviewTarget} from "./review-preview";

/** A research theme lists the questions it asks, each with the measure that answers it, the stain it reads and the
 * region it is measured on (#257 E-7, NS-01). It chooses among the common measures; it computes nothing itself. */
export interface ThemeQuestion {question: string; metric: string; subject: ReviewTarget;
  /** Stain names that answer the question, matched to the registered stains (case-insensitive, whole token). */
  stains: string[];
  /** What the value cannot say. */
  limit: string}
export interface ResearchTheme {id: string; label: string; summary: string; questions: ThemeQuestion[]}

export const NUCLEOLAR_STRESS: ResearchTheme = {
  id: "nucleolar-stress", label: "核小体ストレス",
  summary: "核小体の形・数と、核小体タンパク質の局在、新生 RNA の取り込みを同じ核で読みます。ストレスの程度を一つの閾値で判定せず、各指標の名前・向き・値を示します。",
  questions: [
    {question: "核小体の数と大きさは変わったか", metric: "nucleolar_area_px", subject: "nucleoli", stains: [],
      limit: "核ごとの総面積です。個数と 1 個の大きさは別の指標（核小体数、核小体ごとの面積）で読みます。"},
    {question: "核小体の数は変わったか", metric: "nucleolar_count", subject: "nucleoli", stains: [],
      limit: "接した核小体は 1 個に、暗く小さい核小体は見えなくなることがあります。"},
    {question: "核小体は丸くなったか、崩れたか", metric: "solidity", subject: "nucleoli", stains: [],
      limit: "96 px 未満の核小体は形を測らず欠測です（個数と面積には含めます）。2D の値です。"},
    {question: "核小体タンパク質は核内のどこまで広がったか", metric: "positive_area_fraction", subject: "nuclei", stains: ["NCL", "nucleolin", "NPM1", "B23"],
      limit: "閾値は視野ごとに Otsu 法で決めます。露光や全体の明るさにも左右されるため、核全体の平均輝度と並べて読みます。"},
    {question: "核小体への濃縮はどれだけ弱まったか", metric: "log2_nucleoplasm_over_nucleolus", subject: "nucleoli", stains: ["NCL", "nucleolin", "NPM1", "B23"],
      limit: "同じ染色で核小体を決めた場合、信号の低下で境界も縮むことがあります。"},
    {question: "核内で信号はどれだけ偏っているか", metric: "cv_corrected", subject: "nuclei", stains: ["NPM1", "B23", "NCL", "nucleolin"],
      limit: "染色・露光・ピントに左右されます。同じ撮影条件の中で比べます。"},
    {question: "新生 RNA の取り込みも変わったか", metric: "mean_corrected", subject: "nucleoli", stains: ["5-EU", "EU", "5-ethynyluridine"],
      limit: "5-EU は新生 RNA の標識で、DNA 合成の EdU とは別です。標識時間と処理から撮影までの時間を記録してください。"},
  ],
};

const token = (value: string) => value.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
/** The registered stain that answers a question, by stain name; null when none matches. */
export function themeStain(question: ThemeQuestion, stains: Array<{id: string; name: string}>): {id: string; name: string} | null {
  if (!question.stains.length) return null;
  const wanted = question.stains.map(token);
  return stains.find(stain => {const words = ` ${token(stain.name)} `; return wanted.some(name => words.includes(` ${name} `));}) ?? null;
}

/** One row of the theme table: the measure in the label used everywhere, its region and observation, and whether the
 * registered stains can answer it. */
export function themeRow(question: ThemeQuestion, stains: Array<{id: string; name: string}>) {
  const stain = themeStain(question, stains);
  const needsStain = question.stains.length > 0;
  return {
    question: question.question, metric: question.metric, subject: question.subject,
    label: measureLabel(question.metric, question.subject, stain?.name ?? null),
    // The partition ratio reads two regions: the nucleoplasm (the nucleus without its adopted nucleoli) and the nucleoli.
    region: question.metric === "log2_nucleoplasm_over_nucleolus" ? "核質と核小体" : subjectName(metricStructure(question.metric, question.subject)),
    regionSet: metricTarget(question.metric, question.subject),
    unit: metricUnit(question.metric, question.subject),
    stain: needsStain ? stain?.name ?? `${question.stains.slice(0, 2).join(" または ")}（未登録）` : "なし（領域の形と数）",
    channel: stain?.id ?? null,
    available: !needsStain || !!stain,
    definition: metricChoice(question.metric)?.definition ?? "",
    limit: question.limit,
  };
}
