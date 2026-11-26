import {describe,expect,it,vi} from "vitest";
import probes from "../../../fixtures/proposal-version-probes.json";
import {handle,type Env} from "./index";
import {MemoryStore} from "./store";
import {redeemSupport} from "./test-support";
import {FIGURE_PROMPT_VERSION} from "./openai";
import {DISCUSSION_PROMPT_VERSION} from "./discussion";

const env:Env={DB:undefined as never,OPENAI_API_KEY:"sk-test",OPENAI_MODEL:"gpt-6.1-sol",ADMIN_TOKEN:"admin-token-0123456789abcdef",
  MONTHLY_BUDGET_USD:"1",DEVICE_MONTHLY_REQUESTS:"3",PRICE_INPUT_USD_PER_MTOK:"2",PRICE_OUTPUT_USD_PER_MTOK:"10",
  PRICE_CACHED_INPUT_USD_PER_MTOK:"0.1",PRICE_CACHE_WRITE_USD_PER_MTOK:"2.5"};

describe("release prompt probes stop before admission",()=>{
  it("uses the actual current client versions for both routes",()=>{
    expect(probes.map(item=>item.prompt_version)).toEqual([FIGURE_PROMPT_VERSION,DISCUSSION_PROMPT_VERSION]);
  });
  for(const item of probes)for(const supported of [true,false])it(`${item.route}: ${supported?"accepted":"unsupported"} version never incurs use`,async()=>{
    const store=new MemoryStore(),fetcher=vi.fn();
    const invitationResponse=await handle(new Request("https://service.example/v1/admin/invitations",{method:"POST",body:"{}",
      headers:{authorization:`Bearer ${env.ADMIN_TOKEN}`}}),env,store);
    const {invitation}=await invitationResponse.json() as {invitation:string};
    const limiter=await redeemSupport();
    const deviceResponse=await handle(new Request("https://service.example/v1/devices",{method:"POST",body:JSON.stringify({invitation})}),{...env,...limiter.env},store,limiter.options);
    const {device_token:token}=await deviceResponse.json() as {device_token:string};
    const admission=[vi.spyOn(store,"claimRequest"),vi.spyOn(store,"countDeviceRequest"),vi.spyOn(store,"reserve"),
      vi.spyOn(store,"reserveForUser"),vi.spyOn(store,"settle")];
    const response=await handle(new Request(`https://service.example${item.route}`,{method:"POST",
      headers:{authorization:`Bearer ${token}`,"content-type":"application/json"},
      body:JSON.stringify({context:item.context,prompt_version:supported?item.prompt_version:"9999-01-01.1"})}),env,store,{fetcher});
    expect([response.status,await response.json()]).toEqual([400,{code:supported?"request_id_required":"prompt_version_unsupported"}]);
    admission.forEach(method=>expect(method).not.toHaveBeenCalled());
    expect(fetcher).not.toHaveBeenCalled();
    expect(store.requests.size+store.claimedRequests.size+store.reservations.size+store.spent.size+store.usage.size).toBe(0);
  });
});
