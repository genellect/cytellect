import {describe, expect, it} from "vitest";
import {tiffInputMode} from "./tiff-intake";

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
