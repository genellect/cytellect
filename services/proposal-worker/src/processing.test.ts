import {expect,it} from "vitest";
import {PROMPT_VERSION,PREVIOUS_PROMPT_VERSION,PREIMPORT_PROMPT_VERSION,requestPayload,hasDraftShape,inputTokenCeiling} from "./openai";
import {checkRequest} from "./index";

it("uses executable settings only for the new prompt while preserving old clients", () => {
  const options = {apiKey:"test",model:"gpt-6.1-sol",maxOutputTokens:8000};
  const current = requestPayload(options,{},[]);
  const previous = requestPayload({...options,promptVersion:PREVIOUS_PROMPT_VERSION},{},[]);
  expect(previous.text.format.schema).toEqual(current.text.format.schema);
  expect(current.input[0].content[0].text).toContain("Mixed or implicit/null axis regions are unsupported");
  expect(previous.input[0].content[0].text).not.toContain("Mixed or implicit/null axis regions are unsupported");
  const old = requestPayload({...options,promptVersion:PREIMPORT_PROMPT_VERSION},{},[]);
  expect(PROMPT_VERSION).toBe("2026-10-08.1");
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
