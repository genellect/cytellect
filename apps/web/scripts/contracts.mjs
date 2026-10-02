import fs from "node:fs/promises";
import { fileURLToPath } from "node:url";
import openapiTS, { astToString } from "openapi-typescript";
const schema=new URL("../../../packages/contracts/openapi.json",import.meta.url);
const target=new URL("../src/lib/generated.ts",import.meta.url);
const result=astToString(await openapiTS(schema));
if(process.argv.includes("--check")){
 const existing=await fs.readFile(target,"utf8").catch(()=>"");
 if(existing!==result){console.error("OpenAPI TypeScript contract is stale. Run pnpm contracts.");process.exit(1);}
}else{await fs.writeFile(target,result);console.log("Generated "+fileURLToPath(target));}
