"use client";
import {createContext,useContext,useState,type ReactNode} from "react";
import type {CandidateId,PlanInput} from "@/lib/analysis-plan";
type PendingPlan={input:PlanInput;candidateId:CandidateId};
const Context=createContext<{pending:PendingPlan|null;setPending:(value:PendingPlan|null)=>void}>({pending:null,setPending:()=>{}});
export function PlanMemory({children}:{children:ReactNode}){const [pending,setPending]=useState<PendingPlan|null>(null);return <Context.Provider value={{pending,setPending}}>{children}</Context.Provider>;}
export const usePlanMemory=()=>useContext(Context);
