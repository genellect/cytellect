import {expect,type Page} from "@playwright/test";
export async function verifyVectorDownloads(page:Page,expected:{width:number;height:number;labels:string[]}){
 for(const format of ["SVG","PDF"]){
  const button=page.getByRole("button",{name:`${format} ↓`,exact:true});const pending=page.waitForEvent("download");await button.click();
  const download=await pending;expect(await download.failure()).toBeNull();const stream=await download.createReadStream();if(!stream)throw Error("Vector download unavailable");
  const chunks:Buffer[]=[];for await(const chunk of stream)chunks.push(Buffer.from(chunk));const bytes=Buffer.concat(chunks);
  if(format==="PDF"){expect(bytes.subarray(0,5).toString()).toBe("%PDF-");expect(bytes.toString("latin1")).toContain("/FontFile2");}
  else{const svg=bytes.toString("utf8");const root=/<svg\b[^>]*>/.exec(svg)?.[0]||"";expect(Number(/width="([\d.]+)pt"/.exec(root)?.[1])).toBeCloseTo(expected.width*72,4);expect(Number(/height="([\d.]+)pt"/.exec(root)?.[1])).toBeCloseTo(expected.height*72,4);expect(svg).toContain("<text");for(const label of expected.labels)expect(svg).toContain(label);}
  // The app refreshes the workspace after download() resolves. A download event
  // alone does not mean the surrounding controls can receive input again.
  await expect(button).toBeEnabled();await expect.poll(()=>button.evaluate(element=>!element.closest("[inert]"))).toBe(true);
 }
}
