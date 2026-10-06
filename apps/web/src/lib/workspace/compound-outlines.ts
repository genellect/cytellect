import type {Outline} from "./model";

type Contour = {outline: Outline; state: "included" | "excluded" | "deleted"};

/** One even-odd path per label preserves holes and disconnected islands. */
export function compoundOutlines(contours: readonly Contour[]) {
  const regions = new Map<string, {id:string;state:Contour["state"];path:string}>();
  for (const {outline, state} of contours) {
    if (state === "deleted" || outline.points.length < 3) continue;
    const path = outline.points.map(([x,y], index) => `${index ? "L" : "M"}${x},${y}`).join(" ") + " Z";
    const existing = regions.get(outline.id);
    if (existing) existing.path += " " + path;
    else regions.set(outline.id, {id:outline.id,state,path});
  }
  return [...regions.values()];
}
