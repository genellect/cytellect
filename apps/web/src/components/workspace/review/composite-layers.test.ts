import {describe, expect, it} from "vitest";
import {compositeLayers} from "./composite-layers";
import type {ReviewChannel} from "@/lib/workspace/review-preview";

const channel = (id: string, role: ReviewChannel["role"]): ReviewChannel => ({id, label: id, stain: id.toUpperCase(), role});
const previews = (...ids: string[]) => Object.fromEntries(ids.map(id => [id, `blob:${id}`]));

describe("colour merge", () => {
  it("shows the nuclear stain blue and gives each other stain its own colour", () => {
    const layers = compositeLayers({channels: [channel("hoechst", "nuclear"), channel("npm1", "measure"), channel("eu5", "measure")], previews: previews("hoechst", "npm1", "eu5")});
    expect(layers.map(layer => layer.channel)).toEqual(["hoechst", "npm1", "eu5"]);
    expect(layers[0].color).toBe("#3f86ff");
    expect(new Set(layers.map(layer => layer.color)).size).toBe(3);
  });

  it("takes the nuclear stain from the adopted nuclei, and from the assignment before any", () => {
    const channels = [channel("c1", null), channel("c2", null)];
    expect(compositeLayers({channels, previews: previews("c1", "c2"), nuclearChannelId: "c2"}).map(layer => layer.color)).toEqual(["#ff4fb3", "#3f86ff"]);
    // Before the stains are assigned no channel is the nuclear one, and the two still differ.
    const unassigned = compositeLayers({channels, previews: previews("c1", "c2")});
    expect(unassigned.map(layer => layer.color)).not.toContain("#3f86ff");
    expect(new Set(unassigned.map(layer => layer.color)).size).toBe(2);
    // Assigning the nuclear stain recolours only that channel.
    expect(compositeLayers({channels, previews: previews("c1", "c2"), nuclearChannelId: "c1"})[1].color).toBe(unassigned[1].color);
  });

  it("leaves out channels assigned 「使用しない」 and previews not yet loaded", () => {
    const layers = compositeLayers({channels: [channel("dapi", "nuclear"), channel("bright", "unused"), channel("gfp", "measure"), channel("late", "measure")], previews: previews("dapi", "bright", "gfp")});
    expect(layers.map(layer => layer.channel)).toEqual(["dapi", "gfp"]);
  });
});
