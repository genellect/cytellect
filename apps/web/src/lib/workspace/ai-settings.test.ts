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

  it("reads a choice stored by another tab once this page's own choice was stored (review of #236)", () => {
    const stored = new Map<string, string>();
    vi.stubGlobal("localStorage", {getItem: (key: string) => stored.get(key) ?? null, setItem: (key: string, value: string) => void stored.set(key, value)});
    setIncludePreviews(true);
    expect(includePreviews()).toBe(true);
    stored.set("cytellect.ai.include-previews", "0");
    expect(includePreviews()).toBe(false);
  });

  it("keeps the choice made on this page over an older stored value", () => {
    const stored = new Map<string, string>([["cytellect.ai.include-previews", "1"]]);
    vi.stubGlobal("localStorage", {getItem: (key: string) => stored.get(key) ?? null, setItem: () => {throw new Error("blocked");}});
    setIncludePreviews(false);
    expect(includePreviews()).toBe(false);
  });
});
