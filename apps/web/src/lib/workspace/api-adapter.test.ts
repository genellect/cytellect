import {describe, expect, it, vi} from "vitest";
import {assertWorkspaceConnection, channelSpecification, createApiAdapter, figureIdentity, nuclearRecipe, type SavedResult, type Transport} from "./api-adapter";
import type {ChannelDefinition} from "./grouping";

const channel: ChannelDefinition = {token: "channel2", stain: null, role: "nuclear", evidence: "user"};
const result: SavedResult = {revision: "r1", field: "f1", rows: [], masks: {regions: [], metadata: {mask_revision_id: "m1"}}, exclusions: []};
function fake(handler: (path: string, options?: RequestInit) => Promise<unknown>, postHandler?: (path: string, body?: unknown) => Promise<unknown>) {
  const request = vi.fn(handler) as unknown as Transport["request"];
  const post = vi.fn(postHandler ?? (async () => ({job_id: "j1", revision_id: "r1"}))) as unknown as Transport["post"];
  return {adapter: createApiAdapter({request, post, wait: async () => {}}), request, post};
}
describe("real workspace transport boundaries", () => {
  it("refuses a public page connecting to loopback even if an API origin was configured", () => {
    expect(() => assertWorkspaceConnection("example.vercel.app", "http://127.0.0.1:8000")).toThrow("公開サイト");
    expect(() => assertWorkspaceConnection("127.0.0.1", "http://127.0.0.1:8000")).not.toThrow();
    expect(() => assertWorkspaceConnection("app.example.org", "https://api.example.org")).not.toThrow();
  });
  it("records inference and an explicit nuclear-role choice without inventing confirmations or a stain", () => {
    expect(channelSpecification({...channel, role: null, evidence: "filename"})).toMatchObject({identity_source: "filename", stain: null});
    expect(channelSpecification(channel)).not.toHaveProperty("identity_confirmed");
    expect(nuclearRecipe(channel)).toMatchObject({version: "1.2.0", nuclear_role_source: "user_selected_role", defining_channel_id: "channel2"});
    expect(nuclearRecipe(channel)).not.toHaveProperty("nuclear_stain_confirmed");
    expect(() => nuclearRecipe({...channel, role: null})).toThrow();
  });
  it("does not substitute another revision's measurements or retry a failed run silently", async () => {
    const {adapter, post} = fake(async path => path.endsWith("/jobs") ? [{id: "j1", state: "succeeded"}] : {revision_id: "other", field_failures: [], field_tables: {f1: {rows: []}}, exclusions: []});
    await expect(adapter.run("w1", "f1", nuclearRecipe(channel))).rejects.toThrow("解析版");
    expect(post).toHaveBeenCalledTimes(1);
    expect(post).toHaveBeenCalledWith("/v1/workspaces/w1/region-analyses", expect.objectContaining({measurement: {version: "1.1.0", mode: "raw_intensity"}, backgrounds: {}}));
  });
  it("never resubmits after an uncertain POST or a polling connection failure", async () => {
    const uncertain = fake(async () => [], async () => {throw new TypeError("network");});
    await expect(uncertain.adapter.run("w1", "f1", nuclearRecipe(channel))).rejects.toThrow();
    await expect(uncertain.adapter.run("w1", "f1", nuclearRecipe(channel))).rejects.toThrow("受付状態");
    expect(uncertain.post).toHaveBeenCalledTimes(1);
    const polling = fake(async () => {throw new TypeError("network");});
    await expect(polling.adapter.run("w1", "f1", nuclearRecipe(channel))).rejects.toThrow();
    await expect(polling.adapter.run("w1", "f1", nuclearRecipe(channel))).rejects.toThrow();
    expect(polling.post).toHaveBeenCalledTimes(1);
  });
  it("retains the exact mask version and parent for a delete", async () => {
    const {adapter, post} = fake(async path => path.endsWith("/jobs") ? [{id: "j1", state: "succeeded"}] : path.includes("region-masks") ? result.masks : {revision_id: "r1", field_tables: {f1: {rows: []}}, field_failures: [], exclusions: []});
    await adapter.correct("w1", result, "delete", 7, nuclearRecipe(channel));
    expect(post).toHaveBeenNthCalledWith(1, "/v1/workspaces/w1/current", {revision_id: "r1"});
    expect(post).toHaveBeenNthCalledWith(2, "/v1/revisions/r1/region-edits", expect.objectContaining({ids: [7], expected_mask_revision_id: "m1"}));
  });
  it("styles only the saved measurement revision and never marks it reviewed", async () => {
    const {adapter, post, request} = fake(async path => path.endsWith("/jobs") ? [{id: "j1", state: "succeeded"}] : {revision_id: "r1"});
    const choice = {channel: "channel2", metric: "mean", width: 178, height: 76, label: "Raw intensity"};
    await adapter.figure("w1", result, choice);
    expect(post).toHaveBeenCalledTimes(1);
    expect(request).toHaveBeenLastCalledWith("/v1/jobs/j1/result", undefined);
    expect(post).toHaveBeenCalledWith("/v1/revisions/r1/descriptive-preview", expect.objectContaining({selection: {source: "region", region_set_id: "nuclei", metric: "mean", channel_id: "channel2"}, plot: expect.objectContaining({width_inches: 178/25.4, y_label: "Raw intensity"})}));
    expect(figureIdentity("r1", choice)).not.toBe(figureIdentity("r2", choice));
    expect(figureIdentity("r1", choice)).not.toBe(figureIdentity("r1", {...choice, channel: "channel1"}));
  });
  it("sends only a goal and explicit scope consent for optional proposals", async () => {
    const {adapter, post} = fake(async () => ({}));
    await adapter.draft("w1", "核面積を確認");
    expect(post).toHaveBeenCalledWith("/v1/workspaces/w1/proposal-drafts", {goal: "核面積を確認", transmission_confirmed: true});
  });
});
