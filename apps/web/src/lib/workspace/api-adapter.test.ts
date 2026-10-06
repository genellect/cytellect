import {describe, expect, it, vi} from "vitest";
import {assertWorkspaceConnection, automaticBackground, channelSpecification, createApiAdapter, figureIdentity, nuclearRecipe, type SavedResult, type Transport} from "./api-adapter";
import type {ChannelDefinition} from "./grouping";

const channel: ChannelDefinition = {token: "channel2", stain: null, role: "nuclear", evidence: "user"};
const result: SavedResult = {revision: "r1", field: "f1", rows: [], masks: {regions: [], metadata: {mask_revision_id: "m1"}}, exclusions: []};
function fake(handler: (path: string, options?: RequestInit) => Promise<unknown>, postHandler?: (path: string, body?: unknown) => Promise<unknown>) {
  let selection = {version: 0, entries: [{id: "f1", field_id: "f1", revision_id: "r1", exclusion_reason: null}]};
  const request = vi.fn((path: string, options?: RequestInit) => path.endsWith("/selection") ? Promise.resolve(selection) : handler(path, options)) as unknown as Transport["request"];
  const action = postHandler ?? (async () => ({job_id: "j1", revision_id: "r1"}));
  const post = vi.fn((path: string, body?: unknown) => {if (path.endsWith("/selection")) {const next = body as typeof selection; selection = {...next, version: next.version + 1}; return Promise.resolve(selection);} return action(path, body);}) as unknown as Transport["post"];
  return {adapter: createApiAdapter({request, post, wait: async () => {}}), request, post};
}
describe("real workspace transport boundaries", () => {
  it("keeps legacy detection unchanged and versions an explicitly selected detection scale", () => {
    expect(nuclearRecipe(channel)).not.toHaveProperty("detection_max_side_px");
    expect(nuclearRecipe(channel, 320)).toMatchObject({version: "1.5.0", detection_max_side_px: 320, defining_channel_id: "channel2"});
    for (const invalid of [0, 63, 2049, 320.5, NaN]) expect(() => nuclearRecipe(channel, invalid)).toThrow();
  });
  it("merges a deduplicated upload without changing the existing adopted revision", async () => {
    const {adapter} = fake(async () => ({id: "f1", workspace_id: "w1", image_info: {shape: [2, 2], channels: []}, metadata: {}}));
    await adapter.registerImport("w1", "pending");
    await adapter.upload("w1", {key: "incoming", files: {channel2: {path: "plane.tif", size: 1}}, candidates: {}}, [channel], new Map([["plane.tif", new File(["x"], "plane.tif")]]), "pending");
    expect(adapter.selection()!.entries).toEqual([{id: "f1", field_id: "f1", revision_id: "r1", exclusion_reason: null}]);
  });
  it("explicitly recovers an orphan field without adopting old results or failed slots", async () => {
    const {adapter, post} = fake(async () => ({}));
    const entry = await adapter.recoverField("w1", "orphan-field");
    expect(entry).toMatchObject({field_id: "orphan-field", revision_id: null, exclusion_reason: null});
    expect(adapter.selection()!.entries).toHaveLength(2);
    expect(post).toHaveBeenCalledTimes(1);
    expect(await adapter.recoverField("w1", "orphan-field")).toEqual(entry);
    expect(post).toHaveBeenCalledTimes(1);
  });
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
  it("sends the automatic background policy only when asked and keeps it as a separate run", async () => {
    const {adapter, post} = fake(async path => path.endsWith("/jobs") ? [{id: "j1", state: "succeeded"}] : {revision_id: "other", field_failures: [], field_tables: {f1: {rows: []}}, exclusions: []});
    await expect(adapter.run("w1", "f1", nuclearRecipe(channel), undefined, automaticBackground)).rejects.toThrow("解析版");
    expect(post).toHaveBeenCalledWith("/v1/workspaces/w1/region-analyses", expect.objectContaining({measurement: {version: "1.2.0", mode: "automatic_background"}, backgrounds: {}}));
  });
  it("sends split with one region and its polygon, and merge with the chosen regions and no polygon", async () => {
    const square: Array<[number, number]> = [[0, 0], [2, 0], [2, 2]];
    const recipe = nuclearRecipe(channel);
    for (const [operation, region, merged] of [["split", 4, []], ["merge", undefined, [3, 5]]] as const) {
      const {adapter, post} = fake(async () => ({revision_id: "other", field_failures: [], field_tables: {}, exclusions: []}));
      await expect(adapter.editMask("w1", result, recipe, operation, [...square], region, [...merged])).rejects.toThrow();
      expect(post).toHaveBeenCalledWith("/v1/revisions/r1/region-edits", expect.objectContaining(operation === "split" ? {operation, ids: [4], polygon: square} : {operation, ids: [3, 5], polygon: []}));
    }
    const {adapter, post} = fake(async () => ({}));
    await expect(adapter.editMask("w1", result, recipe, "merge", [], undefined, [3])).rejects.toThrow("修正する領域");
    expect(post).not.toHaveBeenCalledWith("/v1/revisions/r1/region-edits", expect.anything());
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
  it("creates a new job when the defining channel changes", async () => {
    const {adapter, post} = fake(async path => path.endsWith("/jobs") ? [{id: "j1", state: "succeeded"}] : {revision_id: "different", field_failures: [], field_tables: {}});
    await expect(adapter.run("w1", "f1", nuclearRecipe(channel))).rejects.toThrow("解析版");
    await expect(adapter.run("w1", "f1", {...nuclearRecipe(channel), defining_channel_id: "channel3"})).rejects.toThrow("解析版");
    expect(post).toHaveBeenCalledTimes(2);
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
    for (const patch of [{xLabel: "Field"}, {fontSize: 9}, {language: "en" as const}, {yMin: 0}, {yMax: 100}, {yTickStep: 10}, {pointSize: 25}]) {
      expect(figureIdentity("r1", choice)).not.toBe(figureIdentity("r1", {...choice, ...patch}));
    }
    expect(figureIdentity("r1", choice)).not.toBe(figureIdentity("r1", {...choice, channel: "channel1"}));
  });
  it("keeps positive-region identity in graph and delete requests", async () => {
    const {adapter, post} = fake(async path => path.endsWith("/jobs") ? [{id: "j1", state: "succeeded"}] : path.includes("region-masks") ? result.masks : {revision_id: "r1", field_tables: {f1: {rows: []}}, field_failures: [], exclusions: []});
    const recipe = {...nuclearRecipe(channel), version: "1.3.0" as const, source: "fiji_positive_regions" as const, region_set_id: "gfp_positive", label: "GFP陽性領域"};
    await adapter.correct("w1", {...result, regionSet: "gfp_positive"}, "delete", 7, recipe);
    expect(post).toHaveBeenCalledWith("/v1/revisions/r1/region-edits", expect.objectContaining({region_set_id: "gfp_positive"}));
    await adapter.figure("w1", {...result, regionSet: "gfp_positive"}, {channel: "channel2", metric: "mean", width: 178, height: 76, label: "Intensity"});
    expect(post).toHaveBeenCalledWith("/v1/revisions/r1/descriptive-preview", expect.objectContaining({selection: expect.objectContaining({region_set_id: "gfp_positive"})}));
  });
  it("sends only a goal and explicit scope consent for optional proposals", async () => {
    const {adapter, post} = fake(async () => ({}));
    await adapter.draft("w1", "核面積を確認");
    expect(post).toHaveBeenCalledWith("/v1/workspaces/w1/proposal-drafts", {goal: "核面積を確認", transmission_confirmed: true});
    await adapter.draft("w1", "核面積を確認", true);
    expect(post).toHaveBeenLastCalledWith("/v1/workspaces/w1/proposal-drafts", {goal: "核面積を確認", transmission_confirmed: true, retry_failed: true});
  });
});
