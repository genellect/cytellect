import {describe,it,expect} from "vitest";
import {axisPlotOptions,emptyAxis} from "./AxisControls";
describe("display-only numeric axis controls",()=>{
  it("ignores retained scatter X limits for categorical views",()=>{
    expect(axisPlotOptions({...emptyAxis(),min:"1",max:"10",scale:"log2"},emptyAxis(),false)).toMatchObject({axes:{x_scale:"linear",x_min:null,x_max:null}});
  });
  it("records real-unit ticks and log display without data transformation",()=>{
    expect(axisPlotOptions({...emptyAxis(),min:"1",max:"9",step:"2",scale:"log2"},{...emptyAxis(),step:"10",scale:"log10"},true)).toMatchObject({axes:{version:"1.0.0",x_scale:"log2",x_min:1,x_max:9,x_tick_step:2,y_scale:"log10"},y_tick_step:10});
  });
  it("refuses nonpositive log ranges, invalid spacing and unbounded tick counts",()=>{
    expect(()=>axisPlotOptions(emptyAxis(),{...emptyAxis(),min:"0",scale:"log10"},false)).toThrow("正の値");
    expect(()=>axisPlotOptions(emptyAxis(),{...emptyAxis(),step:"-1"},false)).toThrow();
    expect(()=>axisPlotOptions({...emptyAxis(),min:"0",max:"1000",step:"1"},emptyAxis(),true)).toThrow();
  });
});
