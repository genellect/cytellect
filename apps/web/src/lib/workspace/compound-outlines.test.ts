import {describe, expect, it} from 'vitest';
import {compoundOutlines} from './compound-outlines';
const square = (id:string, a:number,b:number,c:number,d:number) => ({outline:{id,points:[[a,b],[c,b],[c,d],[a,d]] as [number,number][]},state:'included' as const});
// Independent ray crossings over SVG subpaths exercise even-odd membership.
function contains(path:string,x:number,y:number) {
  let crossings=0;
  for(const subpath of path.split('Z').filter(s=>s.trim())) {
    const points=[...subpath.matchAll(/[ML](-?[\d.]+),(-?[\d.]+)/g)].map(m=>[Number(m[1]),Number(m[2])]);
    for(let i=0,j=points.length-1;i<points.length;j=i++) {
      const [ax,ay]=points[i], [bx,by]=points[j];
      if((ay>y)!==(by>y) && x<(bx-ax)*(y-ay)/(by-ay)+ax) crossings++;
    }
  }
  return crossings%2===1;
}
describe('compound region outlines',()=>{
 it('preserves nested holes and an island regardless of ring orientation',()=>{
  const [region]=compoundOutlines([square('1',0,0,10,10),square('1',2,2,8,8),square('1',4,4,6,6)]);
  expect(contains(region.path,1,1)).toBe(true);
  expect(contains(region.path,3,3)).toBe(false);
  expect(contains(region.path,5,5)).toBe(true);
  expect(contains(region.path,11,5)).toBe(false);
 });
 it('keeps disconnected contours selectable as one region, but separates different IDs',()=>{
  const regions=compoundOutlines([square('1',0,0,2,2),square('1',5,0,7,2),square('2',10,0,12,2)]);
  expect(regions.map(r=>r.id)).toEqual(['1','2']);
  expect(contains(regions[0].path,1,1)).toBe(true);
  expect(contains(regions[0].path,6,1)).toBe(true);
  expect(contains(regions[0].path,3,1)).toBe(false);
  expect(contains(regions[0].path,11,1)).toBe(false);
 });
 it('omits deleted regions and degenerate contours',()=>{
  expect(compoundOutlines([{...square('1',0,0,2,2),state:'deleted'}, {outline:{id:'2',points:[[0,0],[1,1]]},state:'included'}])).toEqual([]);
 });
});
