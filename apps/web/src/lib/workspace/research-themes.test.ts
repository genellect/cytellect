import {describe, expect, it} from "vitest";
import {metricChoice} from "./metric-catalog";
import {NUCLEOLAR_STRESS, themeRows} from "./research-themes";

describe("nucleolar stress theme (NS-01)", () => {
  it("lists only measures that exist, with stain, region and observation", () => {
    for (const measure of NUCLEOLAR_STRESS.measures) expect(metricChoice(measure.metric), measure.metric).toBeDefined();
    const metrics = NUCLEOLAR_STRESS.measures.map(measure => measure.metric);
    for (const absent of ["cv_corrected", "positive_area_fraction", "solidity"]) expect(metrics).not.toContain(absent);
    const rows = themeRows(NUCLEOLAR_STRESS, [{id: "c1", name: "Hoechst"}, {id: "c2", name: "NPM1-mTagRFP"}]);
    expect(rows.find(row => row.metric === "largest_nucleolus_fraction")).toEqual({metric: "largest_nucleolus_fraction", subject: "nucleoli",
      label: "最大の核小体の割合", stain: "NPM1-mTagRFP", region: "核小体", unit: "核ごと", available: true, channel: null});
    // A partition or an intensity is chosen together with the registered stain it is read in.
    expect(rows.find(row => row.metric === "log2_nucleoplasm_over_nucleolus")).toMatchObject({label: "核質／核小体 log₂ 比（NPM1-mTagRFP）", region: "核質と核小体",
      available: true, subject: "nucleoplasm", channel: "c2"});
    expect(rows.find(row => row.metric === "mean")).toEqual({metric: "mean", subject: "nucleoli", label: "核小体の平均輝度（5-EU）", stain: "5-EU",
      region: "核小体", unit: "核小体ごと", available: false, channel: null});
  });
  it("needs a nucleolar marker for the nucleolar measures", () => {
    const rows = themeRows(NUCLEOLAR_STRESS, [{id: "c1", name: "Hoechst"}, {id: "c2", name: "5-EU"}]);
    expect(rows.filter(row => row.available).map(row => row.metric)).toEqual(["mean"]);
    expect(rows[0].stain).toBe("核小体のマーカー（NPM1・NCL・FBL）");
    // Whole words only: "eu" inside another name is not 5-EU.
    expect(themeRows(NUCLEOLAR_STRESS, [{id: "c", name: "Neurofilament"}]).some(row => row.available)).toBe(false);
  });
});
