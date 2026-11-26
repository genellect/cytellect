import {createElement} from "react";
import {renderToStaticMarkup} from "react-dom/server";
import {describe, expect, it} from "vitest";
import type {AssistantMessage} from "@/lib/workspace/api-adapter";
import type {AnswerView, RunTargets} from "@/lib/workspace/use-workspace-runtime";
import {AssistantPanel, targetText} from "./AssistantPanel";

const message = (id: string): AssistantMessage => ({id, field_id: "f1", created: 1, text: "依頼", state: "answered", reply: "回答", applicable: true, reasons: [], stage: null, effect: "none"});
const none = () => undefined;

function render(view: AnswerView | null, targets: RunTargets | null = null) {
  return renderToStaticMarkup(createElement(AssistantPanel, {
    messages: [message("m")], busy: false, demo: false, undoable: null,
    canApply: () => view?.intent !== "answer" && view !== null, canTry: () => view?.intent === null, canRun: () => view?.intent === "run",
    answerOf: () => view, runTargets: () => targets,
    onApply: none, onResend: none, onUndo: none, onShowSettings: none, onPlace: none, onRun: none, onChoose: none,
  }));
}

describe("the actions of an answer follow its kind of request (#284 W7, plan 5.6)", () => {
  it("a question shows its answer and the items to confirm, and no action that changes settings or runs", () => {
    const html = render({intent: "answer", scope: null, choices: [{question: "核染色のチャンネル", options: ["核染色は DRAQ", "核染色は GFP"]}], assignments: 2});
    expect(html).toContain("核染色は DRAQ");
    expect(html).toContain("割付の案：2 視野");
    expect(html).not.toContain("設定を適用");
    expect(html).not.toContain("適用して実行");
    expect(html).not.toContain("適用して試行");
    // Answered in this session: nothing to send again.
    expect(html).not.toContain("再送");
  });
  it("a settings request offers 「設定を適用」 only", () => {
    const html = render({intent: "settings", scope: null, choices: [], assignments: 0});
    expect(html).toContain("設定を適用");
    expect(html).not.toContain("適用して実行");
    expect(html).not.toContain("適用して試行");
  });
  it("a run request names its target fields and offers 「適用して実行」", () => {
    const html = render({intent: "run", scope: "all", choices: [], assignments: 0}, {scope: "all", fields: [{id: "a", label: "A01"}, {id: "b", label: "A02"}], excluded: 1});
    expect(html).toContain("対象：全視野 · 2 視野 · 対象外 1");
    expect(html).toContain("適用して実行");
    expect(html).not.toContain("設定を適用");
  });
  it("an earlier draft keeps 「設定を適用」 and 「適用して試行」, and a restored answer offers 「再送」", () => {
    const earlier = render({intent: null, scope: null, choices: [], assignments: 0});
    expect(earlier).toContain("設定を適用");
    expect(earlier).toContain("適用して試行");
    expect(render(null)).toContain("再送");
  });
  it("states the selected target as one value", () => {
    expect(targetText({scope: "selected", fields: [{id: "a", label: "A01"}], excluded: 0})).toBe("対象：選択した視野 · A01");
    expect(targetText({scope: "all", fields: [{id: "a", label: "A01"}], excluded: 0})).toBe("対象：全視野 · 1 視野");
  });
});
