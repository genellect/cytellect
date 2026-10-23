import {describe, expect, it} from "vitest";
import {closestExample} from "./index";

const examples = [
  {label: "核の面積の分布", instruction: "核の面積の分布を視野ごとに確認したい"},
  {label: "NPM1 の核内輝度を条件間で比較", instruction: "NPM1の核内平均輝度を未処理とActD処理で比較したい"},
  {label: "核の面積と NPM1 輝度の関係", instruction: "核の面積とNPM1の平均輝度の関係を条件ごとに見たい"},
];

describe("closestExample", () => {
  it("maps free wording onto the recorded analysis it asks for", () => {
    expect(closestExample("ActDで核小体のタンパク質の量は変わる？", examples)?.label).toBe("NPM1 の核内輝度を条件間で比較");
    expect(closestExample("核の大きさのばらつきを見たい", examples)?.label).toBe("核の面積の分布");
    expect(closestExample("面積と輝度は相関している？", examples)?.label).toBe("核の面積と NPM1 輝度の関係");
    expect(closestExample("compare NPM1 intensity between treatments", examples)?.label).toBe("NPM1 の核内輝度を条件間で比較");
  });
  it("returns nothing for a request this dataset cannot answer", () => {
    expect(closestExample("こんにちは", examples)).toBeNull();
    expect(closestExample("ミトコンドリアを数えたい", examples)).toBeNull();
  });
});
