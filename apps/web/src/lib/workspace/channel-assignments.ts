import type {ChannelAssignment, ChannelAssignments} from "./api-adapter";
import type {ChannelDefinition, Grouping} from "./grouping";

export function assignmentDraft(channels: ChannelDefinition[]): ChannelAssignment[] {
  return channels.map(channel => ({channel_id:channel.token,stain:channel.stain,role:channel.role === "nuclear" ? "nuclear" : "measure"}));
}

export function editAssignmentStain(assignments: ChannelAssignment[], token: string, input: string): ChannelAssignment[] {
  const stain = input.trim() || null;
  const key = stain?.toLowerCase().replace(/[\s_-]/g, "");
  const nuclear = !!key && /^(dapi|hoechst\d*|draq[567]?)$/.test(key);
  const namedSignal = !!key && /^(gfp|egfp|ncl|nucleolin|ubf|fbl|fibrillarin)$/.test(key);
  return assignments.map(value => value.channel_id === token ? {...value,stain,role:nuclear ? "nuclear" : namedSignal || !stain ? "measure" : value.role}
    : nuclear && value.role === "nuclear" ? {...value,role:"measure"} : value);
}

export function assignmentChannels(grouping: Grouping, saved: ChannelAssignments): Grouping {
  const byToken = new Map(saved.assignments.map(value => [value.channel_id,value]));
  return {...grouping,channels:grouping.channels.map(channel => {
    const assignment = byToken.get(channel.token);
    return assignment ? {...channel,stain:assignment.stain,role:assignment.role === "unused" ? null : assignment.role,evidence:"user" as const} : channel;
  })};
}

export function assignmentRoles(assignments: ChannelAssignment[]) {
  const unique = (predicate: (value:ChannelAssignment) => boolean) => {
    const matches = assignments.filter(predicate); return matches.length === 1 ? matches[0].channel_id : "";
  };
  return {nuclear:unique(value => value.role === "nuclear"),gfp:unique(value => value.role !== "unused" && /^(e?gfp)$/i.test(value.stain || "")),ncl:unique(value => value.role !== "unused" && /^(ncl|nucleolin)$/i.test(value.stain || ""))};
}

export function channelCaption(token: string, channels: ChannelDefinition[]) {
  const stain = channels.find(value => value.token === token)?.stain;
  return stain && stain !== token ? `${token} · ${stain}` : token;
}

/** A new field never inherits a different acquisition configuration's mapping. */
export function effectiveChannelAssignments(saved:ChannelAssignments,fieldId:string):ChannelAssignment[]{
  const group=saved.groups?.find(value=>value.field_ids.includes(fieldId));
  if(group)return group.assignments;
  if(saved.global_field_ids&&!saved.global_field_ids.includes(fieldId))return [];
  return saved.assignments;
}