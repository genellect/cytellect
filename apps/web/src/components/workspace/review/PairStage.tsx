"use client";
import {useEffect,useMemo,useState} from "react";
import type {ReviewField,ReviewTarget} from "@/lib/workspace/review-preview";
import type {useWorkspaceRuntime} from "@/lib/workspace/use-workspace-runtime";
import {fieldsIn,type ExperimentDesign} from "@/lib/workspace/experiment-design";
import {planeRange,remapTable,remappedPreview,sharedRange} from "@/lib/shared-display";
import {ReviewImageCanvas,type ReviewImageViewport} from "./ReviewImageCanvas";
import styles from "./pair-stage.module.css";

type Runtime=ReturnType<typeof useWorkspaceRuntime>;
interface Props {
  design:ExperimentDesign;fields:ReviewField[];runtime:Runtime;target:ReviewTarget;channel:string;
  selectedField?:string;onSelect:(fieldId:string,channel:string,region?:number)=>void;
  onEditing:(value:boolean)=>void;demo?:boolean;
}

/** Two groups of one independent run side by side (requirements V-01–V-04). Fields of different
 * groups are different cells: no position correspondence is assumed, and zoom is linked only on request. */
export function PairStage({design,fields,runtime:r,target,channel,selectedField,onSelect,onEditing,demo=false}:Props){
  const runs=(design.runs??[]).filter(run=>design.groups.some(group=>fieldsIn(design,group.id,run.id).length));
  const [runId,setRunId]=useState(runs[0]?.id??"");
  const run=runs.find(value=>value.id===runId)??runs[0];
  const [chosen,setChosen]=useState<Record<string,string>>({});
  const [linked,setLinked]=useState(true);
  const [viewport,setViewport]=useState<Record<string,ReviewImageViewport|null>>({});
  const [regions,setRegions]=useState<Record<string,number|undefined>>({});
  // Control first, so the reading order matches the comparison (treatment − control).
  const groups=[...design.groups].sort((a,b)=>(a.id===design.control_group_id?-1:0)-(b.id===design.control_group_id?-1:0));
  const panes=groups.map(group=>{
    const ids=run?fieldsIn(design,group.id,run.id).map(([id])=>id):[];
    const fieldId=ids.includes(chosen[group.id])?chosen[group.id]:ids.includes(selectedField??"")?selectedField!:ids[0];
    return {group,ids,field:fields.find(value=>value.id===fieldId)};
  });
  const receipts=panes.map(pane=>pane.field?.previewDisplay?.[channel]);
  const shared=sharedRange(receipts);
  const displayKey=JSON.stringify([shared,receipts.map(planeRange)]);
  const urls=useSharedPreviews(panes.map(pane=>pane.field?.previews[channel]),receipts.map(planeRange),shared.status==="shared"?shared:null,displayKey);

  if(!run)return <p className={styles.empty}>2 つの群に画像がある実験回がありません。「実験」で群と実験回に画像を割り当ててください。</p>;
  return <div className={styles.pair}>
    <div className={styles.toolbar}>
      <label>実験回<select value={run.id} onChange={event=>{setRunId(event.target.value);setChosen({});}}>{runs.map(value=><option key={value.id} value={value.id}>{value.label}</option>)}</select></label>
      <label className={styles.check}><input type="checkbox" checked={linked} onChange={event=>setLinked(event.target.checked)}/>拡大と位置を連動</label>
    </div>
    <div className={styles.panes}>
      {panes.map((pane,index)=>{
        const field=pane.field,value=field?r.currentResult(field.id,target):undefined;
        const editable=!demo&&!!field&&!!value&&target!=="nucleoplasm";
        const view=linked?viewport.shared:field?viewport[field.id]:undefined;
        return <section key={pane.group.id} className={styles.pane} aria-label={`${pane.group.label}${pane.group.id===design.control_group_id?"（対照）":""}`}>
          <header className={styles.paneHead}>
            <strong>{pane.group.label}</strong>{pane.group.id===design.control_group_id&&<span className={styles.badge}>対照</span>}
            {pane.ids.length>1&&<select aria-label={`${pane.group.label} の視野`} value={field?.id} onChange={event=>setChosen(previous=>({...previous,[pane.group.id]:event.target.value}))}>
              {pane.ids.map(id=><option key={id} value={id}>{fields.find(item=>item.id===id)?.label??id}</option>)}</select>}
            <small>{pane.ids.length} 視野{value?` · 核 ${new Set(value.masks.regions.map(region=>region.id)).size}`:""}</small>
          </header>
          {!field?<p className={styles.empty}>この実験回の画像がありません。</p>:urls[index]?<ReviewImageCanvas
            src={urls[index]!} width={field.width} height={field.height} contours={value?.masks.regions||[]}
            selected={regions[field.id]} label={`${pane.group.label} ${field.label}`}
            onSelect={n=>{setRegions(previous=>({...previous,[field.id]:n}));onSelect(field.id,channel,n);}} editingKey={`${field.id}:${target}:${value?.revision||"none"}`}
            editDisabled={r.busy||!editable}
            onEdit={editable?(operation,polygon,n,merged)=>r.editMask(field.id,target,value!.revision,operation,polygon,n,merged):undefined}
            onDelete={editable?n=>r.correct(field.id,target,value!.revision,"delete",n):undefined}
            onUndo={editable?()=>r.undo(field.id,target):undefined} onRedo={editable?()=>r.redo(field.id,target):undefined}
            canUndo={!r.busy&&r.canUndo(field.id,target)} canRedo={!r.busy&&r.canRedo(field.id,target)} onEditingChange={onEditing}
            viewport={view??null} onViewportChange={next=>setViewport(previous=>linked?{...previous,shared:next}:{...previous,[field.id]:next})}
            outlineTone={target==="nuclei"||target==="cell"?"nuclear":"marker"} className={styles.canvas}/>:<p className={styles.empty}>画像を読み込み中…</p>}
        </section>;
      })}
    </div>
    <p className={styles.note} role="note">{shared.status==="shared"
      ?`2 つの画像を同じ表示範囲（保存値 ${format(shared.black)}–${format(shared.white)}）で表示しています。同じ明るさは同じ保存値です。露光・ゲインなど撮影条件の違いは、この表示では補正されません。拡大は画素単位でそろえています。`
      :"この画像では表示範囲をそろえられないため、それぞれの画像の範囲で表示しています。明るさを比べず、測定値で比べてください。"}</p>
  </div>;
}

const format=(value:number)=>Number.isInteger(value)?String(value):value.toPrecision(4);

/** Object URLs of previews redrawn on the shared scale; the originals while unavailable. */
function useSharedPreviews(sources:Array<string|undefined>,ranges:Array<{black:number;white:number}|null>,shared:{black:number;white:number}|null,key:string){
  const sourceKey=sources.join("\n")+key;
  const [state,setState]=useState<{key:string;urls:Array<string|undefined>}>({key:"",urls:[]});
  const tables=useMemo(()=>shared?ranges.map(range=>range?remapTable(range,shared):null):[],[key]);// eslint-disable-line react-hooks/exhaustive-deps
  useEffect(()=>{
    if(!shared){return;}
    let live=true;const created:string[]=[];
    void Promise.all(sources.map(async(src,index)=>{const table=tables[index];if(!src||!table)return src;const url=await remappedPreview(src,table);created.push(url);return url;}))
      .then(urls=>{if(live)setState({key:sourceKey,urls});else created.forEach(url=>URL.revokeObjectURL(url));})
      .catch(()=>{if(live)setState({key:sourceKey,urls:sources});});
    return()=>{live=false;created.forEach(url=>URL.revokeObjectURL(url));};
  },[sourceKey]);// eslint-disable-line react-hooks/exhaustive-deps
  if(!shared)return sources;
  // A changed request hides the previous pair until the new one is ready (as for previews).
  return state.key===sourceKey?state.urls:sources.map(()=>undefined);
}
