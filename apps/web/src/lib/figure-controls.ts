export type FigureEdits={width_inches:number;height_inches:number;font_size:number;x_label:string;y_label:string;group_order:string[]};
export const defaultFigureEdits=():FigureEdits=>({width_inches:7,height_inches:3,font_size:7,x_label:"",y_label:"",group_order:[]});
export function validFigureEdits(value:FigureEdits,preset:string){
 return Number.isFinite(value.width_inches)&&value.width_inches>=3&&value.width_inches<=16&&Number.isFinite(value.height_inches)&&value.height_inches>=1&&value.height_inches<=(preset==="custom"?16:170/25.4)&&Number.isFinite(value.font_size)&&value.font_size>=5&&value.font_size<=(preset==="custom"?24:7)&&value.x_label.length<=120&&value.y_label.length<=120;
}
export function figureOrder(order:string[],available:string[]){return [...order.filter(id=>available.includes(id)),...available.filter(id=>!order.includes(id))];}
export function sameFigureEdits(source:Partial<FigureEdits>,current:FigureEdits){const saved={...defaultFigureEdits(),...source};return saved.width_inches===current.width_inches&&saved.height_inches===current.height_inches&&saved.font_size===current.font_size&&saved.x_label===current.x_label&&saved.y_label===current.y_label&&JSON.stringify(saved.group_order)===JSON.stringify(current.group_order);}
