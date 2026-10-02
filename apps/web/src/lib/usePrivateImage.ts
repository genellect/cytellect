"use client";
import { useEffect, useState } from "react";
import { fetchBlob } from "./api";
export function usePrivateImage(path:string|null) {
 const [url,setUrl]=useState<string|null>(null);
 useEffect(() => {
  setUrl(null); if(!path) return;
  const controller=new AbortController(); let objectUrl:string|undefined;
  fetchBlob(path,controller.signal).then(blob=>{ if(!controller.signal.aborted){objectUrl=URL.createObjectURL(blob);setUrl(objectUrl);} }).catch(()=>{});
  return ()=>{controller.abort();if(objectUrl) URL.revokeObjectURL(objectUrl);};
 },[path]);
 return url;
}
