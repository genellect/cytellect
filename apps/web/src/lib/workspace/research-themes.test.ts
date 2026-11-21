import {describe, expect, it} from "vitest";
import {NUCLEOLAR_STRESS, themeRow, themeStain} from "./research-themes";

// The DS6a stains of the public demo: Hoechst, NPM1 and 5-EU (no NCL).
const stains = [{id: "hoechst", name: "Hoechst"}, {id: "npm1", name: "NPM1"}, {id: "eu5", name: "5-EU"}];
const row = (metric: string) => themeRow(NUCLEOLAR_STRESS.questions.find(question => question.metric === metric)!, stains);

describe("nucleolar stress theme (#257 NS-01)", () => {
  it("names each measure, its stain, region and observation before any comparison", () => {
    expect(row("cv_corrected")).toMatchObject({label: "核の画素の変動係数（CV、背景補正、NPM1）", stain: "NPM1", region: "核", unit: "核ごと", channel: "npm1", available: true});
    expect(row("log2_nucleoplasm_over_nucleolus")).toMatchObject({stain: "NPM1", region: "核質と核小体", unit: "核ごと（核質と核小体の比）", regionSet: "nucleoplasm"});
    expect(row("mean_corrected")).toMatchObject({label: "核小体の平均輝度（背景補正、5-EU）", stain: "5-EU", unit: "核小体ごと"});
    expect(row("solidity")).toMatchObject({stain: "なし（領域の形と数）", region: "核小体", unit: "核小体ごと", available: true});
    expect(row("nucleolar_count")).toMatchObject({region: "核小体", unit: "核ごと（その核の核小体をまとめた値）"});
  });
  it("matches stains by name, not by part of a word, and says which stain is missing", () => {
    expect(themeStain({question: "", metric: "mean", subject: "nuclei", stains: ["EU"], limit: ""}, [{id: "edu", name: "EdU"}])).toBeNull();
    expect(themeStain({question: "", metric: "mean", subject: "nuclei", stains: ["NCL"], limit: ""}, [{id: "a", name: "anti-NCL (Alexa 488)"}])?.id).toBe("a");
    const withoutNucleolar = themeRow(NUCLEOLAR_STRESS.questions.find(question => question.metric === "positive_area_fraction")!, [{id: "h", name: "Hoechst"}]);
    expect(withoutNucleolar).toMatchObject({available: false, stain: "NCL または nucleolin（未登録）", channel: null});
  });
  it("states what each value cannot say", () => {
    for (const question of NUCLEOLAR_STRESS.questions) expect(question.limit.length).toBeGreaterThan(10);
  });
});
