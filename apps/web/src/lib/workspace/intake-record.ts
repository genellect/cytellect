/** How the record of added images reads (#284 W1): what one addition did, and the images the comparison counts as
 * technical missing data. Every count comes from the saved rows or the addition's own outcome; nothing is estimated. */
import type {SelectionEntry} from "./api-adapter";
import type {ExperimentDesign} from "./experiment-design";
import {isMaskRow, MASK_CANDIDATE_CODE, type IntakeOutcome} from "./use-workspace-runtime";

/** Names shown in one line: at most three, then the remainder as a count. */
export function namesText(names:readonly string[]):string {
  if (!names.length) return "名称の記録なし";
  return `${names.slice(0, 3).join("、")}${names.length > 3 ? ` ほか ${names.length - 3} 件` : ""}`;
}

/** Why an image did not become a field, as a short status value (UC-02). Every code the region readers and
 * the upload return has one; an unknown code is shown as a refusal with its code. */
const REASONS:Record<string,string> = {
  unsupported_or_invalid_region_image: "不正または未対応の TIFF",
  region_image_not_2d: "2D 以外の画像",
  region_image_not_grayscale: "グレースケール以外の画像",
  region_image_multichannel_requires_ome: "複数チャンネルの TIFF · OME メタデータなし",
  region_image_pixel_limit: "画素数の上限を超過",
  region_channel_dimensions_mismatch: "チャンネル間の寸法の不一致",
  region_image_bit_depth_unsupported: "マスクの候補 · 32-bit 整数ラベル",
  field_upload_limit: "1 視野の上限 256 MiB を超過",
  workspace_limit: "作業の容量または視野数の上限を超過",
  field_channel_limit: "チャンネル数の上限 4 を超過",
  field_input_modes_mixed: "グレースケールと RGB 表示画像の混在",
  ledger_full: "取り込みの記録が上限 100 件",
  region_upload_id_conflict: "登録済みの内容と不一致",
  unregistered_upload: "未登録の画像 · この環境は登録済みの公開画像のみ",
};
/** `mask: false` names an image the judgement before adding found unreadable for its sample type (32-bit float,
 * signed 16-bit): registration answers the mask candidate's code for it, but it is an image, not a label. */
export function intakeReason(code:string|null, mask = true):string {
  if (!code) return "登録未完了";
  if (code === MASK_CANDIDATE_CODE && !mask) return "8/16-bit 以外の画像";
  return REASONS[code] ?? `登録不可 · ${code}`;
}

/** One status line for the last addition (UC-02), so a choice never ends without a visible result (#284 W1 change 11). */
export function outcomeLine(outcome:IntakeOutcome|null):string {
  if (!outcome) return "";
  if (outcome.empty === "nothing") return "受け取ったファイル：0 件";
  if (outcome.empty === "no_images") return `TIFF：0 件 · 対象外：${outcome.skipped.length} 件`;
  const parts = [`登録：${outcome.registered.length} 視野`];
  const rejected = outcome.rejected.filter(item => item.code !== MASK_CANDIDATE_CODE).length, masks = outcome.rejected.length - rejected;
  if (rejected) parts.push(`読み取れない：${rejected} 件`);
  if (masks) parts.push(`マスクの候補：${masks} 件`);
  if (outcome.held.length) parts.push(`要確認：${outcome.held.length} 視野`);
  if (outcome.duplicates.length) parts.push(`同一内容：${outcome.duplicates.length} 件`);
  if (outcome.skipped.length) parts.push(`対象外：${outcome.skipped.length} 件`);
  return parts.join(" · ");
}

/** Items of the last addition that ask the researcher to look (the 取込 list opens for them). */
export function needsAttention(outcome:IntakeOutcome|null):boolean {
  return !!outcome && (outcome.rejected.length + outcome.held.length + outcome.duplicates.length > 0 || !!outcome.empty);
}

export interface MissingImages {group:string; run:string|null; reason:string; count:number}

/**
 * The images that never became a field, by the group and run the researcher chose and by reason, from the selection
 * saved with a comparison. They are technical missing data: counted, never excluded by hand (#284 decision 2). A mask
 * candidate (a 32-bit label image) is not missing data and is not counted. Removed rows ("記録から削除") are absent.
 */
export function missingImages(selection:{entries:readonly SelectionEntry[]}|null|undefined, design:ExperimentDesign|null|undefined):MissingImages[] {
  const groups = new Map((design?.groups ?? []).map(group => [group.id, group.label]));
  const runs = new Map((design?.runs ?? []).map(run => [run.id, run.label]));
  const counted = new Map<string, MissingImages>();
  for (const entry of selection?.entries ?? []) {
    if (entry.field_id) continue;
    const intake = entry.intake;
    if (isMaskRow(intake)) continue;
    const group = intake?.target ? groups.get(intake.target.group_id) ?? "群の指定なし" : "群の指定なし";
    const run = intake?.target ? runs.get(intake.target.run_id) ?? null : null;
    const reason = !intake ? (entry.exclusion_reason ? `除外の理由：${entry.exclusion_reason}` : "理由の記録なし")
      : intake.state === "pending" ? intakeReason(null) : intakeReason(intake.code ?? null, false);
    const key = `${group}\u0000${run ?? ""}\u0000${reason}`;
    const value = counted.get(key) ?? {group, run, reason, count: 0};
    value.count += 1;counted.set(key, value);
  }
  return [...counted.values()];
}
