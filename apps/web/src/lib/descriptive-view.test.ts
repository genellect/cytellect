import { describe, expect, it } from "vitest";
import { descriptiveFieldNumber, descriptiveFieldStatus, descriptiveFigureView, descriptiveJobs, descriptiveRecovery, descriptiveRequest, sameDescriptiveSettings, savedDescriptiveLabel, selectedDescriptiveJob, type DescriptiveResult } from "./descriptive-view";
import type {components} from "./generated";
import type { Job } from "./types";

const job = (id: string, state: string, created: number, revision_id = "r1"): Job => ({ id, state, created, revision_id, kind: "statistics", analysis_mode: "descriptive", error: null, attempts: 1 });
const saved: DescriptiveResult = {
  analysis_kind: "descriptive", revision_id: "r1", metric: "mean_corrected", unit: "a.u.",
  spec: { selection: { source: "region", region_set_id: "cytoplasm", channel_id: "actin", metric: "mean_corrected" }, plot: { language: "en", preset: "nature-double" } },
  counts: { observations: 2, input_fields: 2, selected_fields: 1, excluded_failed_fields: 1, experimental_units: null },
  selection: { input_rows: 2, excluded: 0, gate_unselected: 0, missing_metric_selected: 0 },
  field_summary: [], source_fields: [{ field_id: "f1", region_set: { label: "Cell interiors" }, channel_provenance: [{ channel: { channel_id: "actin", label: "Actin", stain: "Phalloidin" } }, { channel: { channel_id: "dna", label: "DNA", stain: null } }] }],
  excluded_failed_fields: [{ field_id: "f2", reason: "Unusable image" }], figure: { source_files: [] }, warnings: [],
};

describe("source-bound descriptive display", () => {
  it.each(["queued", "running", "failed", "cancelled"])("retains the selected %s job instead of falling back to an older success", state => {
    const previous = job("previous", "succeeded", 1);
    const requested = job("requested", state, 2);
    expect(selectedDescriptiveJob([previous, requested], "requested", "r1")).toBe(requested);
  });

  it("does not substitute history before the selected job is visible to polling", () => {
    expect(selectedDescriptiveJob([job("previous", "succeeded", 1)], "not-yet-polled", "r1")).toBeUndefined();
  });

  it("selects the latest current-version request on first entry, including failures", () => {
    const current = job("current", "failed", 2);
    expect(selectedDescriptiveJob([job("historical", "succeeded", 3, "r0"), current, job("old-current", "succeeded", 1)], "", "r1")).toBe(current);
  });

  it("permits an explicit historical result without claiming the current revision", () => {
    expect(selectedDescriptiveJob([job("current", "succeeded", 2), job("historical", "succeeded", 1, "r0")], "historical", "r1")?.revision_id).toBe("r0");
  });

  it("never uses an inferential or export result as a descriptive result", () => {
    expect(descriptiveJobs([{ ...job("inference", "succeeded", 2), analysis_mode: "experimental-unit" }, { ...job("export", "succeeded", 3), kind: "export" }, job("description", "succeeded", 1)]).map(value => value.id)).toEqual(["description"]);
  });

  it("attributes the saved metric to the selected actual channel and region, not another source channel", () => {
    expect(savedDescriptiveLabel(saved)).toBe("Cell interiors · Actin（標識: Phalloidin） · 平均（背景補正）");
    const area = { ...saved, spec: { ...saved.spec, selection: { source: "region" as const, region_set_id: "cytoplasm", channel_id: null, metric: "area_px" } } };
    expect(savedDescriptiveLabel(area)).toBe("Cell interiors · 面積 / px²");
  });

  it("does not fabricate a missing stain or apply labels from the current options", () => {
    const dna = { ...saved, spec: { ...saved.spec, selection: { ...saved.spec.selection, source: "region" as const, region_set_id: "cytoplasm", channel_id: "dna" } } };
    expect(savedDescriptiveLabel(dna)).toContain("DNA（標識: 未記録）");
  });

  it("recognizes ungenerated channel, region, metric, language and width choices", () => {
    expect(sameDescriptiveSettings(saved, saved.spec.selection, "en", "nature-double")).toBe(true);
    for (const patch of [{ channel_id: "dna" }, { region_set_id: "nucleus" }, { metric: "mean" }]) {
      expect(sameDescriptiveSettings(saved, { source: "region", region_set_id: "cytoplasm", channel_id: "actin", metric: "mean_corrected", ...patch }, "en", "nature-double")).toBe(false);
    }
    expect(sameDescriptiveSettings(saved, saved.spec.selection, "ja", "nature-double")).toBe(false);
    expect(sameDescriptiveSettings(saved, saved.spec.selection, "en", "nature-single")).toBe(false);
    expect(sameDescriptiveSettings(saved, undefined, "en", "nature-double")).toBe(false);
  });

  it("keeps absent regions distinct from regions whose values cannot be selected", () => {
    expect(descriptiveFieldStatus("no_regions")).toBe("領域なし");
    expect(descriptiveFieldStatus("no_selected_values")).toBe("採用可能な値なし");
  });
});


it("uses the saved figure order rather than list positions for field tracing", () => {
 const fields=["f1","f2"].map(field_id=>({field_id,selected_rows:0,median:null,q1:null,q3:null,status:"no_regions"}));
 const source={...saved,field_summary:fields,spec:{...saved.spec,plot:{...saved.spec.plot,group_order:["f2","f1"]}}};
 expect(descriptiveFieldNumber(source,"f1")).toBe(2);
 expect(descriptiveFieldNumber(source,"f2")).toBe(1);
 expect(descriptiveFieldNumber(source,"absent")).toBeNull();
 expect(descriptiveFieldNumber({...source,spec:{...source.spec,plot:{...source.spec.plot,group_order:[]}}},"f1")).toBe(1);
});

function paged():DescriptiveResult & {figure:components["schemas"]["PagedDescriptiveOutput"]}{
 const order=["f9","f8","f7","f6","f5","f4","f3","f2","f1"];
 const pages=[1,2].map(page_index=>({page_index,files:{svg:`figure-00${page_index}.svg`,pdf:`figure-00${page_index}.pdf`,png:`figure-00${page_index}.png`}}));
 const source_files=["plot-data.csv","field-summary.csv","selection.csv","methods.md","figure-data.json","figure-caption.md",...pages.flatMap(page=>Object.values(page.files))];
 return {...saved,spec:{...saved.spec,figure_policy:{version:"2.0.0",layout:"field-pages"},plot:{...saved.spec.plot,group_order:order}},
  counts:{...saved.counts,input_fields:10,selected_fields:8,observations:16},
  field_summary:order.toReversed().map(field_id=>({field_id,selected_rows:field_id==="f9"?0:2,median:field_id==="f9"?null:11,q1:10,q3:12,status:field_id==="f9"?"no_regions":"selected"})),
  figure:{descriptive_figure_version:"2.0.0",status:"ready",error:null,field_order:order,page_plan:[{page_index:1,field_ids:order.slice(0,8),field_numbers:[1,2,3,4,5,6,7,8]},{page_index:2,field_ids:["f1"],field_numbers:[9]}],pages,y_limits:[-3,25],y_ticks:[0,10,20],style:{},font_metadata:{family:"Test font"},source_result_sha256:"b".repeat(64),source_files,files:Object.fromEntries(source_files.map(name=>[name,{sha256:"a".repeat(64),bytes:1}]))}};
}

describe("saved descriptive figure pages",()=>{
 it.each([undefined,"1.0.0","1.0.1"] as const)("keeps historical single figure %s without silently upgrading its output",version=>{
  const result={...saved,figure:{...(version?{descriptive_figure_version:version}:{}),source_files:["figure.svg","figure.pdf","figure.png"]}};
  expect(descriptiveFigureView(result)).toMatchObject({kind:"legacy",pages:[{files:{png:"figure.png"}}]});
  expect(result.spec).not.toHaveProperty("figure_policy");
 });
 it("uses saved order and global numbers including empty fields, with unchanged full ledgers",()=>{
  const result=paged(),before=structuredClone(result);const view=descriptiveFigureView(result);
  expect(view).toMatchObject({kind:"ready",fieldCount:9,limits:[-3,25],pages:[{fieldIds:["f9","f8","f7","f6","f5","f4","f3","f2"]},{fieldIds:["f1"],fieldNumbers:[9],files:{png:"figure-002.png"}}]});
  expect(result).toEqual(before);expect(result.counts.input_fields).toBe(10);expect(result.excluded_failed_fields).toEqual(saved.excluded_failed_fields);
 });
 it.each(["missing-page","wrong-file","duplicate-field","wrong-number","unknown-version","missing-policy","wrong-scale","extra-file"])("rejects %s without single-figure fallback",kind=>{
  const result=paged();
  if(kind==="missing-page")result.figure.pages.pop();
  if(kind==="wrong-file")result.figure.pages[1].files.png="figure-001.png";
  if(kind==="duplicate-field")result.figure.page_plan[1].field_ids=["f9"];
  if(kind==="wrong-number")result.figure.page_plan[1].field_numbers=[1];
  if(kind==="unknown-version")Object.assign(result.figure,{descriptive_figure_version:"3.0.0"});
  if(kind==="missing-policy")delete result.spec.figure_policy;
  if(kind==="wrong-scale")result.figure.y_limits=[25,-3];
  if(kind==="extra-file"){result.figure.source_files.push("../figure.png");result.figure.files["../figure.png"]={sha256:"a".repeat(64),bytes:1};}
  expect(descriptiveFigureView(result)).toEqual({kind:"invalid"});
 });
 it("exposes tables-only status while preserving failed-page identity and all source records",()=>{
  const result=paged();result.figure.status="tables_only";result.figure.pages=[];result.figure.error={code:"figure_font_glyphs_unavailable",page_index:2};result.figure.font_metadata=null;
  result.figure.source_files=result.figure.source_files.filter(name=>!name.startsWith("figure-00"));
  result.figure.files=Object.fromEntries(result.figure.source_files.map(name=>[name,{sha256:"a".repeat(64),bytes:1}]));
  expect(descriptiveFigureView(result)).toEqual({kind:"tables_only",code:"figure_font_glyphs_unavailable",failedPage:2,plannedPages:2,limits:[-3,25]});
  const empty=structuredClone(result);empty.figure.source_files=[];empty.figure.files={};
  expect(descriptiveFigureView(empty)).toEqual({kind:"invalid"});
  result.figure.pages=[{page_index:1,files:{svg:"figure-001.svg",pdf:"figure-001.pdf",png:"figure-001.png"}}];
  expect(descriptiveFigureView(result)).toEqual({kind:"invalid"});
 });
 it("creates a new paged request and retries only the saved revision, selector and order",()=>{
  expect(descriptiveRequest(saved.spec.selection,"en","nature-single")).toMatchObject({figure_policy:{version:"2.0.0",layout:"field-pages"},selection:saved.spec.selection});
  const result=paged();result.revision_id="historical";
  const recovered=descriptiveRecovery(result,"ja","nature-single");
  expect(recovered.path).toBe("/v1/revisions/historical/descriptive");
  expect(recovered.body.selection).toEqual(result.spec.selection);
  expect(recovered.body.plot).toMatchObject({language:"ja",preset:"nature-single",group_order:result.spec.plot.group_order});
  expect(result.spec.plot.language).toBe("en");
 });
});
