import {describe, expect, it} from "vitest";
import cases from "../../../../fixtures/result-summary-cases.json";
import {summarize, type ComparisonEstimates} from "./result-summary";

// The Python legend tests read this same file. Synthetic numbers check text rules only.
describe("the Japanese summary and English legend state the same saved result (FL-12)", () => {
  for (const row of cases.cases) it(row.id, () => {
    expect(summarize(row.estimates as ComparisonEstimates, row.comparison, row.label, row.unit).heading)
      .toBe(row.expected_ja);
  });
});
