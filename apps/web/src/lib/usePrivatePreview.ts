"use client";
import { useEffect, useState } from "react";
import { fetchPrivateResponse } from "./api";
import { PREVIEW_DISPLAY_HEADER, readPreviewDisplay, type DisplayReceipt, type PreviewIdentity } from "./preview-display";

type PreviewState = {key:string;status:"loading"|"error"} | {key:string;status:"ready";image:HTMLImageElement;display:DisplayReceipt};

export function usePrivatePreview(path:string, expected:PreviewIdentity) {
 const [attempt,setAttempt]=useState(0);
 const {fieldId,channel,gain,composite}=expected;
 const key=JSON.stringify([path,fieldId,channel,gain,composite,attempt]);
 const [state,setState]=useState<PreviewState>({key:"",status:"loading"});
 useEffect(()=>{
  const controller=new AbortController();let objectUrl:string|undefined;let image:HTMLImageElement|undefined;
  const timer=window.setTimeout(()=>{controller.abort();setState({key,status:"error"});},15000);
  (async()=>{
   try {
    const response=await fetchPrivateResponse(path,controller.signal);
    const display=readPreviewDisplay(response.headers.get(PREVIEW_DISPLAY_HEADER),{fieldId,channel,gain,composite});
    const blob=await response.blob();if(controller.signal.aborted)return;
    objectUrl=URL.createObjectURL(blob);image=new window.Image();
    const decoded=image;
    await new Promise<void>((resolve,reject)=>{decoded.onload=()=>resolve();decoded.onerror=()=>reject(new Error("preview_decode_failed"));decoded.src=objectUrl!;});
    if(controller.signal.aborted)return;
    window.clearTimeout(timer);setState({key,status:"ready",image:decoded,display});
   } catch {if(!controller.signal.aborted){window.clearTimeout(timer);setState({key,status:"error"});}}
  })();
  return()=>{controller.abort();window.clearTimeout(timer);if(image){image.onload=null;image.onerror=null;}if(objectUrl)URL.revokeObjectURL(objectUrl);};
 },[key,path,fieldId,channel,gain,composite]);
 return {preview:state.key===key?state:({key,status:"loading"} as const),retry:()=>setAttempt(value=>value+1)};
}
