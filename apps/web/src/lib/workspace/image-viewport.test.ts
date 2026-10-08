import {describe, expect, it} from "vitest";
import {imageFit, regionAnnotations, scrollToRegion, visibleRegionAnnotations} from "./image-viewport";

const square = (id:string, x:number, y:number, side:number) => ({outline:{id,points:[[x,y],[x+side,y],[x+side,y+side],[x,y+side]] as [number,number][]},state:"included" as const});

describe("image viewport geometry", () => {
  it("fits both axes without rounding overflow for square and portrait images", () => {
    for (const image of [{width:4096,height:4096},{width:1000,height:2000}]) {
      const zoom = imageFit(image.width,image.height,911,517);
      expect(image.width * zoom).toBeLessThanOrEqual(909);
      expect(image.height * zoom).toBeLessThanOrEqual(515);
    }
  });
  it("labels each mask once inside its pixels, avoiding holes and deleted masks", () => {
    const labels = regionAnnotations([square("7",0,0,100),square("7",20,20,60),{...square("9",0,0,10),state:"deleted"}]);
    expect(labels).toHaveLength(1);
    const [{id,x,y}] = labels;
    expect(id).toBe(7);
    expect(x > 20 && x < 80 && y > 20 && y < 80).toBe(false);
    expect(x).toBeGreaterThan(0); expect(x).toBeLessThan(100);
  });
  it("keeps the selected region number when adjacent numbers would overlap", () => {
    const labels = visibleRegionAnnotations([{id:1,x:20,y:20},{id:2,x:21,y:21},{id:3,x:100,y:100}],1,2);
    expect(labels.map(label => label.id)).toEqual([2,3]);
  });
  it("pans an off-screen table selection into view, leaving visible selections stationary", () => {
    const viewport = {width:400,height:300,left:0,top:0};
    const image = {width:1000,height:1000};
    expect(scrollToRegion({id:1,x:800,y:700},1,viewport,image)).toEqual({left:600,top:550});
    expect(scrollToRegion({id:1,x:200,y:200},1,viewport,image)).toEqual({left:0,top:0});
  });
  it("accounts for centered fitted images when locating a selected region", () => {
    expect(scrollToRegion({id:1,x:50,y:50},1,{width:800,height:300,left:0,top:0},{width:100,height:100})).toEqual({left:0,top:0});
  });
});
