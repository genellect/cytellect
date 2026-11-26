/** Why an AI answer could not become settings, or could not be had, as the researcher reads it (#284 W2, judgement 3).
 * `researcher`: something in the workspace the researcher can change, with the place to change it. `service`: the
 * answer or the service failed; the action is to send again. The rejection codes are those of
 * packages/analysis/src/cytellect_analysis/proposal_validation.py (REJECTION_CODES); a test keeps them in step. */
export type ReasonPlace = "images" | "channels" | "experiment" | "settings";
export interface ReasonView {kind: "researcher" | "service"; text: string; place?: ReasonPlace}

const RESEARCHER: Record<string, Omit<ReasonView, "kind">> = {
  proposal_images_not_registered: {text: "画像：未登録", place: "images"},
  proposal_requires_images: {text: "画像：未登録", place: "images"},
  proposal_acquisition_dates_required: {text: "撮影日：未入力", place: "experiment"},
  proposal_independent_units_insufficient: {text: "実験回：不足", place: "experiment"},
  proposal_units_required: {text: "実験回：未設定", place: "experiment"},
  proposal_pairing_required: {text: "対の対応：未設定", place: "experiment"},
  proposal_design_requires_paired: {text: "実験デザイン：対の比較が必要", place: "experiment"},
  proposal_gfp_controls_not_registered: {text: "陰性対照の視野：未登録", place: "experiment"},
  proposal_stain_not_established: {text: "染色名：未設定", place: "channels"},
  proposal_one_nuclear_channel_required: {text: "核染色のチャンネル：未指定", place: "channels"},
  proposal_processing_marker_not_established: {text: "マーカーのチャンネル：未指定", place: "channels"},
  proposal_gfp_channel_not_established: {text: "GFP のチャンネル：未指定", place: "channels"},
  proposal_ncl_channel_not_acquired: {text: "NCL のチャンネル：なし", place: "channels"},
  proposal_channel_identity_conflict: {text: "視野ごとの染色名：不一致", place: "channels"},
  proposal_channel_coverage_incomplete: {text: "染色名：一部の視野で未設定", place: "channels"},
  proposal_channel_limit: {text: "チャンネル数：上限 4 を超過", place: "channels"},
  proposal_mixed_input_modes: {text: "グレースケールと RGB 表示画像の混在", place: "images"},
  proposal_selected_field_excluded: {text: "選択した視野：対象外", place: "images"},
  proposal_measured_table_absent: {text: "測定表：なし"},
  proposal_supplied_regions_absent: {text: "領域のマスク：なし"},
  proposal_background_not_available: {text: "背景領域：未確定", place: "settings"},
  proposal_model_not_selected: {text: "検出モデル：未選択", place: "settings"},
};

const SERVICE: Record<string, string> = {
  proposal_shape_invalid: "AI の応答の形式の不備",
  proposal_text_not_allowed: "AI の応答に使えない記述",
  proposal_context_changed: "送信中の画像・設定の変更",
  proposal_context_unsupported: "この作業の内容は送信の対象外",
  proposal_quota_exhausted: "今月の利用の上限",
  proposal_service_unavailable: "AI のサービスへの接続なし",
  proposal_service_misconfigured: "AI のサービスの設定の不備",
  proposal_service_version_mismatch: "AI のサービスの版の不一致",
  proposal_request_superseded: "同じ依頼の重複",
  proposal_internal_error: "アプリ内の処理の失敗",
};

export function reasonView(code: string): ReasonView {
  const researcher = RESEARCHER[code];
  if (researcher) return {kind: "researcher", ...researcher};
  return {kind: "service", text: SERVICE[code] ?? "AI の解析案と画像・設定の不一致"};
}

/** The codes this table names for the researcher; the others are service-side (for the coverage test). */
export const RESEARCHER_CODES = Object.keys(RESEARCHER);
