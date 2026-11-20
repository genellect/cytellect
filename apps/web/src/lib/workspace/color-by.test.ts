import {describe, expect, it} from "vitest";
import {PARTITION_DIRECTION, colorByChoices, gateHistogram, gateLegend, gateLegendItems, gateStates, nextComparison, shownColorBy, tableHeading} from "./color-by";

const nucleus = (field: string, region: number, status: "positive" | "negative" | "unclassified" | "control" | "excluded", mean: number | null, date = "2021-12-01", threshold: number | null = 100) =>
  ({field_id: field, region_id: region, acquisition_date: date, channel_mean: mean, positive: status === "positive" ? true : status === "negative" ? false : null, status, reason: "", threshold, exclusion_reason: null});
const all = {nuclei: true, gateChannels: 1, nucleoli: true, nucleoplasm: true, saved: false};

describe("colour modes (MV-01)", () => {
  it("offers every mode, naming what is missing instead of hiding one", () => {
    expect(colorByChoices(all).map(choice => [choice.id, choice.reason])).toEqual([["outline", null], ["positivity", null], ["compartments", null]]);
    const nucleiOnly = colorByChoices({...all, nucleoli: false, nucleoplasm: false, gateChannels: 0});
    expect(nucleiOnly.find(choice => choice.id === "positivity")?.reason).toBe("判定できる染色がありません");
    expect(nucleiOnly.find(choice => choice.id === "compartments")?.reason).toBe("核小体と核質の結果が必要です");
    expect(colorByChoices({...all, nuclei: false}).filter(choice => choice.reason === "採用した核が必要です")).toHaveLength(2);
    // A saved version or a candidate is read-only: only its outlines are drawn.
    expect(colorByChoices({...all, saved: true}).filter(choice => choice.reason === null).map(choice => choice.id)).toEqual(["outline"]);
  });

  it("falls back to the outlines while the chosen mode cannot be shown", () => {
    expect(shownColorBy("positivity", colorByChoices(all))).toBe("positivity");
    expect(shownColorBy("compartments", colorByChoices({...all, nucleoli: false}))).toBe("outline");
  });
});

describe("positive and negative nuclei (MV-03)", () => {
  const nuclei = [nucleus("a", 1, "positive", 150), nucleus("a", 2, "negative", 50), nucleus("a", 3, "unclassified", null), nucleus("a", 4, "control", 40),
    nucleus("a", 5, "excluded", 90), nucleus("b", 1, "positive", 170)];

  it("keeps every state of one field apart, never folding them into negative", () => {
    expect(gateStates(nuclei, "a")).toEqual({1: "positive", 2: "negative", 3: "unclassified", 4: "control", 5: "excluded"});
    expect(gateStates(nuclei, "b")).toEqual({1: "positive"});
    expect(gateStates(undefined, "a")).toEqual({});
  });

  it("counts each state of an image in a fixed order", () => {
    expect(gateLegend(gateStates(nuclei, "a")).map(item => `${item.label} ${item.count}`)).toEqual(["陽性 1", "陰性 1", "未判定 1", "除外 1", "対照 1"]);
    expect(gateLegend({1: "negative", 2: "positive", 3: "positive"}).map(item => item.status)).toEqual(["positive", "negative"]);
  });

  it("names an exploratory decision on the image, as the table and statistics do (M22)", () => {
    const states = gateStates(nuclei, "a");
    expect(gateLegendItems(states, "batch_otsu").at(-1)).toEqual({key: "exploratory", label: "探索的（撮影日ごとの Otsu）"});
    expect(gateLegendItems(states, "manual").at(-1)?.label).toBe("探索的（指定したしきい値）");
    expect(gateLegendItems(states, "negative_control").map(item => item.key)).toEqual(["positive", "negative", "unclassified", "excluded", "control"]);
    expect(gateLegendItems({}, "batch_otsu")).toEqual([]);
  });

  it("places the saved values of one date on a chart with its threshold, skipping missing values", () => {
    const chart = gateHistogram([...nuclei, nucleus("c", 1, "positive", 200, "2021-12-02", 120)], "2021-12-01", 4);
    expect(chart.total).toBe(5);
    expect([chart.low, chart.high, chart.threshold]).toEqual([40, 170, 100]);
    expect(chart.counts.reduce((sum, bin) => sum + bin.positive, 0)).toBe(2);
    expect(chart.counts[0].control + chart.counts[0].negative).toBe(2);
    expect(gateHistogram([], "x").total).toBe(0);
  });
});

describe("partition direction (owner decision 1)", () => {
  it("reads nucleoplasm ÷ nucleoli, the direction of the statistics metric", () => {
    expect(PARTITION_DIRECTION).toEqual({target: "nucleoplasm", reference: "nucleoli"});
  });
});

describe("table heading (MV-06)", () => {
  it("names per what, which stain and which values", () => {
    expect(tableHeading({colorBy: "outline", target: "nucleoli", stain: "5-EU", corrected: true, nucleusTable: false})).toBe("核小体ごと · 5-EU（原値・背景補正）");
    expect(tableHeading({colorBy: "outline", target: "nuclei", stain: "DAPI", corrected: false, nucleusTable: true})).toBe("核ごと · すべての染色");
    expect(tableHeading({colorBy: "positivity", stain: "5-EU", method: "batch_otsu", values: "raw"})).toBe("核ごと · 5-EUで判定（原値、撮影日ごとの Otsu・探索的）");
    expect(tableHeading({colorBy: "positivity", stain: "GFP", method: "negative_control", values: "corrected"})).toBe("核ごと · GFPで判定（背景補正値、撮影日ごとの陰性対照）");
    expect(tableHeading({colorBy: "compartments", stain: "5-EU", target: "核質", reference: "核小体"})).toBe("核ごと · 核質 ÷ 核小体 · 5-EU");
  });
});

describe("next step (MV-09)", () => {
  const view = {metric: "mean", target: "nucleoli" as const, channel: "eu5", stain: "5-EU"};
  it("compares groups by what the colour mode shows", () => {
    expect(nextComparison({...view, colorBy: "outline"})).toMatchObject({label: "核小体の平均輝度（5-EU）を群間で比較", metric: "mean", target: "nucleoli", channel: "eu5", reclassify: false});
    expect(nextComparison({...view, metric: "area_px", colorBy: "outline"})).toMatchObject({label: "核小体の面積（px²）を群間で比較", channel: null});
    // Positivity says that the compared fields are judged again by the same rule (M22).
    const positivity = nextComparison({...view, colorBy: "positivity"});
    expect(positivity).toMatchObject({label: "陽性率を群間で比較", metric: "positive_fraction", target: "nuclei", channel: null, reclassify: true});
    expect(positivity.note).toContain("再判定してから");
    expect(nextComparison({...view, colorBy: "compartments"})).toMatchObject({metric: "log2_nucleoplasm_over_nucleolus", target: "nucleoplasm", channel: "eu5"});
  });
});

describe("the next step follows the table beside the image (A-2, TB-02)", () => {
  const view = {colorBy: "outline" as const, target: "nucleoli" as const, channel: "npm1", stain: "NPM1"};
  it("compares the brightness the stain's table lists, not a metric the table does not show", () => {
    // The statistics view opened on the eccentricity; the table lists each nucleolus's NPM1 brightness.
    expect(nextComparison({...view, metric: "nucleolar_eccentricity"})).toMatchObject({label: "核小体の平均輝度（NPM1）を群間で比較", metric: "mean", target: "nucleoli", channel: "npm1"});
    expect(nextComparison({...view, metric: "integrated_corrected"})).toMatchObject({label: "核小体の積算輝度（背景補正、NPM1）を群間で比較", metric: "integrated_corrected"});
  });
  it("compares a nucleolar summary the nucleus table lists, on the nucleoplasm set it is read from", () => {
    expect(nextComparison({...view, metric: "nucleolar_eccentricity", nucleusTable: true})).toMatchObject({label: "核小体の離心率を群間で比較", metric: "nucleolar_eccentricity", target: "nucleoplasm", channel: null});
    expect(nextComparison({...view, metric: "nucleus_count", nucleusTable: true})).toMatchObject({metric: "nucleolar_area_px", target: "nucleoplasm"});
    expect(nextComparison({...view, target: "nuclei", metric: "mean", nucleusTable: true})).toMatchObject({label: "核の平均輝度（NPM1）を群間で比較", target: "nuclei"});
  });
  it("names the nucleolar summaries in the nucleus table's heading beside the nucleoli (A-1)", () => {
    expect(tableHeading({colorBy: "outline", target: "nucleoli", stain: "NPM1", corrected: false, nucleusTable: true})).toBe("核ごと · 核小体のまとめとすべての染色");
    expect(tableHeading({colorBy: "outline", target: "nuclei", stain: "NPM1", corrected: false, nucleusTable: true})).toBe("核ごと · すべての染色");
  });
});
