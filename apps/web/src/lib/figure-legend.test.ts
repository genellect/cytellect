import {expect, it} from "vitest";
import {plainFigureLegend} from "./figure-legend";

it("keeps every statistical star in the plain manuscript text", () => {
  const body = "* P < 0.05, ** P < 0.01, *** P < 0.001; n.s., P ≥ 0.05.";
  expect(plainFigureLegend(`**Saved result.**\n\n${body}\n`)).toBe(`Saved result.\n\n${body}`);
  expect(plainFigureLegend(body)).toBe(body);
});
