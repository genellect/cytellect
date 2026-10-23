import { describe, expect, it } from "vitest";
import { featureText } from "./paid-access";

describe("paid feature status", () => {
  it("states availability, the remaining monthly allowance and the limit", () => {
    expect(featureText({ enabled: true, used: 3, limit: 200 }, "視野")).toBe("利用できます（今月の残り 197 視野）");
    expect(featureText({ enabled: true, used: 200, limit: 200 }, "視野")).toBe("今月の上限に達しました（200 視野）");
    expect(featureText({ enabled: false, used: 0, limit: 0 }, "回")).toBe("現在は提供されていません");
    expect(featureText(null, "回")).toBe("確認できません");
  });
});
