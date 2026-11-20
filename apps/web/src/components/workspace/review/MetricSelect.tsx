import {METRIC_QUESTIONS, metricChoice, metricSentence, metricsForSubject, type MetricChoice} from "@/lib/workspace/metric-catalog";
import type {ReviewTarget} from "@/lib/workspace/review-preview";

/** The measurement of the chosen subject (核・核小体・核質), grouped by what one observation is, with one sentence of
 * the subject and the observation and the definition beside it (B-1, B-2, requirements M-01 revised 2026-11-20).
 * Without a subject the metrics are grouped by the question they answer. Metrics in physical units need a confirmed
 * pixel size and cannot be chosen without one (M-02). */
export function MetricSelect({value, onChange, disabled, describe = false, calibrated = false, offered = () => true, subject}: {value: string; onChange: (value: string) => void; disabled?: boolean; describe?: boolean; calibrated?: boolean;
  /** Whether this workspace (the demo) has the region set the metric needs. */
  offered?: (metric: string) => boolean;
  /** The subject chosen before the metric; only its metrics are listed. */
  subject?: ReviewTarget}) {
  const choice = metricChoice(value);
  const groups: Array<{label: string; metrics: MetricChoice[]}> = subject
    ? metricsForSubject(subject).map(group => ({label: group.unit, metrics: group.metrics}))
    : METRIC_QUESTIONS.map(group => ({label: group.question, metrics: group.metrics}));
  return <>
    <label>指標<select value={value} disabled={disabled} onChange={event => onChange(event.target.value)}>
      {groups.filter(group => group.metrics.some(metric => offered(metric.id))).map(group => <optgroup key={group.label} label={group.label}>
        {group.metrics.filter(metric => offered(metric.id)).map(metric => {
          const unavailable = !!metric.calibrated && !calibrated;
          return <option key={metric.id} value={metric.id} disabled={unavailable}>{metric.label}{unavailable ? "（画素の大きさが必要）" : ""}</option>;
        })}
      </optgroup>)}
    </select></label>
    {describe && choice && <small data-testid="metric-definition">{subject && <strong style={{display: "block", marginBottom: 2}}>{metricSentence(value, subject)}</strong>}{choice.definition}</small>}
  </>;
}
