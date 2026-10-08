import {describe,it,expect} from "vitest";
import {imageStageLayout} from "./image-stage-layout";
describe("native aspect image stage",()=>{
  it("does not create a full width image frame around a square source",()=>{
    const layout=imageStageLayout([{width:2048,height:2048}],{width:1280,height:450});
    expect(layout.tiles[0]).toEqual({width:450,height:450,imageHeight:450});
  });
  it("fits portrait and landscape sources independently without letterboxing their viewports",()=>{
    const images=[{width:512,height:1024},{width:1024,height:512}];
    const layout=imageStageLayout(images,{width:1000,height:600});
    layout.tiles.forEach((tile,index)=>expect(tile.width/tile.imageHeight).toBe(images[index].width/images[index].height));
    expect(layout.tiles.every(tile=>tile.height<=600)).toBe(true);
  });
  it("uses scrolling rather than shrinking many images into unreadable thumbnails",()=>{
    const layout=imageStageLayout(Array.from({length:20},()=>({width:512,height:512})),{width:1000,height:400});
    expect(layout.scroll).toBe(true);
    expect(layout.tiles.every(tile=>tile.width>=220)).toBe(true);
  });
});
