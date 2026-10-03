import {describe,expect,it} from "vitest";
import path from "node:path";
import {workspaceTestRuntime} from "../../tests/workspace-session";

const checkout=path.resolve(__dirname,"../../../..");
const localEnv={CYTELLECT_TEST_LOCAL:"1",CYTELLECT_WEB_URL:"http://127.0.0.1:8765",
 CYTELLECT_TEST_API_ORIGIN:"http://127.0.0.1:8765",CYTELLECT_TEST_PYTHON:path.resolve(checkout,"../accepted-app/python"),
 CYTELLECT_TEST_DATA_DIR:path.resolve(checkout,"../accepted-private-data")};

describe("installed workspace acceptance isolation",()=>{
 it("keeps ordinary API tests independent of local-only settings",()=>{
  expect(workspaceTestRuntime({CYTELLECT_TEST_API_ORIGIN:"http://localhost:8000"}).local).toBe(false);
 });
 it("accepts explicit loopback origins and a separate private data directory",()=>{
  expect(workspaceTestRuntime(localEnv)).toMatchObject({local:true,api:localEnv.CYTELLECT_TEST_API_ORIGIN});
 });
 it.each(["CYTELLECT_WEB_URL","CYTELLECT_TEST_API_ORIGIN","CYTELLECT_TEST_PYTHON","CYTELLECT_TEST_DATA_DIR"])("requires explicit %s in local acceptance",key=>{
  expect(()=>workspaceTestRuntime({...localEnv,[key]:undefined})).toThrow(/explicit/);
 });
 it.each(["http://localhost:8765","http://127.0.0.1:8000","https://example.com","http://user@127.0.0.1:8765","http://127.0.0.1:8765/?token=unused"])("rejects a different or decorated API origin: %s",api=>{
  expect(()=>workspaceTestRuntime({...localEnv,CYTELLECT_TEST_API_ORIGIN:api})).toThrow(/literal loopback/);
 });
 it.each([checkout,path.join(checkout,"runtime"),"relative-data"])("rejects data within source or an implicit path: %s",dataDir=>{
  expect(()=>workspaceTestRuntime({...localEnv,CYTELLECT_TEST_DATA_DIR:dataDir})).toThrow(/outside the checkout/);
 });
});
