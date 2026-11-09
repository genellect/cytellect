import type {NucleusTableData} from "@/lib/workspace/api-adapter";

/** A field's channel as the workspace shows it: the stain name when known, else the channel ID. */
export interface NucleusTableChannel {id:string;stain?:string|null}
interface Column {key:string;label:string;title?:string}
interface Cell {text:string;title?:string}
type Row = NucleusTableData["rows"][number];
type Values = Row["channels"][number];

const reasons:Record<string,string>={
  no_candidate:"核小体の候補なし",indeterminate:"核小体を判定できない",review_required:"候補の確認待ち",
  processing_failed:"処理に失敗",no_adopted_nucleolus:"採用した核小体なし",nucleus_excluded:"除外した核",
  nucleolar_revision_not_selected:"核小体は未解析",degenerate_objects:"1 画素の核小体だけで形を測れない",
  calibration_unknown:"画素寸法が未確認",not_requested:"輝度は測定していない",
  background_not_established:"背景を決めていない",acquisition_limit_unknown:"検出器の飽和値が未確認",
  automatic_background_insufficient_tiles:"背景の候補が足りない",automatic_background_insufficient_coverage:"背景の候補が画像の一部に偏る",
};
export const reasonText=(reason:string|null|undefined)=>reason?reasons[reason]??reason:"";
const missing=(reason?:string|null):Cell=>({text:"—",title:reasonText(reason)||"値なし"});
const number=(value:number|null|undefined,digits:number,reason?:string|null):Cell=>
  value===null||value===undefined?missing(reason):{text:value.toLocaleString("ja-JP",{maximumFractionDigits:digits,minimumFractionDigits:digits})};
const percent=(value:number|null|undefined,reason?:string|null):Cell=>
  value===null||value===undefined?missing(reason):{text:`${(value*100).toLocaleString("ja-JP",{maximumFractionDigits:1,minimumFractionDigits:1})}%`};

/** Columns, rows and the nucleus ledger of a nucleus table, in the order the API returned them. */
export function nucleusTableView(table:NucleusTableData,channels:NucleusTableChannel[]){
  const name=(id:string)=>channels.find(channel=>channel.id===id)?.stain||id;
  const calibrated=table.calibration!==null;
  const order=table.rows[0]?.channels.map(item=>({id:item.channel_id,role:item.role}))??[];
  const corrected=new Set(order.filter(({id})=>table.rows.some(row=>row.channels.some(item=>item.channel_id===id&&(item.mean_corrected!==null||item.integrated_corrected!==null)))).map(({id})=>id));
  const nucleoli=table.nucleolar_source!==null;
  const columns:Column[]=[{key:"id",label:"核"},{key:"area",label:calibrated?"核面積 / µm²":"核面積 / px²"}];
  const cells:Array<{id:string;cell:(values:Values)=>Cell}>=[];
  for(const {id,role} of order){
    // The nuclear stain's integrated signal is a relative DNA signal; other stains are read as means.
    const [key,label,title]=role==="nuclear_stain"?["integrated","積算",`${name(id)}（核の染色）の積算輝度。染色・撮影条件が同じ視野の間で比べる相対的な DNA 信号`]:["mean","平均",`${name(id)}の核内の平均輝度`];
    columns.push({key:`${id}:${key}`,label:`${name(id)} ${label}`,title});
    cells.push({id,cell:values=>number(key==="integrated"?values.integrated:values.mean,key==="integrated"?0:1,values.intensity_missing_reason)});
    if(corrected.has(id)){
      columns.push({key:`${id}:${key}:corrected`,label:`${name(id)} ${label}（背景補正）`,title:`${title}から背景を引いた値`});
      cells.push({id,cell:values=>number(key==="integrated"?values.integrated_corrected:values.mean_corrected,key==="integrated"?0:1,values.correction_missing_reason??values.intensity_missing_reason)});
    }
  }
  if(nucleoli)columns.push({key:"count",label:"核小体数"},{key:"fraction",label:"核小体の面積 / 核",title:"核小体の合計面積を核の面積で割った値"},
    {key:"largest",label:"最大の核小体 / 核小体全体",title:"最も大きい核小体の面積を、その核の核小体の合計面積で割った値"},
    {key:"eccentricity",label:"離心率",title:"核小体ごとの離心率を面積で重み付けした平均。0 が円、1 に近いほど細長い"});
  columns.push({key:"state",label:"状態"});
  const rows=table.rows.map(row=>{
    const byChannel=new Map(row.channels.map(item=>[item.channel_id,item]));
    const area=calibrated?number(row.nucleus_area_um2,1,row.area_missing_reason):number(row.nucleus_area_px,0);
    const signal=cells.map(({id,cell})=>cell(byChannel.get(id)!));
    const m=row.nucleoli,reason=m.status==="measured"?null:m.reason;
    const nucleolar=nucleoli?[m.count===null?missing(reason):{text:String(m.count)},percent(m.area_fraction,reason),percent(m.largest_object_fraction,reason),
      number(m.eccentricity,3,m.status==="measured"?m.eccentricity_missing_reason:reason)]:[];
    const state=row.excluded?`除外${row.exclusion_reason?`：${row.exclusion_reason}`:""}`:m.status==="missing"?reasonText(m.reason):row.touches_border?"画像の端に接する":"";
    return {id:row.nucleus_id,excluded:row.excluded,cells:[area,...signal,...nucleolar,{text:state}]};
  });
  return {columns,rows,ledger:ledger(table,nucleoli,order.map(({id})=>({id,name:name(id)})))};
}

/** Every nucleus is accounted for: resolved, missing by reason, excluded; saturated pixels by stain. */
function ledger(table:NucleusTableData,nucleoli:boolean,channels:Array<{id:string;name:string}>){
  const rows=table.rows,excluded=rows.filter(row=>row.excluded).length;
  const parts=[`核 ${rows.length} 個`];
  if(excluded)parts.push(`除外 ${excluded}`);
  if(nucleoli){
    const kept=rows.filter(row=>!row.excluded),measured=kept.filter(row=>row.nucleoli.status==="measured").length;
    const counts=new Map<string,number>();
    for(const row of kept)if(row.nucleoli.status==="missing")counts.set(reasonText(row.nucleoli.reason),(counts.get(reasonText(row.nucleoli.reason))??0)+1);
    parts.push(`核小体を確定 ${measured}`);
    if(counts.size)parts.push(`欠測 ${[...counts.values()].reduce((a,b)=>a+b,0)}（${[...counts].map(([text,n])=>`${text} ${n}`).join("、")}）`);
  }else parts.push("核小体を解析すると、核ごとの核小体の値が加わります");
  for(const {id,name} of channels){
    const saturated=rows.filter(row=>(row.channels.find(item=>item.channel_id===id)?.acquisition_saturation_fraction??0)>0).length;
    if(saturated)parts.push(`${name}の飽和画素を含む核 ${saturated}`);
  }
  return parts.join(" · ");
}
