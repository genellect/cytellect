import {describe, expect, it} from "vitest";
import {tiffInputMode,tiffHasOmeMetadata} from "./tiff-intake";

describe("TIFF intake metadata", () => {
  it.each([true, false])("recognizes RGB without decoding pixels (little endian %s)", async little => {
    const bytes = new ArrayBuffer(26); const data = new DataView(bytes);
    data.setUint16(0, little ? 0x4949 : 0x4d4d);
    data.setUint16(2, 42, little); data.setUint32(4, 8, little);
    data.setUint16(8, 1, little); data.setUint16(10, 262, little);
    data.setUint16(12, 3, little); data.setUint32(14, 1, little); data.setUint16(18, 2, little);
    expect(await tiffInputMode(new Blob([bytes]))).toBe("display-rgb");
    data.setUint16(18, 1, little);
    expect(await tiffInputMode(new Blob([bytes]))).toBe("native");
  });
  it("leaves malformed content for authoritative API validation", async () => {
    expect(await tiffInputMode(new Blob(["not a TIFF image"]))).toBe("native");
    expect(await tiffInputMode(new Blob([]))).toBe("native");
  });
});

describe("OME routing",()=>{
  it.each([true,false])("reads bounded ImageDescription XML and never guesses dye roles (%s)",async little=>{
    const xml=new TextEncoder().encode('<?xml version="1.0"?><OME xmlns="http://www.openmicroscopy.org/Schemas/OME/2016-06"><Image/></OME>\0');
    const buffer=new ArrayBuffer(26+xml.length),view=new DataView(buffer);
    view.setUint16(0,little?0x4949:0x4d4d);view.setUint16(2,42,little);view.setUint32(4,8,little);view.setUint16(8,1,little);
    view.setUint16(10,270,little);view.setUint16(12,2,little);view.setUint32(14,xml.length,little);view.setUint32(18,26,little);new Uint8Array(buffer,26).set(xml);
    expect(await tiffHasOmeMetadata(new Blob([buffer]))).toBe(true);
    view.setUint32(14,3*1024*1024,little);expect(await tiffHasOmeMetadata(new Blob([buffer]))).toBe(false);
  });
  it("does not infer metadata from an OME filename or invalid contents",async()=>{
    expect(await tiffHasOmeMetadata(new File(["ordinary image"],"DAPI_GFP.ome.tif"))).toBe(false);
  });
});