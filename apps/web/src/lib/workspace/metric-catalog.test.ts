import {describe, expect, it} from "vitest";
import {METRIC_QUESTIONS, SUBJECT_METRICS, SUBJECTS, metricChoice, metricForSubject, metricLabel, metricSubject, metricTarget, metricUsesChannel, subjectEntry, type MetricSubject} from "./metric-catalog";

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
});

/** Every (subject, observation unit, entry label) a metric id is listed under. */
function placements(id: string) {
  return SUBJECTS.flatMap(subject => SUBJECT_METRICS[subject].flatMap(group => group.metrics
    .filter(metric => metric.variants.some(variant => variant.id === id)).map(metric => `${subject}/${group.unit}/${metric.label}`)));
}

describe("metrics by subject (M-01)", () => {
  it("lists only existing metrics, and every existing metric under some subject", () => {
    const catalog = METRIC_QUESTIONS.flatMap(group => group.metrics.map(metric => metric.id)).sort();
    const listed = [...new Set(SUBJECTS.flatMap(subject => SUBJECT_METRICS[subject].flatMap(group => group.metrics.flatMap(metric => metric.variants.map(variant => variant.id)))))].sort();
    expect(listed).toEqual(catalog);
  });
  it("puts each metric under exactly its subjects and observation units", () => {
    const perRegion = (label: string) => [`nuclei/nucleus/${label}`, `nucleoli/nucleolus/${label}`, `nucleoplasm/nucleus/${label}`, `cell/cell/${label}`];
    const expected: Record<string, string[]> = {
      area_px: perRegion("面積"), area_um2: perRegion("面積"),
      mean: perRegion("平均輝度"), mean_corrected: perRegion("平均輝度"), median: perRegion("中央値"),
      integrated: perRegion("積算輝度"), integrated_corrected: perRegion("積算輝度"),
      nucleus_count: ["nuclei/field/数"], nucleus_density_per_mm2: ["nuclei/field/密度（mm² あたり）"],
      positive_count: ["nuclei/field/陽性核数"], positive_fraction: ["nuclei/field/陽性率"],
      nucleolar_count: ["nucleoli/nucleus/数"], nucleolar_area_px: ["nucleoli/nucleus/総面積"], nucleolar_area_um2: ["nucleoli/nucleus/総面積"],
      nucleolar_area_fraction: ["nucleoli/nucleus/面積割合"], nucleolar_eccentricity: ["nucleoli/nucleus/離心率"],
      largest_nucleolus_fraction: ["nucleoli/nucleus/最大の核小体の割合"],
      solidity: ["nuclei/nucleus/ソリディティ"], axis_ratio: ["nuclei/nucleus/長短軸比"], eccentricity: ["nuclei/nucleus/離心率"],
      log2_nucleoplasm_over_nucleolus: ["nucleoplasm/nucleus/核質／核小体 log₂ 比"],
    };
    for (const [id, where] of Object.entries(expected)) expect(placements(id), id).toEqual(where);
    expect(Object.keys(expected).sort()).toEqual(METRIC_QUESTIONS.flatMap(group => group.metrics.map(metric => metric.id)).sort());
  });
  it("lists the nucleoli as agreed: per nucleolus, then per nucleus", () => {
    expect(SUBJECT_METRICS.nucleoli.map(group => [group.unit, group.metrics.map(metric => metric.label)])).toEqual([
      ["nucleolus", ["面積", "平均輝度", "中央値", "積算輝度"]],
      ["nucleus", ["数", "総面積", "面積割合", "離心率", "最大の核小体の割合"]],
    ]);
    expect(SUBJECT_METRICS.nuclei.flatMap(group => group.metrics)).toHaveLength(11);
    expect(SUBJECT_METRICS.nucleoplasm.flatMap(group => group.metrics)).toHaveLength(5);
  });
  it("switches only between the variants of one quantity: px² / µm² and 原値 / 背景補正", () => {
    for (const subject of SUBJECTS) for (const group of SUBJECT_METRICS[subject]) for (const metric of group.metrics) {
      const ids = metric.variants.map(variant => variant.id);
      for (const id of ids) expect(metricChoice(id), id).toBeDefined();
      if (ids.length === 1) continue;
      expect(ids).toHaveLength(2);
      const [base, other] = metric.variants;
      if (other.label === "µm²") {
        expect(base.label).toBe("px²");
        expect([metricChoice(base.id)?.calibrated, metricChoice(other.id)?.calibrated]).toEqual([undefined, true]);
        expect(other.id).toBe(base.id.replace(/_px$/, "_um2"));
      } else {
        expect([base.label, other.label]).toEqual(["原値", "背景補正"]);
        expect(other.id).toBe(`${base.id}_corrected`);
      }
      // Both variants read the same region set and stain, so the request differs only in the metric id.
      expect([metricChoice(other.id)?.target, metricUsesChannel(other.id)]).toEqual([metricChoice(base.id)?.target, metricUsesChannel(base.id)]);
    }
  });
  it("reads a metric's subject and unit from the structure it is checked on", () => {
    const at = (id: string, chosen: MetricSubject) => {const subject = metricSubject(id, chosen); return [subject, subjectEntry(subject, id)?.unit];};
    expect(at("nucleolar_eccentricity", "nuclei")).toEqual(["nucleoli", "nucleus"]);
    expect(at("nucleolar_area_um2", "nucleoplasm")).toEqual(["nucleoli", "nucleus"]);
    expect(at("mean_corrected", "nucleoli")).toEqual(["nucleoli", "nucleolus"]);
    expect(at("area_px", "nucleoplasm")).toEqual(["nucleoplasm", "nucleus"]);
    expect(at("log2_nucleoplasm_over_nucleolus", "nucleoli")).toEqual(["nucleoplasm", "nucleus"]);
    expect(at("positive_fraction", "nucleoli")).toEqual(["nuclei", "field"]);
    expect(at("integrated", "cell")).toEqual(["cell", "cell"]);
  });
  it("keeps the metric when the new subject offers it, else the mean intensity, else the first offered entry", () => {
    const all = () => true;
    expect(metricForSubject("mean_corrected", "nucleoplasm", all)).toBe("mean_corrected");
    expect(metricForSubject("area_um2", "nucleoli", all)).toBe("area_um2");
    expect(metricForSubject("nucleolar_count", "nuclei", all)).toBe("mean");
    expect(metricForSubject("nucleus_count", "nucleoli", all)).toBe("mean");
    expect(metricForSubject("nucleus_count", "nucleoli", id => id.startsWith("nucleolar_"))).toBe("nucleolar_count");
    expect(metricForSubject("mean", "nucleoplasm", id => id !== "mean")).toBe("area_px");
  });
  it("offers nuclear shape on the nuclei only, without a stain, and no pixel CV or positive-area fraction", () => {
    for (const id of ["solidity", "axis_ratio", "eccentricity"]) {
      expect(metricTarget(id, "nucleoli"), id).toBe("nuclei");
      expect(metricUsesChannel(id), id).toBe(false);
      expect(metricSubject(id, "nucleoli"), id).toBe("nuclei");
    }
    expect(metricTarget("largest_nucleolus_fraction", "nuclei")).toBe("nucleoplasm");
    expect(metricSubject("largest_nucleolus_fraction", "nuclei")).toBe("nucleoli");
    expect(metricChoice("cv_corrected")).toBeUndefined();
    expect(metricChoice("positive_area_fraction")).toBeUndefined();
  });
});
