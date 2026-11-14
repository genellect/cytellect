import {createElement} from "react";
import {renderToStaticMarkup} from "react-dom/server";
import {describe, expect, it} from "vitest";
import type {DiscussionView} from "@/lib/workspace/api-adapter";
import {SavedDiscussion} from "./DiscussionPanel";

const view = (origin: "model" | "example"): DiscussionView => ({job_id: "job", created: Date.UTC(2026, 10, 12) / 1000, discussion: {
  protocol: "result-discussion/1.0.0", origin, context_sha256: "a".repeat(64), prompt_version: "2026-11-12.2", model: origin === "example" ? "demo-example" : "gpt-6.1-sol",
  draft: {protocol: "result-discussion/1.0.0", implications: ["核小体が小さくなる可能性がある。"], alternatives: [], next_steps: ["視野を増やして確かめる。"]}}});
const text = (value: DiscussionView) => renderToStaticMarkup(createElement(SavedDiscussion, {view: value})).replace(/<[^>]+>/g, " ");

describe("saved discussion (AC-01, AC-06, AC-08)", () => {
  it("names its source, model and day as a reference, not a computed value", () => {
    const page = text(view("model"));
    expect(page).toContain("AI 生成（参考）· gpt-6.1-sol · 2026-11-12");
    expect(page).toContain("解釈");
    expect(page).toContain("追加検証");
    // An empty heading is left out.
    expect(page).not.toContain("限界・代替説明");
  });
  it("marks the demo's example as not a model's output", () => {
    const page = text(view("example"));
    expect(page).toContain("デモ用サンプル（参考）");
    expect(page).not.toContain("AI 生成");
  });
});
