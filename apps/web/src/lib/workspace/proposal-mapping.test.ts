import {expect,it} from "vitest";
import {localProposal} from "./proposal-mapping";
import type {ValidatedProposal} from "./api-adapter";

it("restores anonymous channel references throughout the executable proposal", () => {
  const raw = {needs_confirmation:["ch2"],draft:{recipe:"nuclear-intensity",
    channels:[{token:"ch1",role:"measure"},{token:"ch2",role:"nuclear"}],metrics:[{channel:"ch1"}],
    statistics:{kind:"association",x:{channel:"ch1"},y:{channel:"ch2"}},
    additional_analyses:[{x:{channel:"ch1"},y:{channel:"ch2"}}],figures:[{channel:"ch1"}],
    processing:{nuclei:{channel:"ch2"},signal:{channel:"ch1"},nucleoli:null}}} as unknown as ValidatedProposal;
  const local = localProposal(raw,[{token:"ch1",channel_id:"c1",stain:null},{token:"ch2",channel_id:"c4",stain:"DAPI"}]);
  expect(local.draft.channels[1].token).toBe("c4");
  expect(local.draft.processing!.nuclei!.channel).toBe("c4");
  expect(local.draft.processing!.signal!.channel).toBe("c1");
  expect(local.draft.metrics[0].channel).toBe("c1");
  expect(local.draft.statistics).toMatchObject({x:{channel:"c1"},y:{channel:"c4"}});
  expect(local.needs_confirmation).toEqual(["c4"]);
  expect(raw.draft.channels[1].token).toBe("ch2");
  expect(() => localProposal(raw,[{token:"ch1",channel_id:"c1",stain:null}])).toThrow();
});
