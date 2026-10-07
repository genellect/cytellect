import {beforeEach, describe, expect, it, vi} from "vitest";
const calls = vi.hoisted(() => ({request: vi.fn(), post: vi.fn(), preview: vi.fn(), revoke: vi.fn(), create: vi.fn()}));
vi.mock("../api", () => ({API: "http://localhost:8000", request: calls.request, post: calls.post,
  fetchBlob: vi.fn(), fetchPrivateResponse: calls.preview, errorCodeMessage: (value: string) => value,
  ApiError: class extends Error {constructor(public code: string, public status: number) {super(code);}}}));
import {loadReviewPreview, releaseReviewPreview} from "./review-preview";

const nuclear = {id: "region-2d", version: "1.7.0", source: "stardist_nuclear", defining_channel_id: "c4", region_set_id: "nuclei", label: "Nuclei"};
const revisions = [
  {id: "n1", state: "succeeded", created: 1, config: {field_ids: ["f1"], recipe: nuclear}},
  {id: "bright", state: "succeeded", created: 2, config: {field_ids: ["f1"], recipe: {...nuclear, source: "fiji_positive_regions", region_set_id: "gfp_positive"}}},
  {id: "unadopted", state: "succeeded", created: 3, config: {field_ids: ["f1"], recipe: nuclear}},
];
const registered = {id: "f1", workspace_id: "latest", metadata: {}, image_info: {shape: [80, 120],
  channels: [{channel_id: "c4", label: "c4", stain: null}]}};
let fixtures: Record<string, unknown>;
beforeEach(() => {
  vi.clearAllMocks();
  fixtures = {
    "/v1/session": {authenticated: true},
    "/v1/workspaces": [{id: "old", created: 1, expires: 9e10}, {id: "latest", created: 2, expires: 9e10}, {id: "deleted", created: 3, expires: 9e10, deleted: true}],
    "/v1/workspaces/latest": {id: "latest", title: "Saved workspace"},
    "/v1/workspaces/latest/region-fields": [registered],
    "/v1/workspaces/latest/revisions": revisions,
    "/v1/workspaces/latest/jobs": [],
    "/v1/workspaces/latest/selection": {version: 1, entries: [{id: "f1", field_id: "f1", revision_id: "bright", exclusion_reason: null, target_revisions: {nuclei: "n1", gfp: "bright"}}]},
    "/v1/workspaces/latest/channel-assignments": {version: 0, assignments: []},
    "/v1/revisions/n1/region-measurements": {revision_id: "n1", field_tables: {f1: {rows: [{region_id: 17, channel_id: "c4", mean: 20, area_px: 4}]}}, field_failures: [], exclusions: []},
    "/v1/revisions/n1/region-masks?field_id=f1": {regions: [{id: 17, points: [[2, 2], [4, 2], [4, 4]]}], metadata: {mask_revision_id: "mask1"}},
  };
  calls.request.mockImplementation(async (path: string, options?: RequestInit) => {
    if (options?.method && options.method !== "GET") throw new Error("mutation forbidden");
    if (!(path in fixtures)) throw new Error("unregistered fixture");
    return structuredClone(fixtures[path]);
  });
  calls.preview.mockResolvedValue(new Response(new Blob(["synthetic fixture"]), {status: 200}));
  calls.create.mockReturnValue("blob:test-preview");
  vi.stubGlobal("URL", Object.assign(URL, {createObjectURL: calls.create, revokeObjectURL: calls.revoke}));
});

describe("stage-one read-only review loader", () => {
  it("loads only the requested new field preview during sequential intake", async () => {
    fixtures["/v1/workspaces/latest/region-fields"] = [registered, {...registered,id:"f2"}];
    const data = await loadReviewPreview("latest",["f2"]);
    expect(data.fields.map(field=>field.id)).toEqual(["f2"]);
    expect(calls.preview).toHaveBeenCalledTimes(1);
    expect(calls.preview.mock.calls[0][0]).toContain("/f2/preview");
    expect(calls.request.mock.calls.some(([path])=>String(path).includes("/n1/region-"))).toBe(false);
  });
  it("loads newest live workspace and only adopted biological masks without inferring a cell or c4 stain", async () => {
    const data = await loadReviewPreview();
    expect(data.workspaceId).toBe("latest");
    expect(data.fields[0]).toMatchObject({width: 120, height: 80, channels: [{id: "c4", stain: null, role: null}]});
    expect(data.fields[0].results.nuclei?.masks.regions[0].id).toBe(17);
    expect(data.fields[0].nuclearChannelId).toBe("c4");
    expect(Object.keys(data.fields[0].results)).toEqual(["nuclei"]);
    expect(calls.request.mock.calls.some(([path]) => String(path).includes("bright/region-") || String(path).includes("unadopted/region-"))).toBe(false);
    expect(calls.post).not.toHaveBeenCalled();
    expect(data.fields[0].previewDisplay?.c4.status).toBe("missing");
    releaseReviewPreview(data);
    expect(calls.revoke).toHaveBeenCalledWith("blob:test-preview");
  });
  it("retains the field with explicit failures and applies only persisted channel assignments", async () => {
    fixtures["/v1/workspaces/latest/channel-assignments"] = {version: 2, assignments: [{channel_id: "c4", stain: "GFP", role: "measure"}]};
    delete fixtures["/v1/revisions/n1/region-masks?field_id=f1"];
    calls.preview.mockRejectedValue(new Error("private details must not propagate"));
    const data = await loadReviewPreview("latest");
    expect(data.channels[0]).toMatchObject({id: "c4", stain: "GFP", role: "measure"});
    expect(data.fields[0].results).toEqual({});
    expect(data.fields[0].nuclearChannelId).toBeUndefined();
    expect(data.fields[0].error).toContain("採用した領域または測定値を読み込めません");
    expect(data.fields[0].error).toContain("画像プレビューを読み込めません");
    expect(data.fields[0].error).not.toContain("private");
    expect(calls.post).not.toHaveBeenCalled();
  });
  it("does not resurrect a historical mask when no revision is adopted", async () => {
    fixtures["/v1/workspaces/latest/selection"] = {version: 2, entries: [{id: "f1", field_id: "f1", revision_id: null, target_revisions: {}}]};
    const data = await loadReviewPreview("latest");
    expect(data.fields[0].results).toEqual({});
    expect(data.fields[0].nuclearChannelId).toBeUndefined();
    expect(calls.request.mock.calls.some(([path]) => String(path).startsWith("/v1/revisions/"))).toBe(false);
  });
  it("loads only the explicit manual cell region set as cells", async () => {
    fixtures["/v1/workspaces/latest/revisions"] = [{id:"n1",state:"succeeded",created:1,config:{field_ids:["f1"],recipe:{...nuclear,version:"1.0.0",source:"manual",region_set_id:"cell"}}}];
    fixtures["/v1/workspaces/latest/selection"] = {version:2,entries:[{id:"f1",field_id:"f1",revision_id:"n1",target_revisions:{cell:"n1"}}]};
    const data=await loadReviewPreview("latest");expect(Object.keys(data.fields[0].results)).toEqual(["cell"]);expect(data.fields[0].nuclearChannelId).toBeUndefined();
    fixtures["/v1/workspaces/latest/revisions"] = [{id:"n1",state:"succeeded",created:1,config:{field_ids:["f1"],recipe:{...nuclear,source:"fiji_positive_regions",region_set_id:"cell"}}}];
    expect((await loadReviewPreview("latest")).fields[0].results).toEqual({});
  });  it("reports an empty account without creating a workspace", async () => {
    fixtures["/v1/workspaces"] = [];
    await expect(loadReviewPreview()).rejects.toThrow("no_saved_workspace");
    expect(calls.post).not.toHaveBeenCalled();
  });
});
