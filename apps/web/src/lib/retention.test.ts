import {describe, expect, it} from "vitest";
import {retentionText, workspaceDeadline, workspaceNotExpired} from "./retention";

describe("workspace retention metadata", () => {
  it("distinguishes manual retention from TTL and an unknown policy", () => {
    expect(retentionText({retention_mode: "manual", retention_hours: null})).toContain("手動で削除するまで");
    expect(retentionText({retention_mode: "ttl", retention_hours: 12})).toContain("12時間");
    expect(retentionText()).toContain("接続後");
    expect(workspaceDeadline(null)).toContain("手動");
    expect(workspaceDeadline(undefined)).toContain("確認中");
  });
  it("requires an explicit null deadline to restore a non-expiring workspace", () => {
    expect(workspaceNotExpired(null, 100)).toBe(true);
    expect(workspaceNotExpired(101, 100)).toBe(true);
    for (const value of [undefined, NaN, Infinity, 100, 99]) expect(workspaceNotExpired(value, 100)).toBe(false);
  });
});
