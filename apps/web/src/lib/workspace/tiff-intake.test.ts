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
  it("recognizes the comment Bio-Formats (Fiji) writes before the OME root, and nothing else after a comment",async()=>{
    const tiff=(text:string)=>{const xml=new TextEncoder().encode(text),buffer=new ArrayBuffer(26+xml.length),view=new DataView(buffer);
      view.setUint16(0,0x4949);view.setUint16(2,42,true);view.setUint32(4,8,true);view.setUint16(8,1,true);
      view.setUint16(10,270,true);view.setUint16(12,2,true);view.setUint32(14,xml.length,true);view.setUint32(18,26,true);new Uint8Array(buffer,26).set(xml);return new Blob([buffer]);};
    const comment="<!-- Warning: this comment is an OME-XML metadata block, which contains crucial dimensional parameters and other important metadata. Please edit cautiously (if at all), and back up the original data before doing so. For more information, see the OME-TIFF documentation: https://docs.openmicroscopy.org/latest/ome-model/ome-tiff/ -->";
    expect(await tiffHasOmeMetadata(tiff(`<?xml version="1.0" encoding="UTF-8"?>${comment}<OME xmlns="http://www.openmicroscopy.org/Schemas/OME/2016-06"><Image/></OME>`))).toBe(true);
    expect(await tiffHasOmeMetadata(tiff(`<?xml version="1.0"?>${comment}<ImageJ/>`))).toBe(false);
    expect(await tiffHasOmeMetadata(tiff(`<?xml version="1.0"?><!-- unterminated <OME/>`))).toBe(false);
  });
  it("does not infer metadata from an OME filename or invalid contents",async()=>{
    expect(await tiffHasOmeMetadata(new File(["ordinary image"],"DAPI_GFP.ome.tif"))).toBe(false);
  });
});