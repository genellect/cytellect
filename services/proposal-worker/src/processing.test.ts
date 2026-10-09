import {expect,it} from "vitest";
import {PROMPT_VERSION,NUCLEAR_FILTER_PREVIOUS_PROMPT_VERSION,PARENT_PREVIOUS_PROMPT_VERSION,PREVIOUS_PROMPT_VERSION,PREIMPORT_PROMPT_VERSION,requestPayload,hasDraftShape,inputTokenCeiling} from "./openai";
import {checkRequest} from "./index";

it("uses executable settings only for the new prompt while preserving old clients", () => {
  const options = {apiKey:"test",model:"gpt-6.1-sol",maxOutputTokens:8000};
  const current = requestPayload(options,{},[]);
  const previous = requestPayload({...options,promptVersion:PREVIOUS_PROMPT_VERSION},{},[]);
  expect(JSON.stringify(previous.text.format.schema)).not.toContain("cellpose-sam");
  expect(JSON.stringify(current.text.format.schema)).toContain("cellpose-sam");
  expect(JSON.stringify(current.text.format.schema)).toContain("cellpose-sam-ncl");
  expect(current.input[0].content[0].text).toContain("cellpose-sam-ncl/4.1.0");
  expect(current.input[0].content[0].text).toContain("background_radius_px 10");
  expect(current.input[0].content[0].text).toContain("cellpose-sam/4.0.0 (without NCL preprocessing)");
  expect(current.input[0].content[0].text).toContain("Mixed or implicit/null axis regions are unsupported");
  expect(current.input[0].content[0].text).toContain("cellpose-sam-ncl-parent/4.3.0");
  expect(current.input[0].content[0].text).toContain("Only existing model candidates can anchor a supported region");
  expect(previous.input[0].content[0].text).not.toContain("Mixed or implicit/null axis regions are unsupported");
  const old = requestPayload({...options,promptVersion:PREIMPORT_PROMPT_VERSION},{},[]);
  expect(PROMPT_VERSION).toBe("2026-10-09.1");
  expect(current.text.format.schema.required).toContain("processing");
  expect(old.text.format.schema.required).not.toContain("processing");
  expect(current.input[0].content[0].text).toContain("dapi_poor");
  expect(old.input[0].content[0].text).not.toContain("Registered processing settings");
  const draft = {recipe:"none",channels:[],metrics:[],statistics:{kind:"descriptive",test:null,omnibus:null,association:null,x:null,y:null},additional_analyses:[],figures:[],missing_information:[],reference_ids:[],rationale:""};
  expect(hasDraftShape(draft)).toBe(true);
  expect(hasDraftShape({...draft,processing:null})).toBe(true);
  expect(hasDraftShape({...draft,processing:{code:"anything"}})).toBe(false);
});

it("bounds and budgets the full continuation rather than losing follow-up context", () => {
  const settings = {apiKey:"test",model:"gpt-6.1-sol",maxOutputTokens:8000};
  const context = {protocol:"1.1.0",goal:"もう少し細かく",channels:[{token:"ch1",stain:"DAPI",role:"nuclear"}],field_count:1};
  const followUp = {...context,previous_goal:"核の輪郭を検出",previous_proposal:null,current_processing:{version:"1.0.0",
    nuclei:{channel:"ch1",detection_max_side_px:1024,detector:{engine:"fiji-stardist-2d",model:"Versatile (fluorescent nuclei)",probability:0.65,nms:0.3,percentile_low:1,percentile_high:99.8}},nucleoli:null,signal:null}};
  expect(checkRequest({context:followUp})).not.toBeNull();
  expect(inputTokenCeiling(settings,followUp,[])).toBeGreaterThan(inputTokenCeiling(settings,context,[]));
  expect(requestPayload(settings,followUp,[]).input[1].content[0].text).toContain('"probability":0.65');
  expect(checkRequest({context:{...followUp,previous_goal:"x".repeat(2001)}})).toBeNull();
  expect(checkRequest({context:{...followUp,current_processing:{...followUp.current_processing,
    nuclei:{...followUp.current_processing.nuclei,detector:{...followUp.current_processing.nuclei.detector,probability:1}}}}})).toBeNull();
});

it("keeps the parent protocol readable by the previous installed client",()=>{
 const settings={apiKey:"test",model:"gpt-6.1-sol",maxOutputTokens:8000,promptVersion:PARENT_PREVIOUS_PROMPT_VERSION};
 const serialized=JSON.stringify(requestPayload(settings,{},[]).text.format.schema);
 expect(serialized).toContain("4.2.0"); expect(serialized).not.toContain("4.2.1"); expect(serialized).not.toContain("4.3.0"); expect(serialized).not.toContain("maximum_nuclear_coverage");
});

it("keeps 4.2.1 installed clients on their original schema and inference prompt",()=>{
 const settings={apiKey:"test",model:"gpt-6.1-sol",maxOutputTokens:8000,promptVersion:NUCLEAR_FILTER_PREVIOUS_PROMPT_VERSION};
 const payload=requestPayload(settings,{},[]),serialized=JSON.stringify(payload.text.format.schema);
 expect(serialized).toContain("4.2.0");expect(serialized).toContain("4.2.1");expect(serialized).not.toContain("4.3.0");
 expect(serialized).toContain("maximum_nuclear_coverage");
 expect(payload.input[0].content[0].text).toContain("cellpose-sam-ncl-parent/4.2.1");
 expect(payload.input[0].content[0].text).not.toContain("4.3.0");
 expect(payload.input[0].content[0].text).not.toContain("signal-supported boundary refinement");
});

it("validates returned detector protocols against the installed client's capabilities",()=>{
 const detector={engine:"cellpose-sam-ncl-parent",protocol_version:"4.3.0",model:"cpsam_v2",
  model_sha256:"0f1cc3f7ecdd8a037a57c6c48d9d8921391be4cbce3fa9f13c3e3a2e1253c667",
  diameter_px:null,normalization_percentile_low:1,normalization_percentile_high:99,flow_threshold:.4,
  cellprob_threshold:0,minimum_area_px:15,maximum_size_fraction:1,iterations:null,batch_size:1,compute_device:"cpu",
  smoothing_sigma_px:.9,parent_background_percentile:75,nuclear_diameter_fraction:.25,crop_padding_px:32,
  minimum_contrast_snr:5,local_background_radius_px:8,maximum_nuclear_coverage:.5};
 const draft={recipe:"nuclear-ncl",channels:[],metrics:[],statistics:{kind:"descriptive",test:null,omnibus:null,association:null,x:null,y:null},
  additional_analyses:[],figures:[],missing_information:[],reference_ids:[],rationale:"",background:null,gfp_selection:null,
  processing:{version:"1.0.0",nuclei:null,nucleoli:{channel:"ncl",detector},signal:null,cells:null}};
 expect(hasDraftShape(draft,PROMPT_VERSION)).toBe(true);
 expect(hasDraftShape(draft,NUCLEAR_FILTER_PREVIOUS_PROMPT_VERSION)).toBe(false);
 expect(hasDraftShape({...draft,processing:{...draft.processing,nucleoli:{channel:"ncl",detector:{...detector,protocol_version:"4.2.1"}}}},NUCLEAR_FILTER_PREVIOUS_PROMPT_VERSION)).toBe(true);
 expect(hasDraftShape({...draft,processing:{...draft.processing,nucleoli:{channel:"ncl",detector:{...detector,protocol_version:"4.2.1"}}}},PARENT_PREVIOUS_PROMPT_VERSION)).toBe(false);
});
