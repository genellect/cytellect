import type {Route} from "@playwright/test";

/** Read-only defaults for transport fixtures. Real configuration, ownership and history are API-tested. */
export async function aiReadFixture(route:Route):Promise<boolean>{
  const request=route.request(),path=new URL(request.url()).pathname;
  const status=path==="/v1/ai/status",history=/^\/v1\/jobs\/[^/]+\/discussion-history$/.test(path);
  if(!status&&!history)return false;
  const headers={"Access-Control-Allow-Origin":request.headers().origin||"http://localhost:3000",
    "Access-Control-Allow-Credentials":"true","Access-Control-Allow-Headers":"content-type,x-cytellect-request",
    "Access-Control-Allow-Methods":"GET,OPTIONS"};
  await route.fulfill({status:request.method()==="OPTIONS"?204:200,headers,contentType:"application/json",
    ...(request.method()==="OPTIONS"?{}:{body:JSON.stringify(status?{state:"available",source:"operator"}:{current:null,previous:null})})});
  return true;
}
