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

/** Display only: the centre of the nucleus with the most neighbours within `radius` source pixels. */
export function densestPoint(regions:Array<{id:number;points:Point[]}>,radius:number):Point|undefined{
  const centres=regions.filter(region=>region.points.length).map(region=>[region.points.reduce((sum,point)=>sum+point[0],0)/region.points.length,region.points.reduce((sum,point)=>sum+point[1],0)/region.points.length] as Point);
  let best:Point|undefined,most=-1;
  for(const centre of centres){const count=centres.filter(other=>Math.hypot(other[0]-centre[0],other[1]-centre[1])<=radius).length;if(count>most){most=count;best=centre;}}
  return best;
}
