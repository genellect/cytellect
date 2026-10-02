import { formatValue, type Cell } from "./types";

const compartments = [["ncl_nucleus", "NCL 核全体"], ["ncl_nucleoli", "NCL 核小体"], ["ncl_nucleoplasm", "NCL 核質"], ["gfp", "GFP 核内"]] as const;
const reasons:Record<string,string> = {
 threshold_not_set:"閾値未設定", below_threshold:"弱い信号・要確認", at_or_above_threshold:"設定閾値以上",
 channel_not_acquired:"チャンネル未取得", recipe_not_measured:"このレシピの測定対象外", compartment_empty:"領域なし",
 nucleolar_processing_failed:"核小体処理失敗", background_dispersion_zero:"背景のばらつきが0", background_dispersion_invalid:"背景のばらつきが無効", ratio_nonfinite:"比を計算できません",
};
export function signalQualityItems(cell:Cell){
 if(!cell.signal_qc_protocol_version)return [];
 return compartments.map(([prefix,label])=>({
  prefix,label,value:formatValue(cell[`${prefix}_signal_to_background`]),
  weak:cell[`${prefix}_weak_signal`]===true,
  reason:reasons[String(cell[`${prefix}_signal_qc_reason`])]??"診断値なし",
 }));
}
