import {readFileSync} from "node:fs";
import path from "node:path";
import {describe, expect, it} from "vitest";
import {RESEARCHER_CODES, reasonView} from "./assistant-reasons";

const root = path.resolve(__dirname, "../../../../..");
const codes = (file: string) => new Set([...readFileSync(path.join(root, file), "utf8").matchAll(/"(proposal_[a-z_]+)"/g)].map(match => match[1]));

describe("AI answer reasons (#284 W2)", () => {
  it("names every rejection code, either as a place the researcher changes or as a service-side failure", () => {
    const rejection = codes("packages/analysis/src/cytellect_analysis/proposal_validation.py");
    expect(rejection.size).toBeGreaterThan(40);
    for (const code of rejection) {
      const view = reasonView(code);
      expect(view.text.length, code).toBeGreaterThan(0);
      if (view.kind === "researcher") expect(view.place ?? "none", code).toMatch(/images|channels|experiment|settings|none/);
    }
    // A researcher-side entry names a code the API really returns (validation or context).
    const known = new Set([...rejection, ...codes("services/api/src/cytellect_api/proposals.py")]);
    for (const code of RESEARCHER_CODES) expect(known.has(code), code).toBe(true);
  });
  it("tells the researcher where to change what is theirs, and treats the model's errors as the service's", () => {
    expect(reasonView("proposal_one_nuclear_channel_required")).toEqual({kind: "researcher", text: "核染色のチャンネル：未指定", place: "channels"});
    expect(reasonView("proposal_shape_invalid")).toEqual({kind: "service", text: "AI の応答の形式の不備"});
    expect(reasonView("proposal_channels_mismatch").kind).toBe("service");
    expect(reasonView("unknown_code").kind).toBe("service");
  });
});
