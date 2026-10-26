"use client";
import {useEffect,useState} from "react";
import type {ReviewField,ReviewTarget} from "@/lib/workspace/review-preview";
import type {useWorkspaceRuntime} from "@/lib/workspace/use-workspace-runtime";
import {fieldsIn,type ExperimentDesign} from "@/lib/workspace/experiment-design";
import {decodedPreview,percentileRange,planeRange,redrawnPreview,remapTable,sharedRange} from "@/lib/shared-display";
import {ReviewImageCanvas,type ReferenceMarker,type ReviewImageViewport} from "./ReviewImageCanvas";
import {MeasurementTable} from "./MeasurementTable";
import styles from "./pair-stage.module.css";

type Runtime=ReturnType<typeof useWorkspaceRuntime>;
/** How the two panes are drawn: one shared brightness range, or each image's own when that fails. */
export type PairDisplay={shared:boolean;black?:number;white?:number;fields?:string[]};
interface Props {
  design:ExperimentDesign;fields:ReviewField[];runtime:Runtime;target:ReviewTarget;channel:string;
  selectedField?:string;onSelect:(fieldId:string,channel:string,region?:number)=>void;
  onEditing:(value:boolean)=>void;demo?:boolean;
  /** The run shown (the toolbar chooses it), whether zoom is linked and whether each pane lists its measurements. */
  runId:string;linked:boolean;tables:boolean;onDisplay?:(value:PairDisplay|null)=>void;
  /** Display-only reference objects per field, with a short caption for the pane header. */
  overlay?:Record<string,{markers:ReferenceMarker[];caption:string}>;
}

/** Runs in which at least one group has a field, in the design's order. */
export const pairRuns=(design:ExperimentDesign)=>(design.runs??[]).filter(run=>design.groups.some(group=>fieldsIn(design,group.id,run.id).length));

/** Two groups of one independent run side by side (requirements V-01–V-04): each pane shows its image
 * with outlines and, below it, that field's measurements. Fields of different groups are different
 * cells: no position correspondence is assumed, and zoom is linked only on request. */
export function PairStage({design,fields,runtime:r,target,channel,selectedField,onSelect,onEditing,demo=false,runId,linked,tables,onDisplay,overlay}:Props){
  const runs=pairRuns(design);
  const run=runs.find(value=>value.id===runId)??runs[0];
  const [chosen,setChosen]=useState<Record<string,string>>({});
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
  // What is shown: the same fields, channel and display ranges are the same images, even when the
  // runtime re-creates their preview URLs (for example when the remaining fields have loaded).
  const displayKey=JSON.stringify([panes.map(pane=>pane.field?.id??null),channel,shared,receipts.map(planeRange)]);
  const {urls,failed,range,own}=useSharedPreviews(panes.map(pane=>pane.field?.previews[channel]),receipts.map(planeRange),shared.status==="shared",displayKey);
  const shownFields=panes.flatMap(pane=>pane.field?[pane.field.id]:[]);
  const display:PairDisplay|null=!run?null:shared.status==="shared"&&!failed&&!own?{shared:true,black:(range??shared).black,white:(range??shared).white,fields:shownFields}:{shared:false,fields:shownFields};
  const displayValue=JSON.stringify(display);
  useEffect(()=>{onDisplay?.(display);},[displayValue]);// eslint-disable-line react-hooks/exhaustive-deps
  useEffect(()=>()=>onDisplay?.(null),[]);// eslint-disable-line react-hooks/exhaustive-deps

  if(!run)return <p className={styles.empty}>2 つの群に画像がある実験回がありません。「実験」で群と実験回に画像を割り当ててください。</p>;
  return <div className={styles.pair} data-tables={tables}>
    {panes.map((pane,index)=>{
      const field=pane.field;
      // A detection preview (for example an AI proposal) is shown as in one field, read-only until adopted.
      const candidate=field?r.candidateResult(field.id,target):undefined,value=field?candidate||r.currentResult(field.id,target):undefined;
      const editable=!demo&&!!field&&!!value&&!candidate&&target!=="nucleoplasm";
      const view=linked?viewport.shared:field?viewport[field.id]:undefined;
      const rows=value?.rows.filter(row=>row.channel_id===channel)??[];
      const count=value?new Set(value.masks.regions.map(region=>region.id)).size:null;
      const select=(n:number)=>{if(!field)return;setRegions(previous=>({...previous,[field.id]:n}));onSelect(field.id,channel,n);};
      const label=`${pane.group.label}${pane.group.id===design.control_group_id?"（対照）":""}`;
      return <section key={pane.group.id} className={styles.pane} aria-label={label}>
        <header className={styles.paneHead}>
          <strong title={pane.group.label}>{pane.group.label}</strong>{pane.group.id===design.control_group_id&&<span className={styles.badge}>対照</span>}
          {pane.ids.length>1&&<select aria-label={`${pane.group.label} の視野`} value={field?.id} onChange={event=>{const id=event.target.value;setChosen(previous=>({...previous,[pane.group.id]:id}));
            // The chosen field is also the selected one, so measuring and candidates act on what is shown.
            onSelect(id,channel);}}>
            {pane.ids.map((id,position)=>{const known=fields.find(item=>item.id===id);return <option key={id} value={id} disabled={!known}>{known?.label??`視野 ${position+1}（読み込み中）`}</option>;})}</select>}
          <small>{pane.ids.length} 視野 · {count===null?"未測定":`${targets[target]} ${count}`}{candidate?" · 検出候補":""}{field&&overlay?.[field.id]?` · ${overlay[field.id].caption}`:""}</small>
        </header>
        <div className={styles.paneImage}>{!field?<p className={styles.empty}>この実験回の画像がありません。</p>:urls[index]?<ReviewImageCanvas
          src={urls[index]!} width={field.width} height={field.height} contours={value?.masks.regions||[]}
          selected={regions[field.id]} label={`${pane.group.label} ${field.label}`}
          onSelect={select} editingKey={`${field.id}:${target}:${value?.revision||"none"}`}
          editDisabled={r.busy||!editable}
          onEdit={editable?(operation,polygon,n,merged)=>r.editMask(field.id,target,value!.revision,operation,polygon,n,merged):undefined}
          onDelete={editable?n=>r.correct(field.id,target,value!.revision,"delete",n):undefined}
          onUndo={editable?()=>r.undo(field.id,target):undefined} onRedo={editable?()=>r.redo(field.id,target):undefined}
          canUndo={!r.busy&&r.canUndo(field.id,target)} canRedo={!r.busy&&r.canRedo(field.id,target)} onEditingChange={onEditing}
          viewport={view??null} onViewportChange={next=>setViewport(previous=>linked?{...previous,shared:next}:{...previous,[field.id]:next})}
          outlineTone={target==="nuclei"||target==="cell"?"nuclear":"marker"} markers={overlay?.[field.id]?.markers} className={styles.canvas}
          // Both panes start filled (no letterbox) on the same relative place, the image centre, so neither
          // view is chosen by its content; 画像全体を表示 shows the whole field.
          initialFill context={demo&&(target==="nucleoli"||target==="nucleoplasm")?r.currentResult(field.id,"nuclei")?.masks.regions:undefined}/>:<p className={styles.empty}>画像を読み込み中…</p>}</div>
        {tables&&field&&<div className={styles.paneTable} role="region" aria-label={`${pane.group.label} の測定値`} tabIndex={0}>
          {rows.length?<MeasurementTable rows={rows} selected={regions[field.id]} onSelect={select}/>:<p className={styles.tableEmpty}>{value?"この染色の測定値はありません。":"「測定」で輪郭と測定値を作ります。"}</p>}</div>}
      </section>;
    })}
  </div>;
}

const targets:Record<ReviewTarget,string>={nuclei:"核",nucleoli:"核小体",nucleoplasm:"核質",cell:"細胞ROI"};

/** Pair toolbar text for the brightness transform (V-03): the shared range, or why each image uses its own. */
export function pairDisplayText(value:PairDisplay):{label:string;detail:string}{
  return value.shared
    ?{label:"共通の表示範囲",detail:`2 つの画像を、同じ表示範囲（保存値 ${format(value.black!)}–${format(value.white!)}。2 つの画像の画素の 0.5〜99.5 パーセンタイル）の共通の明るさの変換で描いています。範囲の外の値は黒または白で示すので、その差と、表示の階調による差は、この表示からは比べられません。露光・ゲインなど撮影条件の違いは補正していません。拡大は画素単位でそろえています。`}
    :{label:"表示範囲は画面ごと",detail:"この画像では表示範囲をそろえられないため、それぞれの画像の範囲で描いています。明るさを比べず、測定値で比べてください。"};
}

const format=(value:number)=>Number.isInteger(value)?String(value):value.toPrecision(4);

/** Object URLs of previews redrawn on one shared scale (shared display range 1.1.0: percentiles of both
 * previews' stored values), with that range; the originals (and failed) when redrawing fails. */
function useSharedPreviews(sources:Array<string|undefined>,ranges:Array<{black:number;white:number}|null>,verified:boolean,key:string):{urls:Array<string|undefined>;failed:boolean;range:{black:number;white:number}|null;own?:boolean}{
  const sourceKey=sources.join("\n")+key;
  const [state,setState]=useState<{key:string;identity:string;urls:Array<string|undefined>;owned:string[];failed:boolean;range:{black:number;white:number}|null}>({key:"",identity:"",urls:[],owned:[],failed:false,range:null});
  // A redrawn pair is released only once the next one is on screen (or on unmount).
  useEffect(()=>{const owned=state.owned;return()=>owned.forEach(url=>URL.revokeObjectURL(url));},[state]);
  useEffect(()=>{
    if(!verified){return;}
    let live=true,committed=false;const created:string[]=[];
    void (async()=>{
      const shown=sources.map((src,index)=>src&&ranges[index]?{src,range:ranges[index]!}:null);
      const decoded=await Promise.all(shown.map(item=>item?decodedPreview(item.src):Promise.resolve(null)));
      const present=shown.flatMap((item,index)=>item&&decoded[index]?[{range:item.range,histogram:decoded[index]!.histogram}]:[]);
      const range=percentileRange(present.map(item=>item.histogram),present.map(item=>item.range));
      const urls=await Promise.all(decoded.map(async(value,index)=>{if(!value||!shown[index])return sources[index];const url=await redrawnPreview(value,remapTable(shown[index]!.range,range));created.push(url);return url;}));
      return {urls,range};
    })().then(({urls,range})=>{if(live){committed=true;setState({key:sourceKey,identity:key,urls,owned:created,failed:false,range});}else created.forEach(url=>URL.revokeObjectURL(url));})
      .catch(()=>{if(live)setState({key:sourceKey,identity:key,urls:sources,owned:[],failed:true,range:null});});
    return()=>{live=false;if(!committed)created.forEach(url=>URL.revokeObjectURL(url));};
  },[sourceKey]);// eslint-disable-line react-hooks/exhaustive-deps
  if(!verified)return {urls:sources,failed:false,range:null};
  if(state.key===sourceKey)return {urls:state.urls,failed:state.failed,range:state.range};
  // The same images under re-created URLs stay on screen while they are redrawn. Otherwise each image is
  // shown in its own range until the shared one is ready, and the view says so (own), so nothing blanks
  // and no image is shown under the wrong label.
  return state.identity===key?{urls:state.urls,failed:state.failed,range:state.range}:{urls:sources,failed:false,range:null,own:true};
}
