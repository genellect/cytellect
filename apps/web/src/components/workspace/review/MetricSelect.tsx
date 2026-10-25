import {METRIC_QUESTIONS, metricChoice} from "@/lib/workspace/metric-catalog";

/** The measurement, chosen by the question it answers; its definition is shown with it (requirements M-01).
 * Metrics in physical units need a confirmed pixel size and cannot be chosen without one (M-02). */
export function MetricSelect({value, onChange, disabled, describe = false, calibrated = false, offered = () => true}: {value: string; onChange: (value: string) => void; disabled?: boolean; describe?: boolean; calibrated?: boolean;
  /** Whether this workspace (the demo) has the region set the metric needs. */
  offered?: (metric: string) => boolean}) {
  const choice = metricChoice(value);
  return <>
    <label>指標<select value={value} disabled={disabled} onChange={event => onChange(event.target.value)}>
      {METRIC_QUESTIONS.filter(group => group.metrics.some(metric => offered(metric.id))).map(group => <optgroup key={group.question} label={group.question}>
        {group.metrics.filter(metric => offered(metric.id)).map(metric => {
          const unavailable = !!metric.calibrated && !calibrated;
          return <option key={metric.id} value={metric.id} disabled={unavailable}>{metric.label}{unavailable ? "（画素の大きさが必要）" : ""}</option>;
        })}
      </optgroup>)}
    </select></label>
    {describe && choice && <small data-testid="metric-definition">{choice.definition}</small>}
  </>;
}
