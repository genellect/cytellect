import {test,expect} from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import {createRegionWorkspace} from "./workspace-session";

const root=path.resolve(__dirname,"../../..");
const files=["A01","A06","A12"].map(field=>path.join(root,`fixtures/public/bbbc013/${field}-dapi.tif`));

test("common batch metadata preserves distinct experimental records and supports reviewed replacement and local undo",async({page})=>{
 // Registered BBBC013 DRAQ pixels are used only to populate the file mapper.
 // Metadata and pixel size below are artificial draft inputs. No image is uploaded.
 const errors:string[]=[];let imageUploads=0;
 page.on("pageerror",error=>errors.push(error.message));
 page.on("request",request=>{if(request.method()==="POST"&&new URL(request.url()).pathname.endsWith("/region-fields"))imageUploads++;});
 await createRegionWorkspace(page,"Common metadata form regression");
 await page.getByText("＋ 複数視野をまとめて登録",{exact:true}).click();
 await page.getByLabel("一括 チャンネル 1 の表示名",{exact:true}).fill("DRAQ");
 await page.getByLabel("一括 チャンネル 1 の染色",{exact:true}).fill("DRAQ");
 const imageInput=page.getByLabel("一括 チャンネル 1 の画像",{exact:true});
 await imageInput.setInputFiles(files.slice(0,2));
 await page.getByLabel("一括 チャンネル 1 の末尾文字",{exact:true}).fill("-dapi");
 await page.getByText("行ごとの実験情報を確認・修正",{exact:true}).click();
 const row=(index:number,label:string)=>page.getByLabel(`一括 視野 ${index} の${label}`,{exact:true});
 for(const [index,condition,sample,unit,pair] of [[1,"A","A-s1","U-A1","P1"],[2,"B","B-s2","U-B2","P2"]] as const){
  for(const [label,value] of [["条件",condition],["試料",sample],["独立実験単位",unit],["対応ペア",pair]])await row(index,label).fill(value);
 }
 await page.getByText("共通の実験情報",{exact:true}).click();
 const apply=page.getByRole("button",{name:"共通情報を全行へ適用",exact:true});
 await expect(apply).toBeDisabled();
 await page.getByLabel("全視野の画像対応と実験情報を確認しました。",{exact:true}).check();
 await page.getByLabel("一括 共通の撮影日／バッチ",{exact:true}).fill("draft-batch-1");
 await apply.click();
 for(const [index,condition,sample,unit,pair] of [[1,"A","A-s1","U-A1","P1"],[2,"B","B-s2","U-B2","P2"]] as const){
  for(const [label,value] of [["条件",condition],["試料",sample],["独立実験単位",unit],["対応ペア",pair],["撮影日／バッチ","draft-batch-1"]])await expect(row(index,label)).toHaveValue(value);
 }
 await expect(page.getByLabel("全視野の画像対応と実験情報を確認しました。",{exact:true})).not.toBeChecked();
 const review=page.getByRole("group",{name:"共通情報の変更確認",exact:true});
 await page.getByLabel("一括 共通の条件",{exact:true}).fill("Common-C");
 await apply.click();
 await expect(review).toBeVisible();
 await expect(review.locator("tbody td")).toHaveText(["条件","Common-C","0","2"]);
 await expect(row(1,"条件")).toHaveValue("A");await expect(row(2,"条件")).toHaveValue("B");
 await review.getByRole("button",{name:"適用せず戻る",exact:true}).click();
 await expect(review).toHaveCount(0);await expect(row(1,"条件")).toHaveValue("A");
 await apply.click();await row(1,"条件").fill("A-revised");
 await expect(review).toHaveCount(0);
 await apply.click();await expect(review.locator("tbody td")).toHaveText(["条件","Common-C","0","2"]);
 await page.setViewportSize({width:390,height:844});
 if(process.env.CYTELLECT_SCREENSHOT_DIR){
  fs.mkdirSync(process.env.CYTELLECT_SCREENSHOT_DIR,{recursive:true});
  await review.screenshot({path:path.join(process.env.CYTELLECT_SCREENSHOT_DIR,"batch-common-review-mobile.png")});
  const geometry=await page.evaluate(()=>({viewport:innerWidth,document:document.documentElement.scrollWidth,overflow:[...document.querySelectorAll("body *")].filter(element=>element.getBoundingClientRect().right>innerWidth+1).map(element=>{const rect=element.getBoundingClientRect();const parent=element.parentElement;return {tag:element.tagName,class:element.className,width:rect.width,left:rect.left,right:rect.right,clientWidth:element.clientWidth,scrollWidth:element.scrollWidth,overflowX:getComputedStyle(element).overflowX,parent:parent?{tag:parent.tagName,class:parent.className,clientWidth:parent.clientWidth,scrollWidth:parent.scrollWidth,overflowX:getComputedStyle(parent).overflowX}:null};})}));
  fs.writeFileSync(path.join(process.env.CYTELLECT_SCREENSHOT_DIR,"batch-common-mobile-geometry.json"),JSON.stringify(geometry,null,2));
 }
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await review.getByRole("button",{name:"変更を確認して適用",exact:true}).click();
 await expect(row(1,"条件")).toHaveValue("Common-C");await expect(row(2,"条件")).toHaveValue("Common-C");
 // Later edits and a new row are not part of the earlier common application.
 await row(1,"試料").fill("later-sample");
 await imageInput.setInputFiles(files);
 await row(3,"条件").fill("new-condition");await row(3,"独立実験単位").fill("new-unit");
 await page.getByText("画素サイズ・領域マスク",{exact:true}).click();
 await page.getByLabel("一括 X方向 µm/px",{exact:true}).fill("0.2");
 await page.getByLabel("一括 Y方向 µm/px",{exact:true}).fill("0.3");
 const calibration=page.getByLabel("全視野のX・Y画素サイズを撮影記録で確認しました。",{exact:true});
 await calibration.check();
 const channel=page.getByLabel("チャンネル 1 の全画像と表示名の対応を確認しました。",{exact:true});
 await channel.check();
 await page.getByLabel("全視野の画像対応と実験情報を確認しました。",{exact:true}).check();
 await page.getByRole("button",{name:"直前の共通情報適用を取り消す",exact:true}).click();
 await expect(row(1,"条件")).toHaveValue("A-revised");await expect(row(2,"条件")).toHaveValue("B");
 await expect(row(1,"試料")).toHaveValue("later-sample");await expect(row(3,"条件")).toHaveValue("new-condition");await expect(row(3,"独立実験単位")).toHaveValue("new-unit");
 for(const index of [1,2])await expect(row(index,"撮影日／バッチ")).toHaveValue("draft-batch-1");
 await expect(row(3,"撮影日／バッチ")).toHaveValue("");
 await expect(page.getByLabel("一括 X方向 µm/px",{exact:true})).toHaveValue("0.2");await expect(page.getByLabel("一括 Y方向 µm/px",{exact:true})).toHaveValue("0.3");
 await expect(calibration).toBeChecked();await expect(channel).toBeChecked();
 await expect(page.getByLabel("一括 チャンネル 1 の末尾文字",{exact:true})).toHaveValue("-dapi");
 expect(await imageInput.evaluate(element=>(element as HTMLInputElement).files?.length)).toBe(3);
 await expect(page.getByLabel("全視野の画像対応と実験情報を確認しました。",{exact:true})).not.toBeChecked();
 expect(imageUploads).toBe(0);expect(errors).toEqual([]);
});
