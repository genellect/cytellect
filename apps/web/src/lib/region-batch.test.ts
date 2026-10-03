import {describe,expect,it} from "vitest";
import {batchMetadata,emptyBatchMetadata,mapBatchFiles} from "./region-batch";

describe("explicit batch file mapping",()=>{
 it("matches only the user-specified suffix and preserves original names",()=>{
  const image={name:"field2_DNA.tif"};const result=mapBatchFiles([{id:"nuclear",suffix:"_DNA",files:[image,{name:"field1_DNA.tif"}]},{id:"signal",suffix:"_actin",files:[{name:"field1_actin.tiff"},{name:"field2_actin.tiff"}]}]);
  expect(result.valid).toBe(true);expect(result.rows.map(row=>row.key)).toEqual(["field1","field2"]);expect(result.rows[1].files.nuclear).toBe(image);
 });
 it("rejects missing, duplicate, mismatched and non-TIFF inputs before transmission",()=>{
  expect(mapBatchFiles([{id:"a",suffix:"_a",files:[{name:"field_a.tif"}]},{id:"b",suffix:"_b",files:[]}]).valid).toBe(false);
  expect(mapBatchFiles([{id:"a",suffix:"",files:[{name:"field.tif"},{name:"FIELD.tiff"}]}]).rows[0].errors).toHaveLength(1);
  expect(mapBatchFiles([{id:"a",suffix:"_a",files:[{name:"field_b.tif"}]}]).valid).toBe(false);
  expect(mapBatchFiles([{id:"a",suffix:"",files:[{name:"field.png"}]}]).valid).toBe(false);
 });
 it("supports explicit same-basename pairing without deriving scientific metadata",()=>{
  const mapped=mapBatchFiles([{id:"a",suffix:"",files:[{name:"Control_mouse1.tif"}]}]);expect(mapped.valid).toBe(true);
  expect(batchMetadata(emptyBatchMetadata)).toEqual({condition:null,sample:null,experimental_unit:null,acquisition_date:null,pair:null,repeat_length:null});
 });
 it("validates nullable metadata without inventing independent units",()=>{
  expect(batchMetadata({...emptyBatchMetadata,condition:" Treatment A ",repeat_length:"0"})).toMatchObject({condition:"Treatment A",repeat_length:0,experimental_unit:null});
  expect(()=>batchMetadata({...emptyBatchMetadata,repeat_length:"NaN"})).toThrow();expect(()=>batchMetadata({...emptyBatchMetadata,repeat_length:"-1"})).toThrow();
 });
 it("rejects more than the workspace field ceiling",()=>{expect(mapBatchFiles([{id:"a",suffix:"",files:Array.from({length:101},(_,i)=>({name:`${i}.tif`}))}]).valid).toBe(false);});
});
