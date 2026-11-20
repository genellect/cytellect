import {describe, expect, it} from "vitest";
import {METRIC_QUESTIONS, measureLabel, metricChoice, metricLabel, metricSentence, metricsForSubject, metricSubjects, metricTarget, metricUnit, metricUsesChannel} from "./metric-catalog";

// Shape and pixel signal (region-features/1.0.0, #257 E-1, E-3, E-7) describe each region of the chosen subject.
const FEATURES = ["solidity", "axis_ratio", "eccentricity", "cv", "cv_corrected", "positive_area_fraction"];

describe("metric catalog", () => {
  it("offers each metric once, under the question it answers, with a definition", () => {
    const ids = METRIC_QUESTIONS.flatMap(group => group.metrics.map(metric => metric.id));
    expect(new Set(ids).size).toBe(ids.length);
    expect(METRIC_QUESTIONS.find(group => group.metrics.some(metric => metric.id === "nucleus_count"))?.question).toBe("数の増減");
    for (const group of METRIC_QUESTIONS) for (const metric of group.metrics) expect(metric.definition.length).toBeGreaterThan(10);
  });
  it("fixes the region set and the stain only where the metric needs them", () => {
    expect(metricTarget("nucleus_count", "nucleoli")).toBe("nuclei");
    expect(metricTarget("nucleolar_count", "nuclei")).toBe("nucleoplasm");
    expect(metricTarget("mean", "nucleoli")).toBe("nucleoli");
    expect([metricUsesChannel("area_um2"), metricUsesChannel("nucleus_count"), metricUsesChannel("log2_nucleoplasm_over_nucleolus")]).toEqual([false, false, true]);
    expect(metricLabel("area_um2")).toBe("面積（µm²）");
  });
  it("lists each subject's metrics by what one observation is (B-1, B-4)", () => {
    const groups = (subject: "nuclei" | "nucleoli" | "nucleoplasm" | "cell") => metricsForSubject(subject).map(group => [group.unit, group.metrics.map(metric => metric.id)]);
    // The nucleoli: their own areas and brightness per nucleolus, then the per-nucleus summaries and the partition.
    expect(groups("nucleoli")).toEqual([
      ["核小体ごと", ["area_px", "area_um2", "mean", "median", "integrated", "mean_corrected", "integrated_corrected", ...FEATURES]],
      ["核ごと（その核の核小体をまとめた値）", ["nucleolar_area_px", "nucleolar_area_um2", "nucleolar_eccentricity", "nucleolar_count", "nucleolar_area_fraction"]],
      ["核ごと（核質と核小体の比）", ["log2_nucleoplasm_over_nucleolus"]],
    ]);
    expect(groups("nuclei").map(([unit]) => unit)).toEqual(["核ごと", "視野ごと"]);
    expect(groups("nuclei")[1][1]).toEqual(["nucleus_count", "nucleus_density_per_mm2", "positive_count", "positive_fraction"]);
    expect(groups("nucleoplasm").map(([unit]) => unit)).toEqual(["核ごと（核質の領域）", "核ごと（核質と核小体の比）"]);
    expect(groups("cell")).toEqual([["細胞ROIごと", ["area_px", "area_um2", "mean", "median", "integrated", "mean_corrected", "integrated_corrected", ...FEATURES]]]);
    // Every metric is listed under at least one subject, and a subject's metrics come from its own region set or the per-nucleus summary.
    for (const metric of METRIC_QUESTIONS.flatMap(group => group.metrics)) expect(metricSubjects(metric.id).length).toBeGreaterThan(0);
  });
  it("names shape and pixel-signal measures by their region and, where they read one, the stain (#257 E-1, E-7)", () => {
    expect([metricUsesChannel("solidity"), metricUsesChannel("eccentricity"), metricUsesChannel("cv"), metricUsesChannel("positive_area_fraction")]).toEqual([false, false, true, true]);
    expect(measureLabel("solidity", "nucleoli", "NPM1")).toBe("核小体のソリディティ");
    expect(measureLabel("cv", "nuclei", "NPM1")).toBe("核の画素の変動係数（CV、NPM1）");
    expect(measureLabel("positive_area_fraction", "nuclei", "NCL")).toBe("核の陽性面積率（NCL）");
    expect(metricSentence("axis_ratio", "nucleoli")).toBe("対象：核小体。観測の単位：核小体ごと。");
    for (const id of FEATURES) expect(metricChoice(id)?.definition).toMatch(/。/);
  });
  it("states the subject and one observation in one sentence (B-2, SL-01)", () => {
    expect(metricSentence("nucleolar_eccentricity", "nucleoli")).toBe("対象：核小体。観測の単位：核ごと（その核の核小体をまとめた値）。");
    expect(metricSentence("mean", "nucleoli")).toBe("対象：核小体。観測の単位：核小体ごと。");
    expect(metricSentence("nucleus_count", "nuclei")).toBe("対象：核。観測の単位：視野ごと。");
    expect(metricUnit("area_px", "nucleoplasm")).toBe("核ごと（核質の領域）");
  });
});
