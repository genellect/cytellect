import {expect,it} from "vitest";
import {defaultFigureEdits,figureOrder,sameFigureEdits,validFigureEdits} from "./figure-controls";
import {descriptiveRequest,sameDescriptiveSettings} from "./descriptive-view";
it("retains existing defaults and validates custom versus preset dimensions",()=>{
 expect(validFigureEdits(defaultFigureEdits(),"nature-double")).toBe(true);
 expect(validFigureEdits({...defaultFigureEdits(),font_size:10},"custom")).toBe(true);
 expect(validFigureEdits({...defaultFigureEdits(),font_size:10},"nature-double")).toBe(false);
 for(const value of [NaN,Infinity,0,17])expect(validFigureEdits({...defaultFigureEdits(),height_inches:value},"custom")).toBe(false);
});
it("reorders identities without parsing labels or retaining removed conditions",()=>{expect(figureOrder(["B, control","removed"],["A","B, control","C"])).toEqual(["B, control","A","C"]);});
it("retains literal display settings in descriptive requests without changing selection or paging",()=>{
 const selection={source:"region" as const,region_set_id:"cells",channel_id:"signal",metric:"mean" as const};
 const edits={...defaultFigureEdits(),x_label:"Fields",y_label:"Signal (a.u.)",height_inches:4,font_size:6,group_order:["field-b","field-a"]};
 const request=descriptiveRequest(selection,"en","nature-double",edits);
 expect(request.selection).toEqual(selection);expect(request.figure_policy).toEqual({version:"2.0.0",layout:"field-pages"});expect(request.plot).toMatchObject(edits);
 const result={spec:{selection,plot:request.plot}};
 expect(sameDescriptiveSettings(result,selection,"en","nature-double",edits)).toBe(true);
 for(const change of [{x_label:"New"},{height_inches:5},{font_size:7},{group_order:["field-a","field-b"]}])expect(sameDescriptiveSettings(result,selection,"en","nature-double",{...edits,...change})).toBe(false);
 expect(sameFigureEdits({},defaultFigureEdits())).toBe(true);
});
