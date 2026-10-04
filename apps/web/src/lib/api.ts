export const LOCAL_MODE = process.env.NEXT_PUBLIC_CYTELLECT_WEB_MODE === "local";
export const API = LOCAL_MODE ? "" : process.env.NEXT_PUBLIC_API_ORIGIN || (process.env.NODE_ENV === "development" ? "http://localhost:8000" : "");
export const API_CONFIGURED = LOCAL_MODE || !!API;
export class ApiError extends Error { constructor(public code: string, public status: number) { super(code); } }
export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
 if(!API_CONFIGURED) throw new ApiError("server_not_configured",503);
 if(LOCAL_MODE && typeof window!=="undefined" && !["localhost","127.0.0.1","[::1]","::1"].includes(window.location.hostname)) throw new ApiError("local_host_required",403);
 const headers = new Headers(options.headers);
 if (options.body && !(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
 if (options.method && !["GET", "HEAD"].includes(options.method)) headers.set("X-Cytellect-Request", "1");
 const result = await fetch(API + path, {...options, headers, credentials: "include", cache: "no-store"});
 if (!result.ok) {
   let code = "request_failed";
   try { const value = await result.json(); if (typeof value.detail === "string") code = value.detail; } catch {}
   throw new ApiError(code, result.status);
 }
 return result.json() as Promise<T>;
}
export const post = <T,>(path: string, body?: unknown) => request<T>(path, {method:"POST",body:body === undefined ? undefined : JSON.stringify(body)});
export async function fetchBlob(path: string, signal?: AbortSignal): Promise<Blob> {
 return (await fetchPrivateResponse(path,signal)).blob();
}
export async function fetchPrivateResponse(path: string, signal?: AbortSignal): Promise<Response> {
 if(!API_CONFIGURED) throw new ApiError("server_not_configured",503);
 if(LOCAL_MODE && typeof window!=="undefined" && !["localhost","127.0.0.1","[::1]","::1"].includes(window.location.hostname)) throw new ApiError("local_host_required",403);
 const result = await fetch(API + path, {credentials:"include",cache:"no-store",signal});
 if (!result.ok) throw new ApiError("artifact_unavailable", result.status);
 return result;
}
export async function download(path: string, name: string) {
 const blob = await fetchBlob(path); const url = URL.createObjectURL(blob);
 const anchor = document.createElement("a"); anchor.href=url;anchor.download=name;anchor.click();
 setTimeout(() => URL.revokeObjectURL(url),1000);
}
const messages:Record<string,string> = {
 common_statistics_finite_units_required:"実験単位の値に有限でない数値が含まれています。測定値と採否を確認してください。",
 common_statistics_insufficient_units:"この検定に必要な独立実験単位数がありません。対象数と実験デザインを確認してください。",
 common_statistics_constant_units:"値にばらつきがないため、この検定・相関を算出できません。測定値を確認してください。",
 common_statistics_not_estimable:"指定した条件では統計量を推定できません。測定値と実験単位を確認してください。",
 common_statistics_insufficient_nonzero_pairs:"ゼロ以外の対応差があるペアが2組未満のため、Wilcoxon検定を実行できません。",
 common_statistics_unmatched_units:"両軸の実験単位または採否が一致しません。欠測と除外を確認してください。",
 common_statistics_test_design_mismatch:"検定方式と独立・対応の指定が一致しません。実験デザインを確認してください。",
 common_statistics_three_groups_required:"全体検定には3条件以上が必要です。",
 common_statistics_omnibus_required:"3条件以上の独立群比較では、全体検定の方式を指定してください。",
 common_statistics_omnibus_design_mismatch:"全体検定は3条件以上の独立群比較に使用できます。",
 common_statistics_omnibus_contrast_mismatch:"全体検定と群間比較の方式が一致しません。検定方式を確認してください。",
 common_statistics_independent_association_required:"相関には独立実験単位を指定し、両軸の採否を確認してください。",
 common_statistics_distinct_metrics_required:"相関の横軸と縦軸には異なる測定値を指定してください。",
 common_statistics_matched_region_set_required:"相関の横軸と縦軸には同じ領域からの測定値が必要です。",
 common_statistics_pooling_confirmation_required:"全条件を統合する根拠と、群・撮影バッチの影響を確認してください。",
 common_statistics_unknown_method:"指定された統計手法には対応していません。解析設定を確認してください。",
 common_statistics_result_required:"保存された統計結果を確認できません。解析版と履歴を確認してください。",

 statistical_methods_template_invalid:"保存されたMethodsの版を確認できません。解析版と出力条件を確認してください。",
 statistical_methods_source_invalid:"Methodsに必要な保存情報が一致しません。元の測定値と解析版を確認してください。",
 region_upload_id_conflict:"同じ登録操作の内容が変わっています。登録済みの視野を確認し、変更した画像は新しい登録として追加してください。",
 planning_legacy_requires_review:"以前の計画メモです。現在の計画ガイドで内容を確認し直してください。",
 planning_snapshot_mismatch:"計画の保存内容が一致しません。計画を読み込み直して確認してください。",
 planning_candidate_unavailable:"この条件に対応する解析候補がありません。計画を見直してください。",
 planning_resolution_required:"実画像のチャンネルと測定指標を選び、計画との対応を確認してください。",
 planning_resolution_without_plan:"この作業には採用した計画がありません。作業と解析条件を確認してください。",
 planning_adoption_mismatch:"選択した計画と作業の記録が一致しません。作業を開き直してください。",
 planning_workflow_mismatch:"計画と解析の種類が一致しません。対応する作業で解析してください。",
 planning_metric_unavailable:"この解析で測定できる指標を選択してください。",
 planning_channel_unavailable:"選んだ測定指標に対応する実画像のチャンネルを確認してください。",
 planning_calibration_required:"µm²で測定するには、対象となる全画像の画素サイズを確認してください。",
 planning_changes_review_required:"計画から変更した条件を確認してから解析してください。",
 planning_measurement_mismatch:"計画の面積・輝度の測定範囲と今回の設定が一致しません。測定する量を確認してください。",
 planning_revision_record_mismatch:"解析版の計画記録が一致しません。採用中の条件を確認してください。",
 descriptive_failure_exclusion_mismatch:"失敗した視野の除外記録が解析条件と一致しません。除外理由を確認した解析版で再測定してください。",
 region_export_statistics_source_mismatch:"統計結果と出力する解析版の条件が一致しません。採用中の版で比較や図を作成し直してください。",
 region_comparison_review_required:"領域・背景・失敗や除外を確認した解析版で比較してください。",
 region_comparison_source_mismatch:"測定値と解析版の出典が一致しません。採用中の版を再確認してください。",
 region_comparison_metadata_required:"条件・試料・独立実験単位と、必要な対応ペアを記録してください。",
 region_comparison_sample_identity_mismatch:"同じ条件・試料に異なる実験単位が記録されています。試料の対応を確認してください。",
 region_comparison_condition_scope_mismatch:"対象条件と指定した比較の組み合わせが一致しません。",
 region_comparison_unit_without_values:"未除外の実験単位に有効な値がありません。領域・欠測・除外を確認してください。",
 region_comparison_acquisition_review_required:"撮影条件と測定値を比較できる根拠を確認してください。",
 region_comparison_acquisition_batch_required:"輝度比較には実際の撮影日またはバッチの記録が必要です。",
 region_comparison_condition_batch_confounded:"比較する条件で撮影バッチが完全に分かれています。条件の差と撮影の差を区別できません。",
 region_comparison_paired_acquisition_mismatch:"対応する試料の撮影バッチが一致しません。対応関係と撮影記録を確認してください。",
 region_comparison_incompatible_sampling:"画素サイズや空間サンプリングが比較条件と一致しません。面積の単位と撮影情報を確認してください。",
 region_comparison_incompatible_intensity_scale:"画像間で輝度の保存形式が異なります。異なる尺度の値をそのまま比較できません。",
 region_comparison_saturated_signal:"採用領域に上限値または飽和した画素があります。輝度比較の対象と取得条件を確認してください。",
 region_comparison_invalid_family:"重複や同一条件同士の比較を除き、対照群と比較対象を確認してください。",
 region_comparison_invalid_text:"条件名や実験単位の説明を、空欄や改行を含めず入力してください。",
 region_comparison_pairing_basis_required:"対応ありの場合は、試料が対応する根拠を記録してください。",
 unique_complete_pairs_required:"各ペアに各条件の実験単位を1つずつ対応させてください。",
 inconsistent_pair_identity_for_shared_unit:"同じ実験単位が異なるペアに割り当てられています。",
 incomplete_pairs:"対応ペアが不完全です。欠測や除外を含め、各条件の対応を確認してください。",
 two_pairs_required:"対応ありの比較には、有効な対応ペアが2組以上必要です。",
 shared_units_require_paired_analysis:"条件間で同じ実験単位が使われています。独立性と対応関係を確認してください。",
 two_independent_units_per_group_required:"各条件に独立した実験単位が2つ以上必要です。領域数や視野数では代用できません。",
 comparison_not_estimable:"分散や有効な反復が不足し、この比較を推定できません。",
 group_order_must_match_groups:"図に表示する条件と比較対象が一致しません。",
 paired_plot_requires_paired_inference:"対応線のある図には、対応ありの実験デザインを指定してください。",
 explicit_confirmation_required:"必要な条件を実験記録で確認し、確認欄にチェックしてください。",
 region_comparison_result_required:"比較結果を確認できません。処理履歴から再実行してください。",
 nuclear_stain_confirmation_required:"検出に使うチャンネルが核染色画像であることを確認してください。",
 nuclear_normalization_interval_invalid:"正規化の下限percentileを上限より小さくしてください。",
 region_metadata_invalid:"実験情報の文字数・数値と空欄の扱いを確認してください。",
 unknown_region_metadata_field:"実験情報を変更する視野が、現在の解析版に含まれていません。",
 region_parent_definition_changed:"採用中の領域定義が変わりました。最新の版で条件を確認してください。",
 region_parent_fields_must_be_retained:"修正済みの全視野を対象に含めてください。",
 workflow_kind_mismatch:"この作業とは異なる解析形式です。新しい作業へ登録してください。",
 batch_must_include_reused_fields:"修正済みの視野を含めて全視野解析を実行してください。",
 stale_region_mask:"領域の版が更新されています。最新の領域を確認してから修正してください。",
 batch_reuse_requires_unchanged_recipe:"代表視野の条件が変更されています。変更を反映した解析版を確認してから一括解析してください。",
 region_workspace_channel_identity_mismatch:"この作業の標識名・染色・チャンネルIDと一致しません。異なるチャンネル構成は新しい作業で登録してください。",
 unsupported_or_invalid_region_image:"2D・8/16-bitグレースケールTIFFと、同じ寸法のラベル画像を確認してください。",
 invalid_region_field_specification:"チャンネルの対応、標識名、画素サイズの入力を確認してください。",
 region_channel_file_count_mismatch:"登録したチャンネル数と選択した画像の数を一致させてください。",
 region_labels_required:"ラベル画像を使う解析には、同じ寸法の整数ラベルTIFFが必要です。",
 manual_region_source_requires_no_imported_labels:"ラベル画像が登録されています。領域の入力方法をラベル画像に変更してください。",
 confirm_background_for_every_channel:"各視野の各チャンネルで背景ROIを描いて確認してください。",
 region_background_overlaps_measured_regions:"背景ROIが測定領域と重なっています。信号を含まない場所に背景を描き直してください。",
 region_area_only_backgrounds_forbidden:"面積のみの測定には背景ROIを含められません。測定する量を選び直してください。",
 region_measurement_protocol_mismatch:"測定内容と保存済み結果の版が一致しません。解析版を選び直してください。",
 region_metric_not_measured:"この解析版では、その輝度指標を測定していません。面積を選ぶか、背景を確認して輝度を再測定してください。",
 region_definition_requires_new_analysis:"領域の定義を変更する場合は、新しい解析を開始してください。",
 field_selection_requires_new_analysis:"視野の追加には全視野解析を使用してください。",
 region_analysis_required:"この操作には領域・輝度解析の解析版が必要です。",
 descriptive_source_mismatch:"選択した測定値が解析版の種類と一致しません。採用中の版で測定値を選び直してください。",
 descriptive_unresolved_field_failures:"失敗した視野を再処理するか、理由付きで除外してから図を生成してください。",
 descriptive_channel_identity_mismatch:"視野間でチャンネルの意味が一致しません。登録時の標識名と染色を確認してください。",
 descriptive_calibration_mismatch:"画像の校正情報と測定結果が一致しません。原画像から再測定してください。",
 descriptive_field_coverage_mismatch:"採用した視野と測定結果が一致しません。解析版を再確認してください。",
 no_valid_selected_measurements:"選択した指標に有効な測定値がありません。領域・対象選別・欠測理由を確認してください。",
 figure_labels_overlap:"条件名や目盛りが重なっています。図の幅を広げるか、ラベルを短くしてください。",
 figure_text_outside_canvas:"図中の文字が枠からはみ出します。図の高さ・幅またはラベルを調整してください。",
 region_sensitivity_requires_native_ncl:"核小体領域の感度解析には通常NCLレシピの解析版を選択してください。",
 region_sensitivity_fields_differ:"比較する解析版の対象視野が異なります。同じ視野を使った解析版を選択してください。",
 region_sensitivity_inputs_or_metadata_differ:"比較する解析版の原画像または実験情報が異なります。",
 region_sensitivity_backgrounds_differ:"比較する解析版の背景ROIが異なります。核小体領域だけを変更した版を選択してください。",
 region_sensitivity_exclusions_differ:"比較する解析版の除外指定が異なります。核小体領域だけを変更した版を選択してください。",
 region_sensitivity_nonregion_parameters_differ:"核小体以外の解析条件が異なります。同じGFP選別・核検出条件の版を選択してください。",
 region_sensitivity_nuclear_or_manual_masks_differ:"比較する解析版の核または手動ROIが異なります。核小体領域だけを変更した版を選択してください。",
 region_sensitivity_review_required:"比較する両方の解析版で品質確認を完了してください。",
 region_sensitivity_complete_reviewed_masks_required:"未解決の失敗や再確認待ちの領域がある解析版は比較できません。",
 region_sensitivity_measurement_protocol_differs:"測定方式の版が異なります。同じ測定方式で再測定してください。",

 nucleolar_processing_failed:"核小体の処理に失敗した核があります。再検出、手動修正、または理由を記録して除外してください。",
 detection_parameters_require_explicit_resegmentation:"核小体の検出条件を変更しました。核小体候補の再検出を実行してください。核検出条件の変更には新しい全視野解析が必要です。",
 nucleus_parameters_require_new_analysis:"核の検出条件が変更されています。新しい全視野解析を実行してください。",
 resegment_changed_recipe_requires_all_fields:"検出条件を変更した場合は、解析版の全視野に同じ条件を適用してください。",
 field_analysis_failed:"この視野の解析に失敗しました。処理履歴と入力条件を確認してください。",

 fiji_temporary_path_too_long:"解析用の保存先パスが長すぎます。短い保存先での再セットアップが必要です。原画像は変更されていません。",
 fiji_temporary_path_invalid:"解析用の一時保存先が正しく設定されていません。セットアップを確認してください。",
 japanese_font_not_installed:"図に使用できる通常の太さの日本語フォントが見つかりません。フォント環境を確認してください。",
 sans_serif_font_not_installed:"図に使用できる通常の太さのフォントが見つかりません。フォント環境を確認してください。",
 figure_font_glyphs_unavailable:"選択した書体では図中の一部の文字を表示できません。図の言語・ラベルとフォント環境を確認してください。",
 local_host_required:"ローカル版はランチャーから開いたワークスペースで使用してください。",
 fiji_detection_capacity_exceeded:"この画像は現在の自動検出の上限を超えています（1辺2048 px、270万画素）。原画像は変更されていません。",
 recipe_required_channels_missing:"このレシピに必要なチャンネルが不足しています。NCL解析には核染色とNCL、GFP解析には核染色とGFPが必要です。",
 outcome_cannot_be_its_own_gfp_covariate:"GFPを目的変数と説明変数の両方に指定できません。独立実験単位での比較を選択してください。",
 invitation_invalid:"招待コードが無効、期限切れ、または使用済みです。",
 session_required:LOCAL_MODE ? "セッションが失効しました。ワークスペースを開き直してください。" : "セッションが失効しました。新しい招待で接続してください。",
 too_many_attempts:"試行が多いため、1分後にお試しください。",
 confirm_background_for_every_field:"すべての視野で背景ROIを描いて確認してください。",
 demo_accepts_synthetic_only:"この環境では実画像の解析を実行できません。",
 unsupported_or_invalid_image:"画像の軸・bit深度・サイズ・チャンネルの対応を確認してください。",
 stale_revision:"別の解析版が採用されています。最新の版へ戻って修正してください。",
 review_required:"品質確認を完了してから統計を実行してください。",
 nucleolar_resegmentation_required:"核の修正後、核小体候補を再検出して確認してください。",
 resolve_or_explicitly_exclude_failed_fields:"失敗した視野を解決するか、理由付きで除外してください。",
 origin_or_csrf_invalid:"UIとAPIの接続元設定が一致しません。管理者に確認してください。",
 field_upload_limit:"1視野のアップロード上限を超えています。",
 workspace_limit:"作業の容量または視野数の上限を超えています。",
 invalid_analysis_input:"入力内容や領域の重なりを確認してください。",
 workspace_not_found:"作業の保存期限が切れたか、アクセス権がありません。",
 fiji_not_configured:"Fiji解析環境が見つかりません。解析環境のセットアップを確認してください。",
};
export const errorCodeMessage = (code:string):string => messages[code] || code;
export function errorMessage(error:unknown) { return error instanceof ApiError ? (messages[error.code] || `処理できませんでした（${error.code}）。入力条件を確認してください。`) : "APIに接続できません。解析サーバーの起動と接続先を確認してください。"; }
