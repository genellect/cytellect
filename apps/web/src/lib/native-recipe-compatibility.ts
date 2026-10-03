import type { Config, Field, Recipe } from "./types";

type RecipeField = { id: string; image_info: Pick<Field["image_info"], "legacy" | "channel_roles"> };
type ChannelRole = "dapi" | "ncl" | "gfp";
export const nativeRecipeLabels: Record<Recipe["id"], string> = {
  "ncl-native-2d": "NCL · 核と核小体",
  "gfp-nuclear-2d": "GFP · 核内輝度",
  "ncl-legacy-rgb": "既存RGB解析の互換モード",
};
export const channelRoleLabels: Record<ChannelRole, string> = { dapi: "核染色", ncl: "NCL", gfp: "GFP" };

/** Mirrors the API's required_channel_roles; no stain is inferred from a filename. */
export function requiredNativeRoles(recipe: Recipe): ChannelRole[] {
  if (recipe.id === "ncl-legacy-rgb") return ["dapi", "ncl", "gfp"];
  if (recipe.id === "gfp-nuclear-2d") return ["dapi", "gfp"];
  return ["dapi", "ncl", ...(recipe.gfp_gate !== "none" || recipe.gfp_maximum !== null ? ["gfp" as const] : [])];
}

export function nativeRecipeCompatibility(recipe: Recipe, fields: RecipeField[], fieldIds: string[], explicitlyExcluded: string[] = []) {
  const required = requiredNativeRoles(recipe);
  const issues = [...new Set(fieldIds)].flatMap(fieldId => {
    const field = fields.find(item => item.id === fieldId);
    if (!field) return [{ fieldId, missingRoles: [] as ChannelRole[], inputModeMismatch: false, unavailable: true }];
    // Only reconfigure skips acquired-role checks for explicit whole-field exclusions.
    // The immutable source record must still exist for worker/replay provenance.
    if (explicitlyExcluded.includes(fieldId)) return [];
    // The three-role fallback is the API's explicit historical-input compatibility rule.
    const acquired = field.image_info.channel_roles ?? ["dapi", "ncl", "gfp"];
    return [{ fieldId, missingRoles: required.filter(role => !acquired.includes(role)),
      inputModeMismatch: field.image_info.legacy !== (recipe.id === "ncl-legacy-rgb"), unavailable: false }]
      .filter(issue => issue.missingRoles.length || issue.inputModeMismatch);
  });
  const outsideControls = recipe.gfp_negative_control_fields.filter(id => !fieldIds.includes(id));
  return { ready: fieldIds.length > 0 && !issues.length && !outsideControls.length, required, issues, outsideControls,
    hasIssues: issues.length > 0 || outsideControls.length > 0 };
}

export function recipeCompatibilityMessage(check: ReturnType<typeof nativeRecipeCompatibility>, fieldIds: string[]) {
  const messages = check.issues.map(issue => {
    const index = fieldIds.indexOf(issue.fieldId);
    const name = index < 0 ? "保存済みの視野" : `視野 ${index + 1}`;
    if (issue.unavailable) return `${name}のチャンネル情報を確認できません。`;
    const reasons = [issue.missingRoles.length ? `${issue.missingRoles.map(role => channelRoleLabels[role]).join("・")}が未取得` : "",
      issue.inputModeMismatch ? "入力形式とレシピが一致しません" : ""].filter(Boolean);
    return `${name}：${reasons.join("、")}。`;
  });
  if (check.outsideControls.length) messages.push("指定した陰性対照が解析対象に含まれていません。対照を含む範囲で解析するか、対照の指定を見直してください。");
  return messages.join(" ");
}

/** Existing revisions use immutable snapshots, never today's upload list as a replacement. */
export function savedRecipeFields(config: Config): RecipeField[] {
  const snapshot = (config as Config & { field_snapshot?: unknown }).field_snapshot;
  if (!snapshot || typeof snapshot !== "object" || Array.isArray(snapshot)) return [];
  return Object.entries(snapshot).flatMap(([id, value]) => {
    if (!value || typeof value !== "object" || !("image_info" in value)) return [];
    const info = value.image_info;
    if (!info || typeof info !== "object" || !("legacy" in info) || typeof info.legacy !== "boolean") return [];
    const roles = "channel_roles" in info ? info.channel_roles : undefined;
    if (roles !== undefined && (!Array.isArray(roles) || !roles.every(role => typeof role === "string"))) return [];
    // Only acquired-role/input-mode data is consumed by the compatibility check.
    return [{ id, image_info: { legacy: info.legacy, channel_roles: roles } }];
  });
}
