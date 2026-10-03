import {emptyBatchMetadata,metadataColumns,type MetadataDraft} from "./region-batch";

type Column=keyof MetadataDraft;
export type MetadataRows=Record<string,MetadataDraft>;
export type CommonMetadataChange={row:string;column:Column;before:string;after:string};
export type CommonMetadataPlan={
 rows:string[];
 columns:{key:Column;label:string;value:string;empty:number;replace:number;unchanged:number}[];
 changes:CommonMetadataChange[];
};

/** Local form edits only. No experimental identities or confirmations are inferred. */
export function planCommonMetadata(metadata:MetadataRows,rows:readonly string[],common:MetadataDraft):CommonMetadataPlan{
 const plan:CommonMetadataPlan={rows:[...new Set(rows)],columns:[],changes:[]};
 for(const [key,label] of metadataColumns){
  const value=common[key].trim();if(!value)continue;
  const column={key,label,value,empty:0,replace:0,unchanged:0};
  for(const row of plan.rows){
   const before=metadata[row]?.[key]??"";
   if(before===value){column.unchanged++;continue;}
   if(before.trim())column.replace++;else column.empty++;
   plan.changes.push({row,column:key,before,after:value});
  }
  plan.columns.push(column);
 }
 return plan;
}

export function applyCommonMetadata(metadata:MetadataRows,plan:CommonMetadataPlan):MetadataRows{
 // Refuse a stale preview atomically, rather than overwrite intervening input.
 if(plan.changes.some(change=>(metadata[change.row]?.[change.column]??"")!==change.before))
  throw Error("common_metadata_preview_changed");
 const next={...metadata};
 for(const change of plan.changes)next[change.row]={...(next[change.row]||emptyBatchMetadata),[change.column]:change.after};
 return next;
}

export function undoCommonMetadata(metadata:MetadataRows,changes:readonly CommonMetadataChange[]){
 const next={...metadata};let restored=0;let kept=0;
 for(const change of changes){
  // Rows added later and subsequent manual edits are outside this operation.
  if(next[change.row]?.[change.column]!==change.after){kept++;continue;}
  next[change.row]={...next[change.row],[change.column]:change.before};restored++;
 }
 return {metadata:next,restored,kept};
}
