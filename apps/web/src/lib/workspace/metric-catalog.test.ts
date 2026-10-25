import {describe, expect, it} from "vitest";
import {METRIC_QUESTIONS, metricLabel, metricTarget, metricUsesChannel} from "./metric-catalog";

describe("metric catalog", () => {
  it("offers each metric once, under the question it answers, with a definition", () => {
    const ids = METRIC_QUESTIONS.flatMap(group => group.metrics.map(metric => metric.id));
    expect(new Set(ids).size).toBe(ids.length);
    expect(METRIC_QUESTIONS.find(group => group.metrics.some(metric => metric.id === "nucleus_count"))?.question).toBe("数が増えた・減ったか");
    for (const group of METRIC_QUESTIONS) for (const metric of group.metrics) expect(metric.definition.length).toBeGreaterThan(10);
  });
  it("fixes the region set and the stain only where the metric needs them", () => {
    expect(metricTarget("nucleus_count", "nucleoli")).toBe("nuclei");
    expect(metricTarget("nucleolar_count", "nuclei")).toBe("nucleoplasm");
    expect(metricTarget("mean", "nucleoli")).toBe("nucleoli");
    expect([metricUsesChannel("area_um2"), metricUsesChannel("nucleus_count"), metricUsesChannel("log2_nucleoplasm_over_nucleolus")]).toEqual([false, false, true]);
    expect(metricLabel("area_um2")).toBe("面積（µm²）");
  });
});
