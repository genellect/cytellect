import type {Point} from "@/lib/types";
/** Layout in CSS pixels only. Each image owns a viewport with its original aspect ratio. */
export function imageStageLayout(images: Array<{width:number;height:number}>, available:{width:number;height:number}) {
  const gap=8,caption=images.length>1?26:0;
  const width=Math.max(1,available.width),height=Math.max(1,available.height);
  if(!images.length)return {columns:1,scroll:false,tiles:[]};
  const fit=(image:{width:number;height:number},w:number,h:number)=>{
    const ratio=image.width/image.height;
    const imageWidth=Math.min(w,Math.max(1,h-caption)*ratio);
    return {width:imageWidth,height:imageWidth/ratio,imageHeight:imageWidth/ratio};
  };
  let best={columns:1,score:-1,tiles:images.map(image=>fit(image,width,height))};
  for(let columns=1;columns<=images.length;columns++){
    const rows=Math.ceil(images.length/columns),w=(width-(columns-1)*gap)/columns,h=(height-(rows-1)*gap)/rows;
    const tiles=images.map(image=>fit(image,w,h));
    const score=tiles.reduce((sum,tile)=>sum+tile.width*tile.imageHeight,0);
    if(w>0&&h>caption&&score>best.score)best={columns,score,tiles};
  }
  const scroll=images.length>1&&best.tiles.some(tile=>Math.min(tile.width,tile.imageHeight)<220);
  if(scroll){
    const columns=Math.max(1,Math.floor((width+gap)/288)),w=(width-(columns-1)*gap)/columns;
    best={columns,score:0,tiles:images.map(image=>({width:w,height:w*image.height/image.width,imageHeight:w*image.height/image.width}))};
  }
  return {columns:best.columns,scroll,tiles:best.tiles.map(tile=>({...tile,height:tile.imageHeight+caption}))};
}

/** Smallest readable measurement table beside an image (CSS px) and the rows kept below one. */
export const PAIR_TABLE={sideWidth:260,rows:8,row:33,head:38};

export type PairPlacement="side"|"below"|"none";
/** Two groups side by side (requirements V-01, N-08). Both images use one scale, so the same channel is
 * drawn at the same magnification, and each shows its whole field at its own aspect ratio (nothing is
 * cropped on opening). With measurements shown, each field's table keeps at least PAIR_TABLE beside or
 * below its image, whichever leaves the images larger; the table takes the rest of the pane. On a narrow
 * screen (`stacked`) the panes scroll, so the images take the pane width and the table follows below. */
export function pairPaneLayout(images:Array<{width:number;height:number}|undefined>,pane:{width:number;height:number},tables:boolean,stacked=false):{placement:PairPlacement;scale:number}{
  const sized=images.filter((value):value is {width:number;height:number}=>!!value&&value.width>0&&value.height>0);
  if(!sized.length)return {placement:tables?"below":"none",scale:0};
  const widest=Math.max(...sized.map(value=>value.width)),tallest=Math.max(...sized.map(value=>value.height));
  const scale=(width:number,height:number)=>Math.max(0,Math.min(width/widest,height/tallest));
  if(stacked)return {placement:tables?"below":"none",scale:Math.max(0,pane.width/widest)};
  if(!tables)return {placement:"none",scale:scale(pane.width,pane.height)};
  const below=scale(pane.width,pane.height-(PAIR_TABLE.head+PAIR_TABLE.rows*PAIR_TABLE.row));
  const side=scale(pane.width-PAIR_TABLE.sideWidth,pane.height);
  return side>below?{placement:"side",scale:side}:{placement:"below",scale:below};
}

/** Display only: the centre of the nucleus with the most neighbours within `radius` source pixels. */
export function densestPoint(regions:Array<{id:number;points:Point[]}>,radius:number):Point|undefined{
  const centres=regions.filter(region=>region.points.length).map(region=>[region.points.reduce((sum,point)=>sum+point[0],0)/region.points.length,region.points.reduce((sum,point)=>sum+point[1],0)/region.points.length] as Point);
  let best:Point|undefined,most=-1;
  for(const centre of centres){const count=centres.filter(other=>Math.hypot(other[0]-centre[0],other[1]-centre[1])<=radius).length;if(count>most){most=count;best=centre;}}
  return best;
}
