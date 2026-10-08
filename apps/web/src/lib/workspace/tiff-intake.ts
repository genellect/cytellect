/** Read only the first IFD's photometric tag. The API validates axes and pixels. */
export async function tiffInputMode(file: Blob): Promise<"native" | "display-rgb"> {
  const head = new DataView(await file.slice(0, 16).arrayBuffer());
  if (head.byteLength < 8) return "native";
  const little = head.getUint16(0) === 0x4949;
  if (!little && head.getUint16(0) !== 0x4d4d) return "native";
  const magic = head.getUint16(2, little);
  if (magic !== 42 && magic !== 43) return "native";
  const big = magic === 43;
  if (big && (head.byteLength < 16 || head.getUint16(4, little) !== 8)) return "native";
  const offset = big ? Number(head.getBigUint64(8, little)) : head.getUint32(4, little);
  if (!Number.isSafeInteger(offset) || offset < 8 || offset + (big ? 8 : 2) > file.size) return "native";
  const countBytes = big ? 8 : 2;
  const countView = new DataView(await file.slice(offset, offset + countBytes).arrayBuffer());
  const count = big ? Number(countView.getBigUint64(0, little)) : countView.getUint16(0, little);
  if (!Number.isSafeInteger(count) || count > 4096) return "native";
  const stride = big ? 20 : 12;
  const entries = new DataView(await file.slice(offset + countBytes, offset + countBytes + count * stride).arrayBuffer());
  for (let index = 0; index + stride <= entries.byteLength; index += stride) {
    if (entries.getUint16(index, little) !== 262 || entries.getUint16(index + 2, little) !== 3) continue;
    const values = big ? Number(entries.getBigUint64(index + 4, little)) : entries.getUint32(index + 4, little);
    if (values === 1 && entries.getUint16(index + (big ? 12 : 8), little) === 2) return "display-rgb";
  }
  return "native";
}

/** Bounded metadata routing only. Axes, channel count, XML and pixels are validated by the API. */
export async function tiffHasOmeMetadata(file: Blob): Promise<boolean> {
  const head=new DataView(await file.slice(0,16).arrayBuffer());
  if(head.byteLength<8)return false;
  const little=head.getUint16(0)===0x4949;
  if(!little&&head.getUint16(0)!==0x4d4d)return false;
  const magic=head.getUint16(2,little),big=magic===43;
  if(magic!==42&&!big)return false;
  if(big&&(head.byteLength<16||head.getUint16(4,little)!==8))return false;
  const offset=big?Number(head.getBigUint64(8,little)):head.getUint32(4,little),countBytes=big?8:2,stride=big?20:12;
  if(!Number.isSafeInteger(offset)||offset<8||offset+countBytes>file.size)return false;
  const countView=new DataView(await file.slice(offset,offset+countBytes).arrayBuffer());
  const count=big?Number(countView.getBigUint64(0,little)):countView.getUint16(0,little);
  if(!Number.isSafeInteger(count)||count>4096||offset+countBytes+count*stride>file.size)return false;
  const entries=new DataView(await file.slice(offset+countBytes,offset+countBytes+count*stride).arrayBuffer());
  for(let index=0;index+stride<=entries.byteLength;index+=stride){
    if(entries.getUint16(index,little)!==270||entries.getUint16(index+2,little)!==2)continue;
    const length=big?Number(entries.getBigUint64(index+4,little)):entries.getUint32(index+4,little);
    if(!Number.isSafeInteger(length)||length<5||length>2*1024*1024)return false;
    const start=length<=(big?8:4)?offset+countBytes+index+(big?12:8):big?Number(entries.getBigUint64(index+12,little)):entries.getUint32(index+8,little);
    if(!Number.isSafeInteger(start)||start<0||start+length>file.size)return false;
    const text=new TextDecoder().decode(await file.slice(start,start+length).arrayBuffer());
    return /^\s*(?:<\?xml[^>]*>\s*)?<(?:(?:[\w.-]+):)?OME(?:\s|>)/.test(text);
  }
  return false;
}
