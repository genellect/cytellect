import {describe, expect, it} from "vitest";
import {validDataset} from "./index";
import {METRIC_HINTS, TERMS} from "./terms";

const base = {title: "公開画像", attribution: "出典"};

describe("scene explainer (DM-11)", () => {
  it("keeps the three plain sentences and the listed terms", () => {
    const dataset = validDataset({...base, explainer: {what: " 細胞に薬を与えた。 ", colors: "青が核。", finding: "小さくなった。", terms: ["核", 3, "核小体"]}});
    expect(dataset?.explainer).toEqual({what: "細胞に薬を与えた。", colors: "青が核。", finding: "小さくなった。", terms: ["核", "核小体"]});
  });

  it("shows nothing when a sentence is missing or the recording predates explainers", () => {
    expect(validDataset({...base, explainer: {what: "a", colors: "", finding: "c"}})?.explainer).toBeNull();
    expect(validDataset(base)?.explainer).toBeNull();
  });

  it("explains in words, never with a result's number", () => {
    for (const text of [...Object.values(TERMS), ...Object.values(METRIC_HINTS)]) expect(text).not.toMatch(/\d+(\.\d+)?\s*%/);
  });
});
