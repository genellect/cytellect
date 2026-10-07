import type {ValidatedProposal} from "./api-adapter";

export interface ProposalChannelLink {token: string; channel_id: string; stain: string | null}

/** The service sees opaque ch1 tokens; the workspace always uses the actual acquired channel ID. */
export function localProposal(proposal: ValidatedProposal, links: ProposalChannelLink[]): ValidatedProposal {
  const channels = new Map(links.map(link => [link.token,link.channel_id]));
  if (channels.size !== links.length || new Set(links.map(link => link.channel_id)).size !== links.length) throw new Error("AIのチャンネル対応を確認できません");
  const resolve = (token: string) => {
    const channel = channels.get(token);
    if (!channel) throw new Error("AIが返したチャンネルが画像と一致しません");
    return channel;
  };
  const map = (value: unknown): unknown => {
    if (Array.isArray(value)) return value.map(map);
    if (value && typeof value === "object") return Object.fromEntries(Object.entries(value).map(([key,item]) =>
      [key,(key === "channel" || key === "token") && typeof item === "string" ? resolve(item) : map(item)]));
    return value;
  };
  return {...proposal,draft:map(proposal.draft) as ValidatedProposal["draft"],needs_confirmation:proposal.needs_confirmation.map(resolve)};
}
