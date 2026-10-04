"use client";
import {useEffect,useRef} from "react";
import type {navigationLosses} from "@/lib/draft-navigation";
import styles from "./draft-navigation.module.css";

export default function DraftNavigationDialog({losses,onCancel,onDiscard}:{losses:ReturnType<typeof navigationLosses>;onCancel:()=>void;onDiscard:()=>void}){
 const dialog=useRef<HTMLDialogElement>(null);
 useEffect(()=>{const node=dialog.current!;node.showModal();return()=>node.close();},[]);
 return <dialog ref={dialog} className={styles.dialog} aria-labelledby="draft-navigation-title" onCancel={event=>{event.preventDefault();onCancel();}}>
  <h2 id="draft-navigation-title">未保存の変更を確認</h2><p>この操作を続けると、次の入力は破棄されます。残す場合は編集へ戻り、保存・反映してください。</p>
  <ul>{losses.region&&<li>保存前の輪郭・座標</li>}{losses.config&&<li>未反映の測定条件・背景・除外指定</li>}{losses.metadata&&<li>未保存の実験情報</li>}{losses.form&&<li>保存前の比較条件・確認</li>}</ul>
  <p>保存済みの画像・測定値は変わりません。</p><div><button type="button" autoFocus onClick={onCancel}>編集を続ける</button><button type="button" onClick={onDiscard}>変更を破棄して続ける</button></div>
 </dialog>;
}
