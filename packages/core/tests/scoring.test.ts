import { describe, expect, it } from "vitest";

import { calculateFitness, defaultJudgeWeights } from "../src/index";

describe("calculateFitness", () => {
  it("uses the approved weighted formula", () => {
    const fitness = calculateFitness(
      {
        logicalConsistency: 0.9,
        evidenceGrounding: 0.5,
        solutionUsefulness: 0.8
      },
      defaultJudgeWeights
    );

    expect(fitness).toBeCloseTo(0.79, 5);
  });

  it("calculates fitness from dynamic scores with custom weights", () => {
    const scores = { accuracy: 0.9, creativity: 0.7, efficiency: 0.8, safety: 0.6 };
    const weights = { accuracy: 0.4, creativity: 0.2, efficiency: 0.3, safety: 0.1 };
    const result = calculateFitness(
      { logicalConsistency: 0, evidenceGrounding: 0, solutionUsefulness: 0 },
      weights as any,
      scores
    );
    expect(result).toBeCloseTo(0.4 * 0.9 + 0.2 * 0.7 + 0.3 * 0.8 + 0.1 * 0.6);
  });
});
