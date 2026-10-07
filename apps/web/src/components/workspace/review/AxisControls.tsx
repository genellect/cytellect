"use client";
export type DisplayScale="linear"|"log10"|"log2";
export interface AxisState {min:string;max:string;step:string;scale:DisplayScale}
export const emptyAxis=():AxisState=>({min:"",max:"",step:"",scale:"linear"});
export function AxisControls({axis,value,onChange,numeric=true}:{axis:"x"|"y";value:AxisState;onChange:(value:AxisState)=>void;numeric?:boolean}){
  if(!numeric)return null;
  const label=axis==="x"?"横軸":"縦軸";
  return <><label>{label}の表示<select value={value.scale} onChange={event=>onChange({...value,scale:event.target.value as DisplayScale})}><option value="linear">線形</option><option value="log10">対数（10）</option><option value="log2">対数（2）</option></select></label>
    <label>{label}の最小値<input inputMode="decimal" value={value.min} placeholder="自動" onChange={event=>onChange({...value,min:event.target.value})}/></label>
    <label>{label}の最大値<input inputMode="decimal" value={value.max} placeholder="自動" onChange={event=>onChange({...value,max:event.target.value})}/></label>
    <label>目盛間隔（元の単位）<input inputMode="decimal" value={value.step} placeholder="自動" onChange={event=>onChange({...value,step:event.target.value})}/></label></>;
}
export function axisPlotOptions(x:AxisState,y:AxisState,numericX:boolean){
  const number=(value:string)=>value.trim()?Number(value):null;
  const validate=(axis:AxisState)=>{const min=number(axis.min),max=number(axis.max),step=number(axis.step);
    if([min,max,step].some(value=>value!==null&&!Number.isFinite(value))||(min!==null&&max!==null&&min>=max)||(step!==null&&step<=0)||(min!==null&&max!==null&&step!==null&&(max-min)/step>99))throw new Error("軸の範囲と目盛間隔を確認してください。");
    if(axis.scale!=="linear"&&[min,max].some(value=>value!==null&&value<=0))throw new Error("対数軸の範囲には正の値を指定してください。");return {min,max,step};};
  const xx=validate(numericX?x:emptyAxis()),yy=validate(y);
  return {axes:{version:"1.0.0" as const,x_scale:numericX?x.scale:"linear" as DisplayScale,y_scale:y.scale,x_min:xx.min,x_max:xx.max,x_tick_step:xx.step},y_tick_step:yy.step};
}
