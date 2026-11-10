import {describe,expect,it} from "vitest";
import {channelGateInputSignature,channelGateName,channelGateRequest,recordedChannelGate,type ChannelGateFilter,type ChannelGateResult} from "./channel-gate";
import {comparisonSelection} from "./comparison-adapter";

const filter:ChannelGateFilter={version:"1.0.0",gate_protocol:"channel-gate/1.0.0",channel_id:"marker",method:"manual",values:"corrected",threshold:10,keep:"negative",percentile:99,control_field_ids:[]};
const fields=[{fieldId:"f",revisionId:"nuclei-1",label:"Field"}];
const result:ChannelGateResult={protocol:"channel-gate/1.0.0",filter,channel:{channel_id:"marker",label:"Marker",stain:"NPM1"},dates:{all:{threshold:10}},nuclei:[],field_counts:{},record:{decision_sha256:"a".repeat(64)}};

describe("channel gate transport",()=>{
  it("sends the actual channel and saved nuclear revision without GFP aliases",()=>{
    const request=channelGateRequest(filter,fields);
    expect(request).toEqual({filter,fields:[{field_id:"f",revision_id:"nuclei-1"}]});
    expect(JSON.stringify(request).toLowerCase()).not.toContain("gfp");
    expect(channelGateName(result)).toBe("NPM1");
    expect(()=>channelGateRequest({...filter,method:"negative_control",threshold:null,control_field_ids:["missing"]},fields)).toThrow("現在の対象");
  });
  it("uses only the server's decision digest and makes input changes stale",()=>{
    const recorded=recordedChannelGate(result);
    expect(recorded.reference_sha256).toBe("a".repeat(64));
    expect(()=>recordedChannelGate({...result,record:{}})).toThrow("再分類");
    const sources=[{field:"f",revision:"nuclei-1"}],metadata={f:{acquisition_date:"d1",condition:"A"}};
    const signature=channelGateInputSignature("w","nuclei",sources,metadata,filter);
    expect(channelGateInputSignature("w","nuclei",sources,metadata,recorded)).toBe(signature);
    expect(channelGateInputSignature("w","nuclei",[{field:"f",revision:"nuclei-2"}],metadata,filter)).not.toBe(signature);
    expect(channelGateInputSignature("w","nuclei",sources,{f:{...metadata.f,acquisition_date:"d2"}},filter)).not.toBe(signature);
    expect(channelGateInputSignature("w","nuclei",sources,metadata,{...filter,values:"raw"})).not.toBe(signature);
  });
  it("uses the same recorded filter for subset selection and pre-filter field positivity",()=>{
    const recorded=recordedChannelGate(result);
    expect(comparisonSelection("nuclei","mean","marker",null,recorded)).toMatchObject({channel_gate:recorded});
    const positive=comparisonSelection("nuclei","positive_fraction",null,null,recorded);
    expect(positive).toEqual({source:"field-summary",version:"1.0.0",region_set_id:"nuclei",metric:"positive_fraction",positivity:recorded});
    expect(JSON.stringify(positive)).not.toContain("gfp");
    expect(()=>comparisonSelection("nuclei","positive_fraction",null)).toThrow("分類");
    expect(comparisonSelection("nuclei","mean","marker")).toEqual({source:"region",region_set_id:"nuclei",metric:"mean",channel_id:"marker"});
  });
});
