/** Explicit filename pairing only. Filenames never establish stain or experimental identity. */
import type {RegionMetadata} from "./region-types";

export type NamedInput={name:string};
export type BatchColumn<T extends NamedInput>={id:string;suffix:string;files:readonly T[]};
export type BatchMapping<T extends NamedInput>={key:string;files:Record<string,T|undefined>;errors:string[]};
export type MetadataDraft=Record<keyof RegionMetadata,string>;
export const emptyBatchMetadata:MetadataDraft={condition:"",sample:"",experimental_unit:"",acquisition_date:"",pair:"",repeat_length:""};
export const metadataColumns=[['condition','条件'],['sample','試料'],['experimental_unit','独立実験単位'],['acquisition_date','撮影日／バッチ'],['pair','対応ペア'],['repeat_length','リピート長']] as const;

export function mapBatchFiles<T extends NamedInput>(columns:readonly BatchColumn<T>[]){
 const rows=new Map<string,BatchMapping<T>>();const errors:string[]=[];
 if(!columns.length||columns.length>4)errors.push("チャンネル構成を確認してください。");
 if(new Set(columns.map(column=>column.id)).size!==columns.length)errors.push("チャンネルIDが重複しています。");
 for(const column of columns){
  for(const file of column.files){
   if(!/\.tiff?$/i.test(file.name)){errors.push(`${file.name}：TIFFファイルを選んでください。`);continue;}
   const stem=file.name.replace(/\.tiff?$/i,"");
   if(column.suffix&&!stem.endsWith(column.suffix)){errors.push(`${file.name}：指定した末尾文字が一致しません。`);continue;}
   const key=(column.suffix?stem.slice(0,-column.suffix.length):stem).trim();
   if(!key){errors.push(`${file.name}：視野を区別する名前がありません。`);continue;}
   const normalized=key.toLocaleLowerCase("en");let row=rows.get(normalized);
   if(!row){row={key,files:{},errors:[]};rows.set(normalized,row);}
   if(row.files[column.id])row.errors.push(`${column.id}：同じ視野に複数ファイルがあります。`);
   else row.files[column.id]=file;
  }
 }
 const values=[...rows.values()].sort((a,b)=>a.key.localeCompare(b.key,"ja",{numeric:true}));
 for(const row of values)for(const column of columns)if(!row.files[column.id])row.errors.push(`${column.id}：画像がありません。`);
 if(values.length>100)errors.push("一度に登録できる視野は100件までです。");
 return {rows:values,errors,valid:values.length>0&&errors.length===0&&values.every(row=>!row.errors.length)};
}

export function batchMetadata(value:MetadataDraft):RegionMetadata{
 const repeat=value.repeat_length.trim();
 if(repeat&&(!Number.isFinite(Number(repeat))||Number(repeat)<0))throw Error("リピート長は0以上の数値にしてください。");
 return {condition:value.condition.trim()||null,sample:value.sample.trim()||null,experimental_unit:value.experimental_unit.trim()||null,acquisition_date:value.acquisition_date.trim()||null,pair:value.pair.trim()||null,repeat_length:repeat?Number(repeat):null};
}
