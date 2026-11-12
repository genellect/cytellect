import {createElement} from "react";
import {renderToStaticMarkup} from "react-dom/server";
import {describe, expect, it} from "vitest";
import type {DiscussionView} from "@/lib/workspace/api-adapter";
import {SavedDiscussion} from "./DiscussionPanel";

const view = (origin: "model" | "example"): DiscussionView => ({job_id: "job", created: Date.UTC(2026, 10, 12) / 1000, discussion: {
  protocol: "result-discussion/1.0.0", origin, context_sha256: "a".repeat(64), prompt_version: "2026-11-12.1", model: origin === "example" ? "demo-example" : "gpt-6.1-sol",
  draft: {protocol: "result-discussion/1.0.0", implications: ["核小体が小さくなる可能性がある。"], alternatives: [], next_steps: ["視野を増やして確かめる。"]}}});
const text = (value: DiscussionView) => renderToStaticMarkup(createElement(SavedDiscussion, {view: value})).replace(/<[^>]+>/g, " ");

describe("saved discussion (AC-01, AC-06, AC-08)", () => {
  it("names the model and the day, and says it is not a computed value", () => {
    const page = text(view("model"));
    expect(page).toContain("AI が作成（gpt-6.1-sol · 2026-11-12）。計算した値ではありません。");
    expect(page).toContain("示唆されること");
    expect(page).toContain("次に確かめること");
    // An empty heading is left out.
    expect(page).not.toContain("ほかの説明と限界");
  });
  it("marks the demo's example as not a model's output", () => {
    const page = text(view("example"));
    expect(page).toContain("デモ用の例です。LLM の出力ではなく、計算した値でもありません。");
    expect(page).not.toContain("AI が作成");
  });
});
