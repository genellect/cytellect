import {afterEach, describe, expect, it, vi} from "vitest";
import {includePreviews, markProposalScopeSeen, proposalScopeSeen, setIncludePreviews} from "./ai-settings";

afterEach(() => {setIncludePreviews(true); vi.unstubAllGlobals();});

describe("AI settings on this PC", () => {
  it("keeps an opt-out of previews when storage cannot be written (review of #231)", () => {
    vi.stubGlobal("localStorage", {getItem: () => null, setItem: () => {throw new Error("QuotaExceededError");}});
    expect(includePreviews()).toBe(true);
    setIncludePreviews(false);
    expect(includePreviews()).toBe(false);
    markProposalScopeSeen();
    expect(proposalScopeSeen()).toBe(true);
  });

  it("keeps the choice made on this page over an older stored value", () => {
    const stored = new Map<string, string>([["cytellect.ai.include-previews", "1"]]);
    vi.stubGlobal("localStorage", {getItem: (key: string) => stored.get(key) ?? null, setItem: () => {throw new Error("blocked");}});
    setIncludePreviews(false);
    expect(includePreviews()).toBe(false);
  });
});
