import {describe,it,expect} from "vitest";
import {imageStageLayout,PAIR_TABLE,pairPaneLayout} from "./image-stage-layout";
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
describe("two groups side by side",()=>{
  const jump={width:1280,height:1080};
  it("shows both whole fields at one scale with a readable table below on a desktop pane",()=>{
    const layout=pairPaneLayout([jump,jump],{width:610,height:705},true);
    expect(layout.placement).toBe("below");
    expect(jump.height*layout.scale).toBeLessThanOrEqual(705-(PAIR_TABLE.head+PAIR_TABLE.rows*PAIR_TABLE.row));
    expect(jump.width*layout.scale).toBeLessThanOrEqual(610);
  });
  it("puts the table beside the image on a short laptop pane instead of hiding its rows",()=>{
    const layout=pairPaneLayout([jump,jump],{width:565,height:365},true);
    expect(layout.placement).toBe("side");
    expect(jump.width*layout.scale).toBeLessThanOrEqual(565-PAIR_TABLE.sideWidth);
    expect(jump.height*layout.scale).toBeLessThanOrEqual(365);
  });
  it("draws fields of different sizes at the same magnification, each whole",()=>{
    const layout=pairPaneLayout([{width:640,height:640},{width:1280,height:1080}],{width:600,height:700},false);
    expect(layout.placement).toBe("none");
    expect(1280*layout.scale).toBeLessThanOrEqual(600);
    expect(1080*layout.scale).toBeLessThanOrEqual(700);
  });
  it("fills the width of a stacked phone pane and keeps the table below",()=>{
    expect(pairPaneLayout([jump,jump],{width:358,height:0},true,true)).toEqual({placement:"below",scale:358/1280});
    expect(pairPaneLayout([undefined,undefined],{width:600,height:600},true).scale).toBe(0);
  });
});
