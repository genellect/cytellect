import { expect, it } from "vitest";
import source from "../../../public/prototype/bbbc013/fields.json";
import { createPrototypeAdapter, fieldDistribution } from "./adapter";
import { groupFiles } from "./grouping";
import { initialState, reducer } from "./model";

it("keeps registered BBBC013 DNA/GFP identities and displays all recorded GFP values", async () => {
  const adapter = createPrototypeAdapter({delayMs: 0, fetcher: (async () => new Response(JSON.stringify(source))) as typeof fetch});
  const sample = await adapter.loadSample();
  const grouping = {...groupFiles(sample.files), channels: sample.channels!};
  let state = reducer(initialState(), {type: "imported", name: sample.name, grouping});
  expect(state.proposal?.nuclearChannel).toMatchObject({token: "channel2", stain: "DRAQ (DNA)", evidence: "registered_source"});
  expect(state.proposal?.metrics.map(metric => metric.key)).toEqual(["area_px", "channel1:mean_raw"]);
  state = reducer(state, {type: "adopt"});
  for (const field of grouping.fields) state = reducer(state, {type: "field-done", field: field.key, result: await adapter.run(field.key)});
  const displayed = fieldDistribution(state, "channel1:mean_raw");
  expect(displayed.summaries.map(field => field.n)).toEqual(source.fields.map(field => field.measurements.length));
  expect(displayed.points[0].value).toBe(source.fields[0].measurements[0].gfp_mean_raw);
});
