"use client";
import {useState} from "react";
import {metricSubjects, metricsForSubject, metricUsesChannel, nucleusPositivity, subjectName} from "@/lib/workspace/metric-catalog";
import {primaryName, primaryOutcome, type PrimaryOutcome} from "@/lib/workspace/primary-outcome";
import type {ReviewTarget} from "@/lib/workspace/review-preview";
import {MetricSelect} from "./MetricSelect";
import styles from "./experiment-setup.module.css";

const SUBJECTS: ReviewTarget[] = ["nuclei", "nucleoli", "nucleoplasm", "cell"];

/** The primary measure, chosen before results are read (#257 RP-04). Every other measure is shown as exploratory, so
 * that a difference found among many measures is not reported as if it had been the question. */
export function PrimaryOutcomeSetup({declared, stains, readOnly, busy, onDeclare, offered = () => true, calibrated = false}: {declared: PrimaryOutcome | null; stains: Array<{id: string; name: string}>;
  readOnly: boolean; busy: boolean; onDeclare: (value: PrimaryOutcome | null) => Promise<void> | void;
  /** Whether this workspace has the region set a metric needs (as in the side panel). */
  offered?: (metric: string, subject: ReviewTarget) => boolean; calibrated?: boolean}) {
  const [editing, setEditing] = useState(false);
  const [chosenSubject, setSubject] = useState<ReviewTarget>("nucleoli");
  const [chosenMetric, setMetric] = useState("nucleolar_area_px");
  // A subject or metric this workspace cannot measure is not kept: the form shows, and declares, the first one it can.
  const firstOffered = (value: ReviewTarget) => metricsForSubject(value).flatMap(group => group.metrics).find(choice => offered(choice.id, value) && !(choice.calibrated && !calibrated))?.id;
  const subject = firstOffered(chosenSubject) ? chosenSubject : SUBJECTS.find(value => firstOffered(value)) ?? chosenSubject;
  const metric = metricSubjects(chosenMetric).includes(subject) && offered(chosenMetric, subject) ? chosenMetric : firstOffered(subject) ?? chosenMetric;
  const [chosenChannel, setChannel] = useState("");
  // The stains may arrive after this view opens: an unchosen stain is the first registered one, as the select shows.
  const channel = stains.some(value => value.id === chosenChannel) ? chosenChannel : stains[0]?.id ?? "";
  const stainName = (id: string) => stains.find(value => value.id === id)?.name ?? id;
  const name = primaryName(declared, stainName);
  const when = declared?.declared_at ? new Date(declared.declared_at * 1000).toLocaleString("ja-JP", {year: "numeric", month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit"}) : "";
  const needsStain = metricUsesChannel(metric) || nucleusPositivity(metric);
  const choose = (value: ReviewTarget) => setSubject(value);
  return <section className={styles.explain} aria-label="主要指標">
    <h2>主要指標</h2>
    <p>結果を見る前に、答えたい問いの指標を 1 つ決めます。統計とグラフでは、ほかの指標の結果を「探索的な指標」と示します。宣言した日時は記録され、あとから変えると変えた日時が残ります。</p>
    {readOnly ? <p>{name ? `主要指標：${name}${when ? `（${when} に宣言）` : ""}` : "この公開データの記録には主要指標の宣言がありません。結果はすべて探索的な指標として示します。"}</p>
    : declared && !editing ? <p>主要指標：<strong>{name}</strong>{when ? `（${when} に宣言）` : ""}
        <button className={styles.link} disabled={busy} onClick={() => setEditing(true)}>変更する</button></p>
    : <div className={styles.primaryForm}>
        <label>対象<select value={subject} disabled={busy} onChange={event => choose(event.target.value as ReviewTarget)}>
          {SUBJECTS.filter(value => firstOffered(value)).map(value => <option key={value} value={value}>{subjectName(value)}</option>)}</select></label>
        <MetricSelect subject={subject} value={metric} onChange={setMetric} disabled={busy} describe calibrated={calibrated} offered={id => offered(id, subject)}/>
        {needsStain && <label>染色<select value={channel} disabled={busy} onChange={event => setChannel(event.target.value)}>
          {stains.map(value => <option key={value.id} value={value.id}>{value.name}</option>)}</select></label>}
        <div><button disabled={busy || (needsStain && !channel)} onClick={async () => {await onDeclare(primaryOutcome(metric, subject, needsStain ? channel : null)); setEditing(false);}}>主要指標として宣言</button>
          {declared && <button className={styles.link} disabled={busy} onClick={() => setEditing(false)}>変更しない</button>}</div>
      </div>}
  </section>;
}
